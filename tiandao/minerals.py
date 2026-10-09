# -*- coding: utf-8 -*-
"""แร่จริงเบื้องหลังแร่ในเรื่อง — ผูกแร่ทั้ง 15 ชนิดของ crafting.ORES กับแร่/ธาตุที่มีอยู่จริง

แร่ในเรื่อง = แร่จริงที่อิ่มปราณ คุณสมบัติทางกายภาพ (ความแข็ง ความหนาแน่น จุดหลอมเหลว) และ
สภาพธรณีที่พบจึงอิงของจริง ส่วน "ระดับโลก" ของแร่ (crafting.ORES) ยังเป็นตัวกำหนดว่าขึ้นที่ชั้นไหน

ค่าทั้งหมดเป็นค่าตัวแทนจากตำราแร่วิทยาทั่วไป (ค่ากลางของช่วง) ปัดให้ใช้ง่าย ไม่ใช่ค่าอ้างอิงเชิงห้องทดลอง:
    mohs      ความแข็งสเกลโมส์ (1 ทัลก์ – 10 เพชร)
    density   ความหนาแน่น g/cm^3
    melt_c    จุดหลอมเหลว °C — None = สลายตัว/ระเหิดก่อนหลอม (ดู note)
    settings  สภาพธรณีที่พบจริง (คีย์ใน SETTING_NAMES) ตัวแรกคือแหล่งหลัก ที่เหลือคือแหล่งรอง เช่น ลานแร่พลัด

เอนจินใช้สองทาง (ปิดได้ที่ config.ORE_GEOLOGY / ORE_QUALITY_W = 0):
  * materials.materials_at — แหล่งแร่ออกแร่ที่เข้ากับจังหวัดธรณีของมันก่อน (order_for_site)
  * การหลอมอาวุธใน sim.py — ความแข็งของแร่ในสูตรปรับคุณภาพชิ้นงาน (forge_quality)
"""
from . import crafting as CR

REAL_MINERALS = {
    # ---- โลกมนุษย์ (ชั้น 0): แร่เหล็กและทองแดงที่มนุษย์ถลุงได้จริงตั้งแต่ยุคโบราณ
    "แร่เหล็กไหลแท้": dict(mineral="แมกนีไทต์", en="magnetite", formula="Fe3O4",
                             mohs=6.0, density=5.17, melt_c=1597, settings=("igneous", "metamorphic"),
                             note="แร่เหล็กที่เป็นแม่เหล็กในตัว"),
    "แร่เหล็กดำทมิฬ": dict(mineral="ฮีมาไทต์", en="hematite", formula="Fe2O3",
                            mohs=6.0, density=5.26, melt_c=1565, settings=("sedimentary", "igneous"),
                            note="แร่เหล็กหลักของโลก ผงสีแดงเลือด"),
    "ทองเหลืองอุ่นดารา": dict(mineral="คาลโคไพไรต์", en="chalcopyrite", formula="CuFeS2",
                               mohs=3.75, density=4.2, melt_c=950, settings=("hydrothermal",),
                               note="สีเหลืองทองเหลือง แร่ทองแดงที่พบมากที่สุด"),
    "แร่เหล็กกล้าร้อยพับ": dict(mineral="ซิเดอไรต์", en="siderite", formula="FeCO3",
                                 mohs=4.0, density=3.96, melt_c=None, settings=("sedimentary",),
                                 note="สลายตัวเป็นเหล็กออกไซด์เมื่อเผา ก่อนจะหลอม"),
    "เศษทองแดงคราม": dict(mineral="อะซูไรต์", en="azurite", formula="Cu3(CO3)2(OH)2",
                            mohs=3.75, density=3.77, melt_c=None, settings=("oxidized",),
                            note="สีครามเข้ม เกิดจากแร่ทองแดงผุพัง สลายตัวเมื่อเผา"),
    # ---- แดนเซียน (ชั้น 1): โลหะธรรมชาติและหยก
    "หินหยกครามเซียน": dict(mineral="เนไฟรต์ (หยก)", en="nephrite", formula="Ca2(Mg,Fe)5Si8O22(OH)2",
                              mohs=6.25, density=2.98, melt_c=None, settings=("metamorphic",),
                              note="เหนียวที่สุดในบรรดาหินธรรมชาติ แตกยากกว่าเหล็กกล้า"),
    "แร่เหล็กสายฟ้าเซียน": dict(mineral="เหล็กอุกกาบาต", en="meteoric iron", formula="Fe-Ni",
                                 mohs=4.0, density=7.9, melt_c=1500, settings=("impact",),
                                 note="เหล็กผสมนิกเกิลจากฟ้า โลหะเหล็กชนิดแรกที่มนุษย์ใช้"),
    "แร่เหล็กไหลคราม": dict(mineral="อิลเมไนต์", en="ilmenite", formula="FeTiO3",
                              mohs=5.5, density=4.72, melt_c=1365, settings=("igneous", "sedimentary"),
                              note="แร่ไทเทเนียม พบสะสมในทรายดำ"),
    "ทองคำเซียนบริสุทธิ์": dict(mineral="ทองคำธรรมชาติ", en="native gold", formula="Au",
                                 mohs=2.75, density=19.3, melt_c=1064, settings=("hydrothermal", "sedimentary"),
                                 note="อ่อน หนักมาก ไม่หมอง พบในสายแร่ควอตซ์และตะกอนแม่น้ำ"),
    "แผ่นทองแดงลม": dict(mineral="ทองแดงธรรมชาติ", en="native copper", formula="Cu",
                           mohs=2.75, density=8.96, melt_c=1085, settings=("volcanic",),
                           note="นำความร้อนและไฟฟ้าดีเยี่ยม พบในหินบะซอลต์"),
    # ---- สวรรค์นอกชั้นฟ้า (ชั้น 2): ธาตุหายากและสุดขั้ว
    "แก่นแร่เหล็กดารานิรันดร์": dict(mineral="วุลแฟรไมต์", en="wolframite", formula="(Fe,Mn)WO4",
                                      mohs=4.25, density=7.3, melt_c=None, settings=("hydrothermal",),
                                      note="แร่ทังสเตน โลหะที่จุดหลอมเหลวสูงสุด (3,422 °C)"),
    "ผลึกแก่นแสงดาวฤกษ์": dict(mineral="ฟลูออไรต์", en="fluorite", formula="CaF2",
                                 mohs=4.0, density=3.18, melt_c=1418, settings=("hydrothermal", "sedimentary"),
                                 note="เรืองแสงใต้แสงเหนือม่วง ที่มาของคำว่า fluorescence"),
    "แร่หินธาตุมืดปฐพี": dict(mineral="ยูเรนิไนต์", en="uraninite", formula="UO2",
                               mohs=5.5, density=10.6, melt_c=2865, settings=("igneous", "sedimentary"),
                               note="แร่ยูเรเนียม สีดำ หนัก แผ่รังสี"),
    "เหล็กไหลเงินอวกาศ": dict(mineral="แพลทินัมธรรมชาติ", en="native platinum", formula="Pt",
                               mohs=4.25, density=19.0, melt_c=1768, settings=("igneous", "sedimentary"),
                               note="สีเงิน หนักกว่าทอง ไม่ทำปฏิกิริยา ทนไฟสูง"),
    "แร่วัชรเพชรสวรรค์": dict(mineral="เพชร", en="diamond", formula="C",
                               mohs=10.0, density=3.51, melt_c=None, settings=("mantle", "sedimentary"),
                               note="แข็งที่สุดในธรรมชาติ เกิดลึกในเนื้อโลก ขึ้นมากับปล่องคิมเบอร์ไลต์"),
}

