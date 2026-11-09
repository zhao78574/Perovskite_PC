"""Plot an I 3d XPS high-resolution spectrum from an Avantage Excel export.

The source workbook is read only. No smoothing, normalization, fitting, or
in-place workbook edits are performed.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Iterable

import matplotlib.pyplot as plt
from matplotlib import font_manager
import openpyxl
import pandas as pd


DEFAULT_INPUT = Path(
    r"F:\研究生阶段\ZH\3_钝化\表征\3.XPS\1605_1793946284911_26103078424"
    r"\26103078424\A\I.xlsx"
)
OUTPUT_DIR = Path(__file__).resolve().parent


def text(value: object) -> str:
    return "" if value is None or pd.isna(value) else str(value).replace("\ufeff", "").strip()


def matches(pattern: re.Pattern[str], value: object) -> bool:
    return bool(pattern.search(text(value)))


def numeric_series(frame: pd.DataFrame, column: int) -> pd.Series:
    return pd.to_numeric(frame.iloc[:, column], errors="coerce")


def valid_pairs(frame: pd.DataFrame, x_column: int, y_column: int) -> pd.DataFrame:
    pairs = pd.DataFrame(
        {
            "x": numeric_series(frame, x_column),
            "y": numeric_series(frame, y_column),
        }
    ).dropna()
    return pairs.reset_index(drop=True)


def monotonic(values: Iterable[float]) -> bool:
    values = list(values)
    if len(values) < 3:
        return False
    differences = pd.Series(values).diff().dropna()
    return bool((differences.ge(0).all() or differences.le(0).all()) and differences.ne(0).any())


def find_header_candidate(frame: pd.DataFrame) -> dict | None:
    x_pattern = re.compile(r"binding\s*energy|energy|结合能|能量", re.I)
    experimental_pattern = re.compile(
        r"experimental|i\s*3d(?:\s*scan)?\b|scan|intensity|counts?|cps|signal|强度|计数", re.I
    )
    excluded_pattern = re.compile(
        r"background|backgnd|envelope|residual|背景|包络|残差", re.I
    )
    envelope_pattern = re.compile(r"envelope|fit\s*envelope|包络", re.I)
    background_pattern = re.compile(r"background|backgnd|背景", re.I)
    residual_pattern = re.compile(r"residuals?|residual|残差", re.I)

    best: dict | None = None
    scan_rows = min(80, len(frame))
    for header_row in range(scan_rows):
        headers = frame.iloc[header_row].tolist()
        for x_column, x_header in enumerate(headers):
            if not matches(x_pattern, x_header):
                continue
            for y_column, y_header in enumerate(headers):
                if x_column == y_column or excluded_pattern.search(text(y_header)):
                    continue
                if not matches(experimental_pattern, y_header):
                    continue
                pairs = valid_pairs(frame.iloc[header_row + 1 :], x_column, y_column)
                if len(pairs) < 2:
                    continue
                score = len(pairs) + 100
                if re.search(r"^i\s*3d$", text(y_header), re.I):
                    score += 1000
                elif re.search(r"i\s*3d\s*scan|experimental|scan", text(y_header), re.I):
                    score += 20
                candidate = {
                    "header_row": header_row,
                    "x_column": x_column,
                    "experimental_column": y_column,
                    "x_label": text(x_header),
                    "experimental_label": text(y_header),
                    "score": score,
                    "envelope_column": next(
                        (i for i, value in enumerate(headers) if i != x_column and matches(envelope_pattern, value)),
                        None,
                    ),
                    "background_column": next(
                        (i for i, value in enumerate(headers) if i != x_column and matches(background_pattern, value)),
                        None,
                    ),
                    "residual_column": next(
                        (i for i, value in enumerate(headers) if i != x_column and matches(residual_pattern, value)),
                        None,
                    ),
                }
                if best is None or candidate["score"] > best["score"]:
                    best = candidate
    if best is not None and best["envelope_column"] is not None and best["residual_column"] is not None:
        data = frame.iloc[best["header_row"] + 1 :]
        energy = numeric_series(data, best["x_column"])
        envelope = numeric_series(data, best["envelope_column"])
        residual = numeric_series(data, best["residual_column"])
        reference = envelope + residual
        valid = energy.notna() & reference.notna()
        if valid.sum() >= 20:
            tolerance = max(1.0, float(envelope[valid].abs().max()) * 1e-4)
            reconstructed = []
            for column, header in enumerate(frame.iloc[best["header_row"]]):
                if column in (best["x_column"], best["envelope_column"], best["residual_column"]):
                    continue
                if matches(excluded_pattern, header):
                    continue
                values = numeric_series(data, column)
                paired = valid & values.notna()
                if paired.sum() < valid.sum() * 0.95:
                    continue
                error = float((values[paired] - reference[paired]).abs().max())
                if error <= tolerance:
                    reconstructed.append((error, column, header, int(paired.sum())))
            reconstructed.sort()
            if reconstructed and (len(reconstructed) == 1 or reconstructed[0][0] < reconstructed[1][0]):
                _, column, header, count = reconstructed[0]
                best["experimental_column"] = column
                best["experimental_label"] = text(header) or f"Experimental (column {column + 1}, verified by Envelope + Residuals)"
                best["score"] = count + 1000
    return best


def find_numeric_fallback(frame: pd.DataFrame) -> dict:
    candidates = []
    for x_column in range(frame.shape[1]):
        x_values = numeric_series(frame, x_column).dropna()
        if len(x_values) < 20 or not monotonic(x_values):
            continue
        for y_column in range(frame.shape[1]):
            if x_column == y_column:
                continue
            pairs = valid_pairs(frame, x_column, y_column)
            if len(pairs) >= 20:
                candidates.append((len(pairs), x_column, y_column))
    if not candidates:
        raise ValueError("未找到可可靠识别的结合能与强度数据列；请提供列标题。")
    candidates.sort(reverse=True)
    if len(candidates) > 1 and candidates[0][0] == candidates[1][0]:
        raise ValueError("无列标题时存在多个同样可能的数据列，拒绝猜测。")
    _, x_column, y_column = candidates[0]
    return {
        "header_row": -1,
        "x_column": x_column,
        "experimental_column": y_column,
        "x_label": "Binding Energy",
        "experimental_label": "Experimental",
        "score": candidates[0][0],
        "envelope_column": None,
        "background_column": None,
        "residual_column": None,
    }


def read_xps_workbook(path: Path) -> dict:
    workbook = openpyxl.load_workbook(path, read_only=True, data_only=True)
    workbook_sheets = {sheet.title: (sheet.max_row, sheet.max_column) for sheet in workbook.worksheets}
    workbook.close()

    sheets = pd.read_excel(path, sheet_name=None, header=None, engine="openpyxl")
    candidates = []
    for sheet_name, frame in sheets.items():
        detected = find_header_candidate(frame)
        if detected is None:
            try:
                detected = find_numeric_fallback(frame)
            except ValueError:
                continue
        detected["sheet_name"] = sheet_name
        detected["sheet_shape"] = workbook_sheets.get(sheet_name)
        candidates.append((detected["score"], sheet_name, frame, detected))
    if not candidates:
        raise ValueError("所有工作表都无法可靠识别 XPS 数据列；未生成图像。")

    candidates.sort(key=lambda item: item[0], reverse=True)
    _, sheet_name, frame, detected = candidates[0]
    start = detected["header_row"] + 1 if detected["header_row"] >= 0 else 0
    result = {
        "sheet_name": sheet_name,
        "frame": frame,
        "detected": detected,
        "experimental": valid_pairs(frame.iloc[start:], detected["x_column"], detected["experimental_column"]),
        "envelope": None,
        "background": None,
        "residual": None,
    }
    for key in ("envelope", "background", "residual"):
        column = detected[f"{key}_column"]
        if column is not None:
            pairs = valid_pairs(frame.iloc[start:], detected["x_column"], column)
            if not pairs.empty:
                result[key] = pairs
    return result


def style_axes(axis: plt.Axes) -> None:
    axis.set_facecolor("white")
    axis.grid(False)
    axis.tick_params(direction="in", width=1.2, length=5, labelsize=12)
    for spine in axis.spines.values():
        spine.set_linewidth(1.2)


def peak_indices(series: pd.DataFrame, count: int = 2) -> list[int]:
    candidates = [
        index
        for index in range(1, len(series) - 1)
        if series.iloc[index]["y"] >= series.iloc[index - 1]["y"]
        and series.iloc[index]["y"] > series.iloc[index + 1]["y"]
    ]
    candidates.sort(key=lambda index: float(series.iloc[index]["y"]), reverse=True)
    selected: list[int] = []
    for index in candidates:
        if all(abs(float(series.iloc[index]["x"]) - float(series.iloc[other]["x"])) >= 2 for other in selected):
            selected.append(index)
        if len(selected) == count:
            break
    return selected


def plot_xps(data: dict, output_dir: Path) -> list[Path]:
    plt.rcParams.update({"font.family": "Arial", "font.size": 12})
    has_residual = data["residual"] is not None
    fig, axes = plt.subplots(
        2 if has_residual else 1,
        1,
        figsize=(6, 4.5),
        sharex=has_residual,
        gridspec_kw={"height_ratios": [3, 1]} if has_residual else None,
        facecolor="white",
        constrained_layout=True,
    )
    main = axes[0] if has_residual else axes
    experimental = data["experimental"]
    main.scatter(experimental["x"], experimental["y"], s=10, color="#303030", label="Experimental", zorder=3)
    for order, peak_index in enumerate(peak_indices(experimental)):
        peak_x = float(experimental.iloc[peak_index]["x"])
        peak_y = float(experimental.iloc[peak_index]["y"])
        main.scatter([peak_x], [peak_y], s=58, facecolors="white", edgecolors="#1f4e79", linewidths=1.5, zorder=5)
        main.annotate(
            f"{peak_x:.2f} eV\n{peak_y:.0f}",
            xy=(peak_x, peak_y),
            xytext=((-55 if order == 0 else 55), 20),
            textcoords="offset points",
            fontsize=10,
            color="#1f4e79",
            ha="right" if order == 0 else "left",
            va="bottom",
            arrowprops={"arrowstyle": "-", "color": "#1f4e79", "linewidth": 0.9},
        )
    for key, label, color, linestyle, linewidth in (
        ("envelope", "Envelope", "#D94A4A", "-", 2.0),
        ("background", "Background", "#888888", "--", 1.3),
    ):
        series = data[key]
        if series is not None:
            main.plot(series["x"], series["y"], color=color, linestyle=linestyle, linewidth=linewidth, label=label, zorder=2)

    main.set_ylabel("Intensity (a.u.)", fontsize=14)
    style_axes(main)
    main.legend(frameon=False, fontsize=11, loc="upper right")
    all_y = [experimental["y"]]
    all_y.extend(data[key]["y"] for key in ("envelope", "background") if data[key] is not None)
    y_values = pd.concat(all_y, ignore_index=True)
    y_min, y_max = float(y_values.min()), float(y_values.max())
    y_pad = max((y_max - y_min) * 0.05, 1.0)
    main.set_ylim(y_min - y_pad, y_max + y_pad)
    x_values = pd.concat([experimental["x"]] + [data[key]["x"] for key in ("envelope", "background") if data[key] is not None], ignore_index=True)
    main.set_xlim(float(x_values.max()), float(x_values.min()))

    if has_residual:
        residual = data["residual"]
        axes[1].plot(residual["x"], residual["y"], color="#666666", linewidth=1.0)
        axes[1].axhline(0, color="#aaaaaa", linewidth=0.8)
        axes[1].set_xlabel("Binding Energy (eV)", fontsize=14)
        axes[1].set_ylabel("Residual", fontsize=12)
        style_axes(axes[1])
    else:
        main.set_xlabel("Binding Energy (eV)", fontsize=14)

    for axis in (axes if has_residual else [main]):
        axis.tick_params(axis="both", labelsize=12)
    fig.patch.set_facecolor("white")
    outputs = [output_dir / "I3d_XPS.png", output_dir / "I3d_XPS.pdf", output_dir / "I3d_XPS.svg"]
    fig.savefig(outputs[0], dpi=600, facecolor="white")
    fig.savefig(outputs[1], facecolor="white")
    fig.savefig(outputs[2], facecolor="white")
    plt.close(fig)
    return outputs


def main() -> None:
    parser = argparse.ArgumentParser(description="Plot an I 3d XPS spectrum from Excel.")
    parser.add_argument("input", nargs="?", type=Path, default=DEFAULT_INPUT)
    args = parser.parse_args()
    input_path = args.input.expanduser()
    if not input_path.exists():
        raise FileNotFoundError(f"找不到输入文件: {input_path}")
    data = read_xps_workbook(input_path)
    outputs = plot_xps(data, OUTPUT_DIR)
    detected = data["detected"]
    print(f"工作表: {data['sheet_name']}")
    print(f"识别列: {detected['x_label']} | {detected['experimental_label']}")
    print(f"Envelope: {detected['envelope_column'] is not None}; Background: {detected['background_column'] is not None}; Residual: {detected['residual_column'] is not None}")
    print(f"有效 Experimental 数据点: {len(data['experimental'])}")
    peak_index = data["experimental"]["y"].idxmax()
    print(f"Experimental 最高峰: {float(data['experimental'].loc[peak_index, 'x']):.6g} eV, {float(data['experimental'].loc[peak_index, 'y']):.6g}")
    for key in ("envelope", "background", "residual"):
        if data[key] is not None:
            print(f"有效 {key} 数据点: {len(data[key])}")
    print("X 轴: reversed")
    for output in outputs:
        print(f"输出: {output}")
    if not font_manager.findfont("Arial", fallback_to_default=False):
        print("警告: 当前系统未找到 Arial，matplotlib 可能使用回退字体。")


if __name__ == "__main__":
    main()
