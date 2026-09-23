# รันระบบ "ผู้มีจิตใจ" ของ Sim Dao ด้วยโมเดลเดียวกับ CWS เพื่อเทียบเนื้อเรื่องกันตรงๆ
# 9 ตัวละคร · 25 นาที · โมเดล cws-typhoon2-8b · ผลอยู่ที่ out\minds-compare-6 (ตั้งชื่อใหม่ด้วย -OutName)
param([int]$Minutes = 25, [int]$Count = 9, [string]$Model = 'cws-typhoon2-8b', [string]$OutName = 'minds-compare-6')
$ErrorActionPreference = 'Continue'
$root = $PSScriptRoot
$out = Join-Path $root ('out\' + $OutName)
New-Item -ItemType Directory -Force -Path $out | Out-Null
$py = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
if (-not (Test-Path $py)) { $py = (Get-Command python -ErrorAction SilentlyContinue).Source }
$env:PYTHONPATH = "$root\out\jianghu-runtime;$root"
$env:PYTHONIOENCODING = 'utf-8'
$env:PYTHONUTF8 = '1'
$env:PYTHONUNBUFFERED = '1'
Set-Location $root
[Console]::OutputEncoding = [Text.Encoding]::UTF8

Write-Host '== ถ้าเกม CWS ยังเปิดอยู่ ให้ปิดหน้าต่าง Start-CWS ก่อน (สองระบบจะแย่งการ์ดจอกัน) ==' -ForegroundColor Yellow
Write-Host "Python: $py"
Write-Host "`n== 1/2 ทดสอบโมเดลด้วยพรอมต์จริงหนึ่งครั้ง ==" -ForegroundColor Cyan
& $py run_minds.py --probe --provider ollama --model $Model --out $out --count $Count 2>&1 |
    ForEach-Object { "$_" } | Tee-Object -FilePath (Join-Path $out 'probe.log')
if ($LASTEXITCODE -ne 0) {
    Write-Host "`nทดสอบไม่ผ่าน (ดู out\$OutName\probe.log) — บอก Claude ได้เลย" -ForegroundColor Red
    Read-Host 'กด Enter เพื่อปิด'; exit 1
}
Write-Host "`n== 2/2 เดินโลก $Minutes นาที ($Count ผู้มีจิตใจ) ==" -ForegroundColor Cyan
& $py run_minds.py --provider ollama --model $Model --out $out --count $Count --years 100000 --minutes $Minutes 2>&1 |
    ForEach-Object { "$_" } | Tee-Object -FilePath (Join-Path $out 'console.log')
Write-Host "`nเสร็จแล้ว — บอก Claude ว่า 'รันเสร็จแล้ว'" -ForegroundColor Green
Read-Host 'กด Enter เพื่อปิด'