# จังหวัดธรณี (geologic province) — แถบกว้างของเปลือกดาวที่ให้แร่คนละชุด
# ทำไมไม่ใช้ biome ของ terrain.py: 576 จาก 755 สถานที่เป็น biome เดียวกัน (กำหนดจากชื่อแดน ไม่ใช่ภูมิประเทศ)
# และ biome ของบางที่เปลี่ยนตาม seed ของโลก — แหล่งแร่ต้องคงที่ทุก seed เพราะตารางแหล่งแร่ถูกแคชระดับโมดูล
PROVINCES = {
    "magmatic": dict(name="แนวเทือกเขาอัคนี",
                     settings=("igneous", "volcanic", "hydrothermal", "mantle")),
    "basin": dict(name="แอ่งตะกอน", settings=("sedimentary", "oxidized")),
    "craton": dict(name="แผ่นหินโบราณ", settings=("metamorphic", "impact", "mantle")),
}
SETTING_NAMES = {
    "igneous": "หินอัคนี", "volcanic": "ลาวาภูเขาไฟ", "hydrothermal": "สายแร่น้ำร้อน",
    "sedimentary": "ชั้นตะกอน/ลานแร่พลัด", "oxidized": "ส่วนผุพังเหนือสายแร่",
    "metamorphic": "หินแปร", "impact": "หลุมอุกกาบาต", "mantle": "ปล่องจากเนื้อดาว",
}
GEOLOGY_SEED = 20261009      # เมล็ดคงที่ของสนามธรณี — ไม่ผูกกับ seed ของโลก (ดูเหตุผลด้านบน)
GEOLOGY_WAVELENGTH = 60.0    # หน่วยกราฟต่อหนึ่งช่องของสนาม — ราวหนึ่งในสามของความกว้างแดน เพื่อนบ้านจึงมักอยู่จังหวัดเดียวกัน
_PROVINCE = None


