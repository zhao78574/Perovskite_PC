from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from scipy.ndimage import median_filter
from scipy.signal import savgol_filter


SOURCE = Path(r"F:\研究生阶段\ZH\3_钝化\实验\1009-MPP\1.txt")
OUT = Path(__file__).resolve().parent / "mpp_output"
VOLTAGE_V = 0.9
AREA_CM2 = 0.07065

data = np.loadtxt(SOURCE, delimiter=",")
assert data.ndim == 2 and data.shape[1] >= 2 and np.all(np.isfinite(data[:, :2]))
time_s = data[:, 0]
pce = np.abs(data[:, 1]) * 1000 * VOLTAGE_V / AREA_CM2

# A 5 s median baseline bridges the measured 0.8–2.2 s dropouts but keeps the 9.7 s startup.
baseline = median_filter(pce, size=501, mode="nearest")
corrected = np.where(np.abs(pce - baseline) > 0.5, baseline, pce)
smoothed = median_filter(corrected, size=21, mode="nearest")
steady = time_s >= 12
smoothed[steady] = savgol_filter(corrected[steady], window_length=201, polyorder=2, mode="interp")

OUT.mkdir(exist_ok=True)
np.savetxt(
    OUT / "1_mpp_smoothed_data.csv",
    np.column_stack((time_s, pce, smoothed)),
    delimiter=",",
    header="Time_s,Original_PCE_percent,Smoothed_PCE_percent",
    comments="",
)

plt.rcParams.update({"font.size": 11, "axes.linewidth": 1.0})
fig, ax = plt.subplots(figsize=(7.2, 4.6), constrained_layout=True)
ax.plot(time_s, smoothed, color="#1565C0", lw=1.6)
ax.set(xlabel="Time (s)", ylabel="Efficiency (%)", title="MPP Tracking (Smoothed)")
ax.grid(alpha=0.25)
fig.savefig(OUT / "1_mpp_smoothed.png", dpi=600)
fig.savefig(OUT / "1_mpp_smoothed.pdf")
plt.close(fig)
