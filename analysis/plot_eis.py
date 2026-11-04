from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


SOURCE = Path(r"F:\研究生阶段\ZH\3_钝化\表征\12.EIS\处理\1-1.txt")
OUT = Path(__file__).resolve().parent / "eis_output"


data = np.genfromtxt(SOURCE, delimiter="\t", names=True)
freq, z_real, z_imag = data["Freq"], data["Z_a"], data["Z_b"]
assert len(freq) and np.all(freq > 0) and np.all(np.isfinite([z_real, z_imag]))

OUT.mkdir(exist_ok=True)
plt.rcParams.update({"font.size": 10, "axes.linewidth": 1.0})


def nyquist(ax):
    ax.plot(z_real, -z_imag, "o-", ms=3.5, lw=1.2, color="#1565C0")
    ax.set(xlabel=r"$Z'$ ($\Omega$)", ylabel=r"$-Z''$ ($\Omega$)")
    ax.set_aspect("equal", adjustable="box")
    ax.grid(alpha=0.25)


fig, ax = plt.subplots(figsize=(5.6, 4.6), constrained_layout=True)
nyquist(ax)
fig.savefig(OUT / "1-1_nyquist.png", dpi=600)
fig.savefig(OUT / "1-1_nyquist.pdf")
plt.close(fig)

fig, axes = plt.subplots(1, 3, figsize=(13, 4), constrained_layout=True)
nyquist(axes[0])
axes[0].set_title("Nyquist")

axes[1].semilogx(freq, data["Mag"], "o-", ms=3, lw=1.1, color="#D84315")
axes[1].set(xlabel="Frequency (Hz)", ylabel=r"$|Z|$ ($\Omega$)", title="Bode magnitude")
axes[1].grid(alpha=0.25, which="both")

axes[2].semilogx(freq, data["Phase"], "o-", ms=3, lw=1.1, color="#2E7D32")
axes[2].set(xlabel="Frequency (Hz)", ylabel="Phase (deg)", title="Bode phase")
axes[2].grid(alpha=0.25, which="both")

fig.savefig(OUT / "1-1_eis.png", dpi=600)
fig.savefig(OUT / "1-1_eis.pdf")
plt.close(fig)
