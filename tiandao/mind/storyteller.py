# -*- coding: utf-8 -*-
"""เล่าการตัดสินใจหนึ่งครั้งเป็นเรื่องสั้น — ทำหลังเหตุการณ์จบแล้วเสมอ (ข้อเท็จจริงมาก่อน เรื่องเล่าตามหลัง)

เรื่องเล่าไม่ย้อนไปเปลี่ยนโลก: ถ้าโมเดลแต่งเกิน ผลในโลกก็ยังเป็นตามที่เอนจินตัดสิน บันทึกชีวิตจึง
เก็บทั้งข้อเท็จจริง (outcome/text) และเรื่องเล่าแยกกัน ผู้อ่านเทียบได้เสมอ
"""
from . import persona as P
from .. import rules as R

SYSTEM = (
    "คุณเป็นนักเขียนนิยายกำลังภายในภาษาไทย เขียนฉากสั้นจากบันทึกเหตุการณ์จริงของโลกจำลอง "
    "เล่าบุคคลที่สาม ภาษาอ่านง่าย เห็นภาพเหมือนดูหนัง ให้ผู้อ่านเข้าใจว่าตัวละครคิดอะไรจึงตัดสินใจแบบนั้น "
    "ห้ามเปลี่ยนผลของเหตุการณ์ ห้ามเพิ่มการตายหรือของที่ได้มาเอง ห้ามสร้างตัวละครมีชื่อที่ไม่อยู่ในข้อมูล "
    "กฎเหล็ก: เล่าได้เฉพาะสิ่งที่อยู่ในข้อมูลที่ให้มา ห้ามเพิ่มสิ่งของ สมบัติ ยา อาวุธ คำสัญญา หรือเงื่อนไข "
    "ที่ข้อมูลไม่ได้บอก ถ้าข้อมูลมีน้อย ให้ขยายความรู้สึก ความคิด และบรรยากาศของสถานที่ "
    "ไม่ใช่เพิ่มเหตุการณ์ใหม่ "
    "ลำดับเวลาเป็นกฎบังคับ: ตอนเปิดฉากทุกคนที่ลงมือยังมีชีวิต เหตุการณ์ใน [ผลที่เกิดขึ้นจริง] "
    "เพิ่งเกิดในฉากนี้ ห้ามเล่าว่าใครเคยตาย ถูกฆ่า หรือฟื้นคืนชีพมาก่อนฉาก ถ้าผลมีคนตาย "
    "ให้ความตายนั้นเกิดครั้งเดียวตรงท้ายฉากตามข้อความผลเท่านั้น "
    "ส่งเฉพาะเนื้อเรื่อง ไม่ใส่หัวข้อหรือคำอธิบาย ไม่ครอบเนื้อเรื่องด้วยวงเล็บเหลี่ยม"
)


# คำสั่งเสียงเล่าเรื่อง ใช้ร่วมกันทั้งฉากที่ตัวละครเลือกเองและฉากที่เกิดกับตัวละคร
# วัดจากรันจริง: 38 จาก 151 เรื่องเล่าด้วย "ข้า" เป็นผู้เล่า และ 29 เรื่องมีหัวข้อในวงเล็บติดมาด้วย
# ป้ายเดิมชื่อ "คำสาบานของสายเขา" ทำให้โมเดลเข้าใจว่าเป็นคุณลักษณะของตัวละคร แล้วเขียนว่า
# "ซาโตะเป็นที่รู้จักในเรื่องของการให้คำสัตย์ต่อจิตอสูร" (เจอจริงในรอบเทียบโมเดล) จึงเปลี่ยนเป็น
# "ถ้อยคำเวลาสาบาน" พร้อมบอกชัดว่าใช้ได้เฉพาะในบทพูดตอนสาบานจริง
OATH_RULE = ("ถ้าในฉากมีการให้สัญญา สาบาน หรือรับปาก ให้ผู้พูดกล่าวถ้อยคำตาม [ถ้อยคำเวลาสาบาน] "
             "ของตัวเองในบทพูดตรงๆ ห้ามเขียนถ้อยคำนั้นเป็นคุณสมบัติหรือชื่อเสียงของตัวละคร "
             "และห้ามให้ผู้ฝึกตนพูดแบบชาวบ้านว่า ให้คำมั่นสัญญา ")
