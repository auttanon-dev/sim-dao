import json
import sys
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

FACTIONS = {
    "ฝ่ายธรรมะ": [
        {"name": "สำนักกระบี่สวรรค์", "focus": "วิถีดาบ", "trait": "โจมตีรุนแรง, ยึดมั่นคุณธรรม"},
        {"name": "หุบเขายาเทวะ", "focus": "วิถียา", "trait": "ฟื้นฟูยอดเยี่ยม, เส้นสายกว้างขวาง"}
    ],
    "ฝ่ายอธรรม": [
        {"name": "นิกายโลหิตทมิฬ", "focus": "วิถีเลือด", "trait": "ดูดกลืนพลังชีวิต, โจมตีโหดเหี้ยม"},
        {"name": "ตำหนักวิญญาณแค้น", "focus": "วิถีความว่าง", "trait": "ลอบสังหาร, ควบคุมจิตใจ"}
    ],
    "ขั้วอำนาจกลาง/ราชสำนัก": [
        {"name": "ค่ายทหารเหล็กไหล", "focus": "วิถีเหล็ก", "trait": "ค่ายกลกลยุทธ์ทหาร, พลังป้องกันสูง, ทำงานเป็นทีม"},
        {"name": "หอการค้าหมื่นลี้", "focus": "วิถีค้าขาย", "trait": "ทรัพยากรมหาศาล, ข่าวสารฉับไว"}
    ],
    "ตระกูลโบราณ": [
        {"name": "ตระกูลตงฟาง", "focus": "วิถีเปลวไฟ", "trait": "สืบทอดสายเลือดอสูร, เชี่ยวชาญเพลิง"},
        {"name": "ตระกูลเป่ยหมิง", "focus": "วิถีสายน้ำ", "trait": "ทนทาน, พลังปราณลึกล้ำ"}
    ]
}

# Example logic for joining canonical factions
def check_join(moral, dao):
    available = []
    for align, sects in FACTIONS.items():
        if align == "ฝ่ายธรรมะ" and moral < 10: continue
        if align == "ฝ่ายอธรรม" and moral > -10: continue
        
        for sect in sects:
            if sect["focus"] == dao:
                available.append(sect["name"])
    return available

print("Moral 50, Dao วิถีดาบ:", check_join(50, "วิถีดาบ"))
print("Moral -50, Dao วิถีเลือด:", check_join(-50, "วิถีเลือด"))
print("Moral 0, Dao วิถีเหล็ก:", check_join(0, "วิถีเหล็ก"))
