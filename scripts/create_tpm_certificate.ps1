#Requires -Version 5.1
#Requires -RunAsAdministrator

param(
    [string]$CommonName = "my.teltonika.com",
    [string[]]$DnsName = @("my.teltonika.com"),
    [string[]]$IpAddress = @("192.168.1.195"),
    [int]$Years = 2,
    [string]$StoreLocation = "Cert:\LocalMachine\My"
)

$ErrorActionPreference = "Stop"

$tpm = Get-Tpm
if (-not $tpm.TpmPresent -or -not $tpm.TpmReady) {
    throw "TPM is not present or not ready. Run scripts\check_tpm.ps1 as Administrator for details."
}

$sanParts = @()
foreach ($name in $DnsName) {
    if (-not [string]::IsNullOrWhiteSpace($name)) {
        $sanParts += "DNS=$name"
    }
}
foreach ($ip in $IpAddress) {
    if (-not [string]::IsNullOrWhiteSpace($ip)) {
        $sanParts += "IPAddress=$ip"
    }
}
if ($sanParts.Count -eq 0) {
    $sanParts += "DNS=$CommonName"
}

$params = @{
    Type = "Custom"
    Subject = "CN=$CommonName"
    TextExtension = @( "2.5.29.37={text}1.3.6.1.5.5.7.3.1", "2.5.29.17={text}$($sanParts -join '&')" )
    CertStoreLocation = $StoreLocation
    Provider = "Microsoft Platform Crypto Provider"
    KeyAlgorithm = "RSA"
    KeyLength = 2048
    KeyExportPolicy = "NonExportable"
    KeyUsage = "DigitalSignature", "KeyEncipherment"
    NotAfter = (Get-Date).AddYears($Years)
}

$cert = New-SelfSignedCertificate @params

Write-Host "Created TPM-backed certificate." -ForegroundColor Green
Write-Host "Subject:     $($cert.Subject)"
Write-Host "Thumbprint:  $($cert.Thumbprint)"
Write-Host "Store:       $StoreLocation"
Write-Host "Provider:    Microsoft Platform Crypto Provider"
Write-Host "Exportable:  No"
Write-Host ""
Write-Host "Public certificate export example:"
Write-Host "Export-Certificate -Cert Cert:\LocalMachine\My\$($cert.Thumbprint) -FilePath C:\ProgramData\ShobUI\certs\shob-ui.cer"