MODERN_BAN = ("ห้ามใช้คำสมัยใหม่ว่า คุณ ผม ฉัน ครับ ค่ะ — ใช้ ข้า เจ้า ท่าน สหาย เท่านั้น "
              "ห้ามเพิ่มสิ่งของหรือเหตุการณ์ที่ไม่มีในข้อมูล และห้ามครอบย่อหน้าด้วยวงเล็บเหลี่ยม "
              # โมเดลลอกรายการนิสัยจากใบตัวละครมาเขียนเป็นประโยคตรงๆ ("เขามีนิสัยโลภมาก ระมัดระวัง
              # พอประมาณ เย็นชาไร้เมตตา") ซึ่งอ่านเหมือนใบสมัครงาน ไม่ใช่ฉากในนิยาย
              "ห้ามลอกรายการนิสัย ขั้นพลัง หรืออาชีพจากข้อมูลมาเขียนเรียงเป็นประโยค "
              "ให้แสดงนิสัยผ่านการกระทำ ท่าทาง และคำพูดแทน ")
VOICE = ("เล่าด้วยมุมบุคคลที่สาม ใช้ชื่อตัวละครเป็นประธาน ส่วนสรรพนาม ข้า/เจ้า ใช้เฉพาะในบทพูดและความคิด "
         "ของตัวละคร ในบทพูดให้เรียกอีกฝ่ายตาม [คำเรียกอีกฝ่าย] ที่ให้ไว้ (คนทั่วไปเรียกอย่างสุภาพว่า "
         "สหาย+แซ่ เช่น สหายหาน ผู้ที่สูงกว่าเรียก ท่าน ศัตรูจึงใช้ เจ้า) "
         "ห้ามใส่หัวข้อหรือวงเล็บเหลี่ยมใดๆ ห้ามเล่าเหตุการณ์ที่เกิดหลังจากผลนี้")


