param([int]$Port = 8000, [string]$SavePath = '', [switch]$ReadOnly)
$ErrorActionPreference = 'Stop'
$projectPath = $PSScriptRoot
$bundledPython = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
$pythonCommand = Get-Command python.exe -ErrorAction SilentlyContinue
$pythonPath = if (Test-Path -LiteralPath $bundledPython) { $bundledPython } elseif ($pythonCommand) { $pythonCommand.Source } else { throw 'Python not found. Install Python and the dashboard dependencies first.' }
$previousPythonPath = $env:PYTHONPATH
$previousSavePath = $env:TIANDAO_SAVE_PATH
$previousLive = $env:TIANDAO_LIVE
$previousEncoding = $env:PYTHONIOENCODING
try {
    $env:PYTHONPATH = "$projectPath\out\jianghu-runtime;$projectPath;$previousPythonPath"
    if ($SavePath) { $env:TIANDAO_SAVE_PATH = [IO.Path]::GetFullPath($SavePath) }
    elseif (-not $env:TIANDAO_SAVE_PATH) { $env:TIANDAO_SAVE_PATH = Join-Path $projectPath 'tiandao\world.save' }
    $env:TIANDAO_LIVE = if ($ReadOnly) { '0' } else { '1' }
    $env:PYTHONIOENCODING = 'utf-8'
    & $pythonPath -m uvicorn dashboard:app --app-dir $projectPath --host 127.0.0.1 --port $Port
} finally {
    $env:PYTHONPATH = $previousPythonPath
    $env:TIANDAO_SAVE_PATH = $previousSavePath
    $env:TIANDAO_LIVE = $previousLive
    $env:PYTHONIOENCODING = $previousEncoding
}
