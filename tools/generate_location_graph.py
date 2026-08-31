# -*- coding: utf-8 -*-
"""Generator tool for tiandao world geography (tiandao/geo.py) from tiandao/places.py.

Usage:
    python tools/generate_location_graph.py
"""
import math
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tiandao import places as PL

realm_centers = {
    0: (0.0, 0.0),             # โลกมนุษย์ (Mortal Realm - Center)
    "siam": (-180.0, -120.0),   # แดนสยาม (Siam - South West)
    "bharata": (-40.0, -220.0), # แดนชมพูทวีป (Bharata / Vedic - South)
    "oasis": (-240.0, 40.0),    # แดนโอเอซิสพันราตรี (Oasis / Silk Road - West)
    "steppe": (-20.0, 220.0),   # แดนทุ่งหญ้าคีตาวายุ (Steppe - North)
    "fusang": (200.0, -40.0),   # แดนอาทิตย์อุทัย (Fusang / Yamato - East)
    1: (350.0, 180.0),         # แดนเซียน (Immortal Realm - North East Sky)
    2: (650.0, 320.0),         # สวรรค์นอกชั้นฟ้า (Heaven - Highest Sky)
    "mara": (240.0, -260.0),    # แดนมาร (Mara Realm - South East Abyss)
    "chaos": (520.0, -120.0),   # ที่กบดานเผ่าโกลาหล (Chaos Realm - Void)
}


def layout_coords():
    coords = []
    for i, p in enumerate(PL.PLACES):
        name, w, grade, ptype, res, furn, sec_parent, is_sealed = p
        cx, cy = realm_centers[w]
        
        if w == 0:
            if ptype == "แดนลับ":
                angle = (i * 2.1) % (2 * math.pi)
                r = 75.0 + (grade * 20.0)
                x = cx + r * math.cos(angle)
                y = cy + r * math.sin(angle)
            elif ptype == "ประตูมิติ":
                x = cx + 60.0
                y = cy + 55.0
            else:
                angle = (i * 1.37) % (2 * math.pi)
                r = 15.0 + (i % 5) * 11.0 + (2 - grade) * 8.0
                x = cx + r * math.cos(angle)
                y = cy + r * math.sin(angle)
                
        elif w in ("siam", "fusang", "steppe", "oasis", "bharata"):
            if ptype == "แดนลับ":
                angle = (i * 2.4) % (2 * math.pi)
                r = 70.0 + (grade * 12.0)
                x = cx + r * math.cos(angle)
                y = cy + r * math.sin(angle)
            elif ptype == "ด่านชายแดน":
                # ปลายทางหันหน้าเข้าหาโลกมนุษย์ (0, 0)
                dx = (0.0 - cx) * 0.45
                dy = (0.0 - cy) * 0.45
                offset = ((i % 3) - 1) * 15.0
                x = cx + dx + offset
                y = cy + dy - offset
            elif ptype == "ประตูมิติ":
                dx = (0.0 - cx) * 0.35
                dy = (0.0 - cy) * 0.35
                x = cx + dx + 10.0
                y = cy + dy + 10.0
            else:
                angle = (i * 1.45) % (2 * math.pi)
                r = 12.0 + (i % 4) * 13.0 + (2 - grade) * 9.0
                x = cx + r * math.cos(angle)
                y = cy + r * math.sin(angle)
                
        elif w == 1:
            if ptype == "แดนลับ":
                angle = (i * 1.9) % (2 * math.pi)
                r = 80.0 + (grade * 15.0)
                x = cx + r * math.cos(angle)
                y = cy + r * math.sin(angle)
            elif ptype == "ประตูมิติ":
                if "เซียนมาร" in name:
                    x = cx - 20.0
                    y = cy - 65.0
                elif "หมื่นดารา" in name:
                    x = cx + 45.0
                    y = cy + 45.0
                else:
                    x = cx - 55.0 + (i % 2) * 20.0
                    y = cy - 20.0 + (i % 2) * 25.0
            else:
                angle = (i * 1.33) % (2 * math.pi)
                r = 14.0 + (i % 5) * 12.0 + (2 - grade) * 8.0
                x = cx + r * math.cos(angle)
                y = cy + r * math.sin(angle)
                
        elif w == 2:
            if ptype == "แดนลับ":
                angle = (i * 2.3) % (2 * math.pi)
                r = 85.0 + (grade * 15.0)
                x = cx + r * math.cos(angle)
                y = cy + r * math.sin(angle)
            elif ptype == "ประตูมิติ":
                x = cx - 60.0 + (i % 2) * 15.0
                y = cy - 40.0 + (i % 2) * 20.0
            else:
                angle = (i * 1.25) % (2 * math.pi)
                r = 15.0 + (i % 5) * 12.0 + (2 - grade) * 8.0
                x = cx + r * math.cos(angle)
                y = cy + r * math.sin(angle)
                
        elif w == "mara":
            if ptype == "แดนลับ":
                if is_sealed:
                    x = (realm_centers["mara"][0] + realm_centers[0][0]) * 0.5
                    y = (realm_centers["mara"][1] + realm_centers[0][1]) * 0.5
                else:
                    angle = (i * 2.0) % (2 * math.pi)
                    r = 80.0 + (grade * 15.0)
                    x = cx + r * math.cos(angle)
                    y = cy + r * math.sin(angle)
            elif ptype == "ประตูมิติ":
                x = cx + 10.0
                y = cy + 60.0
            else:
                angle = (i * 1.35) % (2 * math.pi)
                r = 14.0 + (i % 5) * 13.0 + (2 - grade) * 8.0
                x = cx + r * math.cos(angle)
                y = cy + r * math.sin(angle)
                
        elif w == "chaos":
            if ptype == "แดนลับ":
                angle = (i * 2.2) % (2 * math.pi)
                r = 80.0
                x = cx + r * math.cos(angle)
                y = cy + r * math.sin(angle)
            elif ptype == "ประตูมิติ":
                x = cx + 15.0
                y = cy + 40.0
            else:
                angle = (i * 1.4) % (2 * math.pi)
                r = 15.0 + (i % 3) * 15.0
                x = cx + r * math.cos(angle)
                y = cy + r * math.sin(angle)
                
        coords.append((round(x, 2), round(y, 2)))
    return coords


