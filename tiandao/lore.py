# -*- coding: utf-8 -*-
"""ข้อมูลโลก (เผ่า อาชีพ เมือง สกุลเงิน ฝ่าย ขั้นมนุษย์ วิถีสูงสุด) — แยกจาก config.py
เป็นตารางข้อมูลล้วน ไม่มีค่าคงที่ที่ปรับจูน; config.py re-export ทุกชื่อ ผู้เรียกเดิม (C.CITIES) ไม่ต้องแก้
"""

# --- TRIBES ---
TRIBES = [
    ("ชาวตงหยวน", 0.70),
    ("เผ่าเหมียว", 0.05),
    ("เผ่าเร่ร่อน", 0.10),
    ("เผ่าทิเบต", 0.05),
    ("เผ่าคนป่า", 0.05),
    ("ชาวอุยกูร์", 0.05)
]

# --- PROFESSIONS ---
PROFESSIONS = [
    # สายบู๊ (15%)
    ("เจ้าสำนัก", 0.01), ("ศิษย์เอก", 0.03), ("ศิษย์ฝ่ายนอก", 0.05), ("จอมยุทธพเนจร", 0.02), ("นักคุ้มกันภัย", 0.01), ("นักฆ่า", 0.01), ("โจรป่า", 0.01), ("ผู้คุมกฎ", 0.01),
    # สายสนับสนุน (10%)
    ("หมอยา", 0.02), ("นักปรุงโอสถ", 0.01), ("ช่างตีเหล็ก", 0.02), ("นักสร้างค่ายกล", 0.01), ("หมอดู", 0.02), ("คนเลี้ยงสัตว์อสูร", 0.02),
    # สายข้อมูล/การค้า (15%)
    ("เสี่ยวเอ้อ", 0.05), ("เถ้าแก่", 0.02), ("สายลับ", 0.01), ("พ่อค้าเร่", 0.05), ("นักประมูล", 0.02),
    # สายราชการ/ทหาร (20%)
    ("ท่านอ๋อง", 0.01), ("มือปราบ", 0.03), ("องครักษ์เสื้อแพร", 0.01), ("องครักษ์หลวง", 0.01), ("ทหารรักษาพระนคร", 0.02), ("แม่ทัพใหญ่", 0.01), ("ทหารม้าเหล็ก", 0.02), ("ทหารลาดตระเวน", 0.03), ("ทหารยาม", 0.03), ("ทหารกองปราบ", 0.03),
    # สายนักบวช/นักพรต (5%)
    ("นักบวช", 0.025), ("นักพรต", 0.025),
    # ชาวบ้านทั่วไป (35%)
    ("บัณฑิต", 0.05), ("หลงจู๊", 0.02), ("คนแจวเรือ", 0.03), ("คนสับฟืน", 0.05), ("ชาวนา", 0.20)
]