def _provinces():
    """จังหวัดธรณีของทุกสถานที่ — สนาม fBm คงที่ตัดเป็นสามช่วงที่มีจำนวนสถานที่เท่ากัน"""
    global _PROVINCE
    if _PROVINCE is None:
        from . import geo as GEO
        from . import noise as NZ
        field = NZ.Field(seed=GEOLOGY_SEED)
        vals = [field.fbm(x / GEOLOGY_WAVELENGTH, y / GEOLOGY_WAVELENGTH, octaves=3) for x, y in GEO.COORDS]
        order = sorted(range(len(vals)), key=lambda i: (vals[i], i))
        keys = ("basin", "craton", "magmatic")       # ต่ำ = แอ่ง · กลาง = แผ่นหินเก่า · สูง = แนวเทือกเขา
        out = [None] * len(vals)
        for rank, i in enumerate(order):
            out[i] = keys[min(2, rank * 3 // len(vals))]
        _PROVINCE = out
    return _PROVINCE


def province_of(place_idx):
    """คีย์จังหวัดธรณีของสถานที่ ("magmatic" / "basin" / "craton")"""
    return _provinces()[place_idx]


def province_name(place_idx):
    return PROVINCES[province_of(place_idx)]["name"]


def fits_province(name, province):
    """แร่นี้เกิดในจังหวัดธรณีแบบนี้ได้จริงไหม — ของที่ไม่ใช่แร่ถือว่าไม่จำกัด"""
    info = REAL_MINERALS.get(name)
    return True if info is None else bool(set(info["settings"]) & set(PROVINCES[province]["settings"]))


def order_for_site(pool, place_idx):
    """เรียงแร่ของระดับนั้นใหม่สำหรับแหล่งนี้: แร่ที่เข้ากับจังหวัดธรณีขึ้นก่อน (คงลำดับถูกไปแพงไว้ในแต่ละกลุ่ม)

    แร่ที่ไม่เข้าจังหวัดยังตามหลังเป็น "แร่รอง" — แหล่งชั้นดีที่ขุดลึกจึงยังเจอได้ทุกชนิดเหมือนเดิม
    แต่แหล่งธรรมดา (ลึก 2 ชนิด) จะให้เฉพาะแร่ของจังหวัดตัวเอง แร่บางชนิดจึงต้องเดินทางไปหาหรือซื้อ
    """
    prov = province_of(place_idx)
    return ([m for m in pool if fits_province(m, prov)]
            + [m for m in pool if not fits_province(m, prov)])


def forge_quality(reqs, weight):
    """ตัวคูณคุณภาพอาวุธจากเนื้อแร่ในสูตร — ความแข็งโมส์เฉลี่ย (ถ่วงด้วยจำนวน) เทียบค่ากลางของแร่ทุกชนิด

    แข็งกว่าค่ากลาง = คมและคงรูปกว่า อ่อนกว่า (ทองคำ ทองแดง) = สวยแต่บิ่นง่าย ผลถูกหนีบไว้ที่ ±weight
    สูตรที่ไม่มีแร่เลยได้ 1.0
    """
    total = sum(q for m, q in reqs if m in REAL_MINERALS)
    if total <= 0 or weight <= 0:
        return 1.0
    mean = sum(REAL_MINERALS[m]["mohs"] * q for m, q in reqs if m in REAL_MINERALS) / total
    return 1.0 + max(-weight, min(weight, weight * (mean - MOHS_REFERENCE) / MOHS_REFERENCE * 2.0))


def real_of(name):
    """ข้อมูลแร่จริงของแร่ในเรื่อง — None ถ้าไม่ใช่แร่ (สมุนไพร แก่นพลัง)"""
    return REAL_MINERALS.get(name)


def scratches(a, b):
    """แร่ a ขีดแร่ b เป็นรอยได้ไหม (สเกลโมส์: แข็งกว่าขีดอ่อนกว่า)"""
    return REAL_MINERALS[a]["mohs"] > REAL_MINERALS[b]["mohs"]


def mass_kg(name, volume_cm3):
    """มวลของก้อนแร่ปริมาตรนี้ — ทองคำก้อนเท่ากำปั้น (~300 cm^3) หนักเกือบ 6 กก."""
    return REAL_MINERALS[name]["density"] * float(volume_cm3) / 1000.0


def describe(name):
    info = REAL_MINERALS.get(name)
    if info is None:
        return ""
    melt = f"หลอมที่ {info['melt_c']:,} °C" if info["melt_c"] is not None else "ไม่หลอม (สลายตัว/ระเหิดก่อน)"
    return (f"{name} = {info['mineral']} ({info['formula']}) · ความแข็ง {info['mohs']:g} · "
            f"หนาแน่น {info['density']:g} g/cm³ · {melt} · {info['note']}")


MOHS_REFERENCE = sum(m["mohs"] for m in REAL_MINERALS.values()) / len(REAL_MINERALS)

assert set(REAL_MINERALS) == {n for n, _ in CR.ORES}, "แร่ในเรื่องกับตารางแร่จริงต้องตรงกันทุกชนิด"
