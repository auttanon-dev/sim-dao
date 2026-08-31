# -*- coding: utf-8 -*-
"""Phase G — Append-only event log บนดิสก์ แยกจาก world.save (pickle)

แก้ปัญหา `world.save` โตไม่มีเพดาน (73MB หลัง 200k เหตุการณ์ — เพราะ `sim.log` สะสมทุกเหตุการณ์ไว้ใน
`Sim` object ที่ pickle ทั้งก้อนทุกครั้ง) โดย **เสริม** ไม่ใช่แทนที่: `sim.log` (in-memory list) ยังมี
อยู่และทำงานเหมือนเดิมทุกจุดที่ใช้อยู่แล้ว (`story.py`, `chronicle.py`, `dashboard.py`,
`tiandao/ai/history.py`) — ไฟล์นี้แค่เพิ่มความสามารถ **"flush ของเก่าลงดิสก์แบบถาวร + ตัดความจำทิ้ง"**
เป็น opt-in เท่านั้น ไม่มีใครเรียก `flush_and_trim()` พฤติกรรมเดิมทุกอย่างเหมือนเดิม 100%

ใช้จริงใน `daemon.py` (จุดที่ log โตไม่มีเพดานจริงในทางปฏิบัติ — รันต่อเนื่องได้เป็นล้านเหตุการณ์)
`run.py` ยังไม่แตะ (รันสั้นกว่ามาก ไม่ใช่จุดที่เจอปัญหาจริง)

`narrative_factory/parser.py:parse_log()` ต้องรวม (merge) เหตุการณ์จากทั้งไฟล์นี้ (ประวัติเก่าที่ถูก
ตัดออกจาก `sim.log` ไปแล้ว) และ `sim.log` ที่เหลืออยู่ (เหตุการณ์ใหม่ที่ยังไม่ทัน flush) เข้าด้วยกัน —
ดู `full_log()` ด้านล่าง เป็นจุดเดียวที่ทำ merge นี้ ให้ทั้ง `parser.py` และโค้ดอื่นในอนาคตเรียกใช้ร่วมกัน
"""
import json
import os
from typing import Iterator, List, Optional

from .models import Event


def default_log_path(save_path: str) -> str:
    """ที่อยู่ไฟล์ log ตามธรรมเนียม — คู่กับ save_path เสมอ (world.save -> world.save.events.jsonl)"""
    return save_path + ".events.jsonl"


def append_events(path: str, events: List[Event]) -> None:
    if not events:
        return
    with open(path, "a", encoding="utf-8") as f:
        for e in events:
            f.write(json.dumps(e.to_dict(), ensure_ascii=False) + "\n")


def read_events(path: str) -> Iterator[Event]:
    if not os.path.exists(path):
        return
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            yield Event(**json.loads(line))


def flush_and_trim(sim, path: str, keep_recent: Optional[int] = 5000) -> int:
    """เขียนเหตุการณ์ที่ยังไม่เคย flush ลง path (append-only) แล้วตัด sim.log ในหน่วยความจำ (และใน
    world.save ที่จะ pickle ต่อไป) ให้เหลือแค่ keep_recent อันล่าสุด (None = ไม่ตัดเลย แค่ flush)

    เรียกซ้ำได้ปลอดภัย — ใช้ sim._log_flushed_count (int ธรรมดา pickle ได้ฟรี ไม่ใช่ file handle)
    เป็นตัวจำว่า flush ไปถึงไหนแล้ว คืนจำนวนเหตุการณ์ใหม่ที่เพิ่ง flush ไป"""
    flushed_before = getattr(sim, "_log_flushed_count", 0)
    new_events = sim.log[flushed_before:]
    append_events(path, new_events)
    if keep_recent is not None and len(sim.log) > keep_recent:
        sim.log = sim.log[-keep_recent:]
    sim._log_flushed_count = len(sim.log)   # ทุกอันที่เหลือใน sim.log ตอนนี้ถูก flush ไปแล้วเสมอ
    return len(new_events)


def full_log(sim, path: Optional[str] = None) -> List[Event]:
    """ประวัติเต็ม — รวมของเก่าที่เคย flush ไปแล้ว (จาก path) กับของใหม่ที่ยังอยู่ใน sim.log เท่านั้น
    (กัน merge ซ้ำด้วย seq: ของใน sim.log ที่ seq <= max ใน path แปลว่าเคย flush ไปแล้ว ไม่เอามาซ้ำ)

    path=None หรือไม่มีไฟล์ = sim.log ยังไม่เคยถูก flush/trim เลย คืน sim.log ตรงๆ (พฤติกรรมเดิม)"""
    if not path or not os.path.exists(path):
        return list(sim.log)
    archived = list(read_events(path))
    max_archived_seq = max((e.seq for e in archived), default=-1)
    return archived + [e for e in sim.log if e.seq > max_archived_seq]