# --- CITIES ---
CITIES = [
    {
        "id": 1,
        "name_th": "เมืองจักรพรรดิมั่นคง",
        "name_pinyin": "Zhencheng",
        "type_id": 1,
        "type_desc": "เมืองหลวง / เมืองใหญ่",
        "attributes": {
            "safety": 95,
            "wealth": 90,
            "jianghu": 20,
            "info": 50
        },
        "dominant_faction": "Imperial"
    },
    {
        "id": 2,
        "name_th": "เมืองมังกรทะยาน",
        "name_pinyin": "Longfeicheng",
        "type_id": 1,
        "type_desc": "เมืองหลวง / เมืองใหญ่",
        "attributes": {
            "safety": 75,
            "wealth": 95,
            "jianghu": 45,
            "info": 70
        },
        "dominant_faction": "Imperial"
    },
    {
        "id": 3,
        "name_th": "เมืองเมฆาพิสุทธิ์",
        "name_pinyin": "Baiyuncheng",
        "type_id": 1,
        "type_desc": "เมืองหลวง / เมืองใหญ่",
        "attributes": {
            "safety": 85,
            "wealth": 85,
            "jianghu": 30,
            "info": 55
        },
        "dominant_faction": "Imperial"
    },
    {
        "id": 4,
        "name_th": "เมืองสวรรค์บัญชา",
        "name_pinyin": "Tianmingcheng",
        "type_id": 1,
        "type_desc": "เมืองหลวง / เมืองใหญ่",
        "attributes": {
            "safety": 90,
            "wealth": 75,
            "jianghu": 40,
            "info": 45
        },
        "dominant_faction": "Imperial"
    },
    {
        "id": 5,
        "name_th": "เมืองปราชญ์รุ่งเรือง",
        "name_pinyin": "Wenchangcheng",
        "type_id": 1,
        "type_desc": "เมืองหลวง / เมืองใหญ่",
        "attributes": {
            "safety": 85,
            "wealth": 70,
            "jianghu": 15,
            "info": 65
        },
        "dominant_faction": "Imperial"
    },
    {
        "id": 6,
        "name_th": "เมืองดารารวม",
        "name_pinyin": "Xingjucheng",
        "type_id": 1,
        "type_desc": "เมืองหลวง / เมืองใหญ่",
        "attributes": {
            "safety": 80,
            "wealth": 85,
            "jianghu": 60,
            "info": 80
        },
        "dominant_faction": "Orthodox"
    },
    {
        "id": 7,
        "name_th": "เมืองทองคำล้น",
        "name_pinyin": "Jinshancheng",
        "type_id": 1,
        "type_desc": "เมืองหลวง / เมืองใหญ่",
        "attributes": {
            "safety": 70,
            "wealth": 90,
            "jianghu": 35,
            "info": 60
        },
        "dominant_faction": "Imperial"
    },
    {
        "id": 8,
        "name_th": "เมืองแสงจรัส",
        "name_pinyin": "Mingguangcheng",
        "type_id": 1,
        "type_desc": "เมืองหลวง / เมืองใหญ่",
        "attributes": {
            "safety": 80,
            "wealth": 80,
            "jianghu": 50,
            "info": 55
        },
        "dominant_faction": "Orthodox"
    },
    {
        "id": 9,
        "name_th": "เมืองวารีสงบ",
        "name_pinyin": "Pingshuicheng",
        "type_id": 1,
        "type_desc": "เมืองหลวง / เมืองใหญ่",
        "attributes": {
            "safety": 75,
            "wealth": 85,
            "jianghu": 40,
            "info": 65
        },
        "dominant_faction": "Imperial"
    },
    {
        "id": 10,
        "name_th": "เมืองกำแพงเหล็ก",
        "name_pinyin": "Tiebicheng",
        "type_id": 1,
        "type_desc": "เมืองหลวง / เมืองใหญ่",
        "attributes": {
            "safety": 90,
            "wealth": 70,
            "jianghu": 25,
            "info": 40
        },
        "dominant_faction": "Imperial"
    },
    {
        "id": 11,
        "name_th": "เมืองด่านกลืนทราย",
        "name_pinyin": "Tunshazhen",
        "type_id": 2,
        "type_desc": "ชายแดน / ทะเลทราย / หิมะ",
        "attributes": {
            "safety": 30,
            "wealth": 40,
            "jianghu": 65,
            "info": 75
        },
        "dominant_faction": "Tribal"
    },
    {
        "id": 12,
        "name_th": "เมืองหิมะโปรย",
        "name_pinyin": "Luoxuecheng",
        "type_id": 2,
        "type_desc": "ชายแดน / ทะเลทราย / หิมะ",
        "attributes": {
            "safety": 50,
            "wealth": 35,
            "jianghu": 55,
            "info": 40
        },
        "dominant_faction": "Orthodox"
    },
    {
        "id": 13,
        "name_th": "เมืองหมาป่าคะนอง",
        "name_pinyin": "Zhanlangcheng",
        "type_id": 2,
        "type_desc": "ชายแดน / ทะเลทราย / หิมะ",
        "attributes": {
            "safety": 40,
            "wealth": 50,
            "jianghu": 70,
            "info": 50
        },
        "dominant_faction": "Tribal"
    },
    {
        "id": 14,
        "name_th": "เมืองด่านสยบประจิม",
        "name_pinyin": "Zhenxicheng",
        "type_id": 2,
        "type_desc": "ชายแดน / ทะเลทราย / หิมะ",
        "attributes": {
            "safety": 60,
            "wealth": 65,
            "jianghu": 50,
            "info": 60
        },
        "dominant_faction": "Imperial"
    },
    {
        "id": 15,
        "name_th": "เมืองไร้ราก",
        "name_pinyin": "Wugencheng",
        "type_id": 2,
        "type_desc": "ชายแดน / ทะเลทราย / หิมะ",
        "attributes": {
            "safety": 25,
            "wealth": 55,
            "jianghu": 60,
            "info": 70
        },
        "dominant_faction": "Heterodox"
    },
    {
        "id": 16,
        "name_th": "เมืองพายุคลั่ง",
        "name_pinyin": "Kuangfengzhen",
        "type_id": 2,
        "type_desc": "ชายแดน / ทะเลทราย / หิมะ",
        "attributes": {
            "safety": 45,
            "wealth": 30,
            "jianghu": 50,
            "info": 45
        },
        "dominant_faction": "Tribal"
    },
    {
        "id": 17,
        "name_th": "เมืองธารน้ำแข็ง",
        "name_pinyin": "Binghezhen",
        "type_id": 2,
        "type_desc": "ชายแดน / ทะเลทราย / หิมะ",
        "attributes": {
            "safety": 55,
            "wealth": 45,
            "jianghu": 45,
            "info": 35
        },
        "dominant_faction": "Orthodox"
    },
    {
        "id": 18,
        "name_th": "เมืองทรายเหลือง",
        "name_pinyin": "Huangshacheng",
        "type_id": 2,
        "type_desc": "ชายแดน / ทะเลทราย / หิมะ",
        "attributes": {
            "safety": 20,
            "wealth": 35,
            "jianghu": 70,
            "info": 65
        },
        "dominant_faction": "Heterodox"
    },
    {
        "id": 19,
        "name_th": "เมืองป้อมทมิฬ",
        "name_pinyin": "Heibaocheng",
        "type_id": 2,
        "type_desc": "ชายแดน / ทะเลทราย / หิมะ",
        "attributes": {
            "safety": 70,
            "wealth": 40,
            "jianghu": 55,
            "info": 45
        },
        "dominant_faction": "Imperial"
    },
    {
        "id": 20,
        "name_th": "เมืองด่านเมฆโลหิต",
        "name_pinyin": "Xueyunzhen",
        "type_id": 2,
        "type_desc": "ชายแดน / ทะเลทราย / หิมะ",
        "attributes": {
            "safety": 35,
            "wealth": 30,
            "jianghu": 75,
            "info": 50
        },
        "dominant_faction": "Tribal"
    },
    {
        "id": 21,
        "name_th": "เมืองคนโฉด",
        "name_pinyin": "Weitucheng",
        "type_id": 3,
        "type_desc": "เมืองลับแล / กบดาน / ตลาดมืด",
        "attributes": {
            "safety": 10,
            "wealth": 60,
            "jianghu": 85,
            "info": 80
        },
        "dominant_faction": "Heterodox"
    },
    {
        "id": 22,
        "name_th": "เมืองตลาดราตรี",
        "name_pinyin": "Heixizhen",
        "type_id": 3,
        "type_desc": "เมืองลับแล / กบดาน / ตลาดมืด",
        "attributes": {
            "safety": 15,
            "wealth": 80,
            "jianghu": 75,
            "info": 90
        },
        "dominant_faction": "Heterodox"
    },
    {
        "id": 23,
        "name_th": "เมืองวิญญาณหลอน",
        "name_pinyin": "Youmingcheng",
        "type_id": 3,
        "type_desc": "เมืองลับแล / กบดาน / ตลาดมืด",
        "attributes": {
            "safety": 15,
            "wealth": 40,
            "jianghu": 80,
            "info": 60
        },
        "dominant_faction": "Heterodox"
    },
    {
        "id": 24,
        "name_th": "เมืองบุปผาโลหิต",
        "name_pinyin": "Xuehuazhen",
        "type_id": 3,
        "type_desc": "เมืองลับแล / กบดาน / ตลาดมืด",
        "attributes": {
            "safety": 35,
            "wealth": 75,
            "jianghu": 65,
            "info": 95
        },
        "dominant_faction": "Heterodox"
    },
    {
        "id": 25,
        "name_th": "เมืองไร้กฎ",
        "name_pinyin": "Wufazhen",
        "type_id": 3,
        "type_desc": "เมืองลับแล / กบดาน / ตลาดมืด",
        "attributes": {
            "safety": 5,
            "wealth": 50,
            "jianghu": 90,
            "info": 75
        },
        "dominant_faction": "Heterodox"
    },
    {
        "id": 26,
        "name_th": "เมืองหมอกพิษ",
        "name_pinyin": "Duyuncheng",
        "type_id": 3,
        "type_desc": "เมืองลับแล / กบดาน / ตลาดมืด",
        "attributes": {
            "safety": 20,
            "wealth": 45,
            "jianghu": 80,
            "info": 30
        },
        "dominant_faction": "Heterodox"
    },
    {
        "id": 27,
        "name_th": "เมืองกระดูกขาว",
        "name_pinyin": "Baiguzhen",
        "type_id": 3,
        "type_desc": "เมืองลับแล / กบดาน / ตลาดมืด",
        "attributes": {
            "safety": 25,
            "wealth": 30,
            "jianghu": 70,
            "info": 55
        },
        "dominant_faction": "Heterodox"
    },
    {
        "id": 28,
        "name_th": "เมืองหน้ากากเหล็ก",
        "name_pinyin": "Tiemiancheng",
        "type_id": 3,
        "type_desc": "เมืองลับแล / กบดาน / ตลาดมืด",
        "attributes": {
            "safety": 30,
            "wealth": 65,
            "jianghu": 85,
            "info": 65
        },
        "dominant_faction": "Heterodox"
    },
    {
        "id": 29,
        "name_th": "เมืองกลลวง",
        "name_pinyin": "Huanyingcheng",
        "type_id": 3,
        "type_desc": "เมืองลับแล / กบดาน / ตลาดมืด",
        "attributes": {
            "safety": 40,
            "wealth": 40,
            "jianghu": 75,
            "info": 40
        },
        "dominant_faction": "Heterodox"
    },
    {
        "id": 30,
        "name_th": "เมืองร้อยอสูร",
        "name_pinyin": "Baishouzhen",
        "type_id": 3,
        "type_desc": "เมืองลับแล / กบดาน / ตลาดมืด",
        "attributes": {
            "safety": 20,
            "wealth": 35,
            "jianghu": 80,
            "info": 45
        },
        "dominant_faction": "Tribal"
    },
    {
        "id": 31,
        "name_th": "เมืองเงาสำนัก",
        "name_pinyin": "Jianyingzhen",
        "type_id": 4,
        "type_desc": "หน้าด่านสำนักยุทธ",
        "attributes": {
            "safety": 85,
            "wealth": 60,
            "jianghu": 95,
            "info": 65
        },
        "dominant_faction": "Orthodox"
    },
    {
        "id": 32,
        "name_th": "เมืองธรรมโอสถ",
        "name_pinyin": "Lingyaozhen",
        "type_id": 4,
        "type_desc": "หน้าด่านสำนักยุทธ",
        "attributes": {
            "safety": 80,
            "wealth": 75,
            "jianghu": 90,
            "info": 55
        },
        "dominant_faction": "Orthodox"
    },
    {
        "id": 33,
        "name_th": "เมืองสระมังกร",
        "name_pinyin": "Longtanzhen",
        "type_id": 4,
        "type_desc": "หน้าด่านสำนักยุทธ",
        "attributes": {
            "safety": 75,
            "wealth": 55,
            "jianghu": 85,
            "info": 50
        },
        "dominant_faction": "Orthodox"
    },
    {
        "id": 34,
        "name_th": "เมืองระฆังทอง",
        "name_pinyin": "Jinzhongzhen",
        "type_id": 4,
        "type_desc": "หน้าด่านสำนักยุทธ",
        "attributes": {
            "safety": 90,
            "wealth": 40,
            "jianghu": 80,
            "info": 45
        },
        "dominant_faction": "Orthodox"
    },
    {
        "id": 35,
        "name_th": "เมืองเต๋าพิสุทธิ์",
        "name_pinyin": "Qingxiuzhen",
        "type_id": 4,
        "type_desc": "หน้าด่านสำนักยุทธ",
        "attributes": {
            "safety": 85,
            "wealth": 50,
            "jianghu": 85,
            "info": 50
        },
        "dominant_faction": "Orthodox"
    },
    {
        "id": 36,
        "name_th": "เมืองห้าธาตุ",
        "name_pinyin": "Wuxingzhen",
        "type_id": 4,
        "type_desc": "หน้าด่านสำนักยุทธ",
        "attributes": {
            "safety": 80,
            "wealth": 55,
            "jianghu": 80,
            "info": 60
        },
        "dominant_faction": "Orthodox"
    },
    {
        "id": 37,
        "name_th": "เมืองไผ่เขียว",
        "name_pinyin": "Cuizhuzhen",
        "type_id": 4,
        "type_desc": "หน้าด่านสำนักยุทธ",
        "attributes": {
            "safety": 55,
            "wealth": 20,
            "jianghu": 100,
            "info": 100
        },
        "dominant_faction": "Orthodox"
    },
    {
        "id": 38,
        "name_th": "เมืองน้ำพุทิพย์",
        "name_pinyin": "Lingchuanzhen",
        "type_id": 4,
        "type_desc": "หน้าด่านสำนักยุทธ",
        "attributes": {
            "safety": 95,
            "wealth": 45,
            "jianghu": 70,
            "info": 35
        },
        "dominant_faction": "Orthodox"
    },
    {
        "id": 39,
        "name_th": "เมืองหมื่นวิชา",
        "name_pinyin": "Wanfacheng",
        "type_id": 4,
        "type_desc": "หน้าด่านสำนักยุทธ",
        "attributes": {
            "safety": 60,
            "wealth": 50,
            "jianghu": 100,
            "info": 85
        },
        "dominant_faction": "Heterodox"
    },
    {
        "id": 40,
        "name_th": "เมืองสะพานเซียน",
        "name_pinyin": "Xiangxianzhen",
        "type_id": 4,
        "type_desc": "หน้าด่านสำนักยุทธ",
        "attributes": {
            "safety": 85,
            "wealth": 65,
            "jianghu": 75,
            "info": 70
        },
        "dominant_faction": "Orthodox"
    },
    {
        "id": 41,
        "name_th": "เมืองสุขสำราญ",
        "name_pinyin": "Anlecheng",
        "type_id": 5,
        "type_desc": "เมืองวิถีชีวิต",
        "attributes": {
            "safety": 80,
            "wealth": 60,
            "jianghu": 20,
            "info": 30
        },
        "dominant_faction": "Imperial"
    },
    {
        "id": 42,
        "name_th": "เมืองรวงข้าวทอง",
        "name_pinyin": "Jinguzhen",
        "type_id": 5,
        "type_desc": "เมืองวิถีชีวิต",
        "attributes": {
            "safety": 85,
            "wealth": 40,
            "jianghu": 15,
            "info": 25
        },
        "dominant_faction": "Imperial"
    },
    {
        "id": 43,
        "name_th": "เมืองล้อมดารา",
        "name_pinyin": "Huanxingzhen",
        "type_id": 5,
        "type_desc": "เมืองวิถีชีวิต",
        "attributes": {
            "safety": 70,
            "wealth": 55,
            "jianghu": 35,
            "info": 60
        },
        "dominant_faction": "Imperial"
    },
    {
        "id": 44,
        "name_th": "เมืองพันสมุนไพร",
        "name_pinyin": "Wanchaozhen",
        "type_id": 5,
        "type_desc": "เมืองวิถีชีวิต",
        "attributes": {
            "safety": 65,
            "wealth": 70,
            "jianghu": 40,
            "info": 45
        },
        "dominant_faction": "Tribal"
    },
    {
        "id": 45,
        "name_th": "เมืองสะพานหิน",
        "name_pinyin": "Shiqiaozhen",
        "type_id": 5,
        "type_desc": "เมืองวิถีชีวิต",
        "attributes": {
            "safety": 75,
            "wealth": 50,
            "jianghu": 25,
            "info": 55
        },
        "dominant_faction": "Imperial"
    },
    {
        "id": 46,
        "name_th": "เมืองสุราหอม",
        "name_pinyin": "Fangjiuzhen",
        "type_id": 5,
        "type_desc": "เมืองวิถีชีวิต",
        "attributes": {
            "safety": 60,
            "wealth": 65,
            "jianghu": 50,
            "info": 75
        },
        "dominant_faction": "Orthodox"
    },
    {
        "id": 47,
        "name_th": "เมืองช่างศิลป์",
        "name_pinyin": "Qiaoshouzhen",
        "type_id": 5,
        "type_desc": "เมืองวิถีชีวิต",
        "attributes": {
            "safety": 85,
            "wealth": 75,
            "jianghu": 30,
            "info": 40
        },
        "dominant_faction": "Imperial"
    },
    {
        "id": 48,
        "name_th": "เมืองเมฆลอย",
        "name_pinyin": "Feiyunzhen",
        "type_id": 5,
        "type_desc": "เมืองวิถีชีวิต",
        "attributes": {
            "safety": 50,
            "wealth": 35,
            "jianghu": 60,
            "info": 45
        },
        "dominant_faction": "Tribal"
    },
    {
        "id": 49,
        "name_th": "เมืองสงบจิต",
        "name_pinyin": "Ningxinzhen",
        "type_id": 5,
        "type_desc": "เมืองวิถีชีวิต",
        "attributes": {
            "safety": 90,
            "wealth": 45,
            "jianghu": 25,
            "info": 35
        },
        "dominant_faction": "Orthodox"
    },
    {
        "id": 50,
        "name_th": "เมืองกระจกเงา",
        "name_pinyin": "Mingjingcheng",
        "type_id": 5,
        "type_desc": "เมืองวิถีชีวิต",
        "attributes": {
            "safety": 80,
            "wealth": 50,
            "jianghu": 15,
            "info": 50
        },
        "dominant_faction": "Imperial"
    }
]


