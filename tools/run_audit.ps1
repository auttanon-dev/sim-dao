param(
    [ValidateSet("Quick", "Full")]
    [string]$Mode = "Quick"
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $ProjectRoot
$LogDir = Join-Path $ProjectRoot "out\audit"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
$Stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$LogPath = Join-Path $LogDir ("{0}-{1}.log" -f $Mode.ToLowerInvariant(), $Stamp)

Start-Transcript -LiteralPath $LogPath | Out-Null
try {
    Write-Host "[Sim Dao] audit=$Mode log=$LogPath" -ForegroundColor Cyan
    & python -B -m compileall -q tiandao tools
    if ($LASTEXITCODE -ne 0) { throw "compileall failed ($LASTEXITCODE)" }

    if ($Mode -eq "Quick") {
        & python -B -m unittest test_body_adaptation test_body test_body_injury test_body_blood test_body_metabolism test_body_perception test_decision_body test_combat_escape test_skill_mastery -q
        if ($LASTEXITCODE -ne 0) { throw "quick unittest failed ($LASTEXITCODE)" }
        & python -B tools/test_system_integrity.py
        if ($LASTEXITCODE -ne 0) { throw "integrity audit failed ($LASTEXITCODE)" }
    }
    else {
        & python -B -m unittest discover -v
        if ($LASTEXITCODE -ne 0) { throw "full unittest failed ($LASTEXITCODE)" }
        & python -B test_determinism.py
        if ($LASTEXITCODE -ne 0) { throw "determinism failed ($LASTEXITCODE)" }
        & python -B test_all_realms.py
        if ($LASTEXITCODE -ne 0) { throw "all-realms failed ($LASTEXITCODE)" }
    }
    Write-Host "[Sim Dao] PASS - no failure in the $Mode suite" -ForegroundColor Green
}
catch {
    Write-Host "[Sim Dao] FAIL - $($_.Exception.Message)" -ForegroundColor Red
    throw
}
finally {
    Stop-Transcript | Out-Null
    Write-Host "Detailed log: $LogPath"
}
