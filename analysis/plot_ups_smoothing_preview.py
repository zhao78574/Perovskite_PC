"""生成 UPS 平滑前后对比图（用于确认 Savitzky-Golay 效果）。"""

import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from ups_fit import fit_ups_sample  # noqa: E402

OUT = ROOT / "outputs" / "ups_smoothing_preview"
OUT.mkdir(parents=True, exist_ok=True)

data = json.loads((ROOT / "outputs" / "ups_plot" / "ups_data.json").read_text(encoding="utf-8"))

plt.rcParams.update({
    "font.family": "Microsoft YaHei",
    "font.size": 9,
    "axes.edgecolor": "#c7d0d6",
    "axes.labelcolor": "#37474f",
    "xtick.color": "#607d8b",
    "ytick.color": "#607d8b",
    "axes.linewidth": 0.8,
})


def curves(name):
    onset = data["spectra"][f"{name}_0V"]
    cutoff = data["spectra"][f"{name}_m5V"]
    smooth = fit_ups_sample(cutoff["energy"], cutoff["intensity"], onset["energy"], onset["intensity"])
    raw = fit_ups_sample(cutoff["energy"], cutoff["intensity"], onset["energy"], onset["intensity"],
                         smooth_window=0)
    return smooth, raw


def panel(ax, smooth, raw, key, low, high, title):
    s, r = smooth[key], raw[key]
    e = np.asarray(s["energy"])
    for series, color, width, label, alpha in (
        (r, "#94a3b8", 1.2, "原始数据", 0.9),
        (s, "#0f9d8a", 1.9, "SavGol 2 阶 / 7 点", 1.0),
    ):
        x = np.asarray(series["energy"])
        y = np.asarray(series["normalized"])
        mask = (x >= low) & (x <= high)
        ax.plot(x[mask], y[mask], color=color, lw=width, label=label, alpha=alpha, zorder=3 if color != "#94a3b8" else 2)
    ax.set_xlim(high, low)  # 与软件一致：结合能轴反向
    ax.set_title(title, fontsize=10, color="#17212b", pad=8)
    ax.set_xlabel("Binding energy (eV)")
    ax.set_ylabel("Normalized intensity (a.u.)")
    ax.grid(color="#eef2f4", lw=0.8)
    ax.set_facecolor("white")
    for spine in ax.spines.values():
        spine.set_color("#d7dee3")


fig, axes = plt.subplots(1, 2, figsize=(11, 4.0), dpi=200, facecolor="white")
smooth, raw = curves("A")
panel(axes[0], smooth, raw, "onset", -0.6, 2.6, "价带边全段 — 原始 vs SavGol(2 阶 / 7 点)")
panel(axes[1], smooth, raw, "onset", 1.25, 2.55, "价带边放大 — 折角被抹平，边沿位置不变")
axes[1].set_title("价带边放大 — 折角被抹平，边沿位置不变", fontsize=10, color="#17212b", pad=8)
axes[0].legend(frameon=False, fontsize=8, loc="upper right")

# 原始散点，说明数据本身是 0.05 eV 步长
e = np.asarray(smooth["onset"]["energy"])
y = np.asarray(smooth["onset"]["normalized"])
mask = (e >= 1.25) & (e <= 2.55)
axes[1].plot(e[mask], y[mask], "o", ms=2.6, color="#0f9d8a", zorder=4)
raw_y = np.asarray(raw["onset"]["normalized"])[mask]
axes[1].plot(e[mask], raw_y, "o", ms=2.6, mfc="none", mec="#94a3b8", mew=0.8, zorder=3)

rough = lambda v: float(np.mean(np.abs(np.diff(v, 2))))
text = (f"Eonset {raw['onset_eV']:.3f} → {smooth['onset_eV']:.3f} eV    "
        f"Ecutoff {raw['cutoff_eV']:.3f} → {smooth['cutoff_eV']:.3f} eV    "
        f"曲线抖动 {rough(raw['onset']['normalized']):.2e} → {rough(smooth['onset']['normalized']):.2e}")
fig.text(0.5, 0.015, text, ha="center", fontsize=8, color="#607d8b")
fig.tight_layout(rect=(0, 0.04, 1, 1))
target = OUT / "ups_smoothing_compare.png"
fig.savefig(target, facecolor="white")
print(target)
print(text)