def build_all_edges(coords):
    name_to_idx = {p[0]: i for i, p in enumerate(PL.PLACES)}
    edges_set = set()
    edges_list = []

    def dist(i, j):
        x1, y1 = coords[i]
        x2, y2 = coords[j]
        return round(math.sqrt((x1 - x2) ** 2 + (y1 - y2) ** 2), 2)

    def add_edge(i, j, edge_type="road", traversable=True):
        if i == j or i is None or j is None:
            return
        a, b = min(i, j), max(i, j)
        if (a, b) not in edges_set:
            d = dist(a, b)
            edges_set.add((a, b))
            edges_list.append((a, b, d, edge_type, traversable))

    # 1. Intra-realm regular edges
    realm_places = {}
    for i, p in enumerate(PL.PLACES):
        w = p[1]
        ptype = p[3]
        if ptype != "แดนลับ":
            realm_places.setdefault(w, []).append(i)

    for w, indices in realm_places.items():
        for i in indices:
            neighbors = sorted([j for j in indices if j != i], key=lambda j: dist(i, j))[:3]
            for nb in neighbors:
                add_edge(i, nb, "road", True)

    # 2. Secret realms
    for i, p in enumerate(PL.PLACES):
        if p[3] == "แดนลับ":
            parent_realm = p[6]
            is_sealed = p[7]
            if not is_sealed:
                eligible = [j for j in realm_places.get(parent_realm, []) if PL.PLACES[j][3] != "แดนลับ"]
                if eligible:
                    nearest = sorted(eligible, key=lambda j: dist(i, j))[:2]
                    for nb in nearest:
                        add_edge(i, nb, "secret", True)
            else:
                mara_nodes = realm_places.get("mara", [])
                mortal_nodes = realm_places.get(0, [])
                if mara_nodes and mortal_nodes:
                    nearest_mara = sorted(mara_nodes, key=lambda j: dist(i, j))[0]
                    nearest_mortal = sorted(mortal_nodes, key=lambda j: dist(i, j))[0]
                    add_edge(i, nearest_mara, "sealed_barrier", False)
                    add_edge(i, nearest_mortal, "sealed_barrier", False)

    # 3. Border edges (Sister Cultural Realms <-> Mortal Realm)
    # Mortal hubs
    mortal_port = name_to_idx.get("เมืองท่าสัตตบงกช")
    mortal_fort = name_to_idx.get("เมืองหน้าด่านทลายศิลา")
    mortal_market = name_to_idx.get("ตลาดมืดรุ่งอรุณ")
    mortal_sand = name_to_idx.get("เมืองทรายเหลือง")

    # Siam
    if "ริมฝั่งแม่น้ำเจ้าพระยาโบราณ" in name_to_idx:
        add_edge(name_to_idx["ริมฝั่งแม่น้ำเจ้าพระยาโบราณ"], mortal_port, "border", True)
        add_edge(name_to_idx["ด่านช่องเขาพรมแดนสยามมนุษย์"], mortal_fort, "border", True)
        add_edge(name_to_idx["ตลาดน้ำรุ่งอรุณ"], mortal_market, "border", True)

    # Fusang
    if "เมืองท่าข้ามสมุทรอาทิตย์อุทัย" in name_to_idx:
        add_edge(name_to_idx["เมืองท่าข้ามสมุทรอาทิตย์อุทัย"], mortal_port, "border", True)
        add_edge(name_to_idx["ตลาดการค้าท่าเรือคาวาซากิ"], mortal_market, "border", True)

    # Steppe
    if "ด่านช่องเขาพายุหมื่นลี้" in name_to_idx:
        add_edge(name_to_idx["ด่านช่องเขาพายุหมื่นลี้"], mortal_fort, "border", True)
        add_edge(name_to_idx["ตลาดแลกเปลี่ยนม้าศึกและหนังสัตว์"], mortal_market, "border", True)

    # Oasis
    if "ด่านประตูดวงดารากลางทะเลทราย" in name_to_idx:
        add_edge(name_to_idx["ด่านประตูดวงดารากลางทะเลทราย"], mortal_sand or mortal_market, "border", True)
        add_edge(name_to_idx["ตลาดบาซาร์เครื่องเทศและอาวุธเวท"], mortal_market, "border", True)

    # Bharata
    if "ด่านข้ามลำน้ำคงคาพรมแดน" in name_to_idx:
        add_edge(name_to_idx["ด่านข้ามลำน้ำคงคาพรมแดน"], mortal_port, "border", True)
        if "ริมฝั่งแม่น้ำเจ้าพระยาโบราณ" in name_to_idx:
            add_edge(name_to_idx["ด่านข้ามลำน้ำคงคาพรมแดน"], name_to_idx["ริมฝั่งแม่น้ำเจ้าพระยาโบราณ"], "border", True)
        if "ตลาดน้ำรุ่งอรุณ" in name_to_idx:
            add_edge(name_to_idx["ตลาดสังฆภัณฑ์และตำราพระเวท"], name_to_idx["ตลาดน้ำรุ่งอรุณ"], "border", True)

    # 4. Gate edges
    # Mortal <-> Immortal
    mortal_gate_immortal = name_to_idx.get("แท่นศิลาทะยานเซียน")
    if mortal_gate_immortal is not None:
        if "ประตูสัจธรรมร่วงหล่น" in name_to_idx:
            add_edge(mortal_gate_immortal, name_to_idx["ประตูสัจธรรมร่วงหล่น"], "gate", True)
        if "บ่อน้ำพุคืนสู่สามัญ" in name_to_idx:
            add_edge(mortal_gate_immortal, name_to_idx["บ่อน้ำพุคืนสู่สามัญ"], "gate", True)

    # Immortal <-> Heaven
    immortal_gate_heaven = name_to_idx.get("ประตูหมื่นดาราทะยานสวรรค์")
    if immortal_gate_heaven is not None:
        if "รอยแยกอวกาศดับสูญ" in name_to_idx:
            add_edge(immortal_gate_heaven, name_to_idx["รอยแยกอวกาศดับสูญ"], "gate", True)
        if "เสาเวทกาลเวลากลับด้าน" in name_to_idx:
            add_edge(immortal_gate_heaven, name_to_idx["เสาเวทกาลเวลากลับด้าน"], "gate", True)

    # Mara <-> Immortal
    if "ประตูทมิฬข้ามภพเซียน" in name_to_idx and "สะพานเชื่อมมิติเซียนมาร" in name_to_idx:
        add_edge(name_to_idx["ประตูทมิฬข้ามภพเซียน"], name_to_idx["สะพานเชื่อมมิติเซียนมาร"], "gate", True)

    # Chaos <-> Heaven
    if "รูหนอนบิดเบี้ยวมิติมืด" in name_to_idx and "รอยแยกมิติอวกาศลึก" in name_to_idx:
        add_edge(name_to_idx["รูหนอนบิดเบี้ยวมิติมืด"], name_to_idx["รอยแยกมิติอวกาศลึก"], "gate", True)

    # Sister Realms Gates -> Mortal Gate
    if mortal_gate_immortal is not None:
        for gate_name in [
            "ประตูมิติทวาราวดีข้ามภพ",
            "ประตูเสาโทริอิสวรรค์ข้ามภพ",
            "ประตูเสาอินทรีเหินข้ามภพ",
            "ประตูตะเกียงวิเศษข้ามภพ",
            "ประตูดอกบัวสหัสวรรษข้ามภพ"
        ]:
            if gate_name in name_to_idx:
                add_edge(name_to_idx[gate_name], mortal_gate_immortal, "gate", True)

    return edges_list


