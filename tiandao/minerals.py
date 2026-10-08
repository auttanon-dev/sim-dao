# -*- coding: utf-8 -*-
"""แร่จริงเบื้องหลังแร่ในเรื่อง — ผูกแร่ทั้ง 15 ชนิดของ crafting.ORES กับแร่/ธาตุที่มีอยู่จริง

แร่ในเรื่อง = แร่จริงที่อิ่มปราณ คุณสมบัติทางกายภาพ (ความแข็ง ความหนาแน่น จุดหลอมเหลว) และ
สภาพธรณีที่พบจึงอิงของจริง ส่วน "ระดับโลก" ของแร่ (crafting.ORES) ยังเป็นตัวกำหนดว่าขึ้นที่ชั้นไหน

ค่าทั้งหมดเป็นค่าตัวแทนจากตำราแร่วิทยาทั่วไป (ค่ากลางของช่วง) ปัดให้ใช้ง่าย ไม่ใช่ค่าอ้างอิงเชิงห้องทดลอง:
    mohs      ความแข็งสเกลโมส์ (1 ทัลก์ – 10 เพชร)
    density   ความหนาแน่น g/cm^3
    melt_c    จุดหลอมเหลว °C — None = สลายตัว/ระเหิดก่อนหลอม (ดู note)
    setting   สภาพธรณีที่พบจริง (คีย์ใน SETTING_BIOMES)

**ไฟล์นี้เป็นข้อมูลล้วน ยังไม่ถูกเอนจินเรียกใช้** — การวางแหล่งแร่ (materials.materials_at) และพลังของ
อาวุธยังใช้กฎเดิม จึงไม่เปลี่ยนผลของซิม
"""
from . import crafting as CR

REAL_MINERALS = {
    # ---- โลกมนุษย์ (ชั้น 0): แร่เหล็กและทองแดงที่มนุษย์ถลุงได้จริงตั้งแต่ยุคโบราณ
    "แร่เหล็กไหลแท้": dict(mineral="แมกนีไทต์", en="magnetite", formula="Fe3O4",
                             mohs=6.0, density=5.17, melt_c=1597, setting="igneous",
                             note="แร่เหล็กที่เป็นแม่เหล็กในตัว"),
    "แร่เหล็กดำทมิฬ": dict(mineral="ฮีมาไทต์", en="hematite", formula="Fe2O3",
                            mohs=6.0, density=5.26, melt_c=1565, setting="sedimentary",
                            note="แร่เหล็กหลักของโลก ผงสีแดงเลือด"),
    "ทองเหลืองอุ่นดารา": dict(mineral="คาลโคไพไรต์", en="chalcopyrite", formula="CuFeS2",
                               mohs=3.75, density=4.2, melt_c=950, setting="hydrothermal",
                               note="สีเหลืองทองเหลือง แร่ทองแดงที่พบมากที่สุด"),
    "แร่เหล็กกล้าร้อยพับ": dict(mineral="ซิเดอไรต์", en="siderite", formula="FeCO3",
                                 mohs=4.0, density=3.96, melt_c=None, setting="sedimentary",
                                 note="สลายตัวเป็นเหล็กออกไซด์เมื่อเผา ก่อนจะหลอม"),
    "เศษทองแดงคราม": dict(mineral="อะซูไรต์", en="azurite", formula="Cu3(CO3)2(OH)2",
                            mohs=3.75, density=3.77, melt_c=None, setting="oxidized",
                            note="สีครามเข้ม เกิดจากแร่ทองแดงผุพัง สลายตัวเมื่อเผา"),
    # ---- แดนเซียน (ชั้น 1): โลหะธรรมชาติและหยก
    "หินหยกครามเซียน": dict(mineral="เนไฟรต์ (หยก)", en="nephrite", formula="Ca2(Mg,Fe)5Si8O22(OH)2",
                              mohs=6.25, density=2.98, melt_c=None, setting="metamorphic",
                              note="เหนียวที่สุดในบรรดาหินธรรมชาติ แตกยากกว่าเหล็กกล้า"),
    "แร่เหล็กสายฟ้าเซียน": dict(mineral="เหล็กอุกกาบาต", en="meteoric iron", formula="Fe-Ni",
                                 mohs=4.0, density=7.9, melt_c=1500, setting="impact",
                                 note="เหล็กผสมนิกเกิลจากฟ้า โลหะเหล็กชนิดแรกที่มนุษย์ใช้"),
    "แร่เหล็กไหลคราม": dict(mineral="อิลเมไนต์", en="ilmenite", formula="FeTiO3",
                              mohs=5.5, density=4.72, melt_c=1365, setting="igneous",
                              note="แร่ไทเทเนียม พบสะสมในทรายดำ"),
    "ทองคำเซียนบริสุทธิ์": dict(mineral="ทองคำธรรมชาติ", en="native gold", formula="Au",
                                 mohs=2.75, density=19.3, melt_c=1064, setting="hydrothermal",
                                 note="อ่อน หนักมาก ไม่หมอง พบในสายแร่ควอตซ์และตะกอนแม่น้ำ"),
    "แผ่นทองแดงลม": dict(mineral="ทองแดงธรรมชาติ", en="native copper", formula="Cu",
                           mohs=2.75, density=8.96, melt_c=1085, setting="volcanic",
                           note="นำความร้อนและไฟฟ้าดีเยี่ยม พบในหินบะซอลต์"),
    # ---- สวรรค์นอกชั้นฟ้า (ชั้น 2): ธาตุหายากและสุดขั้ว
    "แก่นแร่เหล็กดารานิรันดร์": dict(mineral="วุลแฟรไมต์", en="wolframite", formula="(Fe,Mn)WO4",
                                      mohs=4.25, density=7.3, melt_c=None, setting="hydrothermal",
                                      note="แร่ทังสเตน โลหะที่จุดหลอมเหลวสูงสุด (3,422 °C)"),
    "ผลึกแก่นแสงดาวฤกษ์": dict(mineral="ฟลูออไรต์", en="fluorite", formula="CaF2",
                                 mohs=4.0, density=3.18, melt_c=1418, setting="hydrothermal",
                                 note="เรืองแสงใต้แสงเหนือม่วง ที่มาของคำว่า fluorescence"),
    "แร่หินธาตุมืดปฐพี": dict(mineral="ยูเรนิไนต์", en="uraninite", formula="UO2",
                               mohs=5.5, density=10.6, melt_c=2865, setting="igneous",
                               note="แร่ยูเรเนียม สีดำ หนัก แผ่รังสี"),
    "เหล็กไหลเงินอวกาศ": dict(mineral="แพลทินัมธรรมชาติ", en="native platinum", formula="Pt",
                               mohs=4.25, density=19.0, melt_c=1768, setting="igneous",
                               note="สีเงิน หนักกว่าทอง ไม่ทำปฏิกิริยา ทนไฟสูง"),
    "แร่วัชรเพชรสวรรค์": dict(mineral="เพชร", en="diamond", formula="C",
                               mohs=10.0, density=3.51, melt_c=None, setting="mantle",
                               note="แข็งที่สุดในธรรมชาติ เกิดลึกในเนื้อโลก ขึ้นมากับปล่องคิมเบอร์ไลต์"),
}

