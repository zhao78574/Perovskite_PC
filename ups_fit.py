import numpy as np


PHOTON_ENERGY_EV = 21.22
DEFAULT_SMOOTH_WINDOW = 7
DEFAULT_SMOOTH_ORDER = 2


def savgol(y_values, window=DEFAULT_SMOOTH_WINDOW, order=DEFAULT_SMOOTH_ORDER):
    """Savitzky-Golay 平滑，等价于 Origin 的 Method = Savitzky-Golay。

    对每个点用其邻域内的低阶多项式做最小二乘拟合，取拟合值作为输出，
    因此能在压噪声的同时保留峰形和边沿位置（不像移动平均那样把边沿抹平）。
    窗口在两端自动截断，不会因为边界产生异常值。
    """
    y = np.asarray(y_values, dtype=float)
    if not isinstance(window, (int, np.integer)) or int(window) != window:
        raise ValueError("Savitzky-Golay 窗口点数必须是整数")
    window = int(window)
    order = int(order)
    if window < 3 or window % 2 == 0:
        raise ValueError("Savitzky-Golay 窗口点数必须是 >= 3 的奇数")
    if order < 0 or order >= window:
        raise ValueError("多项式阶数必须大于等于 0 且小于窗口点数")

    n = y.size
    if n == 0:
        return y.copy()
    half = window // 2
    out = np.empty_like(y)
    for index in range(n):
        low = max(0, index - half)
        high = min(n, index + half + 1)
        offset = np.arange(low, high, dtype=float) - index
        segment = y[low:high]
        usable = int(min(order, offset.size - 1))
        if usable < 0:
            out[index] = y[index]
            continue
        coefficients = np.polyfit(offset, segment, usable)
        out[index] = float(np.polyval(coefficients, 0.0))
    return out


def _series(x_values, y_values):
    x = np.asarray(x_values, dtype=float)
    y = np.asarray(y_values, dtype=float)
    if x.size != y.size or x.size < 12:
        raise ValueError("UPS 数据至少需要 12 个成对数值点")
    valid = np.isfinite(x) & np.isfinite(y)
    x, y = x[valid], y[valid]
    if x.size < 12:
        raise ValueError("UPS 数据中的有效数值点不足")
    order = np.argsort(x)
    x, y = x[order], y[order]
    unique = np.r_[True, np.diff(x) > 0]
    x, y = x[unique], y[unique]
    if x.size < 12:
        raise ValueError("UPS 能量列包含过多重复值")
    return x, y


def _mean_in_range(x, y, low, high, fallback):
    mask = (x >= low) & (x <= high)
    values = y[mask]
    if values.size < 3:
        values = y[fallback]
    return float(np.mean(values))


def _linear_fit(x, y, window, slope_sign):
    low, high = sorted(map(float, window))
    mask = (x >= low) & (x <= high)
    if np.count_nonzero(mask) < 6:
        raise ValueError("拟合区间内至少需要 6 个数据点")
    slope, intercept = np.polyfit(x[mask], y[mask], 1)
    if slope_sign * slope <= 0:
        direction = "下降" if slope_sign < 0 else "上升"
        raise ValueError(f"所选拟合区间不是有效的{direction}线性边")
    predicted = slope * x[mask] + intercept
    total = np.sum((y[mask] - np.mean(y[mask])) ** 2)
    if total <= 0:
        raise ValueError("拟合区间内没有足够的强度变化")
    r_squared = 1 - np.sum((y[mask] - predicted) ** 2) / total
    return low, high, float(slope), float(intercept), float(r_squared)


