<#
.SYNOPSIS
  一键发布 Perovskite Engine：改版本号 → 构建 exe → 生成安装包。

.DESCRIPTION
  1) 把 <Version> 写进 packaging\PerovskiteEngine.iss（升级版本只需改这里）
  2) 检查 src\vendor 里的本地前端依赖（Plotly / SheetJS）是否齐全，并确认 index.html 不再引用 CDN
  3) 用 PyInstaller 构建 packaging\release-dist\PerovskiteEngine
  4) 用 Inno Setup 生成 packaging\installers\PerovskiteEngine-Setup-<Version>.exe

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File scripts\build_release.ps1 -Version 1.2.0

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File scripts\build_release.ps1 -Version 1.2.0 -SkipInstaller
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][ValidatePattern('^\d+\.\d+\.\d+$')][string]$Version,
    [ValidateSet('Development', 'InternalSigned')][string]$Mode = 'Development',
    [string]$SignToolPath,
    [string]$CertificateFile,
    [switch]$SkipInstaller
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$specDir = Join-Path $root 'packaging'
$issPath = Join-Path $specDir 'PerovskiteEngine.iss'
$htmlPath = Join-Path $root 'src\index.html'
$manifestSigner = Join-Path $PSScriptRoot 'sign_update_manifest.ps1'

function Write-Step($text) { Write-Host "`n==> $text" -ForegroundColor Cyan }

function Resolve-SignTool {
    param([string]$Requested)
    $candidates = @(
        $Requested,
        $env:SIGNTOOL_PATH,
        (Get-Command signtool.exe -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source),
        'C:\Program Files (x86)\Windows Kits\10\bin\x64\signtool.exe',
        'C:\Program Files (x86)\Windows Kits\10\bin\x86\signtool.exe'
    ) | Where-Object { $_ -and (Test-Path -LiteralPath $_) }
    if (-not $candidates) { throw 'InternalSigned mode requires SignTool. Pass -SignToolPath or set SIGNTOOL_PATH.' }
    return @($candidates)[0]
}

function Get-CertificateInfo {
    param([string]$RequestedPath)
    $path = $RequestedPath
    if (-not $path) {
        $path = Get-ChildItem -LiteralPath (Join-Path $root 'certificates') -Filter 'PerovskiteEngine-Internal.cer' -Recurse -ErrorAction SilentlyContinue |
            Sort-Object LastWriteTime -Descending | Select-Object -First 1 -ExpandProperty FullName
    }
    if (-not $path -or -not (Test-Path -LiteralPath $path)) { throw 'InternalSigned mode requires the public .cer certificate file.' }
    $certificate = Get-PfxCertificate -FilePath $path
    $bytes = [System.IO.File]::ReadAllBytes((Resolve-Path -LiteralPath $path))
    $sha = [System.Security.Cryptography.SHA256]::Create()
    try { $certificateSha256 = ([BitConverter]::ToString($sha.ComputeHash($bytes)) -replace '-', '').ToLowerInvariant() }
    finally { $sha.Dispose() }
    $trust = Get-Content -LiteralPath (Join-Path $root 'config\update_trust.json') -Raw | ConvertFrom-Json
    if ($certificateSha256 -ne $trust.certificate_sha256.ToLowerInvariant()) {
        throw 'Certificate SHA-256 does not match config/update_trust.json.'
    }
    if ($certificate.Subject -ne $trust.publisher) { throw 'Certificate Subject does not match the internal publisher.' }
    return [pscustomobject]@{
        Path = (Resolve-Path -LiteralPath $path).Path
        Thumbprint = $certificate.Thumbprint
        Publisher = $certificate.Subject
        CertificateSha256 = $certificateSha256
    }
}

function Sign-File {
    param([string]$Path, [string]$Tool, [string]$Thumbprint)
    & $Tool sign /fd SHA256 /sha1 $Thumbprint $Path
    if ($LASTEXITCODE -ne 0) { throw "SignTool failed for $Path with exit code $LASTEXITCODE." }
}

