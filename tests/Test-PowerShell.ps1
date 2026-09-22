param([string]$PackageRoot = (Split-Path -Parent $PSScriptRoot))
$ErrorActionPreference = 'Stop'
$fixture = Join-Path ([IO.Path]::GetTempPath()) ('codex-skill-test-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $fixture | Out-Null
$installer = Join-Path $PackageRoot 'Install-Skill.ps1'
$skills = Join-Path $fixture 'skills'
& $installer -SkillsRoot $skills -WhatIf
if (Test-Path -LiteralPath $skills) { throw 'WhatIf changed the filesystem.' }
& $installer -SkillsRoot $skills
& $installer -SkillsRoot $skills
$installed = Join-Path $skills 'codex-gemini-windows-skill\SKILL.md'
Add-Content -LiteralPath $installed -Value 'Fixture local customization' -Encoding UTF8
$rejected = $false
try { & $installer -SkillsRoot $skills } catch { $rejected = $true }
if (-not $rejected) { throw 'Installer overwrote a different existing version.' }
Write-Output 'INSTALLER_FIXTURE_PASS: install, idempotence, WhatIf, conflict protection.'

$codexRoot = Join-Path $fixture 'codex'
$toolRoot = Join-Path $codexRoot 'tools\codex-antigravity-unified'
New-Item -ItemType Directory -Path (Join-Path $toolRoot 'Scripts') -Force | Out-Null
$fakePython = Join-Path $toolRoot 'Scripts\python.exe'
$fakeProxy = Join-Path $fixture 'antigravity.exe'
New-Item -ItemType File -Path $fakePython,$fakeProxy | Out-Null
$proxyConfig = Join-Path $fixture 'proxy-fixture.json'
$catalog = Join-Path $toolRoot 'native-models.json'
'{"models":[{"slug":"gpt-fixture"}]}' | Set-Content -LiteralPath $catalog -Encoding UTF8
$priorCodexRoot = $env:CODEX_HOME
$originalNoProxy = $env:NO_PROXY
$originalApiKey = $env:OPENAI_API_KEY
$originalHttpProxy = $env:HTTP_PROXY
$originalHttpsProxy = $env:HTTPS_PROXY
try {
    # Isolate the fixture using the application's supported home setting.
    $env:CODEX_HOME = $codexRoot
    $env:NO_PROXY = 'corp.fixture'
    $env:OPENAI_API_KEY = 'FIXTURE_KEY_ONLY'
    $params = @{ToolRoot=$toolRoot;CodexRoot=$codexRoot;AntigravityExe=$fakeProxy;ProxyConfigPath=$proxyConfig}
    $start = Join-Path $PackageRoot 'scripts\Start-Bridge.ps1'
    '{"proxy":{"enabled":false,"port":8045,"allow_lan_access":false,"api_key":"FIXTURE_LOCAL_ONLY"}}' | Set-Content -LiteralPath $proxyConfig -Encoding UTF8
    $rejected = $false
    try { & $start @params } catch {
        if ($_.Exception.Message -like '*FIXTURE_LOCAL_ONLY*') { throw 'Secret leaked in startup error.' }
        $rejected = $_.Exception.Message -like '*disabled*'
    }
    if (-not $rejected) { throw 'Disabled proxy was not rejected.' }
    if ($env:NO_PROXY -ne 'corp.fixture' -or $env:OPENAI_API_KEY -ne 'FIXTURE_KEY_ONLY') { throw 'Caller environment was changed.' }
    '{"proxy":{"enabled":true,"port":8045,"allow_lan_access":true,"api_key":"FIXTURE_LOCAL_ONLY"}}' | Set-Content -LiteralPath $proxyConfig -Encoding UTF8
    $rejected = $false
    try { & $start @params } catch { $rejected = $_.Exception.Message -like '*LAN access*' }
    if (-not $rejected) { throw 'LAN exposure was not rejected.' }
    '{}' | Set-Content -LiteralPath (Join-Path $codexRoot 'antigravity-openai.json') -Encoding UTF8
    $rejected = $false
    try { & $start @params } catch { $rejected = $_.Exception.Message -like '*billing route*' }
    if (-not $rejected) { throw 'Possible paid API route was not rejected.' }
    Move-Item -LiteralPath (Join-Path $codexRoot 'antigravity-openai.json') -Destination (Join-Path $fixture 'held-api-fixture.json')
    '{"proxy":{"enabled":true,"port":8045,"allow_lan_access":false,"api_key":"FIXTURE_LOCAL_ONLY"}}' | Set-Content -LiteralPath $proxyConfig -Encoding UTF8
    $callerLocalKey = $env:LOCAL_GEMINI_PROXY_KEY
    $env:HTTP_PROXY = 'http://127.0.0.1:21761'
    $env:HTTPS_PROXY = 'http://127.0.0.1:21761'
    function Get-ItemProperty {
        param([string]$LiteralPath)
        if ($LiteralPath -ne 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Internet Settings') { throw 'Unexpected registry request.' }
        [pscustomobject]@{ProxyEnable=1;ProxyServer='127.0.0.1:23054'}
    }
    # Fail after temporary environment changes, before any real process can start.
    function Get-NetTCPConnection {
        if ($env:HTTP_PROXY -ne 'http://127.0.0.1:23054' -or $env:HTTPS_PROXY -ne 'http://127.0.0.1:23054') {
            throw 'Stale inherited proxy was not refreshed before service startup.'
        }
        throw 'FIXTURE_PERMISSION_DENIED'
    }
    try {
        $rejected = $false
        try { & $start @params } catch { $rejected = $_.Exception.Message -like '*FIXTURE_PERMISSION_DENIED*' }
        if (-not $rejected) { throw 'Late startup failure did not reach the isolated guard.' }
        if ($env:NO_PROXY -ne 'corp.fixture' -or $env:OPENAI_API_KEY -ne 'FIXTURE_KEY_ONLY' -or $env:LOCAL_GEMINI_PROXY_KEY -ne $callerLocalKey -or
            $env:HTTP_PROXY -ne 'http://127.0.0.1:21761' -or $env:HTTPS_PROXY -ne 'http://127.0.0.1:21761') {
            throw 'Caller environment was not restored after a late startup failure.'
        }
    } finally { Remove-Item Function:Get-NetTCPConnection; Remove-Item Function:Get-ItemProperty }
} finally {
    [Environment]::SetEnvironmentVariable('CODEX_HOME',$priorCodexRoot,'Process')
    [Environment]::SetEnvironmentVariable('NO_PROXY',$originalNoProxy,'Process')
    [Environment]::SetEnvironmentVariable('OPENAI_API_KEY',$originalApiKey,'Process')
    [Environment]::SetEnvironmentVariable('HTTP_PROXY',$originalHttpProxy,'Process')
    [Environment]::SetEnvironmentVariable('HTTPS_PROXY',$originalHttpsProxy,'Process')
}
Write-Output 'STARTUP_GUARDS_PASS: disabled, LAN, paid-route, no secret output, environment restored after early and late failure.'
Write-Output 'PROXY_PORT_CHANGE_PASS: new system proxy overrides stale inherited values; caller values restored.'
# Keep isolated fixtures available for review; never recursively delete arbitrary paths.
Write-Output ('FIXTURE_DIRECTORY=' + $fixture)
