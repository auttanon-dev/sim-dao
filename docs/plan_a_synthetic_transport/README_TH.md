# Plan A: ขอบเขตหลักฐาน synthetic transport

สถานะ: ยอมรับ synthetic controls แยก5กรณีภายในขอบเขต cooperative เท่านั้น ไม่อนุญาต real reader, runtime receipt integration หรือ G2 extraction จากเอกสารนี้

กรณีที่ยอมรับ
- Positive: actual delayed faulthandler traceback ณ named GIL-releasing synthetic site พร้อม external drainer และ normal closure
- Cancellation: ยกเลิก timer ก่อน deadline และถือ DATA เปิดข้าม deadline; actual empty EOF ต้องเป็น INCOMPLETE ไม่ใช่ capture
- Sink death: direct retained-HANDLE termination หลัง ACK ที่ตรวจ role/nonce/seq แล้ว พร้อม abort producer; partial bytesไม่ใช่ capture และ watchdogต้องไม่เคย fired
- Overflow: finite synthetic byte stream4608, sink before-write cap4096/read256, overflow latched/discardต่อจน actual EOF; prefix/hash/FINALตรงจริง แต่ผล INCOMPLETE
- Held writer: producer STATUS EOF/exit0 ขณะที่ ownerถือ DATA writer; sinkยังไม่มี DATA EOF จน ownerปล่อย fd แล้วตรวจ actual FINAL/reap/close

accepted-controls.json เก็บ revision/artifact hashes และประเภทผลของ5กรณี ไม่มี machine-private absolute paths, PIDs, nonce, handle values, raw stack หรือ private data ตัว hash index ไม่ใช่ลายเซ็นหรือหลักฐาน terminal execution

Provenance: actual terminalcommand/CWD/exit เป็นการสังเกตจาก owning Lead tool; Criticตรวจ retained artifacts/hashes อย่างอิสระ แต่ไม่ใช่ independent authenticated terminal export raw evidence ปัจจุบันอยู่ใน local private untracked scratch ซึ่ง mutable และ subject to pruning; hashes ไม่รับรอง durability, immutability หรือ authentication และยังไม่มี verified archive ไม่ rerunเพื่อเติมประวัติ และไม่ commit raw evidence

Negative control PASS ไม่ใช่ capture COMPLETE/receipt: ต้องมี intentional reason, matched/cleanup/posthash/verified latches, exact ACK/identity/hash, resource/thread cleanupครบตาม schema ที่ยอมรับของแต่ละกรณี, actual terminal1หลัง outer slots write/flush/closeครบ operational errorsต้อง2 ไม่พิจารณา terminal1 หรือ candidateJSON เพียงอย่างเดียว

ขอบเขตทรัพยากร: persisted filecap/ACK boundsเป็น software before-write bounds; RSS/privatecommitเป็น sampled observations มี startup/sampling overshoot ไม่รับรอง hard memory/startup/native termination/deadline การ wait10เป็น observation ไม่ใช่ tree cleanup; taskkill0ไม่ใช่ descendant-reap proof

สิ่งที่ยังไม่พิสูจน์: arbitrary OS signals/owner abrupt death, native C/GIL recovery, universal failure cleanup/conservation, real reader diagnosis, mandatory runtime diagnostic/receipt integration, strict simulation equivalence, save/load equivalence หรือ extraction safety

ลำดับต่อไป: separately reviewed cooperative owner interruption negative -> sandbox transport-to-reader contract/integration -> independently gated real reader phase telemetry -> strict comparator/saveVersion31 -> G2 extraction หากหลักฐาน prerequisite ผ่าน งานที่เสร็จใน repositoryต้อง path-scoped review/test/commit/pushและ verify remote ห้าม stage scratch/private artifacts/other edits

เอกสารนี้ไม่เปิด gate ใหม่และไม่ขยาย timeout/memory guarantee; first unexpected failure/hang STOP ไม่มี auto retry

ขอบเขต watchdog evidence: cancellation historical artifact บันทึกเฉพาะ watchdog joined และ errors[] ไม่มี explicit fired flag จึงไม่อ้างว่าพิสูจน์ firedFalse จากกรณีนั้น ส่วน sinkdeath/overflow/heldwriter และ gate รุ่นหลังบันทึก explicit firedFalse เป็น requirement; prospective gates ต้องตรวจ firedFalse หลัง join ไม่ย้อนเติมหรือ relabel historical cancellation evidence
