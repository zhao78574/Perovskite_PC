<#
.SYNOPSIS
  Create the Perovskite Engine internal code-signing certificate.

.DESCRIPTION
  Creates a self-signed Code Signing certificate in the current user's
  certificate store, exports its public .cer file, and exports an encrypted
  .pfx backup. The private backup directory must never be committed.
##>
[CmdletBinding()]
param(
    [string]$PublicOutputDirectory,
    [string]$PrivateOutputDirectory,
    [string]$Subject = 'CN=Perovskite Engine Internal',
    [int]$Years = 3
)

$ErrorActionPreference = 'Stop'

$projectRoot = Split-Path -Parent $PSScriptRoot
if (-not $PublicOutputDirectory) { $PublicOutputDirectory = Join-Path $projectRoot 'certificates' }
if (-not $PrivateOutputDirectory) { $PrivateOutputDirectory = Join-Path $projectRoot 'certificates-private' }

if ($Years -lt 1) { throw 'Years must be at least 1.' }
New-Item -ItemType Directory -Path $PublicOutputDirectory -Force | Out-Null
New-Item -ItemType Directory -Path $PrivateOutputDirectory -Force | Out-Null

$cerPath = Join-Path $PublicOutputDirectory 'PerovskiteEngine-Internal.cer'
$pfxPath = Join-Path $PrivateOutputDirectory 'PerovskiteEngine-Internal.pfx'
if ((Test-Path -LiteralPath $cerPath) -or (Test-Path -LiteralPath $pfxPath)) {
    throw "Refusing to overwrite an existing certificate backup. Remove or rename the existing files first."
}

$cert = New-SelfSignedCertificate `
    -Type CodeSigningCert `
    -Subject $Subject `
    -CertStoreLocation 'Cert:\CurrentUser\My' `
    -HashAlgorithm SHA256 `
    -KeyAlgorithm RSA `
    -KeyLength 3072 `
    -KeyExportPolicy Exportable `
    -NotAfter (Get-Date).AddYears($Years)

Export-Certificate -Cert $cert -FilePath $cerPath -Type CERT | Out-Null
$password = Read-Host 'Enter a password for the private PFX backup' -AsSecureString
Export-PfxCertificate -Cert $cert -FilePath $pfxPath -Password $password -CryptoAlgorithmOption AES256_SHA256 | Out-Null

$sha256 = [System.Security.Cryptography.SHA256]::Create()
try {
    $fingerprint = ([BitConverter]::ToString($sha256.ComputeHash([System.IO.File]::ReadAllBytes($cerPath))) -replace '-', '').ToLowerInvariant()
}
finally {
    $sha256.Dispose()
}

[pscustomobject]@{
    Subject = $cert.Subject
    Thumbprint = $cert.Thumbprint
    CertificateSha256 = $fingerprint
    NotAfter = $cert.NotAfter
    PublicCertificate = (Resolve-Path -LiteralPath $cerPath).Path
    PrivateBackup = (Resolve-Path -LiteralPath $pfxPath).Path
} | Format-List
