#Requires -Version 5.1

$ErrorActionPreference = "Stop"

try {
    $tpm = Get-Tpm
} catch {
    Write-Error "Get-Tpm failed. Open PowerShell as Administrator and run this script again."
    exit 1
}

$tpm | Format-List TpmPresent,TpmReady,TpmEnabled,TpmActivated,TpmOwned,ManufacturerIdTxt,ManufacturerVersion,SpecVersion

Write-Host ""
if (-not $tpm.TpmPresent) {
    Write-Warning "No TPM was reported by Windows. TPM-backed keys cannot be created on this machine."
} elseif (-not $tpm.TpmReady) {
    Write-Warning "TPM exists but is not ready. Check Windows Security > Device security > Security processor."
} else {
    Write-Host "TPM is present and ready." -ForegroundColor Green
}
