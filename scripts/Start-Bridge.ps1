[CmdletBinding()]
param(
    [string]$ToolRoot,
    [string]$CodexRoot,
    [string]$AntigravityExe,
    [string]$ProxyConfigPath,
    [ValidateRange(1024,65535)][int]$GatewayPort = 51122
)
$ErrorActionPreference = 'Stop'
$trackedNames = @('LOCAL_GEMINI_PROXY_KEY','ABV_BIND_LOCAL_ONLY','ANTIGRAVITY_UNIFIED_MODEL_PICKER',
    'ANTIGRAVITY_OPENAI_USE_CODEX_AUTH','ANTIGRAVITY_ALLOW_REMOTE','CODEX_ANTIGRAVITY_NO_UPDATE_CHECK',
    'ANTIGRAVITY_OPENAI_MODELS','OPENAI_API_KEY','OPENAI_BASE_URL','NO_PROXY','HTTP_PROXY','HTTPS_PROXY')
$previousEnvironment = @{}
foreach ($name in $trackedNames) { $previousEnvironment[$name] = [Environment]::GetEnvironmentVariable($name,'Process') }
try {
$actualCodexRoot = if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $env:USERPROFILE '.codex' }
if (-not $CodexRoot) { $CodexRoot = $actualCodexRoot }
if ([IO.Path]::GetFullPath($CodexRoot) -ne [IO.Path]::GetFullPath($actualCodexRoot)) {
    throw 'CodexRoot must match the actual CODEX_HOME (or the default user .codex directory).'
}
if (-not $ToolRoot) { $ToolRoot = Join-Path $CodexRoot 'tools\codex-antigravity-unified' }
if (-not $AntigravityExe) { $AntigravityExe = Join-Path $env:LOCALAPPDATA 'Antigravity Tools\antigravity-tools.exe' }
if (-not $ProxyConfigPath) { $ProxyConfigPath = Join-Path $env:USERPROFILE '.antigravity_tools\gui_config.json' }
$python = Join-Path $ToolRoot 'Scripts\python.exe'
$catalogPath = Join-Path $ToolRoot 'native-models.json'
foreach ($required in @($python,$AntigravityExe,$ProxyConfigPath,$catalogPath)) {
    if (-not (Test-Path -LiteralPath $required -PathType Leaf)) { throw "Missing prerequisite: $required" }
}
$apiConfigs = @((Join-Path $CodexRoot 'antigravity-openai.json'), (Join-Path $env:USERPROFILE '.codex\antigravity-openai.json')) | Select-Object -Unique
foreach ($apiConfig in $apiConfigs) {
    if (Test-Path -LiteralPath $apiConfig) {
        throw 'An explicit OpenAI API configuration exists in a checked location. Review its billing route before starting.'
    }
}
try { $settings = Get-Content -LiteralPath $ProxyConfigPath -Raw -Encoding UTF8 | ConvertFrom-Json }
catch { throw 'Cannot parse Antigravity configuration as UTF-8 JSON. Its contents were not printed.' }
if ($settings.proxy.enabled -ne $true) { throw 'Antigravity proxy is disabled. Enable it before startup.' }
if ($settings.proxy.allow_lan_access -eq $true) { throw 'Disable LAN access before using this local-only setup.' }
$proxyPort = [int]$settings.proxy.port
if ($proxyPort -lt 1024 -or $proxyPort -gt 65535 -or $proxyPort -eq $GatewayPort) { throw 'Invalid or conflicting local ports.' }
if (-not $settings.proxy.api_key) { throw 'Antigravity local proxy key is missing.' }
try { $catalog = Get-Content -LiteralPath $catalogPath -Raw -Encoding UTF8 | ConvertFrom-Json }
catch { throw 'Cannot parse native model cache as UTF-8 JSON. Validate the file before retrying.' }
$slugs = @($catalog.models | ForEach-Object { $_.slug } | Where-Object { $_ })
if ($slugs.Count -eq 0) { throw 'The native model catalog is empty.' }
# Secrets live only in this process and its children, never in command arguments.
$env:LOCAL_GEMINI_PROXY_KEY = $settings.proxy.api_key
$env:ABV_BIND_LOCAL_ONLY = 'true'
$env:ANTIGRAVITY_UNIFIED_MODEL_PICKER = '1'
$env:ANTIGRAVITY_OPENAI_USE_CODEX_AUTH = '1'
$env:ANTIGRAVITY_ALLOW_REMOTE = '0'
$env:CODEX_ANTIGRAVITY_NO_UPDATE_CHECK = '1'
$env:ANTIGRAVITY_OPENAI_MODELS = $slugs -join ','
Remove-Item Env:OPENAI_API_KEY -ErrorAction SilentlyContinue
Remove-Item Env:OPENAI_BASE_URL -ErrorAction SilentlyContinue
$proxyEntries = @($env:NO_PROXY, [Environment]::GetEnvironmentVariable('NO_PROXY','User'),
    [Environment]::GetEnvironmentVariable('NO_PROXY','Machine'), 'localhost,127.0.0.1,::1')
