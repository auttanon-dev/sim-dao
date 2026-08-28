with open('run.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    if 'format_currency' in line and 'Level:' in line:
        lines[i] = '                print(f" ↳ ฉายา: \'{getattr(char, \'title\', \'ชาวยุทธนิรนาม\')}\' | 🥋 Level: {char.realm} | 🪙 ทรัพย์สิน: {format_currency(money, char.realm)}")\n'.replace("\'", "'")
        # To avoid escaping issues inside f-strings, let's extract it
        lines[i] = '''                title = getattr(char, 'title', 'ชาวยุทธนิรนาม')
                print(f" ↳ ฉายา: '{title}' | 🥋 Level: {char.realm} | 🪙 ทรัพย์สิน: {format_currency(money, char.realm)}")
'''
        break

with open('run.py', 'w', encoding='utf-8') as f:
    f.writelines(lines)
