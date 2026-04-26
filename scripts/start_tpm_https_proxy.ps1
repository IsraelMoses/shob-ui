#Requires -Version 5.1
#Requires -RunAsAdministrator

param(
    [Parameter(Mandatory=$true)]
    [string]$Thumbprint,
    [int]$ListenPort = 8443,
    [string]$InternalBaseUrl = "http://127.0.0.1:8081",
    [string]$AppId = "{1a728abe-60d1-4a12-b7f5-0f6bfe6300b1}"
)

$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Net.Http

$Thumbprint = ($Thumbprint -replace "\s", "").ToUpperInvariant()
$cert = Get-Item "Cert:\LocalMachine\My\$Thumbprint" -ErrorAction Stop
if (-not $cert.HasPrivateKey) {
    throw "Certificate $Thumbprint does not have a private key."
}

$ipPort = "0.0.0.0:$ListenPort"
$prefix = "https://+:$ListenPort/"
$account = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name

$binding = netsh http show sslcert ipport=$ipPort 2>$null | Out-String
if ($binding -notmatch [regex]::Escape($Thumbprint)) {
    if ($binding -match "Certificate Hash") {
        throw "An HTTP.sys SSL binding already exists on $ipPort for another certificate. Remove it manually before continuing."
    }
    netsh http add sslcert ipport=$ipPort certhash=$Thumbprint appid=$AppId certstorename=MY | Out-Null
}

$urlAcl = netsh http show urlacl url=$prefix 2>$null | Out-String
if ($urlAcl -notmatch [regex]::Escape($prefix)) {
    netsh http add urlacl url=$prefix user="$account" | Out-Null
}

$client = [System.Net.Http.HttpClient]::new()
$listener = [System.Net.HttpListener]::new()
$listener.Prefixes.Add($prefix)
$listener.Start()

Write-Host "TPM HTTPS proxy listening on $prefix" -ForegroundColor Green
Write-Host "Forwarding to $InternalBaseUrl"
Write-Host "Certificate thumbprint: $Thumbprint"
Write-Host "Press Ctrl+C to stop."

try {
    while ($listener.IsListening) {
        $context = $listener.GetContext()
        $request = $context.Request
        $response = $context.Response

        try {
            $target = [Uri]("$InternalBaseUrl$($request.RawUrl)")
            $method = [System.Net.Http.HttpMethod]::new($request.HttpMethod)
            $forward = [System.Net.Http.HttpRequestMessage]::new($method, $target)

            $forward.Headers.TryAddWithoutValidation("X-Forwarded-For", $request.RemoteEndPoint.Address.ToString()) | Out-Null
            $forward.Headers.TryAddWithoutValidation("X-Forwarded-Proto", "https") | Out-Null

            if ($request.HasEntityBody) {
                $body = [System.IO.MemoryStream]::new()
                $request.InputStream.CopyTo($body)
                $body.Position = 0
                $forward.Content = [System.Net.Http.StreamContent]::new($body)
            }

            foreach ($name in $request.Headers.AllKeys) {
                if ($name -in @("Host", "Connection", "Content-Length", "Transfer-Encoding", "Expect")) {
                    continue
                }
                $values = $request.Headers.GetValues($name)
                if ($forward.Content -and -not $forward.Content.Headers.TryAddWithoutValidation($name, $values)) {
                    $forward.Headers.TryAddWithoutValidation($name, $values) | Out-Null
                } elseif (-not $forward.Content) {
                    $forward.Headers.TryAddWithoutValidation($name, $values) | Out-Null
                }
            }

            if ($request.ContentType -and $forward.Content) {
                $forward.Content.Headers.TryAddWithoutValidation("Content-Type", $request.ContentType) | Out-Null
            }

            $upstream = $client.SendAsync($forward).GetAwaiter().GetResult()
            $response.StatusCode = [int]$upstream.StatusCode

            foreach ($header in $upstream.Headers) {
                if ($header.Key -notin @("Transfer-Encoding", "Connection")) {
                    $response.Headers[$header.Key] = ($header.Value -join ",")
                }
            }
            foreach ($header in $upstream.Content.Headers) {
                if ($header.Key -notin @("Transfer-Encoding", "Content-Length")) {
                    $response.Headers[$header.Key] = ($header.Value -join ",")
                }
            }

            $upstream.Content.CopyToAsync($response.OutputStream).GetAwaiter().GetResult()
            $upstream.Dispose()
        } catch {
            $message = [System.Text.Encoding]::UTF8.GetBytes("Proxy error: $($_.Exception.Message)")
            $response.StatusCode = 502
            $response.ContentType = "text/plain; charset=utf-8"
            $response.OutputStream.Write($message, 0, $message.Length)
        } finally {
            $response.Close()
        }
    }
} finally {
    $listener.Stop()
    $listener.Close()
    $client.Dispose()
}
