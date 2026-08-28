import re

with open('tiandao/config.py', 'r', encoding='utf-8') as f:
    content = f.read()

supreme_dao_config = '''
SUPREME_DAO_PATHS = {
    "วิถีแห่งเวลา": {"concept": ["อดีต", "อนาคต", "หยุดนิ่ง"], "effect": "ควบคุมลำดับเทิร์นการต่อสู้, ย้อนสถานะ"},
    "วิถีแห่งมิติ": {"concept": ["ระยะทาง", "มิติเอกเทศ", "ตัดขาด"], "effect": "หลบหลีก 100%, โจมตีทะลุพลังป้องกัน"},
    "วิถีหยินหยาง": {"concept": ["สมดุล", "สะท้อนกลับ", "ชีวิตและตาย"], "effect": "สะท้อนการโจมตี, สลับสถานะบัฟ/ดีบัฟ"},
    "วิถีสายฟ้า": {"concept": ["พิพากษา", "รวดเร็ว", "ทัณฑ์สวรรค์"], "effect": "ความเร็วสูงสุด, พลังทำลายล้างเป้าหมายเดี่ยวที่รุนแรงที่สุด"},
    "วิถีโกลาหล": {"concept": ["ไร้กฎเกณฑ์", "กลืนกิน", "ดับสูญ"], "effect": "ลบล้างวิถีเต๋าอื่นทั้งหมด, ป้องกันการฟื้นฟู"}
}

for _dao, _data in SUPREME_DAO_PATHS.items():
    DAO_POOL[_dao] = _data["concept"]
'''
if "SUPREME_DAO_PATHS =" not in content:
    content += "\n" + supreme_dao_config
    with open('tiandao/config.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print("Added SUPREME_DAO_PATHS to config.py")
else:
    print("SUPREME_DAO_PATHS already exists.")
