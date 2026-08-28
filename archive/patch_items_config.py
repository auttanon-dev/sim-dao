import re

with open('tiandao/config.py', 'r', encoding='utf-8') as f:
    content = f.read()

items_config = '''
ITEM_GRADES = ["ขั้นมนุษย์", "ขั้นปฐพี", "ขั้นสวรรค์", "ขั้นเทวะ"]

MANUALS_AND_TALISMANS = {
    "คัมภีร์บ่มเพาะ": [
        "เคล็ดวิชาปราณเมฆา", "เคล็ดหมุนเวียนหยินหยาง", "คัมภีร์กลืนนภา"
    ],
    "วิชาต่อสู้": [
        "เพลงกระบี่ตัดวารี", "ฝ่ามือทลายผา", "หอกมังกรทะลวงทัพ"
    ],
    "วิชาตัวเบา": [
        "ย่างก้าวไร้เงา", "เคล็ดเหินเมฆา", "พริบตาพันลี้"
    ],
    "ยันต์วิเศษ (ใช้แล้วทิ้ง)": [
        "ยันต์เคลื่อนย้ายพันลี้ (หนีจากการต่อสู้)",
        "ยันต์เกราะทองคำ (อมตะ 1 เทิร์น)",
        "ยันต์สายฟ้าพิพากษา (ทำดาเมจทะลุเกราะ)"
    ]
}
'''

if "ITEM_GRADES =" not in content:
    content += "\n" + items_config
    with open('tiandao/config.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print("Added ITEM_GRADES and MANUALS_AND_TALISMANS to config.py")
else:
    print("ITEM_GRADES already exists.")