def build(sim, entry):
    me = sim.cast[entry["cid"]]
    sheet = P.self_sheet(sim, me)
    lines = [
        f"[ตัวละครหลัก] {entry['name']}",
        f"- ถ้อยคำเวลาสาบาน: {R.oath_form(me)}",
        f"- {sheet.get('เผ่า', '')} · {sheet.get('ขั้นพลัง', '')} · {sheet.get('อาชีพ', '')}",
        f"- นิสัย: {sheet.get('นิสัยเด่น', '')}",
        # ใจตอนนี้ (เจ็ดอารมณ์ หกปรารถนา) — บอกคนเล่าเรื่องว่าจะเขียนอาการภายในของเขาอย่างไร
        # ถ้าไม่บอก โมเดลจะเดาอารมณ์จากผลลัพธ์อย่างเดียว ตัวละครทุกตัวจึงรู้สึกเหมือนกันหมด
        f"- ใจตอนนี้: {sheet.get('อารมณ์ในใจตอนนี้', '')}"
        + (f" · {sheet['ใจที่ยังไม่สงบ']}" if sheet.get('ใจที่ยังไม่สงบ') else ""),
        f"- ใจปรารถนา: {sheet.get('สิ่งที่ใจข้าปรารถนาที่สุด', '')}",
        f"- เป้าหมายชีวิต: {entry.get('long_goal') or '-'}",
        f"[สถานที่] {entry.get('place', '')} (ปีที่ {entry.get('year')})",
    ]
    if entry.get("target"):
        lines.append(f"[อีกฝ่าย] {entry.get('target_identity') or entry['target']}")
    if entry.get("by"):
        lines.append(f"[ผู้ที่ลงมือกับตัวละคร] {entry['by']}")
    lines.append("[เส้นเวลาบังคับ]")
    lines.append(f"- ตอนเปิดฉาก {entry['name']}ยังมีชีวิต เหตุการณ์นี้ยังไม่เกิด")
    if entry.get("target"):
        lines.append(f"- ตอนเปิดฉาก {entry['target']}ยังมีชีวิต เหตุการณ์นี้ยังไม่เกิด")
    if entry.get("by"):
        lines.append(f"- ตอนเปิดฉาก {entry['by']}ยังมีชีวิต เหตุการณ์นี้ยังไม่เกิด")
    lines.append(f"- หลังผลลัพธ์ {entry['name']}: "
                 f"{'ยังมีชีวิต' if entry.get('actor_alive_after', entry.get('alive', True)) else 'เสียชีวิต'}")
    if entry.get("target") and entry.get("target_alive_after") is not None:
        lines.append(f"- หลังผลลัพธ์ {entry['target']}: "
                     f"{'ยังมีชีวิต' if entry['target_alive_after'] else 'เสียชีวิต'}")
    lines.append("- ห้ามอ้างว่าคนใดเคยตายหรือถูกฆ่าก่อนฉากนี้ และห้ามให้คนตายพูดหรือกระทำหลังผลลัพธ์")
    other_cid = entry.get("target_cid") if entry.get("target") else entry.get("by_cid")
    two_minds = False
    if isinstance(other_cid, int) and 0 <= other_cid < len(sim.cast) and other_cid != me.cid:
        other = sim.cast[other_cid]
        lines.append(f"[คำเรียกอีกฝ่าย] {entry['name']}เรียกเขาว่า {P.address_form(me, other)}")
        lines.append(f"[ถ้อยคำเวลาสาบานของอีกฝ่าย] {other.name}: {R.oath_form(other)}")
        om = getattr(getattr(sim, "mind", None), "minds", {}).get(other_cid)
        if om is not None and om.alive:
            # อีกฝ่ายก็เป็นตัวละครที่คิดเองเหมือนกัน — ส่งใจของเขาไปด้วย บทสนทนาจึงเป็นการโต้ตอบจริง
            # ไม่ใช่ตัวประกอบที่พูดตามบท (วัดจริง: ฉากสองคนมีแต่ฝ่ายเดียวที่มีเหตุผลในใจ)
            two_minds = True
            lines += [
                f"[ใจของอีกฝ่าย] {other.name}: เป้าหมายชีวิต {om.long_goal or '-'}"
                + (f" · ตั้งใจช่วงนี้ {om.short_goal}" if om.short_goal else "")
                + (f" · อารมณ์ {om.emotion}" if om.emotion else ""),
                f"- นิสัยเขา: {', '.join(P.temperament(other))}",
                f"- เขาเรียก{entry['name']}ว่า {P.address_form(other, me)}",
            ]
    details = entry.get("details") or {}
    useful = {k: v for k, v in details.items() if k not in ("margin", "winner")}
    crowd = details.get("ผู้ร่วมประมูล") or details.get("ผู้ร่วมงาน") or ""
    if useful:
        lines.append("[รายละเอียด] " + "; ".join(f"{k}: {v}" for k, v in list(useful.items())[:6]))
    if crowd:
        # ฉากหมู่: คนในรายชื่อต้องได้พูดจริง ไม่ใช่เป็นฉากหลังของตัวเอกสองคน
        # ใช้ได้ทั้งตอนตัวละครเป็นเจ้าภาพเอง และตอนเขาเป็นผู้ร่วมงาน (ชนะ/พลาดประมูล)
        lines += [f"[ผลที่เกิดขึ้นจริง] {entry['outcome']} — {entry['text']}",
                  "\n[ให้เขียน] ฉากงานชุมนุมยาว 4-7 ย่อหน้า ให้คนในรายชื่อผู้ร่วมงานได้พูดอย่างน้อยคนละครั้ง "
                  "ตามนิสัยและฐานะของเขา เล่าการสู้ราคาเป็นจังหวะขึ้นลง ใครถอย ใครสู้ต่อ จนถึงผลจริง "
                  "แล้วปิดด้วยปฏิกิริยาของผู้ที่พลาดไปอย่างหวุดหวิด " + OATH_RULE + MODERN_BAN + VOICE]
        return SYSTEM, "\n".join(lines)
    if entry.get("type") in ("event", "received"):
        # เหตุการณ์ที่เกิดกับตัวละคร ไม่ใช่สิ่งที่เลือกเอง — ไม่มีความคิดก่อนลงมือให้เล่า จึงเล่าจากการเผชิญหน้า
        lines += [
            f"[สิ่งที่เกิดขึ้นกับตัวละคร] {entry['action']}"
            + (f" โดย {entry['by']}" if entry.get("by") else ""),
            f"[อารมณ์ก่อนหน้านี้] {entry.get('emotion') or '-'}",
            f"[ผลที่เกิดขึ้นจริง] {entry['outcome']} — {entry['text']}",
            "\n[ให้เขียน] ฉากสั้น 3-6 ย่อหน้า เปิดด้วยจังหวะที่เหตุการณ์นี้มาถึงตัวละครโดยไม่ทันตั้งตัว "
            "เล่าว่าเขารับมืออย่างไรตามนิสัยและเป้าหมายของเขา จนถึงผลที่เกิดขึ้นจริง "
            + OATH_RULE + MODERN_BAN + VOICE,
        ]
        return SYSTEM, "\n".join(lines)
    lines += [
        f"[ความคิดก่อนลงมือ] {entry.get('thought') or '-'}",
        f"[อารมณ์] {entry.get('emotion') or '-'}",
        f"[สิ่งที่ตัดสินใจทำ] {entry['action']}" + (f" กับ {entry['target']}" if entry.get("target") else "")
        + (f" มุ่งหน้าสู่ {entry['dest']}" if entry.get("dest") else ""),
        f"[เหตุผลในใจ] {entry.get('why') or '-'}",
        f"[ผลที่เกิดขึ้นจริง] {entry['outcome']} — {entry['text']}",
    ]
    if entry.get("side"):
        lines.append("[เรื่องที่เกิดตามมา] " + " / ".join(entry["side"][:4]))
    two = bool(entry.get("target"))
    lines.append(
        "\n[ให้เขียน] ฉากสั้น 3-6 ย่อหน้า เปิดด้วยสิ่งที่ตัวละครกำลังคิดหรือเผชิญ "
        "แสดงการชั่งใจตามความคิดข้างบน แล้วเล่าการกระทำจนถึงผลที่เกิดขึ้นจริง "
        + ("มีบทสนทนาโต้ตอบกันไปมาอย่างน้อยสามรอบ ทั้งสองฝ่ายพูดจากเหตุผลในใจของตัวเอง "
           "อีกฝ่ายมีสิทธิ์ปฏิเสธ ต่อรอง หรือเห็นต่าง ระบุผู้พูดชัดเจน " if two_minds else
           "มีบทสนทนาโต้ตอบระหว่างสองฝ่ายตามนิสัย ระบุผู้พูดชัดเจน " if two else
           "ตัวละครอยู่คนเดียว เล่าความรู้สึกผ่านการกระทำและความคิดสั้นๆ ")
        + OATH_RULE + MODERN_BAN + VOICE
        + (" เรื่องจบตอนออกเดินทาง ตัวละครยังไม่ถึงที่หมาย" if entry.get("outcome") == "ออกเดินทาง" else "")
    )
    return SYSTEM, "\n".join(lines)


