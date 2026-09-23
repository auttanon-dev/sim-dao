param(
    [int]$Port = 8001, [string]$SavePath = '', [switch]$Paused,
    [ValidateSet('ollama', 'lmstudio')][string]$Provider,
    [string]$Model, [string]$StructureModel, [string]$BaseUrl
)
$ErrorActionPreference = 'Stop'
$projectPath = $PSScriptRoot
$bundledPython = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
$previousPath = $env:PYTHONPATH
$previousSave = $env:TIANDAO_SAVE_PATH
$previousSerial = $env:TIANDAO_SERIAL
$previousEncoding = $env:PYTHONIOENCODING
$writerOverrides = @{}
if ($Provider) { $writerOverrides['TIANDAO_WRITER_PROVIDER'] = $Provider }
if ($Model) { $writerOverrides['TIANDAO_WRITER_MODEL'] = $Model }
if ($StructureModel) { $writerOverrides['TIANDAO_WRITER_STRUCTURE_MODEL'] = $StructureModel }
if ($BaseUrl) { $writerOverrides['TIANDAO_WRITER_BASE_URL'] = $BaseUrl }
$previousWriter = @{}
try {
    foreach ($key in $writerOverrides.Keys) {
        $previousWriter[$key] = [Environment]::GetEnvironmentVariable($key, 'Process')
        [Environment]::SetEnvironmentVariable($key, $writerOverrides[$key], 'Process')
    }
    $env:PYTHONPATH = "$projectPath\out\jianghu-runtime;$projectPath;$previousPath"
    $env:PYTHONIOENCODING = 'utf-8'
    $env:TIANDAO_SAVE_PATH = if ($SavePath) { [IO.Path]::GetFullPath($SavePath) } else { Join-Path $projectPath 'tiandao\world.save' }
    $env:TIANDAO_SERIAL = if ($Paused) { '0' } else { '1' }
    & $bundledPython -m uvicorn novel_app:app --app-dir $projectPath --host 127.0.0.1 --port $Port
} finally {
    foreach ($key in $previousWriter.Keys) {
        [Environment]::SetEnvironmentVariable($key, $previousWriter[$key], 'Process')
    }
    $env:PYTHONPATH = $previousPath
    $env:TIANDAO_SAVE_PATH = $previousSave
    $env:TIANDAO_SERIAL = $previousSerial
    $env:PYTHONIOENCODING = $previousEncoding
}
