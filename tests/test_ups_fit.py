import numpy as np
import pytest

from ups_fit import fit_ups_sample, savgol


def synthetic_ups(cutoff=16.7, onset=0.8):
    cutoff_x = np.arange(-5.0, 24.75, 0.05)
    cutoff_y = 25 + 8e5 / (1 + np.exp((cutoff_x - (cutoff - 0.2)) / 0.16))
    onset_x = np.arange(-5.0, 21.0, 0.05)
    onset_y = 20 + 2200 * np.maximum(onset_x - onset, 0) ** 1.35
    return cutoff_x, cutoff_y, onset_x, onset_y


def test_auto_fit_returns_physical_results():
    data = synthetic_ups()
    result = fit_ups_sample(*data)
    assert result["cutoff"]["slope"] < 0
    assert result["onset"]["slope"] > 0
    assert result["cutoff"]["r_squared"] > 0.9
    assert result["onset"]["r_squared"] > 0.9
    assert abs(result["cutoff_eV"] - 16.7) < 0.35
    assert abs(result["onset_eV"] - 0.8) < 0.3


def test_manual_windows_are_preserved():
    data = synthetic_ups()
    result = fit_ups_sample(*data, cutoff_window=[16.2, 16.7], onset_window=[0.9, 1.4])
    assert result["cutoff"]["window"] == [16.2, 16.7]
    assert result["onset"]["window"] == [0.9, 1.4]


def test_export_series_stay_aligned_when_input_is_descending():
    cutoff_x, cutoff_y, onset_x, onset_y = synthetic_ups()
    result = fit_ups_sample(cutoff_x[::-1], cutoff_y[::-1], onset_x[::-1], onset_y[::-1])
    for key in ("cutoff", "onset"):
        series = result[key]
        assert np.all(np.diff(series["energy"]) > 0)
        assert len(series["energy"]) == len(series["intensity"]) == len(series["normalized"]) == len(series["fit_line"])
    assert result["cutoff"]["intensity_raw"][0] == pytest.approx(cutoff_y[0])
    assert result["onset"]["intensity_raw"][0] == pytest.approx(onset_y[0])


def test_savgol_preserves_constant_and_straight_lines():
    constant = np.full(50, 7.5)
    assert np.allclose(savgol(constant, 7, 2), constant)
    line = 3.0 + 0.4 * np.arange(50)
    # 2 阶多项式能精确表示直线，窗口内拟合不会改变斜率和截距
    assert np.allclose(savgol(line, 7, 2), line)


def test_savgol_suppresses_noise_but_keeps_edge():
    rng = np.random.default_rng(20261102)
    x = np.linspace(-1, 3, 400)
    clean = np.clip(x, 0, None) ** 1.4
    noisy = clean + rng.normal(0, 0.02, x.size)
    smooth = savgol(noisy, 7, 2)
    assert np.std(smooth - clean) < np.std(noisy - clean)
    step = np.where(x < 1.0, 0.0, 1.0)
    assert abs(savgol(step, 7, 2)[np.argmin(np.abs(x - 1.0))] - 0.5) < 0.2


def test_savgol_rejects_invalid_parameters():
    y = np.arange(20.0)
    with pytest.raises(ValueError, match="奇数"):
        savgol(y, 4, 2)
    with pytest.raises(ValueError, match="奇数"):
        savgol(y, 1, 0)
    with pytest.raises(ValueError, match="阶数"):
        savgol(y, 7, 7)


def test_fit_applies_smoothing_before_normalisation_and_can_be_disabled():
    cutoff_x, cutoff_y, onset_x, onset_y = synthetic_ups()
    rng = np.random.default_rng(7)
    noisy = tuple(
        values + rng.normal(0, 0.004 * np.ptp(values), values.size)
        for values in (cutoff_y, onset_y)
    )
    smoothed = fit_ups_sample(cutoff_x, noisy[0], onset_x, noisy[1],
                              cutoff_window=[16.2, 16.7], onset_window=[0.9, 1.4])
    raw = fit_ups_sample(cutoff_x, noisy[0], onset_x, noisy[1],
                         cutoff_window=[16.2, 16.7], onset_window=[0.9, 1.4], smooth_window=0)
    assert smoothed["smoothing"] == {"window": 7, "order": 2}
    assert raw["smoothing"] is None
    assert not np.allclose(smoothed["onset"]["intensity"], raw["onset"]["intensity"])
    assert np.allclose(smoothed["onset"]["intensity_raw"], raw["onset"]["intensity"])
    # 绘出的曲线应更光滑：二阶差分的抖动必须小于原始数据
    roughness = lambda values: float(np.mean(np.abs(np.diff(values, 2))))
    assert roughness(smoothed["onset"]["normalized"]) < roughness(raw["onset"]["normalized"])



def test_rejects_short_or_wrong_direction_data():
    with pytest.raises(ValueError, match="12"):
        fit_ups_sample([1, 2], [3, 4], [1, 2], [3, 4])
    data = synthetic_ups()
    with pytest.raises(ValueError, match="下降"):
        fit_ups_sample(data[0], -data[1], data[2], data[3], cutoff_window=[16.2, 16.7], onset_window=[0.9, 1.4])