$env:NO_PROXY = (($proxyEntries -join ',') -split ',' | ForEach-Object { $_.Trim() } |
    Where-Object { $_ } | Select-Object -Unique) -join ','
$systemProxy = Get-ItemProperty -LiteralPath 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Internet Settings'
if ($systemProxy.ProxyEnable -eq 1 -and $systemProxy.ProxyServer -match '^[^=;]+:\d+$') {
    if (-not $env:HTTPS_PROXY) { $env:HTTPS_PROXY = 'http://' + $systemProxy.ProxyServer }
    if (-not $env:HTTP_PROXY) { $env:HTTP_PROXY = 'http://' + $systemProxy.ProxyServer }
}
function Wait-LocalHealth([int]$Port) {
    $deadline = (Get-Date).AddSeconds(25)
    do {
        try {
            $request = [Net.WebRequest]::Create("http://127.0.0.1:$Port/health")
            $request.Proxy = $null
            $request.Timeout = 1500
            $request.AllowAutoRedirect = $false
            $response = $request.GetResponse()
            try { if ([int]$response.StatusCode -eq 200) { return } }
            finally { $response.Close() }
        } catch { }
        Start-Sleep -Milliseconds 500
    } while ((Get-Date) -lt $deadline)
    throw "Service on port $Port did not pass health check. Inspect local logs."
}
# A permission error must stop here instead of being mistaken for an empty port.
$listeners = @(Get-NetTCPConnection -State Listen -ErrorAction Stop)
$proxyListeners = @($listeners | Where-Object { $_.LocalPort -eq $proxyPort })
$gatewayListeners = @($listeners | Where-Object { $_.LocalPort -eq $GatewayPort })
foreach ($listener in (@($proxyListeners) + @($gatewayListeners))) {
    if ($listener.LocalAddress -notin @('127.0.0.1','::1')) { throw 'A required port has a non-loopback listener; inspect it manually.' }
}
if ($proxyListeners.Count) {
    foreach ($owner in ($proxyListeners.OwningProcess | Select-Object -Unique)) {
        $process = Get-CimInstance Win32_Process -Filter "ProcessId=$owner"
        if ($process.ExecutablePath -ne [IO.Path]::GetFullPath($AntigravityExe)) {
            throw "Proxy port is owned by a different program (PID $owner). No process was stopped."
        }
    }
}
if ($gatewayListeners.Count) {
    throw 'Gateway port is already in use. Existing service was not changed. Verify its owner, CODEX_HOME and route settings separately; do not stop an unknown process.'
}
$logs = Join-Path $ToolRoot 'logs'
New-Item -ItemType Directory -Path $logs -Force | Out-Null
if (-not $proxyListeners.Count) {
    Start-Process -FilePath $AntigravityExe -ArgumentList '--headless' -WindowStyle Hidden | Out-Null
}
Wait-LocalHealth $proxyPort
if (-not $gatewayListeners.Count) {
    $startArgs = @{
        FilePath = $python
        ArgumentList = @('-m','uvicorn','codex_antigravity_auth.server:app','--host','127.0.0.1','--port',"$GatewayPort",'--log-level','warning')
        WindowStyle = 'Hidden'
        RedirectStandardOutput = (Join-Path $logs 'gateway.stdout.log')
        RedirectStandardError = (Join-Path $logs 'gateway.stderr.log')
    }
    Start-Process @startArgs | Out-Null
}
Wait-LocalHealth $GatewayPort
Write-Output "Both local health checks passed: $proxyPort and $GatewayPort."
Write-Output 'Model generation, desktop use and persistence after launcher exit require separate verification.'
} finally {
    foreach ($name in $trackedNames) { [Environment]::SetEnvironmentVariable($name,$previousEnvironment[$name],'Process') }
}