def clean_story(text):
    import re
    from . import config as MC
    for phrase in MC.STORY_LEAK_PHRASES:
        text = text.replace(phrase, "")
    text = re.sub(r"ฉัน(?!ท)", "ข้า", text)
    # หัวข้อสั้นที่โมเดลเติมมาเอง เช่น [ฉากสั้น] [ตัวละครหลัก] [ฉากที่ 1] — ตัดก่อน
    text = re.sub(r"(?m)^\s*\[[^\]\n]{1,24}\]\s*", "", text)
    # โมเดลสาย think (pathumma) ครอบทั้งย่อหน้าด้วยวงเล็บเหลี่ยม — แกะวงเล็บออก ไม่ลบเนื้อหา
    text = re.sub(r"(?m)^\s*\[(.{25,}?)\]\s*$", r"\1", text)
    # "คุณ/ผม" เป็นคำสมัยใหม่ ไม่ใช่ภาษายุทธภพ — เว้นคำที่มี "คุณ" เป็นส่วนของคำอื่น
    text = re.sub(r"(?<!พระ)คุณ(?!ธรรม|ค่า|ภาพ|สมบัติ|งาม|ประโยชน์|วุฒิ|โทษ|ลักษณะ)", "เจ้า", text)
    text = re.sub(r"(?<![ก-๙])ผม(?![ก-๙])", "ข้า", text)
    lines = [re.sub(r"  +", " ", l).strip() for l in text.splitlines()]
    lines = [l for l in lines if l and not any(m in l for m in MC.STORY_INSTRUCTION_MARKS)]
    return "\n".join(lines)


