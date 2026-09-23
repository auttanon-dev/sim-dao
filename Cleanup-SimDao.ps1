# =====================================================================================
# Cleanup-SimDao.ps1 — ลบไฟล์ที่ไม่ได้ใช้ในโปรเจกต์ Sim Dao
#
#   กลุ่ม 1  ของซ้ำ/ขยะ (checkpoint, backup ซ้ำ, archive, __pycache__)
#   กลุ่ม 2  ผลรันเก่าที่สร้างใหม่ได้ (minds-compare, events_*.jsonl, LoRA v1-v4 ...)
#   กลุ่ม 3  ไปป์ไลน์เทรน LoRA ทั้งหมด — ไม่มีส่วนไหนของโลกจำลองใช้แล้ว
#            (ตัดสินใจใช้ cws-typhoon2-8b · Layer 3 ใช้ typhoon2.5-qwen3-4b ตัวต้นฉบับจาก Ollama)
#   กลุ่ม 4  ผลทดสอบ/เทียบรอบเก่าที่เหลือใน out\
#
# ค่าเริ่มต้น: แสดงรายการ + ขนาด แล้วถามยืนยันก่อน จากนั้นย้ายไป Recycle Bin (กู้คืนได้)
#
#   .\Cleanup-SimDao.ps1                 # ทุกกลุ่ม: ดูรายการ → ยืนยัน → ย้ายลงถังขยะ
#   .\Cleanup-SimDao.ps1 -DryRun         # ดูรายการอย่างเดียว ไม่ลบอะไร
#   .\Cleanup-SimDao.ps1 -Group 3        # เฉพาะกลุ่มเดียว (1, 2, 3 หรือ 4)
#   .\Cleanup-SimDao.ps1 -Permanent      # ลบถาวร ไม่ผ่านถังขยะ (กู้ไม่ได้)
#   .\Cleanup-SimDao.ps1 -Yes            # ไม่ต้องถามยืนยัน
#
# ไม่แตะ: tiandao\, narrative_factory\ (ใช้เขียนนิยาย), tools\, static\, templates\, art-preview\,
#         out\bootstrap_v3.save, out\test_audit.save, out\jianghu-runtime, out\cws-data,
#         out\ab_full_results.json + out\episode_compare.json (หลักฐานที่ใช้เลือกโมเดลใน config_ai.py),
#         tiandao\world.save*, tiandao\backups ที่ไม่ซ้ำ, ไฟล์ .md และ test_*.py ทุกไฟล์
# =====================================================================================
param(
    [ValidateSet("1", "2", "3", "4", "all")] [string]$Group = "all",
    [switch]$DryRun,
    [switch]$Permanent,
    [switch]$Yes
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$Root = $PSScriptRoot
if (-not (Test-Path (Join-Path $Root "tiandao\sim.py"))) {
    Write-Host "ไม่พบ tiandao\sim.py — ต้องวางสคริปต์นี้ไว้ที่โฟลเดอร์หลักของ Sim Dao" -ForegroundColor Red
    exit 1
}

# ---------------------------------------------------------------- รายการ (path สัมพัทธ์จาก Root)
$Group1 = @(
    "loras\v5\checkpoint-1785", "loras\v5\checkpoint-2380", "loras\v5\checkpoint-2975",
    "loras\v6\checkpoint-1785", "loras\v6\checkpoint-2380", "loras\v6\checkpoint-2975",
    "datasets\lessons_v1_backup_4style",
    "archive",
    "tiandao\world.save.TRAVEL_TEST_seed7_DO_NOT_USE",
    # backup ซ้ำกัน (ขนาด/เวลาแก้ไขเท่ากัน) — เก็บ 20260917-140542 ไว้ไฟล์เดียว
    "tiandao\backups\world.save.before-novel-20260915-205707-176695",
    "tiandao\backups\world.save.before-novel-20260916-232341-337622",
    "tiandao\backups\world.save.before-novel-20260916-232530-942683"
)
$Group2 = @(
    "out\minds-compare", "out\minds-compare-2", "out\minds-compare-3",
    "out\minds-compare-5", "out\minds-compare-6",
    "loras\v1", "loras\v2", "loras\v3", "loras\v4",
    "datasets\v2", "datasets\v3"
)
# ไฟล์แบบ wildcard ใน out\ (เฉพาะชั้นบนสุด ไม่ลงโฟลเดอร์ย่อย)
$Group2Patterns = @("events_*.jsonl", "autonomy_*.json", "crisis_*.json", "lifespan_*.json", "*.log")
$Group3 = @(
    "loras", "datasets", "vendor_llama_cpp_convert",
    "train_lora.py", "merge_lora.py", "evaluate_model.py", "hotswap.py", "autotrain.py",
    "build_dataset.py", "build_lessons.py", "build_dpo_pairs.py"
)
$Group4 = @(
    "out\autonomy_tests", "out\crisis_tests", "out\smoke_run", "out\smoke2",
    "out\story-model-compare", "out\episodes", "out\serial",
    "out\ab_results_n3_backup.json", "out\writer-budget-probe.json", "out\natural-chapter-1.json"
)

# ---------------------------------------------------------------- รวบรวมเป้าหมาย
$targets = New-Object System.Collections.Generic.List[object]
function Add-Target([string]$full, [string]$grp) {
    if (Test-Path -LiteralPath $full) {
        foreach ($t in $targets) {       # ซ้อนอยู่ในโฟลเดอร์ที่จะลบอยู่แล้ว = ไม่ต้องนับซ้ำ
            if ($t.IsDir -and $full.StartsWith($t.Path + "\")) { return }
        }
        $item = Get-Item -LiteralPath $full -Force
        if ($item.PSIsContainer) {
            $size = (Get-ChildItem -LiteralPath $full -Recurse -File -Force -ErrorAction SilentlyContinue |
                     Measure-Object Length -Sum).Sum
        } else { $size = $item.Length }
        if ($null -eq $size) { $size = 0 }
        $targets.Add([pscustomobject]@{ Group = $grp; Path = $full; IsDir = $item.PSIsContainer; Size = [int64]$size })
    }
}

# กลุ่ม 3 ก่อน (โฟลเดอร์ใหญ่) เพื่อไม่ให้กลุ่ม 1/2 นับไฟล์ข้างในซ้ำ
if ($Group -in @("3", "all")) {
    foreach ($p in $Group3) { Add-Target (Join-Path $Root $p) "3" }
}
if ($Group -in @("1", "all")) {
    foreach ($p in $Group1) { Add-Target (Join-Path $Root $p) "1" }
    # __pycache__ ทุกโฟลเดอร์ (ยกเว้นใน .git)
    Get-ChildItem -LiteralPath $Root -Recurse -Directory -Force -Filter "__pycache__" -ErrorAction SilentlyContinue |
        Where-Object { $_.FullName -notmatch "\\\.git\\" } |
        ForEach-Object { Add-Target $_.FullName "1" }
}
if ($Group -in @("2", "all")) {
    foreach ($p in $Group2) { Add-Target (Join-Path $Root $p) "2" }
    $out = Join-Path $Root "out"
    if (Test-Path $out) {
        foreach ($pat in $Group2Patterns) {
            Get-ChildItem -LiteralPath $out -File -Force -Filter $pat | ForEach-Object { Add-Target $_.FullName "2" }
        }
    }
}
if ($Group -in @("4", "all")) {
    foreach ($p in $Group4) { Add-Target (Join-Path $Root $p) "4" }
}

if ($targets.Count -eq 0) {
    Write-Host "ไม่มีอะไรให้ลบ (อาจลบไปแล้ว)" -ForegroundColor Green
    exit 0
}

# ---------------------------------------------------------------- แสดงรายการ
function Fmt([int64]$b) {
    if ($b -ge 1GB) { return "{0:N2} GB" -f ($b / 1GB) }
    if ($b -ge 1MB) { return "{0:N1} MB" -f ($b / 1MB) }
    return "{0:N0} KB" -f ($b / 1KB)
}
Write-Host ""
Write-Host "รายการที่จะลบ (กลุ่ม $Group):" -ForegroundColor Cyan
foreach ($t in ($targets | Sort-Object Group, Path)) {
    $rel = $t.Path.Substring($Root.Length).TrimStart("\")
    $kind = if ($t.IsDir) { "[โฟลเดอร์]" } else { "" }
    Write-Host ("  [{0}] {1,10}  {2} {3}" -f $t.Group, (Fmt $t.Size), $rel, $kind)
}
$total = ($targets | Measure-Object Size -Sum).Sum
Write-Host ""
Write-Host ("รวม {0} รายการ · {1}" -f $targets.Count, (Fmt $total)) -ForegroundColor Yellow
$mode = if ($Permanent) { "ลบถาวร (กู้คืนไม่ได้)" } else { "ย้ายไป Recycle Bin (กู้คืนได้)" }
Write-Host "วิธีลบ: $mode"

if ($DryRun) { Write-Host "`n-DryRun: ไม่ได้ลบอะไร" -ForegroundColor Green; exit 0 }
if (-not $Yes) {
    $ans = Read-Host "`nยืนยันลบทั้งหมดนี้? พิมพ์ y เพื่อยืนยัน"
    if ($ans -notin @("y", "Y", "yes")) { Write-Host "ยกเลิก — ไม่ได้ลบอะไร"; exit 0 }
}

# ---------------------------------------------------------------- ลบ
Add-Type -AssemblyName Microsoft.VisualBasic
$ok = 0; $fail = 0; $freed = 0
foreach ($t in $targets) {
    try {
        if (-not (Test-Path -LiteralPath $t.Path)) { continue }
        if ($Permanent) {
            Remove-Item -LiteralPath $t.Path -Recurse -Force
        } elseif ($t.IsDir) {
            [Microsoft.VisualBasic.FileIO.FileSystem]::DeleteDirectory($t.Path,
                [Microsoft.VisualBasic.FileIO.UIOption]::OnlyErrorDialogs,
                [Microsoft.VisualBasic.FileIO.RecycleOption]::SendToRecycleBin)
        } else {
            [Microsoft.VisualBasic.FileIO.FileSystem]::DeleteFile($t.Path,
                [Microsoft.VisualBasic.FileIO.UIOption]::OnlyErrorDialogs,
                [Microsoft.VisualBasic.FileIO.RecycleOption]::SendToRecycleBin)
        }
        $ok++; $freed += $t.Size
    } catch {
        $fail++
        Write-Host ("  ลบไม่สำเร็จ: {0} — {1}" -f $t.Path, $_.Exception.Message) -ForegroundColor Red
    }
}
Write-Host ""
Write-Host ("เสร็จ: ลบ {0} รายการ · {1}{2}" -f $ok, (Fmt $freed),
            $(if ($fail) { " · ล้มเหลว $fail รายการ" } else { "" })) -ForegroundColor Green
if (-not $Permanent) { Write-Host "ไฟล์อยู่ใน Recycle Bin — รันเทสต์ให้แน่ใจก่อนค่อยล้างถังขยะ (Empty Recycle Bin)" }
Write-Host "เช็กว่าระบบยังปกติ: python test_decision_engine.py และ python test_minds.py"
