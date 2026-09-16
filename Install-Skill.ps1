[CmdletBinding(SupportsShouldProcess)]
param([string]$SkillsRoot)
$ErrorActionPreference = 'Stop'
$skillName = 'codex-gemini-windows-skill'
if (-not $SkillsRoot) {
    $codexRoot = if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $env:USERPROFILE '.codex' }
    $SkillsRoot = Join-Path $codexRoot 'skills'
}
$destination = [IO.Path]::GetFullPath((Join-Path $SkillsRoot $skillName))
$sourceRoot = [IO.Path]::GetFullPath($PSScriptRoot).TrimEnd('\') + '\'
$files = @()
foreach ($entry in @('SKILL.md','agents','references','scripts')) {
    $source = Join-Path $PSScriptRoot $entry
    if (-not (Test-Path -LiteralPath $source)) { throw "Package incomplete: $entry" }
    if (Test-Path -LiteralPath $source -PathType Leaf) { $files += Get-Item -LiteralPath $source }
    else { $files += Get-ChildItem -LiteralPath $source -Recurse -File | Where-Object { $_.FullName -notmatch '[\\/]__pycache__[\\/]' -and $_.Extension -ne '.pyc' } }
}
foreach ($file in $files) {
    if (($file.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) { throw 'Package contains a linked file; inspect before installing.' }
}
if (Test-Path -LiteralPath $destination) {
    $different = @($files | Where-Object {
        $relative = $_.FullName.Substring($sourceRoot.Length)
        $target = Join-Path $destination $relative
        (-not (Test-Path -LiteralPath $target -PathType Leaf)) -or
        ((Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash -ne (Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash)
    })
    if ($different.Count) { throw 'A different skill version is installed. Back it up and review an update instead of overwriting.' }
    Write-Output "The same skill files are already installed: $destination"
    exit 0
}
if ($PSCmdlet.ShouldProcess($destination, 'Install skill instructions and helper scripts')) {
    foreach ($file in $files) {
        $relative = $file.FullName.Substring($sourceRoot.Length)
        $target = Join-Path $destination $relative
        New-Item -ItemType Directory -Path (Split-Path -Parent $target) -Force | Out-Null
        Copy-Item -LiteralPath $file.FullName -Destination $target
        if ((Get-FileHash -LiteralPath $file.FullName).Hash -ne (Get-FileHash -LiteralPath $target).Hash) { throw "Copy verification failed: $relative" }
    }
    Write-Output "Skill installed and file hashes verified: $destination"
    Write-Output 'Refresh/reopen Codex and invoke $codex-gemini-windows-skill.'
    Write-Output 'No model configuration, software installation or account data was changed.'
}
