# เทียบคุณภาพการแต่งเรื่องของโมเดลในเครื่อง โดยใช้ฉากจริงจากบันทึกที่รันไว้แล้ว
# ไม่ต้องรันโลกใหม่ - ผลอยู่ที่ out\story-model-compare\compare.md
param([int]$Scenes = 6, [string]$Models = '', [string]$Source = 'out\minds-compare-5')
$ErrorActionPreference = 'Continue'
trap { Write-Host "ผิดพลาด: $_" -ForegroundColor Red }
try {
    $root = $PSScriptRoot
    $out = Join-Path $root 'out\story-model-compare'
    New-Item -ItemType Directory -Force -Path $out | Out-Null
    $py = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
    if (-not (Test-Path $py)) { $py = (Get-Command python -ErrorAction SilentlyContinue).Source }
    if (-not $py) { Write-Host 'หา python ไม่เจอ' -ForegroundColor Red }
    $env:PYTHONPATH = "$root\out\jianghu-runtime;$root"
    $env:PYTHONIOENCODING = 'utf-8'
    $env:PYTHONUTF8 = '1'
    $env:PYTHONUNBUFFERED = '1'
    Set-Location $root
    [Console]::OutputEncoding = [Text.Encoding]::UTF8
    Write-Host "Python: $py"

    $ollama = Get-Process ollama -ErrorAction SilentlyContinue
    if (-not $ollama) {
        Write-Host '== เปิด Ollama ==' -ForegroundColor Cyan
        $exe = Join-Path $env:LOCALAPPDATA 'Programs\Ollama\ollama.exe'
        if (-not (Test-Path $exe)) { $exe = (Get-Command ollama -ErrorAction SilentlyContinue).Source }
        if ($exe) {
            Start-Process -FilePath $exe -ArgumentList 'serve' -WindowStyle Hidden `
                -RedirectStandardOutput (Join-Path $root 'out\ollama.stdout.log') `
                -RedirectStandardError  (Join-Path $root 'out\ollama.stderr.log')
            Start-Sleep -Seconds 5
        } else {
            Write-Host 'หา ollama.exe ไม่เจอ - เปิด Ollama เองก่อนแล้วรันอีกครั้ง' -ForegroundColor Red
        }
    }

    $cliArgs = @('compare_story_models.py', '--scenes', $Scenes, '--source', $Source, '--out', $out)
    if ($Models) { $cliArgs += @('--models', $Models) }
    Write-Host "`n== เทียบโมเดลแต่งเรื่อง ($Scenes ฉาก) ==" -ForegroundColor Cyan
    & $py @cliArgs 2>&1 | ForEach-Object { "$_" } | Tee-Object -FilePath (Join-Path $out 'console.log')
    Write-Host "`nเสร็จแล้ว - บอก Claude ว่า 'เทียบโมเดลเสร็จแล้ว'" -ForegroundColor Green
} catch {
    Write-Host "ผิดพลาด: $_" -ForegroundColor Red
}
Read-Host 'กด Enter เพื่อปิด'
