import re

with open('run.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Let's cleanly inject format_currency right after the imports
imports_end = content.find("def main():")

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
        ss_amount = int(amount // 10000)
        if ss_amount == 0:
            ss_amount = 1 
        
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

content = content[:imports_end] + formatter_code + "\n" + content[imports_end:]

# clean up duplicate formatter code at bottom if any
clean_content = content.replace(formatter_code, "", 1) if content.count(formatter_code) > 1 else content

with open('run.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("run.py patched with format_currency before main")
