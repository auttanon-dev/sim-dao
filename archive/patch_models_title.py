import re

with open('tiandao/models.py', 'r', encoding='utf-8') as f:
    content = f.read()

title_logic = '''
    def update_title(self):
        level = getattr(self, "realm", 1)
        if level >= 10:
            self.title = "มหาเทพกระบี่สยบฟ้า" if self.moral >= 50 else "พญามารโลหิตกลืนวิญญาณ" if self.moral <= -50 else "ปรมาจารย์ไร้พ่าย"
        elif level >= 5:
            self.title = "จอมยุทธคุณธรรม" if self.moral >= 20 else "ดาวโจรแดนเถื่อน" if self.moral <= -20 else "ผู้ท่องโลกีย์"
        else:
            self.title = "ศิษย์ฝ่ายธรรมะ" if self.moral >= 10 else "นักเลงเจ้าถิ่น" if self.moral <= -10 else "ชาวยุทธนิรนาม"
'''

content = content.replace('    def age(self, day: int) -> int:', title_logic + '\n    def age(self, day: int) -> int:')

with open('tiandao/models.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("models.py added update_title().")