def _auto_cutoff_window(x, y):
    roi = (x >= 14) & (x <= 19)
    indexes = np.flatnonzero(roi)
    if indexes.size < 12:
        raise ValueError("−5 V 数据未覆盖 14–19 eV 的截止边搜索区间")
    kernel = np.ones(min(9, indexes.size // 2 * 2 + 1))
    kernel /= kernel.size
    smooth = np.convolve(y, kernel, mode="same")
    derivative = np.gradient(smooth, x)
    center = indexes[np.argmin(derivative[indexes])]
    step = float(np.median(np.diff(x)))
    half_width = max(0.25, 5 * step)
    return [float(x[center] - half_width), float(x[center] + half_width)]


def _auto_onset_window(x, y, baseline):
    roi = (x >= -0.5) & (x <= 2.5)
    if np.count_nonzero(roi) < 12:
        raise ValueError("0 V 数据未覆盖 −0.5–2.5 eV 的价带边搜索区间")
    amplitude = float(np.max(y[roi] - baseline))
    if amplitude <= 0:
        raise ValueError("0 V 数据没有可识别的价带上升边")
    edge = roi & (y - baseline >= 0.03 * amplitude) & (y - baseline <= 0.20 * amplitude)
    if np.count_nonzero(edge) < 6:
        raise ValueError("无法自动确定价带线性拟合区间")
    return [float(np.min(x[edge])), float(np.max(x[edge]))]


def _payload(x, y, baseline, scale, fit, raw=None, smoothing=None):
    low, high, slope, intercept, r_squared = fit
    normalized = np.maximum(0, (y - baseline) / scale)
    line = [
        float((slope * value + intercept - baseline) / scale) if low <= value <= high else None
        for value in x
    ]
    return {
        "energy": x.tolist(),
        "intensity": y.tolist(),
        "intensity_raw": (y if raw is None else raw).tolist(),
        "normalized": normalized.tolist(),
        "fit_line": line,
        "window": [low, high],
        "baseline": baseline,
        "slope": slope,
        "intercept": intercept,
        "r_squared": r_squared,
        "smoothing": smoothing,
    }


def fit_ups_sample(cutoff_x, cutoff_y, onset_x, onset_y, cutoff_window=None, onset_window=None,
                   smooth_window=DEFAULT_SMOOTH_WINDOW, smooth_order=DEFAULT_SMOOTH_ORDER):
    cutoff_x, cutoff_y = _series(cutoff_x, cutoff_y)
    onset_x, onset_y = _series(onset_x, onset_y)

    # 平滑在归一化和拟合之前完成：画出来的曲线与切线拟合用的是同一份数据。
    cutoff_raw, onset_raw = cutoff_y.copy(), onset_y.copy()
    smoothing = None
    if smooth_window:
        smooth_window, smooth_order = int(smooth_window), int(smooth_order)
        cutoff_y = savgol(cutoff_y, smooth_window, smooth_order)
        onset_y = savgol(onset_y, smooth_window, smooth_order)
        smoothing = {"window": smooth_window, "order": smooth_order}

    cutoff_baseline = _mean_in_range(cutoff_x, cutoff_y, 18, 21, slice(-max(3, cutoff_x.size // 10), None))
    onset_baseline = _mean_in_range(onset_x, onset_y, -0.8, 0.3, slice(0, max(3, onset_x.size // 10)))
    cutoff_window = cutoff_window or _auto_cutoff_window(cutoff_x, cutoff_y)
    onset_window = onset_window or _auto_onset_window(onset_x, onset_y, onset_baseline)
    cutoff_fit = _linear_fit(cutoff_x, cutoff_y, cutoff_window, -1)
    onset_fit = _linear_fit(onset_x, onset_y, onset_window, 1)
    cutoff = (cutoff_baseline - cutoff_fit[3]) / cutoff_fit[2]
    onset = (onset_baseline - onset_fit[3]) / onset_fit[2]
    if not (cutoff_x.min() <= cutoff <= cutoff_x.max() and -1 <= onset <= 3):
        raise ValueError("拟合交点超出合理的 UPS 能量范围")
    work_function = PHOTON_ENERGY_EV - cutoff
    vbm = -(work_function + onset)
    cutoff_roi = (cutoff_x >= 15) & (cutoff_x <= 18)
    onset_roi = (onset_x >= -1) & (onset_x <= 2.5)
    cutoff_scale = float(np.max(cutoff_y[cutoff_roi]) - cutoff_baseline)
    onset_scale = float(np.max(onset_y[onset_roi]) - onset_baseline)
    if cutoff_scale <= 0 or onset_scale <= 0:
        raise ValueError("UPS 信号强度不足，无法归一化")
    return {
        "photon_energy_eV": PHOTON_ENERGY_EV,
        "cutoff_eV": float(cutoff),
        "onset_eV": float(onset),
        "work_function_eV": float(work_function),
        "vbm_eV": float(vbm),
        "cutoff": _payload(cutoff_x, cutoff_y, cutoff_baseline, cutoff_scale, cutoff_fit, cutoff_raw, smoothing),
        "onset": _payload(onset_x, onset_y, onset_baseline, onset_scale, onset_fit, onset_raw, smoothing),
        "smoothing": smoothing,
    }
