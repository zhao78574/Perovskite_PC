from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from scipy import sparse
from scipy.signal import savgol_filter
from scipy.sparse.linalg import spsolve


SOURCE = Path(r"F:\研究生阶段\ZH\3_钝化\表征\4.XRD\26090711649-A.TXT")
OUT_DIR = Path(r"E:\Vibe coding\Perovskite_PC\outputs\xrd_26090711649_A")


def read_xrd(path: Path) -> tuple[np.ndarray, np.ndarray]:
    x, y = [], []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        fields = line.strip().split()
        if len(fields) != 2:
            continue
        try:
            x_val, y_val = map(float, fields)
        except ValueError:
            continue
        x.append(x_val)
        y.append(y_val)
    return np.asarray(x), np.asarray(y)


def asymmetric_least_squares(y: np.ndarray, lam: float = 2e7, p: float = 0.001, iterations: int = 20) -> np.ndarray:
    n = len(y)
    d = sparse.diags([1.0, -2.0, 1.0], [0, 1, 2], shape=(n - 2, n), format="csc")
    penalty = lam * (d.T @ d)
    weights = np.ones(n)
    for _ in range(iterations):
        w = sparse.spdiags(weights, 0, n, n)
        baseline = spsolve(w + penalty, weights * y)
        weights = p * (y > baseline) + (1 - p) * (y <= baseline)
    return baseline


def main() -> None:
    theta, intensity = read_xrd(SOURCE)
    if len(theta) < 11:
        raise ValueError("No valid XRD data found.")

    baseline = asymmetric_least_squares(intensity)
    corrected = np.clip(intensity - baseline, 0, None)
    smoothed = savgol_filter(corrected, window_length=11, polyorder=3)
    smoothed = np.clip(smoothed, 0, None)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    data_path = OUT_DIR / "26090711649-A_processed.csv"
    np.savetxt(
        data_path,
        np.column_stack([theta, intensity, baseline, corrected, smoothed]),
        delimiter=",",
        header="2theta_deg,raw_intensity,baseline,background_subtracted,smoothed_intensity",
        comments="",
        fmt="%.6f",
    )

    plt.rcParams.update({"font.family": "Arial", "font.size": 10})
    fig, ax = plt.subplots(figsize=(8.2, 5.0), dpi=180)
    ax.plot(theta, smoothed, color="#145DA0", linewidth=1.35)
    ax.set_xlabel(r"2$\theta$ (°)")
    ax.set_ylabel("Intensity (a.u.)")
    ax.set_xlim(theta.min(), theta.max())
    ax.set_ylim(bottom=0)
    ax.tick_params(direction="in", top=True, right=True)
    ax.spines["top"].set_linewidth(0.8)
    ax.spines["right"].set_linewidth(0.8)
    fig.tight_layout()
    fig.savefig(OUT_DIR / "26090711649-A_XRD_processed.png", bbox_inches="tight")
    fig.savefig(OUT_DIR / "26090711649-A_XRD_processed.pdf", bbox_inches="tight")
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8.2, 5.0), dpi=180)
    ax.plot(theta, intensity, color="#8A8A8A", linewidth=0.75, label="Raw")
    ax.plot(theta, baseline, color="#D95F02", linewidth=1.0, label="Estimated background")
    ax.plot(theta, smoothed, color="#145DA0", linewidth=1.2, label="Processed")
    ax.set_xlabel(r"2$\theta$ (°)")
    ax.set_ylabel("Intensity (counts / a.u.)")
    ax.set_xlim(theta.min(), theta.max())
    ax.set_ylim(bottom=0)
    ax.tick_params(direction="in", top=True, right=True)
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(OUT_DIR / "26090711649-A_XRD_comparison.png", bbox_inches="tight")
    plt.close(fig)

    print(f"points={len(theta)} range={theta.min():.2f}-{theta.max():.2f}")
    print(f"raw_min={intensity.min():.2f} raw_max={intensity.max():.2f}")
    print(f"processed_max={smoothed.max():.2f}")
    print(OUT_DIR)


if __name__ == "__main__":
    main()
