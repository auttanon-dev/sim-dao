import re

with open('run.py', 'r', encoding='utf-8') as f:
    content = f.read()

leaderboard_new = '''
    if getattr(a, "leaderboard", False):
        print("=======================================================")
        print("🏆 📜 [ทำเนียบยอดฝีมือผู้ขึ้นสู่จุดสูงสุดแห่งยุทธภพ] 📜 🏆")
        print("=======================================================")
        survivors = [c for c in sim.cast if getattr(c, "alive", True) and c.age(sim.day) >= 18]
        if not survivors:
            print("💀 อนิจจา... โลกยุทธภพสิ้นสูญ ไม่มีใครเหลือรอดชีวิต!")
        else:
            survivors.sort(key=lambda x: (x.realm, sum(getattr(x, "money", {}).values())), reverse=True)
            for index, char in enumerate(survivors[:5], 1):
                medal = "🥇" if index == 1 else "🥈" if index == 2 else "🥉" if index == 3 else "🎖️"
                sect_info = f"สำนัก: {char.sect_name} ({char.sect_role})" if getattr(char, "sect_name", None) else "ศิษย์อิสระ"
                money = sum(getattr(char, "money", {}).values())
                print(f"{medal} อันดับ {index}: [{char.name}] อายุ {char.age(sim.day)} ปี (รุ่นที่ {getattr(char, 'generation', 1)})")
                print(f" ↳ ฉายา: '{getattr(char, 'title', 'ชาวยุทธนิรนาม')}' | 🥋 Level: {char.realm} | 🪙 เงิน: {money} Gold")
                print(f" ↳ สถานะคุณธรรม: {getattr(char, 'moral', 0)} | 🏯 {sect_info} | ⚔️ ฆ่าศัตรูแค้นไปแล้ว: {getattr(char, 'enemies_defeated', 0)} คน")
        print("=======================================================\n")
'''

pattern = re.compile(r'    if getattr\(a, "leaderboard", False\):.*?(?=\n    elif a\.bio)', re.DOTALL)
new_content = pattern.sub(leaderboard_new, content)

with open('run.py', 'w', encoding='utf-8') as f:
    f.write(new_content)
print("run.py updated with Ultimate leaderboard.")
