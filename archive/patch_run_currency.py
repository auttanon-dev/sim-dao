import re

with open('run.py', 'r', encoding='utf-8') as f:
    content = f.read()

formatter_code = '''
def format_currency(amount, realm):
    # Base amount is considered as "อีแปะ" (coins)
    # If realm < 5, use mortal currency
    if realm < 5:
        gold = int(amount // 10000)
        silver = int((amount % 10000) // 100)
        coins = int(amount % 100)
        parts = []
        if gold > 0: parts.append(f"{gold} ตำลึงทอง")
        if silver > 0: parts.append(f"{silver} ตำลึงเงิน")
        if coins > 0 or not parts: parts.append(f"{coins} อีแปะ")
        return " ".join(parts)
    else:
        # If realm >= 5, they use spirit stones. 1 low spirit stone = 10000 coins (1 gold tael)
        # So we divide amount by 10000 to get low spirit stones
        ss_amount = int(amount // 10000)
        if ss_amount == 0:
            ss_amount = 1 # give them at least 1 for display if they had some mortal money
        
        supreme = ss_amount // 1000000
        high = (ss_amount % 1000000) // 10000
        mid = (ss_amount % 10000) // 100
        low = ss_amount % 100
        
        parts = []
        if supreme > 0: parts.append(f"{supreme} ศิลาปราณบริสุทธิ์")
        if high > 0: parts.append(f"{high} ศิลาปราณระดับสูง")
        if mid > 0: parts.append(f"{mid} ศิลาปราณระดับกลาง")
        if low > 0 or not parts: parts.append(f"{low} ศิลาปราณระดับต่ำ")
        return " ".join(parts)
'''

# Find the start of run_sim and insert our formatter above it
content = content.replace("def run_sim", formatter_code + "\ndef run_sim")

# Now replace the printing logic
old_print = r'print\(f" ↳ ฉายา: \'{getattr\(char, \'title\', \'ชาวยุทธนิรนาม\'\)}\' \| 🥋 Level: \{char\.realm\} \| 🪙 เงิน: \{money\} Gold"\)'
new_print = r'print(f" ↳ ฉายา: \'{getattr(char, \'title\', \'ชาวยุทธนิรนาม\')}\' | 🥋 Level: {char.realm} | 🪙 ทรัพย์สิน: {format_currency(money, char.realm)}")'

content = re.sub(old_print, new_print, content)

with open('run.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("run.py updated with currency formatter")
