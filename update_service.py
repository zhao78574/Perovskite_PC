"""Asynchronous, manual-update primitives for the desktop application."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import subprocess
import threading
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.parse import urlparse


API_TIMEOUT = 15
DEFAULT_REPOSITORY = "zhao78574/Perovskite_PC"
REPOSITORY = os.environ.get("PEROVSKITE_UPDATE_REPOSITORY", "").strip() or DEFAULT_REPOSITORY
EXPECTED_PUBLISHER = os.environ.get("PEROVSKITE_UPDATE_PUBLISHER", "").strip() or "CN=Perovskite Engine Internal"
EXPECTED_CERTIFICATE_SHA256 = os.environ.get("PEROVSKITE_UPDATE_CERTIFICATE_SHA256", "").strip().lower() or "12925004ec1ef5a92077a88b40140e2a63115d011a1332e5f3cfe0732d5c2135"

# Retained for a future signed release mode; the default lab workflow does not require them.
MANIFEST_ASSET = "release-manifest.json"
MANIFEST_SIGNATURE_ASSET = "release-manifest.json.sig"
CERTIFICATE_ASSET = "PerovskiteEngine-Internal.cer"
RELEASES_URL = f"https://github.com/{DEFAULT_REPOSITORY}/releases"
TRUSTED_REDIRECT_HOSTS = {"github.com", "api.github.com", "release-assets.githubusercontent.com", "objects.githubusercontent.com", "github-releases.githubusercontent.com"}


class UpdateError(RuntimeError):
    pass


@dataclass(frozen=True)
class ReleaseInfo:
    version: str
    notes: str
    release_url: str
    download_url: str
    sha256: str
    publisher: str = ""
    certificate_sha256: str = ""


def _version(value: str) -> tuple:
    raw = str(value).strip().lstrip("vV")
    match = re.fullmatch(r"(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-([0-9A-Za-z.-]+))?(?:\+[0-9A-Za-z.-]+)?", raw)
    if not match:
        raise UpdateError(f"无效版本号：{value}")
    prerelease = match.group(4)
    prerelease_key = () if prerelease is None else tuple(
        (0, int(part)) if part.isdigit() else (1, part) for part in prerelease.split(".")
    )
    return (int(match.group(1)), int(match.group(2)), int(match.group(3)), 1 if prerelease is None else 0, prerelease_key)


def is_newer(current: str, candidate: str) -> bool:
    return _version(candidate) > _version(current)


def _json_request(url: str) -> dict:
    parsed = urlparse(str(url))
    if parsed.scheme != "https" or parsed.hostname != "api.github.com" or parsed.path != f"/repos/{DEFAULT_REPOSITORY}/releases/latest":
        raise UpdateError("更新 API 地址不属于官方 GitHub 仓库。")
    request = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json", "User-Agent": "PerovskiteEngine-Updater"})
    try:
        opener = urllib.request.build_opener(_SafeRedirectHandler)
        with opener.open(request, timeout=API_TIMEOUT) as response:
            return json.loads(response.read().decode("utf-8"))
    except Exception as error:  # noqa: BLE001
        raise UpdateError(f"无法读取 GitHub 更新信息：{error}") from error


def _validate_asset_url(url: str) -> str:
    parsed = urlparse(str(url))
    if parsed.scheme != "https" or parsed.hostname not in {"github.com", "api.github.com"}:
        raise UpdateError("更新资源 URL 不是官方 HTTPS GitHub 地址。")
    if parsed.hostname == "github.com" and not parsed.path.startswith(f"/{DEFAULT_REPOSITORY}/releases/"):
        raise UpdateError("更新资源 URL 不属于官方 GitHub Release。")
    return str(url)


def is_official_release_url(url: str) -> bool:
    try:
        parsed = urlparse(str(url))
        return (parsed.scheme == "https" and parsed.netloc == "github.com"
                and (parsed.path == f"/{DEFAULT_REPOSITORY}/releases"
                     or bool(re.fullmatch(rf"/{re.escape(DEFAULT_REPOSITORY)}/releases/tag/v?\d+\.\d+\.\d+", parsed.path)))
                and not parsed.params and not parsed.query and not parsed.fragment)
    except ValueError:
        return False


class _SafeRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        parsed = urlparse(newurl)
        if parsed.scheme != "https" or parsed.hostname not in TRUSTED_REDIRECT_HOSTS:
            raise UpdateError("更新资源发生了不受信任的重定向。")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _bytes_request(url: str) -> bytes:
    _validate_asset_url(url)
    request = urllib.request.Request(url, headers={"User-Agent": "PerovskiteEngine-Updater"})
    opener = urllib.request.build_opener(_SafeRedirectHandler)
    try:
        with opener.open(request, timeout=API_TIMEOUT) as response:
            return response.read()
    except UpdateError:
        raise
    except Exception as error:  # noqa: BLE001
        raise UpdateError(f"无法读取更新校验文件：{error}") from error


def _checksum(text: bytes, installer_name: str) -> str:
    match = re.search(r"\b([0-9a-fA-F]{64})\s+(?:\*?)([^\s]+)", text.decode("utf-8", errors="replace"))
    if not match or Path(match.group(2)).name != installer_name:
        raise UpdateError("Release 缺少有效的安装包 SHA-256 文件。")
    return match.group(1).lower()


def fetch_latest_release(current_version: str | None = None) -> ReleaseInfo:
    if REPOSITORY != DEFAULT_REPOSITORY:
        raise UpdateError("更新源必须是官方 GitHub 仓库。")
    release = _json_request(f"https://api.github.com/repos/{DEFAULT_REPOSITORY}/releases/latest")
    release_url = str(release.get("html_url", ""))
    if not is_official_release_url(release_url):
        raise UpdateError("GitHub Release 页面地址不受信任。")
    version = str(release.get("tag_name", "")).lstrip("vV")
    _version(version)
    if current_version is not None and not is_newer(current_version, version):
        return ReleaseInfo(version=version, notes=str(release.get("body", "")), release_url=release_url, download_url="", sha256="")
    assets = release.get("assets") or []
    installer = next((item for item in assets if re.fullmatch(r"PerovskiteEngine-Setup-\d+\.\d+\.\d+\.exe", str(item.get("name", "")))), None)
    if not installer:
        raise UpdateError("Release 缺少安装包。")
    installer_name = str(installer["name"])
    installer_version = re.fullmatch(r"PerovskiteEngine-Setup-(\d+\.\d+\.\d+)\.exe", installer_name).group(1)
    if _version(installer_version) != _version(version):
        raise UpdateError("安装包版本、应用版本和 Release 标签不一致。")
    checksum_asset = next((item for item in assets if str(item.get("name", "")) in {installer_name + ".sha256", installer_name + ".sha256.txt"}), None)
    if not checksum_asset:
        raise UpdateError("Release 缺少安装包 SHA-256 文件。")
    digest = _checksum(_bytes_request(str(checksum_asset.get("browser_download_url", ""))), installer_name)
    return ReleaseInfo(version=version, notes=str(release.get("body", "")), release_url=release_url, download_url=str(installer.get("browser_download_url", "")), sha256=digest)


# These helpers remain available for a future signed release mode. They are not called by the default lab workflow.
def _canonical_manifest(manifest: dict) -> bytes:
    return json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _verify_signed_manifest(manifest_bytes: bytes, signature_bytes: bytes, certificate_bytes: bytes) -> dict:
    if hashlib.sha256(certificate_bytes).hexdigest().lower() != EXPECTED_CERTIFICATE_SHA256:
        raise UpdateError("更新清单证书指纹不匹配。")
    try:
        from cryptography import x509
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import padding
        certificate = x509.load_der_x509_certificate(certificate_bytes)
        manifest = json.loads(manifest_bytes.decode("utf-8"))
        certificate.public_key().verify(base64.b64decode(signature_bytes, validate=True), _canonical_manifest(manifest), padding.PKCS1v15(), hashes.SHA256())
        if EXPECTED_PUBLISHER not in certificate.subject.rfc4514_string():
            raise UpdateError("更新清单证书发布者不匹配。")
        return manifest
    except UpdateError:
        raise
    except Exception as error:  # noqa: BLE001
        raise UpdateError(f"更新清单签名验证失败：{error}") from error


def _verify_authenticode(path: Path, publisher: str, certificate_sha256: str) -> None:
    script = """