def validate_facts(entry, text):
    """คืนเหตุผลที่เรื่องเล่าขัดหรือข้ามผลชี้ขาดของเอนจิน.

    ไม่พยายามตัดสินร้อยแก้วทั้งหมด ตรวจเฉพาะข้อเท็จจริงที่ห้ามคลุมเครือ: ผู้แพ้ ผู้รอด
    และผู้ตาย ถ้าพิสูจน์ไม่ได้ให้ขอเขียนใหม่แทนการเก็บเรื่องที่อาจกลับผลโลก
    """
    import re
    errors = []
    fact = str(entry.get("text") or "")
    actor = str(entry.get("name") or "")
    target = str(entry.get("target") or entry.get("by") or "")
    prose = str(text or "")

    loser = ""
    for name in (actor, target):
        if name and (f"{name}เป็นฝ่ายพ่าย" in fact or f"{name}ยอมแพ้" in fact):
            loser = name
            break
    if loser:
        winner = target if loser == actor else actor
        loss_words = r"(?:เป็นฝ่ายพ่าย|ยอมรับความพ่ายแพ้|ยอมแพ้อย่าง|พ่ายแพ้)"
        lost = (re.search(re.escape(loser) + r".{0,100}" + loss_words, prose, re.S)
                or re.search(loss_words + r".{0,45}" + re.escape(loser), prose, re.S))
        # จับเฉพาะประโยคที่ผูกชื่อกับการแพ้อย่างใกล้ชิด หรือบอกตรงๆ ว่าผู้แพ้ตามจริง
        # กลับเอาชนะผู้ชนะ ห้ามใช้ช่วงกว้างเพราะบทพูด "เจ้าโชคดีที่ไม่พ่ายแพ้" เคยโดนจับผิด
        wrong = None
        if winner:
            wrong = (re.search(re.escape(winner) + r".{0,18}" + loss_words, prose, re.S)
                     or re.search(r"(?:ในที่สุด|สุดท้าย).{0,35}" + re.escape(winner)
                                  + r".{0,35}" + loss_words, prose, re.S)
                     or re.search(re.escape(loser) + r".{0,35}(?:เอาชนะ|ชนะเหนือ)"
                                  + re.escape(winner), prose, re.S))
        if not lost:
            errors.append(f"ไม่ยืนยันว่า{loser}เป็นฝ่ายแพ้")
        if wrong:
            errors.append(f"กลับผลให้{winner}เป็นฝ่ายแพ้")

    if "รอดด้วยชะตา" in fact:
        survivor = fact.split("รอดด้วยชะตา", 1)[0].split("—")[-1].strip()
        if survivor and not re.search(re.escape(survivor) + r".{0,80}รอด", prose, re.S):
            errors.append(f"ไม่ยืนยันว่า{survivor}รอดด้วยชะตา")
        other = target if survivor == actor else actor
        if other and re.search(re.escape(other) + r".{0,80}รอด(?:ตาย)?ด้วยชะตา", prose, re.S):
            errors.append(f"ยกผลรอดด้วยชะตาให้{other}ผิดคน")

    dead = ""
    if not entry.get("actor_alive_after", entry.get("alive", True)):
        dead = actor
    elif entry.get("target_alive_after") is False:
        dead = target
    if dead and not re.search(re.escape(dead) + r".{0,100}(?:ตาย|สิ้นใจ|ดับดิ้น|เสียชีวิต)",
                              prose, re.S):
        errors.append(f"ไม่เล่าความตายของ{dead}ตามผลจริง")
    return errors
