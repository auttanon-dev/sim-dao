import re

with open('tiandao/config.py', 'r', encoding='utf-8') as f:
    content = f.read()

currency_config = '''
CURRENCY = {
    "mortal": ["อีแปะ", "ตำลึงเงิน", "ตำลึงทอง"], # 100 อีแปะ = 1 เงิน, 100 เงิน = 1 ทอง
    "cultivator": {
        "low": "ศิลาปราณระดับต่ำ",
        "mid": "ศิลาปราณระดับกลาง", # 100 ระดับต่ำ = 1 ระดับกลาง
        "high": "ศิลาปราณระดับสูง",
        "supreme": "ศิลาปราณบริสุทธิ์" # หายากมาก ใช้ขับเคลื่อนค่ายกลระดับเมือง
    }
}
'''
if "CURRENCY =" not in content:
    content += "\n" + currency_config
    with open('tiandao/config.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print("Added CURRENCY to config.py")
else:
    print("CURRENCY already exists.")
