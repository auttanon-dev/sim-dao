import re
import json

with open('tiandao/config.py', 'r', encoding='utf-8') as f:
    content = f.read()

factions_config = '''
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

MORTAL_REALMS_CONFIG = {
    1: {"name": "ปุถุชน", "lifespan": 100, "tribulation": "ไม่มี"},
    2: {"name": "ตื่นชี่", "lifespan": 120, "tribulation": "ไม่มี"},
    3: {"name": "หลอมกระดูก", "lifespan": 150, "tribulation": "ไม่มี"},
    4: {"name": "เปิดทวาร", "lifespan": 200, "tribulation": "ไม่มี"},
    5: {"name": "ก่อธาตุ", "lifespan": 300, "tribulation": "ด่านมารในใจ (ทดสอบสมาธิ)"},
    6: {"name": "รวมแกนธาตุ", "lifespan": 500, "tribulation": "ทัณฑ์อัสนี 3 สาย"},
    7: {"name": "ทารกธรรม", "lifespan": 1000, "tribulation": "ทัณฑ์อัสนี 9 สาย"},
    8: {"name": "แปรวิญญาณ", "lifespan": 3000, "tribulation": "เพลิงกรรมเผาผลาญวิญญาณ"},
    9: {"name": "อาศัยฟ้า", "lifespan": 5000, "tribulation": "ทัณฑ์อัสนีสีทอง 27 สาย"},
    10: {"name": "ล่วงพ้นวิถี", "lifespan": 10000, "tribulation": "มหาทัณฑ์สวรรค์เก้าสี (ข้ามมิติ)"}
}
'''

content = content + "\n" + factions_config

# Update LIFESPAN array in config.py
content = re.sub(
    r'LIFESPAN = \[.*?\]',
    'LIFESPAN = [100, 120, 150, 200, 300, 500, 1000, 3000, 5000, 10000]',
    content
)

with open('tiandao/config.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("config.py updated with FACTIONS and MORTAL_REALMS_CONFIG")
