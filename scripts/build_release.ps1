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
    [switch]$SkipInstaller
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$specDir = Join-Path $root 'packaging'
$issPath = Join-Path $specDir 'PerovskiteEngine.iss'
$htmlPath = Join-Path $root 'src\index.html'

function Write-Step($text) { Write-Host "`n==> $text" -ForegroundColor Cyan }

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

$iscc = @($candidates)[0]; & $iscc $issPath
if ($LASTEXITCODE -ne 0) { throw "Inno Setup 失败，退出码 $LASTEXITCODE" }

$setup = Get-ChildItem -LiteralPath (Join-Path $specDir 'installers') -Filter "PerovskiteEngine-Setup-$Version.exe" -ErrorAction SilentlyContinue |
    Sort-Object LastWriteTime -Descending | Select-Object -First 1
if (-not $setup) { throw "未生成安装包 PerovskiteEngine-Setup-$Version.exe" }
$publisher = $env:PEROVSKITE_UPDATE_PUBLISHER
if (-not $publisher) { throw '未设置 PEROVSKITE_UPDATE_PUBLISHER，拒绝发布未配置发布者校验的安装包。' }
$signature = Get-AuthenticodeSignature -LiteralPath $setup.FullName
if ($signature.Status -ne 'Valid' -or -not $signature.SignerCertificate.Subject.Contains($publisher)) {
    throw "安装包 Authenticode 签名无效或发布者不匹配：$($signature.Status) / $($signature.SignerCertificate.Subject)"
}
$digest = (Get-FileHash -LiteralPath $setup.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
Set-Content -LiteralPath ($setup.FullName + '.sha256') -Value "$digest  $($setup.Name)" -Encoding ASCII
Write-Host "`n完成：" -ForegroundColor Green
Write-Host "  exe   : $exe"
Write-Host ('  setup : {0}  ({1:N1} MB)' -f $setup.FullName, ($setup.Length / 1MB))
Write-Host "  sha256: $($setup.FullName).sha256"
