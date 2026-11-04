import re
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


source = Path(sys.argv[1])
output = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("sclc.png")
matches = re.findall(
    r"^\s*([+-]?\d+(?:\.\d*)?(?:[eE][+-]?\d+)?),\s*"
    r"([+-]?\d+(?:\.\d*)?(?:[eE][+-]?\d+)?)\s*$",
    source.read_text(),
    re.MULTILINE,
)
if not matches:
    raise ValueError(f"No voltage-current pairs found in {source}")

data = np.asarray(matches, dtype=float)
voltage, current = data.T

fig, axes = plt.subplots(1, 2, figsize=(10, 4.2))
axes[0].plot(voltage, current * 1e6, color="#2563eb", linewidth=1.8)
axes[0].axhline(0, color="0.75", linewidth=0.8)
axes[0].axvline(0, color="0.75", linewidth=0.8)
axes[0].set(xlabel="Voltage (V)", ylabel="Current (µA)", title="I–V curve")

for mask, label, color in (
    (voltage < 0, "Negative bias", "#dc2626"),
    (voltage > 0, "Positive bias", "#2563eb"),
):
    axes[1].loglog(
        np.abs(voltage[mask]), np.abs(current[mask]), label=label, color=color, linewidth=1.8
    )
axes[1].set(xlabel="|Voltage| (V)", ylabel="|Current| (A)", title="SCLC plot")
axes[1].legend(frameon=False)

for ax in axes:
    ax.grid(True, which="both", alpha=0.2)
fig.tight_layout()
fig.savefig(output, dpi=300, bbox_inches="tight")
print(f"Saved {len(data)} points to {output}")