FACTIONS = {
    "ฝ่ายธรรมะ": [
        {"name": "สำนักกระบี่สวรรค์", "focus": "วิถีดาบ", "trait": "โจมตีรุนแรง, ยึดมั่นคุณธรรม"},
        {"name": "หุบเขายาเทวะ", "focus": "วิถียา", "trait": "ฟื้นฟูยอดเยี่ยม, เส้นสายกว้างขวาง"}
    ],
    "ฝ่ายอธรรม": [
        {"name": "นิกายโลหิตทมิฬ", "focus": "วิถีเลือด", "trait": "ดูดกลืนพลังชีวิต, โจมตีโหดเหี้ยม"},
        {"name": "ตำหนักวิญญาณแค้น", "focus": "วิถีความว่าง", "trait": "ลอบสังหาร, ควบคุมจิตใจ"}
    ],
    "ขั้วอำนาจกลาง/ราชสำนัก": [
        {"name": "ค่ายทหารเหล็กไหล", "focus": "วิถีเหล็ก", "trait": "ค่ายกลกลยุทธ์ทหาร, พลังป้องกันสูง, ทำงานเป็นทีม"},
        {"name": "หอการค้าหมื่นลี้", "focus": "วิถีค้าขาย", "trait": "ทรัพยากรมหาศาล, ข่าวสารฉับไว"}
    ],
    "ตระกูลโบราณ": [
        {"name": "ตระกูลตงฟาง", "focus": "วิถีเปลวไฟ", "trait": "สืบทอดสายเลือดอสูร, เชี่ยวชาญเพลิง"},
        {"name": "ตระกูลเป่ยหมิง", "focus": "วิถีสายน้ำ", "trait": "ทนทาน, พลังปราณลึกล้ำ"}
    ]
}

