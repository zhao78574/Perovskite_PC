<#
.SYNOPSIS
  安装包冒烟测试：静默安装到临时目录 → 校验打包内容 → 静默卸载 → 确认清理干净。

.DESCRIPTION
  不依赖打开界面，只验证“发出去的安装包装了什么、卸得干净不干净”。
  界面本身的验收仍需人工双击运行（本机若无法启动，请先解决 pythonnet/.NET 环境）。

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File scripts\test_installer.ps1 -Version 1.3.0
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$Version,
    [string]$InstallDir = (Join-Path $env:TEMP 'PerovskiteEngine-smoke'),
    [switch]$KeepInstalled
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$setup = Join-Path $root "packaging\installers\PerovskiteEngine-Setup-$Version.exe"

function Write-Step($text) { Write-Host "`n==> $text" -ForegroundColor Cyan }
function Assert-True($condition, $message) {
    if (-not $condition) { throw "检查失败：$message" }
    Write-Host "  ok  $message" -ForegroundColor Green
}

if (-not (Test-Path -LiteralPath $setup)) { throw "找不到安装包 $setup" }
Write-Step "安装包：$setup（$([math]::Round((Get-Item $setup).Length / 1MB, 1)) MB）"
$trust = Get-Content -LiteralPath (Join-Path $root 'config\update_trust.json') -Raw | ConvertFrom-Json
$publisher = $trust.publisher
$signature = Get-AuthenticodeSignature -LiteralPath $setup
Assert-True ($signature.Status -eq 'Valid' -and $signature.SignerCertificate.Subject -eq $publisher) '安装包 Authenticode 签名和发布者正确'
$sha = [System.Security.Cryptography.SHA256]::Create()
try { $certificateSha256 = ([BitConverter]::ToString($sha.ComputeHash($signature.SignerCertificate.RawData)) -replace '-', '').ToLowerInvariant() }
finally { $sha.Dispose() }
Assert-True ($certificateSha256 -eq $trust.certificate_sha256.ToLowerInvariant()) '安装包签名证书 SHA-256 指纹正确'
$shaFile = $setup + '.sha256'
Assert-True (Test-Path -LiteralPath $shaFile) '安装包 SHA-256 sidecar 存在'
$expectedHash = ((Get-Content -LiteralPath $shaFile -Raw).Trim() -split '\s+')[0].ToLowerInvariant()
$actualHash = (Get-FileHash -LiteralPath $setup -Algorithm SHA256).Hash.ToLowerInvariant()
Assert-True ($expectedHash -eq $actualHash) '安装包 SHA-256 校验通过'

if (Test-Path -LiteralPath $InstallDir) {
    Write-Step '清理上一次的测试安装目录'
    Remove-Item -LiteralPath $InstallDir -Recurse -Force
}

Write-Step "1/3 静默安装到 $InstallDir"
$install = Start-Process -FilePath $setup -PassThru -Wait -ArgumentList @(
    '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART', '/NOCANCEL', "/DIR=$InstallDir"
)
Assert-True ($install.ExitCode -eq 0) "安装程序退出码为 0（实际 $($install.ExitCode)）"

Write-Step '2/3 校验打包内容'
$exe = Join-Path $InstallDir 'PerovskiteEngine.exe'
$updater = Join-Path $InstallDir 'Updater.exe'
$index = Join-Path $InstallDir '_internal\src\index.html'
$trustFile = Join-Path $InstallDir '_internal\config\update_trust.json'
$vendor = Join-Path $InstallDir '_internal\src\vendor'
$unins = Join-Path $InstallDir 'unins000.exe'

Assert-True (Test-Path -LiteralPath $exe) '主程序 PerovskiteEngine.exe 存在'
Assert-True (Test-Path -LiteralPath $updater) '独立 Updater.exe 存在'
Assert-True ((Get-Item $exe).Length -gt 5MB) '主程序体积正常（> 5 MB）'
Assert-True (Test-Path -LiteralPath $index) '页面文件 _internal\src\index.html 存在'
Assert-True (Test-Path -LiteralPath $trustFile) '更新信任配置已打包'
Assert-True (Test-Path -LiteralPath $unins) '卸载程序 unins000.exe 存在'

$html = Get-Content -LiteralPath $index -Raw -Encoding UTF8
Assert-True ($html.Contains('id="app-version"')) '页面包含版本号占位'
Assert-True ($html.Contains(">$Version<")) "页面版本号已同步为 $Version"
Assert-True ($html.Contains('rename-preview-table')) '页面包含重命名预览（说明打包的是带安全改动的版本）'
Assert-True ($html.Contains('appendMethodSheet')) '页面包含 Excel Method 记录'
Assert-True ($html.Contains('src="vendor/plotly-2.27.0.min.js"')) '前端依赖指向本地 vendor'

foreach ($name in 'plotly-2.27.0.min.js', 'xlsx.full.min.js') {
    $file = Join-Path $vendor $name
    Assert-True (Test-Path -LiteralPath $file) "本地依赖 $name 已打包（$([math]::Round((Get-Item $file -ErrorAction SilentlyContinue).Length / 1MB, 2)) MB）"
}

$fileCount = (Get-ChildItem -LiteralPath $InstallDir -Recurse -File).Count
$sizeMb = [math]::Round((Get-ChildItem -LiteralPath $InstallDir -Recurse -File | Measure-Object Length -Sum).Sum / 1MB, 1)
Write-Host "  安装后：$fileCount 个文件，$sizeMb MB" -ForegroundColor DarkGray
Assert-True ($fileCount -gt 200) "文件数量正常（$fileCount）"

if ($KeepInstalled) {
    Write-Step "已保留安装目录：$InstallDir"
    return
}

Write-Step '3/3 静默卸载并确认清理'
Start-Process -FilePath $unins -Wait -ArgumentList @('/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART')
$deadline = (Get-Date).AddSeconds(30)
while ((Test-Path -LiteralPath $InstallDir) -and (Get-Date) -lt $deadline) { Start-Sleep -Milliseconds 300 }

# 卸载程序可能残留空目录
if (Test-Path -LiteralPath $InstallDir) {
    $left = Get-ChildItem -LiteralPath $InstallDir -Recurse -File -ErrorAction SilentlyContinue
    Assert-True ($left.Count -eq 0) '卸载后没有残留文件'
    Remove-Item -LiteralPath $InstallDir -Recurse -Force -ErrorAction SilentlyContinue
} else {
    Write-Host '  ok  卸载后安装目录已删除' -ForegroundColor Green
}

Write-Host "`n安装包冒烟测试通过：$Version" -ForegroundColor Cyan
Write-Host '提醒：界面功能与真实数据仍需人工验收（本脚本只验证打包内容与安装/卸载）。'
