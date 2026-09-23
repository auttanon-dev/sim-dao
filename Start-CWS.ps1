# เปิด Cultivation World Simulator (โหมดพัฒนา) — หน้าเว็บจะเปิดเองที่ http://localhost:5173
param([string]$Target = 'D:\cultivation-world-simulator')
$ErrorActionPreference = 'Stop'
$simDao = $PSScriptRoot
if (-not (Test-Path (Join-Path $Target 'src\server\main.py'))) { $Target = $PSScriptRoot }
$logDir = if (Test-Path (Join-Path $simDao 'tiandao')) { Join-Path $simDao 'out' } else { Join-Path $Target 'logs' }
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
# เก็บเซฟ/ตั้งค่า/log ของ CWS ไว้ใน Sim Dao\out\cws-data เพื่อให้เปิดดูและเทียบกับบันทึกของเราได้
$env:CWS_DATA_DIR = Join-Path $logDir 'cws-data'
$env:PYTHONIOENCODING = 'utf-8'
$env:PYTHONUTF8 = '1'
$env:PYTHONUNBUFFERED = '1'
Set-Location $Target

# ---- เตรียมโมเดลสำหรับ CWS ----
# CWS ส่งพรอมต์ยาวผ่าน API แบบ OpenAI ซึ่งตั้ง context ของ Ollama ไม่ได้ (ค่าเริ่มต้นแค่ราว 4096 token
# พรอมต์จะถูกตัดเงียบๆ แล้วตัวละครตอบมั่ว) จึงสร้างโมเดลชื่อใหม่ที่ฝัง num_ctx 16384 ไว้ในตัว
# ใช้ llama3.1-typhoon2-8b เพราะไม่ใช่โมเดลสาย think — ตัวอ่าน JSON ของ CWS ไม่ตัดแท็ก <think> ออก
$cwsModel = 'cws-typhoon2-8b'
$baseModel = 'scb10x/llama3.1-typhoon2-8b-instruct:latest'
try {
    $names = (Invoke-RestMethod 'http://localhost:11434/api/tags' -TimeoutSec 5).models.name
    if ($names -notcontains "${cwsModel}:latest") {
        Write-Host "สร้างโมเดล $cwsModel (context 16384) จาก $baseModel ..."
        $mf = Join-Path $env:TEMP 'cws-modelfile'
        Set-Content -Path $mf -Encoding ascii -Value "FROM $baseModel`nPARAMETER num_ctx 16384"
        ollama create $cwsModel -f $mf
    }
    Write-Host "โมเดลพร้อม: $cwsModel" -ForegroundColor Green
} catch {
    Write-Host 'ติดต่อ Ollama ไม่ได้ — เปิดแอป Ollama ก่อน แล้วค่อยตั้งค่าในหน้าเกม' -ForegroundColor Yellow
}
Write-Host ''
Write-Host '== ตั้งค่าในหน้าเกม (Settings > LLM) ==' -ForegroundColor Cyan
Write-Host '  Preset      : Ollama'
Write-Host '  Base URL    : http://localhost:11434/v1'
Write-Host "  Model       : $cwsModel"
Write-Host "  Fast model  : $cwsModel"
Write-Host '  Max concurrent requests : 2   (ค่าเริ่มต้น 10 จะรอคิวจน timeout)'
Write-Host '  ภาษา (Language) : English'
Write-Host ''
Write-Host "CWS: $Target"
Write-Host "ข้อมูลเกม: $env:CWS_DATA_DIR"
Write-Host 'ปิดเกม = กด Ctrl+C ในหน้าต่างนี้'
# uvicorn เขียน log ลง stderr — ต้องไม่ให้ PowerShell ถือว่าเป็น error แล้วหยุดเซิร์ฟเวอร์
$ErrorActionPreference = 'Continue'
& (Join-Path $Target '.venv\Scripts\python.exe') src\server\main.py --dev 2>&1 |
    ForEach-Object { "$_" } | Tee-Object -FilePath (Join-Path $logDir 'cws-server.log')