MORTAL_REALMS_CONFIG = {
    1: {"name": "ปุถุชน", "lifespan": 100, "tribulation": "ไม่มี"},
    2: {"name": "ตื่นชี่", "lifespan": 120, "tribulation": "ไม่มี"},
    3: {"name": "หลอมกระดูก", "lifespan": 150, "tribulation": "ไม่มี"},
    4: {"name": "เปิดทวาร", "lifespan": 200, "tribulation": "ไม่มี"},
    5: {"name": "ก่อธาตุ", "lifespan": 300, "tribulation": "ด่านมารในใจ (ทดสอบสมาธิ)"},
    6: {"name": "รวมแกนธาตุ", "lifespan": 500, "tribulation": "ทัณฑ์อัสนี 3 สาย"},
    7: {"name": "ทารกธรรม", "lifespan": 1000, "tribulation": "ทัณฑ์อัสนี 9 สาย"},
    8: {"name": "แปรวิญญาณ", "lifespan": 3000, "tribulation": "เพลิงกรรมเผาผลาญวิญญาณ"},
    9: {"name": "อาศัยฟ้า", "lifespan": 5000, "tribulation": "ทัณฑ์อัสนีสีทอง 27 สาย"},
    10: {"name": "ล่วงพ้นวิถี", "lifespan": 10000, "tribulation": "มหาทัณฑ์สวรรค์เก้าสี (ข้ามมิติ)"}
}


