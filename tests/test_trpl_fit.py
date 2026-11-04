import numpy as np

from trpl_fit import expdec2, expdec3, fit_trpl


def test_recovers_synthetic_expdec2():
    x = np.linspace(0, 100, 201)
    y = expdec2(x, 2, 80, 5, 20, 30)
    result = fit_trpl(x, y)
    values = {item["name"]: item["value"] for item in result["parameters"]}
    assert abs(values["t1"] - 5) < 0.01
    assert abs(values["t2"] - 30) < 0.01
    assert result["r_squared"] > 0.999999
    assert abs(result["tau_avg"] - 20) < 0.01


def test_recovers_synthetic_expdec3():
    x = np.linspace(0, 200, 401)
    y = expdec3(x, 2, 70, 3, 25, 20, 10, 80)
    result = fit_trpl(x, y, "expdec3")
    values = {item["name"]: item["value"] for item in result["parameters"]}
    assert [round(values[name], 2) for name in ("t1", "t2", "t3")] == [3, 20, 80]
    assert result["r_squared"] > 0.999999
    assert len(result["component_fractions"]) == 3
