# TPM-backed TLS notes

This app currently serves HTTPS through Python/Werkzeug. Python's ssl module loads a certificate and private key from PEM files, so it cannot directly use a non-exportable TPM private key from the Windows certificate store.

The practical hardening path has two stages:

1. Keep PEM keys out of the repository and preferably outside the project folder.
2. For real TPM-backed TLS, terminate HTTPS in a Windows component that can use the Windows certificate store and Microsoft Platform Crypto Provider, then forward plain HTTP to the local Python app.

## Current repo hardening

The app supports these environment variables:

- `SHOB_TLS_CERT_FILE`: path to a PEM certificate file.
- `SHOB_TLS_KEY_FILE`: path to a PEM private key file.
- `SHOB_SERVER_HOST`: bind host, default `0.0.0.0`.
- `SHOB_SERVER_PORT`: bind port, default `8443`.
- `SHOB_DEBUG_SERVER`: set to `1` only when raw debug logging is needed.
- `SHOB_DEBUG_PORT`: debug server port, default `8080`.

By default, the app still looks for `cert.pem` and `key.pem` next to `main.py` for development compatibility. Those files are ignored by Git.

## Check TPM status

Open PowerShell as Administrator:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\check_tpm.ps1
```

## Create a TPM-backed certificate

Open PowerShell as Administrator:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\create_tpm_certificate.ps1 `
  -CommonName "my.teltonika.com" `
  -DnsName "my.teltonika.com" `
  -IpAddress "192.168.1.195" `
  -Years 2
```

This creates a non-exportable private key using `Microsoft Platform Crypto Provider` in `Cert:\LocalMachine\My`.

## Windows TLS termination option

A TPM-backed certificate can be bound to Windows HTTP.sys with `netsh http add sslcert`. The Python app should then listen on localhost HTTP behind that Windows-facing HTTPS endpoint or behind IIS / a Windows-native proxy.

Example binding shape:

```powershell
netsh http add sslcert ipport=192.168.1.195:8443 certhash=<THUMBPRINT> appid="{PUT-GUID-HERE}" certstorename=MY
```

This does not make Werkzeug use the TPM directly and is not enough on its own. The missing piece is a Windows-facing listener/proxy that uses HTTP.sys/IIS and forwards uploads to the local Python app.

## Development PEM option

If you keep using PEM files during development, move them outside the repo, for example:

```powershell
mkdir C:\ProgramData\ShobUI\certs
copy .\cert.pem C:\ProgramData\ShobUI\certs\cert.pem
copy .\key.pem C:\ProgramData\ShobUI\certs\key.pem
.\scripts\run_with_external_pem.ps1
```

The private key remains a file in this mode, so this is cleaner than storing it in the project folder but not equivalent to TPM protection.
