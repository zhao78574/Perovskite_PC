import json
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(r"E:\Vibe coding\Perovskite_PC")
SOURCE = ROOT / "data" / "ups_source"
OUTPUT = ROOT / "outputs" / "ups_plot"

FILES = {
    "A_0V": SOURCE / "0V_A.xls",
    "B_0V": SOURCE / "0V_B.xls",
    "A_m5V": SOURCE / "minus5V_A.xls",
    "B_m5V": SOURCE / "minus5V_B.xls",
}

# Chosen from the visibly linear leading-edge portions of each spectrum.
FIT_WINDOWS = {
    "A": {"cutoff": [16.10, 16.60], "onset": [1.00, 2.00]},
    "B": {"cutoff": [16.20, 16.70], "onset": [0.60, 1.60]},
}


def read_spectrum(path: Path):
    sheet = pd.ExcelFile(path).sheet_names[0]
    frame = pd.read_excel(path, sheet_name=sheet, header=None)
    energy = pd.to_numeric(frame.iloc[:, 0], errors="coerce")
    intensity = pd.to_numeric(frame.iloc[:, 2], errors="coerce")
    valid = energy.notna() & intensity.notna()
    x = energy[valid].to_numpy(dtype=float)
    y = intensity[valid].to_numpy(dtype=float)
    order = np.argsort(x)
    return x[order], y[order]


def linear_fit(x, y, window):
    mask = (x >= window[0]) & (x <= window[1])
    slope, intercept = np.polyfit(x[mask], y[mask], 1)
    predicted = slope * x[mask] + intercept
    residual = np.sum((y[mask] - predicted) ** 2)
    total = np.sum((y[mask] - np.mean(y[mask])) ** 2)
    r2 = 1.0 - residual / total
    return float(slope), float(intercept), float(r2)


spectra = {name: read_spectrum(path) for name, path in FILES.items()}
results = {}

for sample in ("A", "B"):
    xc, yc = spectra[f"{sample}_m5V"]
    xo, yo = spectra[f"{sample}_0V"]

    cutoff_baseline = float(np.mean(yc[(xc >= 18.0) & (xc <= 21.0)]))
    onset_baseline = float(np.mean(yo[(xo >= -0.8) & (xo <= 0.3)]))

    cm, cb, cr2 = linear_fit(xc, yc, FIT_WINDOWS[sample]["cutoff"])
    om, ob, or2 = linear_fit(xo, yo, FIT_WINDOWS[sample]["onset"])

    cutoff = (cutoff_baseline - cb) / cm
    onset = (onset_baseline - ob) / om
    work_function = 21.22 - cutoff
    vbm = -(work_function + onset)

    cutoff_scale = float(np.max(yc[(xc >= 15.0) & (xc <= 18.0)]) - cutoff_baseline)
    onset_scale = float(np.max(yo[(xo >= -1.0) & (xo <= 2.5)]) - onset_baseline)

    results[sample] = {
        "cutoff_window": FIT_WINDOWS[sample]["cutoff"],
        "onset_window": FIT_WINDOWS[sample]["onset"],
        "cutoff_baseline": cutoff_baseline,
        "onset_baseline": onset_baseline,
        "cutoff_slope": cm,
        "cutoff_intercept": cb,
        "cutoff_r2": cr2,
        "onset_slope": om,
        "onset_intercept": ob,
        "onset_r2": or2,
        "cutoff_eV": float(cutoff),
        "onset_eV": float(onset),
        "work_function_eV": float(work_function),
        "vbm_eV": float(vbm),
        "cutoff_scale": cutoff_scale,
        "onset_scale": onset_scale,
    }


payload = {
    "photon_energy_eV": 21.22,
    "files": {key: str(value) for key, value in FILES.items()},
    "spectra": {
        key: {"energy": x.tolist(), "intensity": y.tolist()}
        for key, (x, y) in spectra.items()
    },
    "results": results,
}

OUTPUT.mkdir(parents=True, exist_ok=True)
(OUTPUT / "ups_data.json").write_text(
    json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
)

for sample, values in results.items():
    print(
        sample,
        f"Ecutoff={values['cutoff_eV']:.3f} eV",
        f"Eonset={values['onset_eV']:.3f} eV",
        f"Phi={values['work_function_eV']:.3f} eV",
        f"VBM={values['vbm_eV']:.3f} eV",
    )
