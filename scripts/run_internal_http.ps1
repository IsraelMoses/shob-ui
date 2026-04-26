#Requires -Version 5.1

param(
    [int]$Port = 8081
)

$ErrorActionPreference = "Stop"

$env:SHOB_SERVER_HOST = "127.0.0.1"
$env:SHOB_SERVER_PORT = "$Port"
$env:SHOB_TLS_ENABLED = "0"
$env:SHOB_DEBUG_SERVER = "0"

python main.py