function Assert-Signature {
    param([string]$Path, $CertificateInfo)
    $signature = Get-AuthenticodeSignature -LiteralPath $Path
    if ($signature.Status -ne 'Valid' -or $signature.SignerCertificate.Subject -ne $CertificateInfo.Publisher) {
        throw "Invalid Authenticode signature: $Path / $($signature.Status) / $($signature.SignerCertificate.Subject)"
    }
    $sha = [System.Security.Cryptography.SHA256]::Create()
    try { $actual = ([BitConverter]::ToString($sha.ComputeHash($signature.SignerCertificate.RawData)) -replace '-', '').ToLowerInvariant() }
    finally { $sha.Dispose() }
    if ($actual -ne $CertificateInfo.CertificateSha256) { throw "Certificate fingerprint mismatch: $Path" }
}

function Wait-FileReady {
    param([string]$Path, [int]$TimeoutSeconds = 30)
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        try {
            $stream = [System.IO.File]::Open($Path, [System.IO.FileMode]::Open, [System.IO.FileAccess]::Read, [System.IO.FileShare]::Read)
            $stream.Dispose()
            return
        }
        catch [System.IO.IOException] { Start-Sleep -Milliseconds 500 }
    }
    throw "Timed out waiting for file to be released: $Path"
}

$signTool = $null
$certificateInfo = $null
if ($Mode -eq 'InternalSigned') {
    $signTool = Resolve-SignTool $SignToolPath
    $certificateInfo = Get-CertificateInfo $CertificateFile
    Write-Host "  publisher: $($certificateInfo.Publisher)"
    Write-Host "  cert sha256: $($certificateInfo.CertificateSha256)"
}

Write-Step "1/4 同步版本号到安装脚本（$Version）"
$iss = Get-Content -LiteralPath $issPath -Raw -Encoding UTF8
$pattern = '#define AppVersion "[^"]*"'
if (-not [regex]::IsMatch($iss, $pattern)) { throw "没能在 $issPath 里找到 AppVersion 定义。" }
$replacement = '#define AppVersion "' + $Version + '"'
$updated = [regex]::Replace($iss, $pattern, $replacement)
Set-Content -LiteralPath $issPath -Value $updated -Encoding UTF8 -NoNewline
$html = Get-Content -LiteralPath $htmlPath -Raw -Encoding UTF8
$htmlPattern = '<span id="app-version">[^<]+</span>'
if (-not [regex]::IsMatch($html, $htmlPattern)) { throw "没能在 $htmlPath 里找到界面版本号。" }
$htmlUpdated = [regex]::Replace($html, $htmlPattern, '<span id="app-version">' + $Version + '</span>')
Set-Content -LiteralPath $htmlPath -Value $htmlUpdated -Encoding UTF8 -NoNewline

Write-Step '2/4 检查本地前端依赖'
foreach ($f in 'plotly-2.27.0.min.js', 'xlsx.full.min.js') {
    $p = Join-Path $root "src\vendor\$f"
    if (-not (Test-Path -LiteralPath $p)) { throw "缺少本地依赖 $p，请不要删除 src\vendor 下的文件。" }
    Write-Host ('  {0}  {1:N0} bytes' -f $f, (Get-Item -LiteralPath $p).Length)
}
if (Select-String -LiteralPath (Join-Path $root 'src\index.html') -Pattern 'https://cdn\.' -Quiet) {
    throw 'src\index.html 里仍有 CDN 引用，请改成本地 vendor 文件。'
}

Write-Step '3/4 构建 exe（PyInstaller）'
Push-Location $specDir
try {
    python -m PyInstaller 'perovskite-engine.spec' --noconfirm --clean --distpath 'release-dist' --workpath 'release-build'
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller 失败，退出码 $LASTEXITCODE" }
    python -m PyInstaller 'updater.spec' --noconfirm --clean --distpath 'release-dist' --workpath 'release-build-updater'
    if ($LASTEXITCODE -ne 0) { throw "Updater 构建失败，退出码 $LASTEXITCODE" }
}
finally { Pop-Location }

$exe = Join-Path $specDir 'release-dist\PerovskiteEngine\PerovskiteEngine.exe'
if (-not (Test-Path -LiteralPath $exe)) { throw "未生成 $exe" }
if (-not (Test-Path -LiteralPath (Join-Path $specDir 'release-dist\Updater.exe'))) { throw '未生成 Updater.exe' }
Write-Host ('  {0}  {1:N1} MB' -f $exe, ((Get-Item -LiteralPath $exe).Length / 1MB))

