"""TRPL ExpDec2/ExpDec3 fitting shared by the desktop UI and tests."""

from __future__ import annotations

import numpy as np
from scipy.optimize import curve_fit


def expdec2(x, y0, a1, t1, a2, t2):
    with np.errstate(over="ignore", under="ignore", invalid="ignore"):
        return y0 + a1 * np.exp(-x / t1) + a2 * np.exp(-x / t2)


def expdec3(x, y0, a1, t1, a2, t2, a3, t3):
    with np.errstate(over="ignore", under="ignore", invalid="ignore"):
        return y0 + a1 * np.exp(-x / t1) + a2 * np.exp(-x / t2) + a3 * np.exp(-x / t3)


def fit_trpl(x_values, y_values, model="expdec2"):
    if model not in {"expdec2", "expdec3"}:
        raise ValueError("不支持的拟合模型。")
    function = expdec2 if model == "expdec2" else expdec3
    components = 2 if model == "expdec2" else 3
    parameter_count = 1 + components * 2
    minimum_points = parameter_count + 1

    xy = np.column_stack((np.asarray(x_values, float), np.asarray(y_values, float)))
    xy = xy[np.isfinite(xy).all(axis=1)]
    if len(xy) < minimum_points:
        raise ValueError(f"至少需要 {minimum_points} 组有效的时间和强度数据。")
    xy = xy[np.argsort(xy[:, 0])]
    x, y = xy[:, 0], xy[:, 1]
    if len(np.unique(x)) < minimum_points or np.ptp(x) <= 0:
        raise ValueError(f"时间列至少需要 {minimum_points} 个不同的数值。")

    peak = int(np.argmax(y))
    x, y = x[peak:] - x[peak], y[peak:]
    if len(y) < minimum_points:
        raise ValueError(f"强度峰值后的有效数据不足 {minimum_points} 组。")
    if len(y) > 20 and y[-1] < 0.1 * np.median(y[-21:-1]):
        x, y = x[:-1], y[:-1]

    span = float(np.ptp(x))
    y0_guess = float(np.median(y[-max(3, len(y) // 10):]))
    amplitude = max(float(np.max(y) - y0_guess), float(np.ptp(y)), 1e-12)
    if components == 2:
        starts = [
            (y0_guess, amplitude * split, span * fast, amplitude * (1 - split), span * slow)
            for split in (0.25, 0.5, 0.75)
            for fast, slow in ((1 / 50, 1 / 5), (1 / 20, 1 / 3), (1 / 10, 1.0))
        ]
    else:
        starts = [
            (y0_guess,
             amplitude * shares[0], span * times[0],
             amplitude * shares[1], span * times[1],
             amplitude * shares[2], span * times[2])
            for shares in ((0.5, 0.3, 0.2), (0.65, 0.25, 0.1), (0.25, 0.35, 0.4))
            for times in ((1 / 80, 1 / 10, 1 / 2), (1 / 30, 1 / 5, 1.0), (1 / 100, 1 / 15, 1 / 3))
        ]

    candidates = []
    for initial in starts:
        try:
            popt, pcov = curve_fit(function, x, y, p0=initial, method="lm", maxfev=150_000)
            if np.all(popt[1::2] >= 0) and np.all(popt[2::2] > 0):
                rss = float(np.sum((y - function(x, *popt)) ** 2))
                candidates.append((rss, popt, pcov))
        except (RuntimeError, ValueError, FloatingPointError):
            pass
    if not candidates:
        raise RuntimeError("拟合未收敛，请检查数据是否为衰减曲线。")

    rss, popt, pcov = min(candidates, key=lambda item: item[0])
    component_order = sorted(range(components), key=lambda index: popt[2 + index * 2])
    order = [0] + [value for index in component_order for value in (1 + index * 2, 2 + index * 2)]
    popt, pcov = popt[order], pcov[np.ix_(order, order)]
    stderr = np.sqrt(np.maximum(np.diag(pcov), 0))

    def lifetime(params):
        amplitudes, lifetimes = params[1::2], params[2::2]
        return np.sum(amplitudes * lifetimes**2) / np.sum(amplitudes * lifetimes)

    tau = float(lifetime(popt))
    gradient = np.zeros(parameter_count)
    for index in range(parameter_count):
        step = max(abs(popt[index]) * 1e-6, 1e-8)
        plus, minus = popt.copy(), popt.copy()
        plus[index] += step
        minus[index] -= step
        gradient[index] = (lifetime(plus) - lifetime(minus)) / (2 * step)
    tau_error = float(np.sqrt(max(float(gradient @ pcov @ gradient), 0)))

    fitted = function(x, *popt)
    n = len(x)
    tss = float(np.sum((y - np.mean(y)) ** 2))
    r_squared = 1 - rss / tss if tss else float("nan")
    adjusted_r_squared = (1 - (1 - r_squared) * (n - 1) / (n - parameter_count)
                          if n > parameter_count else float("nan"))
    reduced_chi_squared = rss / (n - parameter_count) if n > parameter_count else float("nan")
    weights = popt[1::2] * popt[2::2]
    fractions = weights / weights.sum()

    def finite(value):
        value = float(value)
        return value if np.isfinite(value) else None

    names = ["y0"] + [name for index in range(1, components + 1) for name in (f"A{index}", f"t{index}")]
    parameters = [
        {"name": name, "value": finite(value), "error": finite(error)}
        for name, value, error in zip(names, popt, stderr)
    ]
    return {
        "model": model, "x": x.tolist(), "y": y.tolist(), "fitted": fitted.tolist(),
        "parameters": parameters, "tau_avg": finite(tau), "tau_error": finite(tau_error),
        "component_fractions": [finite(value) for value in fractions],
        "fast_fraction": finite(fractions[0]),
        "middle_fraction": finite(fractions[1]) if components == 3 else None,
        "slow_fraction": finite(fractions[-1]),
        "r_squared": finite(r_squared), "adjusted_r_squared": finite(adjusted_r_squared),
        "reduced_chi_squared": finite(reduced_chi_squared), "rss": finite(rss), "points": n,
    }
