[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$ManifestPath,
    [Parameter(Mandatory = $true)][string]$SignaturePath,
    [Parameter(Mandatory = $true)][string]$CertificateThumbprint
)

$ErrorActionPreference = 'Stop'
$normalized = ($CertificateThumbprint -replace '\s', '').ToUpperInvariant()
$certificate = Get-ChildItem "Cert:\CurrentUser\My\$normalized" -ErrorAction SilentlyContinue
if (-not $certificate -or -not $certificate.HasPrivateKey) {
    throw "Code-signing certificate with private key was not found in Cert:\CurrentUser\My."
}
$rsa = [System.Security.Cryptography.X509Certificates.RSACertificateExtensions]::GetRSAPrivateKey($certificate)
if (-not $rsa) { throw 'The code-signing certificate does not expose an RSA private key.' }

$bytes = [System.IO.File]::ReadAllBytes((Resolve-Path -LiteralPath $ManifestPath))
$signature = $rsa.SignData(
    $bytes,
    [System.Security.Cryptography.HashAlgorithmName]::SHA256,
    [System.Security.Cryptography.RSASignaturePadding]::Pkcs1
)
$rsa.Dispose()
[System.IO.File]::WriteAllText(
    (Resolve-Path -LiteralPath (Split-Path -Parent $SignaturePath)).Path + '\' + (Split-Path -Leaf $SignaturePath),
    [Convert]::ToBase64String($signature),
    (New-Object System.Text.UTF8Encoding($false))
)