if ($SkipInstaller) {
    Write-Step '已跳过安装包构建'
    return
}

Write-Step '4/4 生成安装包（Inno Setup）'
$candidates = @(
    $env:INNO_SETUP,
    'C:\Program Files (x86)\Inno Setup 6\ISCC.exe',
    'C:\Program Files\Inno Setup 6\ISCC.exe',
    'C:\InnoSetupTemp\ISCC.exe'
) | Where-Object { $_ -and (Test-Path -LiteralPath $_) }
if (-not $candidates) {
    $cmd = Get-Command ISCC.exe -ErrorAction SilentlyContinue
    if ($cmd) { $candidates = @($cmd.Source) }
}
if (-not $candidates) { throw '找不到 ISCC.exe（Inno Setup 编译器）：请安装 Inno Setup 6，或设置 INNO_SETUP 环境变量。' }

if ($Mode -eq 'InternalSigned') {
    Write-Step '签名主程序和 Updater.exe'
    $updaterExe = Join-Path $specDir 'release-dist\Updater.exe'
    Sign-File $exe $signTool $certificateInfo.Thumbprint
    Sign-File $updaterExe $signTool $certificateInfo.Thumbprint
    Assert-Signature $exe $certificateInfo
    Assert-Signature $updaterExe $certificateInfo
}

$iscc = @($candidates)[0]; & $iscc $issPath
if ($LASTEXITCODE -ne 0) { throw "Inno Setup 失败，退出码 $LASTEXITCODE" }

$setup = Get-ChildItem -LiteralPath (Join-Path $specDir 'installers') -Filter "PerovskiteEngine-Setup-$Version.exe" -ErrorAction SilentlyContinue |
    Sort-Object LastWriteTime -Descending | Select-Object -First 1
if (-not $setup) { throw "未生成安装包 PerovskiteEngine-Setup-$Version.exe" }
Wait-FileReady $setup.FullName
if ($Mode -eq 'Development') {
    Write-Host "`n完成开发模式构建："
    Write-Host "  exe   : $exe"
    Write-Host "  setup : $($setup.FullName)"
    return
}

Write-Step '签名安装包并生成可信更新清单'
Sign-File $setup.FullName $signTool $certificateInfo.Thumbprint
Assert-Signature $setup.FullName $certificateInfo
$digest = (Get-FileHash -LiteralPath $setup.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
$manifestPath = Join-Path $setup.DirectoryName 'release-manifest.json'
$signaturePath = Join-Path $setup.DirectoryName 'release-manifest.json.sig'
$manifest = [ordered]@{
    certificate_sha256 = $certificateInfo.CertificateSha256
    installer = $setup.Name
    notes = "Perovskite Engine $Version"
    publisher = $certificateInfo.Publisher
    sha256 = $digest
    version = $Version
}
$manifestJson = $manifest | ConvertTo-Json -Compress
[System.IO.File]::WriteAllText($manifestPath, $manifestJson, (New-Object System.Text.UTF8Encoding($false)))
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File $manifestSigner -ManifestPath $manifestPath -SignaturePath $signaturePath -CertificateThumbprint $certificateInfo.Thumbprint
if ($LASTEXITCODE -ne 0) { throw 'Update manifest signing failed.' }
Copy-Item -LiteralPath $certificateInfo.Path -Destination (Join-Path $setup.DirectoryName 'PerovskiteEngine-Internal.cer') -Force
$digestLine = "$digest  $($setup.Name)"
Set-Content -LiteralPath ($setup.FullName + '.sha256') -Value $digestLine -Encoding ASCII
$manifestSignature = Get-Content -LiteralPath $signaturePath -Raw
if (-not $manifestSignature.Trim()) { throw 'Update manifest signature is empty.' }
Write-Host "`n完成：" -ForegroundColor Green
Write-Host "  exe   : $exe"
Write-Host ('  setup : {0}  ({1:N1} MB)' -f $setup.FullName, ($setup.Length / 1MB))
Write-Host "  sha256: $($setup.FullName).sha256"
Write-Host "  manifest: $manifestPath"
Write-Host "  signature: $signaturePath"