CURRENCY = {
    "mortal": ["อีแปะ", "ตำลึงเงิน", "ตำลึงทอง"], # 100 อีแปะ = 1 เงิน, 100 เงิน = 1 ทอง
    "cultivator": {
        "low": "ศิลาปราณระดับต่ำ",
        "mid": "ศิลาปราณระดับกลาง", # 100 ระดับต่ำ = 1 ระดับกลาง
        "high": "ศิลาปราณระดับสูง",
        "supreme": "ศิลาปราณบริสุทธิ์" # หายากมาก ใช้ขับเคลื่อนค่ายกลระดับเมือง
    }
}


SUPREME_DAO_PATHS = {
    "วิถีแห่งเวลา": {"concept": ["อดีต", "อนาคต", "หยุดนิ่ง"], "effect": "ควบคุมลำดับเทิร์นการต่อสู้, ย้อนสถานะ"},
    "วิถีแห่งมิติ": {"concept": ["ระยะทาง", "มิติเอกเทศ", "ตัดขาด"], "effect": "หลบหลีก 100%, โจมตีทะลุพลังป้องกัน"},
    "วิถีหยินหยาง": {"concept": ["สมดุล", "สะท้อนกลับ", "ชีวิตและตาย"], "effect": "สะท้อนการโจมตี, สลับสถานะบัฟ/ดีบัฟ"},
    "วิถีสายฟ้า": {"concept": ["พิพากษา", "รวดเร็ว", "ทัณฑ์สวรรค์"], "effect": "ความเร็วสูงสุด, พลังทำลายล้างเป้าหมายเดี่ยวที่รุนแรงที่สุด"},
    "วิถีโกลาหล": {"concept": ["ไร้กฎเกณฑ์", "กลืนกิน", "ดับสูญ"], "effect": "ลบล้างวิถีเต๋าอื่นทั้งหมด, ป้องกันการฟื้นฟู"}
}
