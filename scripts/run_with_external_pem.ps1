#Requires -Version 5.1

param(
    [string]$CertFile = "$env:ProgramData\ShobUI\certs\cert.pem",
    [string]$KeyFile = "$env:ProgramData\ShobUI\certs\key.pem",
    [switch]$DebugServer
)

$ErrorActionPreference = "Stop"

$env:SHOB_TLS_CERT_FILE = $CertFile
$env:SHOB_TLS_KEY_FILE = $KeyFile
$env:SHOB_DEBUG_SERVER = if ($DebugServer) { "1" } else { "0" }

python main.py
