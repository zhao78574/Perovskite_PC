import pytest

import update_service
import build_exe
from update_service import UpdateError, is_newer


def _release(assets=None, url="https://github.com/zhao78574/Perovskite_PC/releases/tag/v1.4.6"):
    return {
        "tag_name": "v1.4.6",
        "html_url": url,
        "body": "修复更新流程。",
        "assets": assets or [
            {"name": "PerovskiteEngine-Setup-1.4.6.exe", "browser_download_url": "https://github.com/zhao78574/Perovskite_PC/releases/download/v1.4.6/PerovskiteEngine-Setup-1.4.6.exe"},
            {"name": "PerovskiteEngine-Setup-1.4.6.exe.sha256", "browser_download_url": "https://github.com/zhao78574/Perovskite_PC/releases/download/v1.4.6/PerovskiteEngine-Setup-1.4.6.exe.sha256"},
        ],
    }


def test_semantic_version_comparison_and_availability():
    assert is_newer("1.4.5", "v1.4.6")
    assert is_newer("1.4.5", "1.4.5-beta.2") is False
    assert is_newer("1.4.5-beta.2", "1.4.5")
    assert not is_newer("1.4.6", "1.4.6")


def test_invalid_version_fails_closed():
    with pytest.raises(UpdateError):
        is_newer("1.4.2", "latest")
    with pytest.raises(UpdateError):
        is_newer("1.4", "1.4.3")


def test_fetch_release_reads_checksum_without_signature(monkeypatch):
    monkeypatch.setattr(update_service, "_json_request", lambda url: _release())
    monkeypatch.setattr(update_service, "_bytes_request", lambda url: b"a" * 64 + b"  PerovskiteEngine-Setup-1.4.6.exe\n")
    release = update_service.fetch_latest_release()
    assert release.version == "1.4.6"
    assert release.sha256 == "a" * 64
    assert release.release_url.endswith("/v1.4.6")
    assert release.publisher == ""


def test_missing_checksum_is_actionable(monkeypatch):
    assets = [_release()["assets"][0]]
    monkeypatch.setattr(update_service, "_json_request", lambda url: _release(assets))
    with pytest.raises(UpdateError, match="SHA-256"):
        update_service.fetch_latest_release()


def test_older_release_without_checksum_is_not_an_error(monkeypatch):
    monkeypatch.setattr(update_service, "_json_request", lambda url: _release([_release()["assets"][0]]))
    result = update_service.fetch_latest_release("1.4.6")
    assert result.version == "1.4.6"
    assert result.sha256 == ""
    assert result.release_url.endswith("/tag/v1.4.6")


def test_older_release_does_not_request_checksum(monkeypatch):
    old = _release(assets=[_release()["assets"][0]], url="https://github.com/zhao78574/Perovskite_PC/releases/tag/v1.4.5")
    old["tag_name"] = "v1.4.5"
    monkeypatch.setattr(update_service, "_json_request", lambda url: old)
    monkeypatch.setattr(update_service, "_bytes_request", lambda url: pytest.fail("older release must not fetch checksum"))
    manager = update_service.UpdateManager()
    manager.check_async("1.4.6")
    import time
    for _ in range(50):
        if manager.state()["status"] != "checking":
            break
        time.sleep(.01)
    assert manager.state()["status"] == "up-to-date"
    assert manager.state()["release"]["sha256"] == ""


def test_invalid_checksum_is_rejected(monkeypatch):
    monkeypatch.setattr(update_service, "_json_request", lambda url: _release())
    monkeypatch.setattr(update_service, "_bytes_request", lambda url: b"bad  PerovskiteEngine-Setup-1.4.6.exe")
    with pytest.raises(UpdateError, match="SHA-256"):
        update_service.fetch_latest_release()


def test_untrusted_release_url_is_rejected(monkeypatch):
    monkeypatch.setattr(update_service, "_json_request", lambda url: _release(url="https://example.com/releases/tag/v1.4.6"))
    with pytest.raises(UpdateError, match="不受信任"):
        update_service.fetch_latest_release()
    assert not update_service.is_official_release_url("http://github.com/zhao78574/Perovskite_PC/releases/tag/v1.4.6")
    assert not update_service.is_official_release_url("https://github.com/other/repo/releases/tag/v1.4.6")
    assert not update_service.is_official_release_url("https://github.com.evil.test/zhao78574/Perovskite_PC/releases")
    assert not update_service.is_official_release_url("https://github.com/zhao78574/Perovskite_PC/releases/tag/v1.4.6/evil")


def test_open_release_page_fallback_and_browser_failures(monkeypatch):
    opened = []
    monkeypatch.setattr(build_exe.webbrowser, "open", lambda url, new: opened.append(url) or True)
    api = build_exe.BackendAPI()
    assert api.open_release_page_python(None)["status"] == "success"
    assert opened == [update_service.RELEASES_URL]
    tag_url = "https://github.com/zhao78574/Perovskite_PC/releases/tag/v1.4.6"
    assert api.open_release_page_python(tag_url)["status"] == "success"
    assert opened[-1] == tag_url
    assert api.open_release_page_python("https://example.com/")["status"] == "error"
    assert len(opened) == 2
    monkeypatch.setattr(build_exe.webbrowser, "open", lambda url, new: False)
    assert api.open_release_page_python(None)["status"] == "error"
    def fail(url, new):
        raise OSError("browser unavailable")
    monkeypatch.setattr(build_exe.webbrowser, "open", fail)
    assert "browser unavailable" in api.open_release_page_python(None)["message"]


def test_untrusted_checksum_asset_url_is_rejected(monkeypatch):
    assets = _release()["assets"]
    assets[1] = {"name": assets[1]["name"], "browser_download_url": "https://example.com/checksum"}
    monkeypatch.setattr(update_service, "_json_request", lambda url: _release(assets))
    with pytest.raises(UpdateError, match="官方 HTTPS"):
        update_service.fetch_latest_release()


def test_github_api_failure_and_timeout_are_reported(monkeypatch):
    monkeypatch.setattr(update_service, "_json_request", lambda url: (_ for _ in ()).throw(UpdateError("GitHub API timeout")))
    with pytest.raises(UpdateError, match="timeout"):
        update_service.fetch_latest_release()


def test_github_rate_limit_is_reported_without_retry(monkeypatch):
    calls = []

    def rate_limited(url):
        calls.append(url)
        raise UpdateError("GitHub API HTTP 403 rate limit exceeded")

    monkeypatch.setattr(update_service, "_json_request", rate_limited)
    manager = update_service.UpdateManager()
    manager.check_async("1.4.6")
    for _ in range(100):
        state = manager.state()
        if state["status"] != "checking":
            break
        __import__("time").sleep(0.01)

    assert len(calls) == 1
    assert state["status"] == "error"
    assert "403" in state["error"]
