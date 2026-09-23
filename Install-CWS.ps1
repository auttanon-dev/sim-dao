# ติดตั้ง Cultivation World Simulator (CWS) จากซอร์สโค้ดลงเครื่อง — เพื่อศึกษาเทียบกับ Sim Dao
# ต้นฉบับ: https://github.com/4thfever/cultivation-world-simulator  (สัญญาอนุญาต CC BY-NC-SA 4.0 — ห้ามใช้เชิงพาณิชย์)
# ติดตั้งไว้แยกที่ D:\cultivation-world-simulator ไม่ปนกับโค้ดของ Sim Dao
param([string]$Target = 'D:\cultivation-world-simulator')
$ErrorActionPreference = 'Stop'
$simDao = $PSScriptRoot
$logDir = Join-Path $simDao 'out'
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
Start-Transcript -Path (Join-Path $logDir 'cws-install.log') -Force | Out-Null

function Step($text) { Write-Host "`n==== $text ====" -ForegroundColor Cyan }
function Have($cmd) { return [bool](Get-Command $cmd -ErrorAction SilentlyContinue) }
function Refresh-Path {
    $env:Path = [Environment]::GetEnvironmentVariable('Path', 'Machine') + ';' + [Environment]::GetEnvironmentVariable('Path', 'User')
}
function Ask-Install($name, $wingetId) {
    Write-Host "ไม่พบ $name ในเครื่อง" -ForegroundColor Yellow
    if (-not (Have 'winget')) { throw "ไม่มี winget — กรุณาติดตั้ง $name เองแล้วรันสคริปต์นี้ใหม่" }
    $ans = Read-Host "ติดตั้ง $name ด้วย winget ($wingetId) เลยไหม? พิมพ์ y แล้ว Enter"
    if ($ans -notmatch '^[yY]') { throw "ยกเลิก: ต้องมี $name ก่อน" }
    winget install --id $wingetId -e --source winget --accept-package-agreements --accept-source-agreements
    Refresh-Path
}
function Check($what) { if ($LASTEXITCODE -ne 0) { throw "$what ล้มเหลว (exit $LASTEXITCODE)" } }

try {
    Step '1/6 ตรวจเครื่องมือ'
    $py = $null
    $candidates = @()
    if (Have 'py') { $candidates += ,@((Get-Command py).Source, '-3') }
    if (Have 'python') { $candidates += ,@((Get-Command python).Source) }
    foreach ($c in $candidates) {
        $extra = @($c | Select-Object -Skip 1)
        try { $ok = (& $c[0] @extra -c "import sys;print(sys.version_info>=(3,10))" 2>$null) -eq 'True' } catch { $ok = $false }
        if ($ok) { $py = $c; break }
    }
    if (-not $py) {
        Ask-Install 'Python 3.12' 'Python.Python.3.12'
        $py = @((Get-Command python).Source)
    }
    $pyExtra = @($py | Select-Object -Skip 1)
    Write-Host ("Python: " + (& $py[0] @pyExtra --version))
    if (-not (Have 'node') -or [int]((node -v).TrimStart('v').Split('.')[0]) -lt 18) { Ask-Install 'Node.js LTS' 'OpenJS.NodeJS.LTS' }
    Write-Host ("Node: " + (node -v) + " / npm " + (npm -v))
    $git = Have 'git'
    Write-Host ("git: " + $(if ($git) { (git --version) } else { 'ไม่มี (จะดาวน์โหลดเป็น zip แทน)' }))

    Step "2/6 ดาวน์โหลดซอร์สโค้ดไปที่ $Target"
    if (Test-Path (Join-Path $Target 'src\server\main.py')) {
        Write-Host 'มีอยู่แล้ว ข้ามการดาวน์โหลด'
        if ($git -and (Test-Path (Join-Path $Target '.git'))) { git -C $Target pull --ff-only }
    } elseif ($git) {
        git clone --depth 1 https://github.com/4thfever/cultivation-world-simulator.git $Target; Check 'git clone'
    } else {
        $zip = Join-Path $env:TEMP 'cws-main.zip'
        Invoke-WebRequest 'https://github.com/4thfever/cultivation-world-simulator/archive/refs/heads/main.zip' -OutFile $zip
        $tmp = Join-Path $env:TEMP 'cws-extract'
        Remove-Item $tmp -Recurse -Force -ErrorAction SilentlyContinue
        Expand-Archive $zip -DestinationPath $tmp
        Move-Item (Get-ChildItem $tmp | Select-Object -First 1).FullName $Target
    }

    Step '3/6 สร้าง Python venv และติดตั้งแพ็กเกจฝั่งเซิร์ฟเวอร์'
    $venvPy = Join-Path $Target '.venv\Scripts\python.exe'
    if (-not (Test-Path $venvPy)) { & $py[0] @pyExtra -m venv (Join-Path $Target '.venv'); Check 'สร้าง venv' }
    & $venvPy -m pip install --upgrade pip
    & $venvPy -m pip install -r (Join-Path $Target 'requirements.txt'); Check 'pip install'

    Step '4/6 ติดตั้งแพ็กเกจหน้าเว็บ (npm install — อาจใช้เวลาหลายนาที)'
    Push-Location (Join-Path $Target 'web')
    try { npm install; Check 'npm install' } finally { Pop-Location }

    Step '5/6 ตรวจ Ollama'
    try {
        $tags = Invoke-RestMethod 'http://localhost:11434/api/tags' -TimeoutSec 5
        Write-Host 'Ollama ทำงานอยู่ มีโมเดล:'
        $tags.models | ForEach-Object { Write-Host ('  - ' + $_.name) }
    } catch {
        Write-Host 'ยังติดต่อ Ollama ไม่ได้ (เปิดแอป Ollama ก่อนเริ่มเกม)' -ForegroundColor Yellow
    }

    Step '6/6 สร้างตัวเปิดเกม'
    Copy-Item (Join-Path $simDao 'Start-CWS.ps1') (Join-Path $Target 'Start-CWS.ps1') -Force -ErrorAction SilentlyContinue
    Write-Host "`nติดตั้งเสร็จแล้ว ✓" -ForegroundColor Green
    Write-Host 'เปิดเกมด้วยดับเบิลคลิก Start-CWS.cmd ในโฟลเดอร์ Sim Dao'
    Write-Host 'INSTALL_OK'
} catch {
    Write-Host "`nติดตั้งไม่สำเร็จ: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host 'INSTALL_FAILED'
} finally {
    Stop-Transcript | Out-Null
    Read-Host "`nกด Enter เพื่อปิดหน้าต่าง"
}
