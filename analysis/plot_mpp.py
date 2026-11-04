from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


SOURCE = Path(r"G:\ZH\3-钝化\0917-MPP\1-1.txt")
OUT = Path(__file__).resolve().parent / "mpp_output"
MPP_VOLTAGE_V = 0.9
AREA_CM2 = 0.07065

data = np.loadtxt(SOURCE, delimiter=",")
assert data.ndim == 2 and data.shape[1] >= 2 and np.all(np.isfinite(data[:, :2]))
time_s, current_ma = data[:, 0], data[:, 1] * 1000
pce_percent = current_ma * MPP_VOLTAGE_V / AREA_CM2

OUT.mkdir(exist_ok=True)
plt.rcParams.update({"font.size": 11, "axes.linewidth": 1.0})
fig, ax = plt.subplots(figsize=(6.4, 4.6), constrained_layout=True)
ax.plot(time_s, pce_percent, color="#1565C0", lw=1.2)
ax.set(xlabel="Time (s)", ylabel="Efficiency (%)", title="MPP Tracking")
ax.grid(alpha=0.25)
fig.savefig(OUT / "1-1_mpp_efficiency.png", dpi=600)
fig.savefig(OUT / "1-1_mpp_efficiency.pdf")
plt.close(fig)
