import os

import pytest

import build_exe


def test_runtime_preference_honours_environment(monkeypatch, tmp_path):
    monkeypatch.setenv("PEROVSKITE_DOTNET_RUNTIME", "coreclr")
    monkeypatch.setattr(build_exe, "RUNTIME_CACHE", str(tmp_path / "missing.txt"))
    runtime, source = build_exe._runtime_preference()
    assert runtime == "coreclr"
    assert source == "环境变量"


def test_runtime_preference_uses_last_success(monkeypatch, tmp_path):
    monkeypatch.delenv("PEROVSKITE_DOTNET_RUNTIME", raising=False)
    cache = tmp_path / "dotnet-runtime.txt"
    cache.write_text("coreclr", encoding="utf-8")
    monkeypatch.setattr(build_exe, "RUNTIME_CACHE", str(cache))
    runtime, source = build_exe._runtime_preference()
    assert runtime == "coreclr"
    assert source == "上次成功记录"


def test_runtime_preference_defaults_to_netfx(monkeypatch, tmp_path):
    monkeypatch.delenv("PEROVSKITE_DOTNET_RUNTIME", raising=False)
    monkeypatch.setattr(build_exe, "RUNTIME_CACHE", str(tmp_path / "missing.txt"))
    runtime, source = build_exe._runtime_preference()
    assert runtime == "netfx", "实验室电脑默认走内置的 .NET Framework，避免 hostfxr 依赖"
    assert source == "默认"


def test_runtime_order_keeps_fallback(monkeypatch, tmp_path):
    monkeypatch.setenv("PEROVSKITE_DOTNET_RUNTIME", "coreclr")
    monkeypatch.setattr(build_exe, "RUNTIME_CACHE", str(tmp_path / "missing.txt"))
    preferred, _ = build_exe._runtime_preference()
    attempts = [preferred] + [runtime for runtime in build_exe.DOTNET_RUNTIMES if runtime != preferred]
    assert attempts == ["coreclr", "netfx"]


def test_log_startup_writes_readable_log(monkeypatch, tmp_path):
    log_file = tmp_path / "logs" / "startup.log"
    monkeypatch.setattr(build_exe, "LOG_DIR", str(log_file.parent))
    monkeypatch.setattr(build_exe, "STARTUP_LOG", str(log_file))
    monkeypatch.setattr(build_exe, "_log_prepared", False)
    build_exe.log_startup("单元测试阶段", "detail")
    content = log_file.read_text(encoding="utf-8")
    assert "单元测试阶段" in content
    assert "detail" in content


def test_window_geometry_stays_in_logical_pixels():
    width, height = build_exe.window_geometry()
    assert (width, height) == (1366, 768), (
        "窗口必须保持逻辑尺寸：手动乘缩放会让 WebView2 二次放大，右侧被裁切"
    )


def test_webview_imported_after_runtime_selection():
    source = open("build_exe.py", encoding="utf-8").read()
    runtime_call = source.index("_activate_dotnet_runtime()")
    webview_import = source.index("import webview  # noqa: E402")
    assert runtime_call < webview_import, "必须先确定 .NET 运行时再导入 pywebview"
