import re

with open('tiandao/sim.py', 'r', encoding='utf-8') as f:
    content = f.read()

old_revenge = '''            winner, loser, combat_log = combat.resolve_combat(a, t, w, self)
            self.kill(loser, f"ถูก {winner.name} สังหาร")'''
new_revenge = '''            winner, loser, combat_log, escaped = combat.resolve_combat(a, t, w, self)
            if not escaped:
                self.kill(loser, f"ถูก {winner.name} สังหาร")'''
content = content.replace(old_revenge, new_revenge)


old_duel = '''                                winner, loser, combat_log = combat.resolve_combat(a, b, w, self)
                                winner.insight += 2.0
                                winner.enemies_defeated = getattr(winner, "enemies_defeated", 0) + 1
                                self.kill(loser, f"ถูก {winner.name} สังหารในการดวลเดือด")'''
new_duel = '''                                winner, loser, combat_log, escaped = combat.resolve_combat(a, b, w, self)
                                winner.insight += 2.0
                                winner.enemies_defeated = getattr(winner, "enemies_defeated", 0) + 1
                                if not escaped:
                                    self.kill(loser, f"ถูก {winner.name} สังหารในการดวลเดือด")'''
content = content.replace(old_duel, new_duel)


old_faction = '''                                winner, loser, combat_log = combat.resolve_combat(a, b, w, self)
                                winner.insight += 3.0
                                self.kill(loser, f"ตกตายในสงครามขั้วอำนาจด้วยเงื้อมมือของ {winner.name}")'''
new_faction = '''                                winner, loser, combat_log, escaped = combat.resolve_combat(a, b, w, self)
                                winner.insight += 3.0
                                if not escaped:
                                    self.kill(loser, f"ตกตายในสงครามขั้วอำนาจด้วยเงื้อมมือของ {winner.name}")'''
content = content.replace(old_faction, new_faction)

with open('tiandao/sim.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("sim.py updated with escape logic!")