$signature = Get-AuthenticodeSignature -LiteralPath $args[0]
$certificateSha256 = ''
if ($signature.SignerCertificate) {
    $sha = [System.Security.Cryptography.SHA256]::Create()
    try { $certificateSha256 = ([BitConverter]::ToString($sha.ComputeHash($signature.SignerCertificate.RawData)) -replace '-', '').ToLowerInvariant() }
    finally { $sha.Dispose() }
}
[pscustomobject]@{ Status = [string]$signature.Status; Subject = if ($signature.SignerCertificate) { [string]$signature.SignerCertificate.Subject } else { '' }; CertificateSha256 = $certificateSha256 } | ConvertTo-Json -Compress
"""
    try:
        result = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", script, str(path)], capture_output=True, text=True, timeout=20, check=True)
        signature = json.loads(result.stdout.strip())
    except Exception as error:  # noqa: BLE001
        raise UpdateError(f"无法验证 Authenticode 签名：{error}") from error
    if signature.get("Status") != "Valid" or publisher not in signature.get("Subject", "") or signature.get("CertificateSha256", "").lower() != certificate_sha256.lower():
        raise UpdateError("安装包签名或证书指纹不匹配。")


class UpdateManager:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._state = {"status": "idle", "release": None, "error": None}

    def state(self) -> dict:
        with self._lock:
            return json.loads(json.dumps(self._state))

    def _set(self, **values) -> None:
        with self._lock:
            self._state.update(values)

    def check_async(self, current_version: str) -> None:
        if self.state()["status"] == "checking":
            return
        self._set(status="checking", error=None)

        def worker() -> None:
            try:
                release = fetch_latest_release(current_version)
                status = "available" if is_newer(current_version, release.version) else "up-to-date"
                self._set(status=status, release=asdict(release))
            except UpdateError as error:
                self._set(status="error", error=str(error))

        threading.Thread(target=worker, name="update-check", daemon=True).start()