# สภาพธรณี -> biome ของ terrain.compute_place_3d_and_biome ที่เข้ากัน (ใช้เมื่อจะวางแหล่งแร่ตามธรณีวิทยา)
SETTING_BIOMES = {
    "igneous": ("mountains", "high_hills", "volcanic_crag"),            # หินอัคนี: เทือกเขา แกนภูเขาไฟ
    "volcanic": ("volcanic_crag", "ash_wastes"),                        # ลาวาบะซอลต์
    "hydrothermal": ("mountains", "high_hills", "volcanic_crag"),       # สายแร่น้ำร้อนในรอยแตกของหิน
    "sedimentary": ("plains", "steppe_grassland", "shallow_water", "blood_swamp"),   # ชั้นตะกอน แอ่ง บึง
    "oxidized": ("yellow_desert", "high_hills", "ash_wastes"),          # ส่วนผุพังเหนือสายแร่ ในที่แห้ง
    "metamorphic": ("mountains", "snow_peaks", "high_hills"),           # หินแปรในแนวเทือกเขา
    "impact": ("yellow_desert", "ash_wastes", "snow_peaks", "floating_sky_island"),  # หลุมอุกกาบาต ที่โล่งแห้ง/น้ำแข็ง
    "mantle": ("volcanic_crag", "mountains", "floating_jade_crag"),     # ปล่องจากเนื้อโลก
}


def real_of(name):
    """ข้อมูลแร่จริงของแร่ในเรื่อง — None ถ้าไม่ใช่แร่ (สมุนไพร แก่นพลัง)"""
    return REAL_MINERALS.get(name)


def fits_biome(name, biome):
    """แร่นี้พบในภูมิประเทศแบบนี้ได้จริงไหม — แร่ที่ไม่รู้จักถือว่าไม่จำกัด"""
    info = REAL_MINERALS.get(name)
    return True if info is None else biome in SETTING_BIOMES[info["setting"]]


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


assert set(REAL_MINERALS) == {n for n, _ in CR.ORES}, "แร่ในเรื่องกับตารางแร่จริงต้องตรงกันทุกชนิด"
