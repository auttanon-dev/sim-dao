import re

with open('tiandao/events.py', 'r', encoding='utf-8') as f:
    content = f.read()

new_events = '''    # หมวดอาชีพใหม่และเมือง
    dict(kind="จับกุมอาชญากร", w=0, gap=(30, 400), tags=["ต่อสู้", "รักษาความสงบ"], tgt=True),
    dict(kind="ลอบสังหาร",     w=0, gap=(20, 300), tags=["เลือด", "ทำลาย"], tgt=True),
    dict(kind="ดักปล้น",       w=0, gap=(10, 200), tags=["ชิงทรัพย์", "คน"], tgt=True),
    dict(kind="ทำนายชะตา",     w=0, gap=(50, 500), tags=["รู้แจ้ง", "คน"], tgt=True),
    dict(kind="ขายข่าวลับ",    w=0, gap=(10, 200), tags=["แลกเปลี่ยน", "คน"], tgt=True),
    dict(kind="เปิดประมูล",    w=0, gap=(100, 1000), tags=["แลกเปลี่ยน", "ทรัพย์"], tgt=False),
    dict(kind="ลาดตระเวน",     w=0, gap=(20, 200), tags=["เดินทาง", "รักษาความสงบ"], tgt=False),
    dict(kind="สะสมบุญบารมี",  w=0, gap=(100, 1000), tags=["รู้แจ้ง", "เมตตา"], tgt=False),
'''

# Find the end of EVENT_TABLE list
content = content.replace('    dict(kind="ขูดรีดชาวบ้าน",   w=0,  gap=(50, 500),   tags=["คน", "ทำลาย"],       tgt=False),\n]', '    dict(kind="ขูดรีดชาวบ้าน",   w=0,  gap=(50, 500),   tags=["คน", "ทำลาย"],       tgt=False),\n' + new_events + ']')

# Now, redefine pick_event to handle professions properly.
# We'll completely replace def pick_event(ch, rng, has_others: bool):
pattern = re.compile(r'def pick_event\(ch, rng, has_others: bool\):.*?return pool\[-1\]\n', re.DOTALL)

def replacer(match):
    return '''def pick_event(ch, rng, has_others: bool, city=None):
    pool = [e for e in EVENT_TABLE if has_others or not e["tgt"]]
    
    weighted_pool = []
    
    # ดึงสเตตัสเมือง
    safety = city["attributes"]["safety"] if city else 50
    jianghu = city["attributes"]["jianghu"] if city else 50
    wealth = city["attributes"]["wealth"] if city else 50
    info = city["attributes"]["info"] if city else 50

    for e in pool:
        w = e["w"]
        k = e["kind"]
        
        prof = ch.profession
        
        # สายราชการ/ทหาร -> เพิ่มโอกาสลาดตระเวน จับกุม
        if prof in ("ท่านอ๋อง", "มือปราบ", "ทหารรักษาพระนคร", "แม่ทัพใหญ่", "ทหารม้าเหล็ก", "ทหารลาดตระเวน", "ทหารยาม", "ทหารกองปราบ"):
            if k == "จับกุมอาชญากร": w += 40
            if k == "ลาดตระเวน": w += 50
            if k == "ปกป้องชาวบ้าน": w += 30
            # เมืองยิ่งปลอดภัย มือปราบยิ่งทำงานได้ดี
            if k in ("จับกุมอาชญากร", "ลาดตระเวน"): w += safety * 0.5
            
        # สายมืด -> ลอบสังหาร ดักปล้น
        if prof in ("นักฆ่า", "โจรป่า", "องครักษ์เสื้อแพร"):
            if k == "ลอบสังหาร": w += 50
            if k == "ดักปล้น": w += 40
            if k == "ชิงสมบัติ": w += 30
            # เมืองยิ่งเถื่อน สายมืดยิ่งทำงานง่าย
            if k in ("ลอบสังหาร", "ดักปล้น"): w += (100 - safety) * 0.5
            
        # สายสนับสนุนคราฟต์
        if prof in ("หมอยา", "นักปรุงโอสถ"):
            if k == "หลอมยา": w += 50
            if k == "รักษาชาวบ้าน": w += 30
        if prof == "ช่างตีเหล็ก":
            if k in ("หลอมอาวุธ", "ตีเหล็กชาวบ้าน"): w += 50
        if prof == "นักสร้างค่ายกล":
            if k == "หลอมค่ายกล": w += 50
            
        # สายพยากรณ์
        if prof == "หมอดู":
            if k == "ทำนายชะตา": w += 50
            
        # สายการค้าและข่าวสาร
        if prof in ("เสี่ยวเอ้อ", "สายลับ", "เถ้าแก่"):
            if k == "ขายข่าวลับ": w += 50 + (info * 0.5)
        if prof in ("นักประมูล", "พ่อค้าเร่", "เถ้าแก่"):
            if k == "เปิดประมูล": w += 40 + (wealth * 0.5)
            if k == "ค้าขาย": w += 30
            
        # สายนักบวช/นักพรต
        if prof in ("นักบวช", "นักพรต"):
            if k == "สะสมบุญบารมี": w += 60
            if k == "ถ่ายทอดวิชา": w += 20
            # โอกาสบำเพ็ญสูง
            if k == "บำเพ็ญ": w += 30
            
        # สายบู๊หลัก
        if prof in ("เจ้าสำนัก", "ศิษย์เอก", "ผู้คุมกฎ", "ผู้ฝึกตน"):
            if k == "บำเพ็ญ": w += 20 + ch.fear * 10
            if k == "ซ่อนตัว": w += ch.fear * 15
            if k == "ประลอง": w += 30 + (jianghu * 0.5)
            
        # ถ้าเป็นชาวบ้าน/อาชีพทั่วไป กรองเรื่องเหนือธรรมชาติ
        if prof in ("ชาวนา", "คนแจวเรือ", "คนสับฟืน", "หลงจู๊", "บัณฑิต"):
            if k in ("บำเพ็ญ", "ข้ามขั้น", "ล่าอสูร", "ค้นแดนลับ", "ประลอง"):
                w = w * 0.05
            if k == "ทำนา" and prof == "ชาวนา": w = 50
            if k == "ค้าขายทั่วไป" and prof == "หลงจู๊": w = 50
            
        weighted_pool.append((e, max(0, w)))
        
    total = sum(w for e, w in weighted_pool)
    if total <= 0:
        return pool[0]
        
    r, acc = rng.random() * total, 0
    for e, w in weighted_pool:
        acc += w
        if r <= acc:
            return e
    return pool[-1]
'''

new_content = pattern.sub(replacer, content)

with open('tiandao/events.py', 'w', encoding='utf-8') as f:
    f.write(new_content)
print('events.py updated.')
