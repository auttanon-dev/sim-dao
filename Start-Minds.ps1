param(
    [int]$Port = 8002,
    [switch]$Paused,
    [ValidateSet('ollama', 'lmstudio', 'mock')][string]$Provider,
    [string]$Model, [string]$StoryModel, [string]$BaseUrl,
    [int]$Count = 40, [int]$Seed = 1,
    [string]$FromSave = '',
    [switch]$NoStory
)
# เปิด "บันทึกวิถีสวรรค์" — ตัวละครคิดเอง ตัดสินใจเอง อ่านได้ที่ http://127.0.0.1:8002
$ErrorActionPreference = 'Stop'
$projectPath = $PSScriptRoot
$bundledPython = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
if (-not (Test-Path $bundledPython)) { $bundledPython = 'python' }
$overrides = @{
    'PYTHONPATH' = "$projectPath\out\jianghu-runtime;$projectPath;$env:PYTHONPATH"
    'PYTHONIOENCODING' = 'utf-8'
    'TIANDAO_MIND_AUTOSTART' = $(if ($Paused) { '0' } else { '1' })
    'TIANDAO_MIND_COUNT' = "$Count"
    'TIANDAO_MIND_SEED' = "$Seed"
    'TIANDAO_MIND_STORY' = $(if ($NoStory) { '0' } else { '1' })
}
if ($Provider) { $overrides['TIANDAO_MIND_PROVIDER'] = $Provider }
if ($Model) { $overrides['TIANDAO_MIND_MODEL'] = $Model }
if ($StoryModel) { $overrides['TIANDAO_MIND_STORY_MODEL'] = $StoryModel }
if ($BaseUrl) { $overrides['TIANDAO_MIND_BASE_URL'] = $BaseUrl }
if ($FromSave) { $overrides['TIANDAO_MIND_SOURCE'] = [IO.Path]::GetFullPath($FromSave) }
$previous = @{}
try {
    foreach ($key in $overrides.Keys) {
        $previous[$key] = [Environment]::GetEnvironmentVariable($key, 'Process')
        [Environment]::SetEnvironmentVariable($key, $overrides[$key], 'Process')
    }
    & $bundledPython -m uvicorn mind_app:app --app-dir $projectPath --host 127.0.0.1 --port $Port
} finally {
    foreach ($key in $previous.Keys) {
        [Environment]::SetEnvironmentVariable($key, $previous[$key], 'Process')
    }
}
