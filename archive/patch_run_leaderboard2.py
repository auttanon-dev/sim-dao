import re

with open('run.py', 'r', encoding='utf-8') as f:
    content = f.read()

new_logic = '''
    print()
    if getattr(a, "leaderboard", False):
        print("=======================================================")
        print("🏆 📜 [ทำเนียบยอดฝีมือแห่งยุทธภพ - บันทึกผู้ที่ยังมีชีวิตอยู่] 📜 🏆")
        print("=======================================================")
        
        survivors = [c for c in sim.cast.values() if getattr(c, "alive", True)]
        
        if not survivors:
            print("💀 อนิจจา... ยุทธภพนองเลือด ไม่มีชาวยุทธท่านใดรอดชีวิตเหลืออยู่เลย!")
        else:
            survivors.sort(key=lambda x: (x.realm, sum(getattr(x, "money", {}).values())), reverse=True)
            
            for index, char in enumerate(survivors[:10], 1):
                medal = "🥇" if index == 1 else "🥈" if index == 2 else "🥉" if index == 3 else "🎖️"
                money = sum(getattr(char, "money", {}).values())
                visited = getattr(char, "cities_visited", 0)
                defeated = getattr(char, "enemies_defeated", 0)
                inv = getattr(char, "inventory", {})
                weapon = inv.get("อาวุธ") if inv.get("อาวุธ") else "มือเปล่า"
                
                print(f"{medal} อันดับ {index}: [{char.name}]")
                print(f"   ↳ 🥋 วรยุทธขั้น: Level {char.realm} | 🪙 เงินตรา: {money} Gold | ⚔️ อาวุธ: {weapon}")
                print(f"   ↳ 🗺️  เดินทางผ่านเมืองมาแล้ว: {visited} ครั้ง | ⚔️ ปราบศัตรูไปได้: {defeated} คน")
        print("=======================================================\n")
    elif a.bio is not None:'''

pattern = re.compile(r'    print\(\)\n    if a\.bio is not None:')
new_content = pattern.sub(new_logic, content)

with open('run.py', 'w', encoding='utf-8') as f:
    f.write(new_content)