def main():
    coords = layout_coords()
    edges = build_all_edges(coords)

    out_path = Path(__file__).resolve().parent.parent / "tiandao" / "geo.py"
    lines = []
    lines.append("# -*- coding: utf-8 -*-")
    lines.append('"""Static geography for tiandao/places.py — GENERATED by tools/generate_location_graph.py.')
    lines.append("")
    lines.append("Do not hand-edit. Re-run the generator (only if places.PLACES changes) to regenerate.")
    lines.append("")
    lines.append("COORDS[i] is the 2D layout position of PLACES[i].")
    lines.append("EDGES is the road-network graph: (place_a, place_b, distance, edge_type, traversable).")
    lines.append('edge_type: "road", "border", "gate", "secret", "sealed_barrier"')
    lines.append("traversable: True / False (เช่น ผนึกมาร-มนุษย์ เป็น False ข้ามไม่ได้)")
    lines.append('"""')
    lines.append("")
    lines.append("COORDS = [")
    for c in coords:
        lines.append(f"    {c!r},")
    lines.append("]")
    lines.append("")
    lines.append("# (place_a, place_b, distance, edge_type, traversable) — undirected, place_a < place_b")
    lines.append("EDGES = [")
    for e in edges:
        lines.append(f"    {e!r},")
    lines.append("]")
    lines.append("")

    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {out_path} — {len(coords)} coords, {len(edges)} edges")


if __name__ == "__main__":
    main()
