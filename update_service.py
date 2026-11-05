"""Safe, asynchronous update primitives for the desktop application."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tempfile
import threading
import urllib.request
import base64
import sys
from dataclasses import asdict, dataclass
from pathlib import Path


API_TIMEOUT = 15
DOWNLOAD_TIMEOUT = 60
DEFAULT_REPOSITORY = "zhao78574/Perovskite_PC"
REPOSITORY = os.environ.get("PEROVSKITE_UPDATE_REPOSITORY", "").strip() or DEFAULT_REPOSITORY
EXPECTED_PUBLISHER = os.environ.get("PEROVSKITE_UPDATE_PUBLISHER", "").strip()
DEFAULT_PUBLISHER = "CN=Perovskite Engine Internal"
DEFAULT_CERTIFICATE_SHA256 = "12925004ec1ef5a92077a88b40140e2a63115d011a1332e5f3cfe0732d5c2135"
EXPECTED_PUBLISHER = EXPECTED_PUBLISHER or DEFAULT_PUBLISHER
EXPECTED_CERTIFICATE_SHA256 = os.environ.get("PEROVSKITE_UPDATE_CERTIFICATE_SHA256", "").strip().lower() or DEFAULT_CERTIFICATE_SHA256
MANIFEST_ASSET = "release-manifest.json"
MANIFEST_SIGNATURE_ASSET = "release-manifest.json.sig"
CERTIFICATE_ASSET = "PerovskiteEngine-Internal.cer"


class UpdateError(RuntimeError):
    pass


@dataclass(frozen=True)
class ReleaseInfo:
    version: str
    notes: str
    download_url: str
    sha256: str
    publisher: str
    certificate_sha256: str


def _version(value: str) -> tuple[int, ...]:
    raw = value.strip().lstrip("vV")
    parts = raw.split(".")
    if not parts or any(not part.isdigit() for part in parts):
        raise UpdateError(f"无效版本号：{value}")
    return tuple(int(part) for part in parts)


def is_newer(current: str, candidate: str) -> bool:
    return _version(candidate) > _version(current)


def _json_request(url: str) -> dict:
    request = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json", "User-Agent": "PerovskiteEngine-Updater"})
    try:
        with urllib.request.urlopen(request, timeout=API_TIMEOUT) as response:
            return json.loads(response.read().decode("utf-8"))
    except Exception as error:  # noqa: BLE001
        raise UpdateError(f"无法读取更新信息：{error}") from error


def _bytes_request(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "PerovskiteEngine-Updater"})
    try:
        with urllib.request.urlopen(request, timeout=API_TIMEOUT) as response:
            return response.read()
    except Exception as error:  # noqa: BLE001
        raise UpdateError(f"无法下载更新元数据：{error}") from error


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
        signature = base64.b64decode(signature_bytes, validate=True)
        certificate.public_key().verify(
            signature,
            _canonical_manifest(manifest),
            padding.PKCS1v15(),
            hashes.SHA256(),
        )
        if EXPECTED_PUBLISHER not in certificate.subject.rfc4514_string():
            raise UpdateError("更新清单证书发布者不匹配。")
        return manifest
    except UpdateError:
        raise
    except Exception as error:  # noqa: BLE001
        raise UpdateError(f"更新清单签名验证失败：{error}") from error


def fetch_latest_release() -> ReleaseInfo:
    if not REPOSITORY or "/" not in REPOSITORY:
        raise UpdateError("更新源未配置：请设置 PEROVSKITE_UPDATE_REPOSITORY（owner/repository）。")
    if not EXPECTED_PUBLISHER:
        raise UpdateError("签名发布者未配置：请设置 PEROVSKITE_UPDATE_PUBLISHER。")
    release = _json_request(f"https://api.github.com/repos/{REPOSITORY}/releases/latest")
    assets = release.get("assets") or []
    by_name = {str(item.get("name", "")): item for item in assets}
    manifest_asset = by_name.get(MANIFEST_ASSET)
    signature_asset = by_name.get(MANIFEST_SIGNATURE_ASSET)
    certificate_asset = by_name.get(CERTIFICATE_ASSET)
    if not manifest_asset or not signature_asset or not certificate_asset:
        raise UpdateError("Release 缺少签名更新清单。")
    manifest = _verify_signed_manifest(
        _bytes_request(manifest_asset["browser_download_url"]),
        _bytes_request(signature_asset["browser_download_url"]),
        _bytes_request(certificate_asset["browser_download_url"]),
    )
    release_version = str(release.get("tag_name", "")).lstrip("vV")
    version = str(manifest.get("version", "")).lstrip("vV")
    if not version or version != release_version:
        raise UpdateError("更新清单版本与 Release 标签不一致。")
    if str(manifest.get("publisher", "")) != EXPECTED_PUBLISHER:
        raise UpdateError("更新清单发布者不匹配。")
    if str(manifest.get("certificate_sha256", "")).lower() != EXPECTED_CERTIFICATE_SHA256:
        raise UpdateError("更新清单证书指纹不匹配。")
    digest = str(manifest.get("sha256", "")).strip().lower()
    if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
        raise UpdateError("更新清单 SHA-256 格式无效。")
    installer = by_name.get(str(manifest.get("installer", "")))
    if not installer:
        raise UpdateError("Release 缺少清单指定的安装包。")
    return ReleaseInfo(
        version=version,
        notes=str(manifest.get("notes", release.get("body", ""))),
        download_url=str(installer["browser_download_url"]),
        sha256=digest,
        publisher=EXPECTED_PUBLISHER,
        certificate_sha256=EXPECTED_CERTIFICATE_SHA256,
    )

    # Legacy unsigned-release path retained below for source compatibility.
    installer = next((item for item in assets if str(item.get("name", "")).lower().startswith("perovskiteengine-setup-") and str(item.get("name", "")).lower().endswith(".exe")), None)
    checksum = next((item for item in assets if str(item.get("name", "")).lower().endswith((".sha256", ".sha256.txt"))), None)
    if not installer or not checksum:
        raise UpdateError("Release 缺少安装包或 SHA-256 文件。")
    checksum_text = _json_request(checksum["browser_download_url"]) if checksum["browser_download_url"].endswith(".json") else None
    if checksum_text is not None:
        digest = str(checksum_text.get("sha256", "")).strip().lower()
    else:
        request = urllib.request.Request(checksum["browser_download_url"], headers={"User-Agent": "PerovskiteEngine-Updater"})
        try:
            with urllib.request.urlopen(request, timeout=API_TIMEOUT) as response:
                digest = response.read().decode("utf-8").split()[0].lower()
        except Exception as error:  # noqa: BLE001
            raise UpdateError(f"无法读取 SHA-256 文件：{error}") from error
    if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
        raise UpdateError("Release 中的 SHA-256 格式无效。")
    return ReleaseInfo(
        version=str(release.get("tag_name", "")).lstrip("vV"),
        notes=str(release.get("body", "")),
        download_url=str(installer["browser_download_url"]),
        sha256=digest,
        publisher=EXPECTED_PUBLISHER,
    )


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
        result = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", script, str(path)],
            capture_output=True, text=True, timeout=20, check=True,
        )
        signature = json.loads(result.stdout.strip())
    except Exception as error:  # noqa: BLE001
        raise UpdateError(f"无法验证安装包 Authenticode 签名：{error}") from error
    if signature.get("Status") != "Valid":
        raise UpdateError(f"安装包签名无效：{signature.get('Status', 'Unknown')}")
    if publisher not in signature.get("Subject", ""):
        raise UpdateError("Authenticode publisher mismatch.")
    if signature.get("CertificateSha256", "").lower() != certificate_sha256.lower():
        raise UpdateError("安装包签名证书指纹不匹配。")
        raise UpdateError("安装包签名发布者不匹配。")


def download_and_verify(release: ReleaseInfo, destination: Path | None = None, progress=None) -> Path:
    target = Path(destination) if destination else Path(tempfile.gettempdir()) / f"PerovskiteEngine-Setup-{release.version}.exe"
    target.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(release.download_url, headers={"User-Agent": "PerovskiteEngine-Updater"})
    digest = hashlib.sha256()
    try:
        with urllib.request.urlopen(request, timeout=DOWNLOAD_TIMEOUT) as response, target.open("wb") as output:
            total = int(response.headers.get("Content-Length", "0") or 0)
            downloaded = 0
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                digest.update(chunk)
                output.write(chunk)
                downloaded += len(chunk)
                if progress and total:
                    progress(min(99, int(downloaded * 100 / total)))
    except Exception as error:  # noqa: BLE001
        target.unlink(missing_ok=True)
        raise UpdateError(f"下载安装包失败：{error}") from error
    if digest.hexdigest().lower() != release.sha256.lower():
        target.unlink(missing_ok=True)
        raise UpdateError("安装包 SHA-256 校验失败。")
    _verify_authenticode(target, release.publisher, release.certificate_sha256)
    return target


class UpdateManager:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._state = {"status": "idle", "release": None, "installer": None, "error": None, "progress": 0}

    def state(self) -> dict:
        with self._lock:
            return json.loads(json.dumps(self._state))

    def _set(self, **values) -> None:
        with self._lock:
            self._state.update(values)

    def check_async(self, current_version: str) -> None:
        if self.state()["status"] in {"checking", "downloading"}:
            return
        self._set(status="checking", error=None)

        def worker() -> None:
            try:
                release = fetch_latest_release()
                if not is_newer(current_version, release.version):
                    self._set(status="up-to-date", release=asdict(release))
                else:
                    self._set(status="available", release=asdict(release))
            except UpdateError as error:
                self._set(status="error", error=str(error))

        threading.Thread(target=worker, name="update-check", daemon=True).start()

    def download_async(self) -> None:
        state = self.state()
        if state["status"] != "available":
            return
        self._set(status="downloading", progress=0, error=None)

        def worker() -> None:
            try:
                release = ReleaseInfo(**state["release"])
                installer = download_and_verify(release, progress=lambda value: self._set(progress=value))
                self._set(status="ready", installer=str(installer), progress=100)
            except UpdateError as error:
                self._set(status="error", error=str(error), progress=0)

        threading.Thread(target=worker, name="update-download", daemon=True).start()
