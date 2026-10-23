# -*- coding: utf-8 -*-
import collections
import copy
import heapq
import math
import random

from .. import config as C
from .. import events as E
from .. import branches as BR
from .. import portals as PORT
from .. import worldtree as WT
from .. import paths as PATHS
from .. import crises as CRISES
from .. import rules as R
from ..models import ActionProcess, Cache, Character, Departed, Event, Item, Org, World
from ..treasures import TREASURES, BURST_MULT
from .. import skills as SK
from .. import crafting as CR
from .. import materials as MAT
from .. import minerals as MIN
from .. import physics as PHYS
from .. import elements as EL
from .. import economy as EC
from .. import geo as GEO
from .. import noise as NZ
from .. import places as PL
from .. import clans as CL
from .. import intent as IN
from .. import travel as TR
from .. import settlement as SETTLE
from .. import chronicle as CH
from .. import seasons as SEASONS
from .. import news as NEWS
from .. import emotions as EM
from .. import body as BODY
from .. import childhood as CHILD
from .. import household as HH
from .. import food as FOOD
from .. import wages as WAGES
from .. import guardians as GUARD
from .. import death as DEATH
from ..ai import BrainManager, EventBus
from ..console import safe_print

# โอกาสพบกันตามระยะทาง คิดครั้งเดียวต่อสถานที่ต้นทาง; จำนวนใช้ PL.PLACES ปัจจุบันแบบ dynamic
# อยู่ระดับโมดูล ไม่ใช่บน Sim เพราะ Sim ถูก pickle ทั้งก้อน (ดู persist.py) ไม่ควรพกแคชไปด้วย
_REACH_CACHE = {}


def _reach_from(place):
    """place ปลายทาง -> โอกาสที่คนที่อยู่ตรงนั้นจะ 'พบได้' จาก place ต้นทางนี้ (0..1)"""
    cached = _REACH_CACHE.get(place)
    if cached is None:
        scale = max(1e-6, C.SOCIAL_RANGE)
        cached = {pl: math.exp(-d / scale) for pl, d in TR.distances_from(place).items()}
        _REACH_CACHE[place] = cached
    return cached


def _auction_q(value: float) -> float:
    """ปัดราคาประมูล **ลง** ให้เหลือทศนิยมเท่าที่บันทึกแสดงจริง (C.AUCTION_PRICE_DP)

    งานประมูลมีตัวเลขสามที่ต้องเป็นค่าเดียวกันเสมอ: เงินที่ย้ายมือจริง ตัวเลขใน deltas
    และราคาที่เขียนในบันทึก ถ้าโอนด้วยทศนิยมเต็มแต่รายงานแค่หนึ่งตำแหน่ง บัญชีของเจ้าภาพกับ
    ผู้ชนะจะไม่ตรงกับราคาที่ประกาศ (วัดจริง: ต่างกัน 0.0467 หน่วยปราณ) การตรวจบัญชีย้อนหลัง
    จากบันทึกจึงทำไม่ได้เลย

    ปัดลงไม่ใช่ปัดใกล้สุด เพราะราคาต้องไม่ทะลุเพดานสองอันของกติกาวิกเครย์:
    ต้องไม่เกินมูลค่าในใจของผู้ชนะ และไม่เกินราคาอันดับสองคูณก้าวราคา
    """
    step = 10.0 ** C.AUCTION_PRICE_DP
    return math.floor(max(0.0, value) * step) / step


def city_office(type_desc):
    """ตำแหน่งผู้ปกครองของเมืองแต่ละแบบ — ความเข้มงวดของกฎเมือง ตำแหน่ง ฝ่าย ชื่อตั้งต้น และขั้นของเจ้าเมืองคนแรก
    (persist._cities_into_save ใช้หาเจ้าเมืองคืนจากตำแหน่งในเซฟก่อนรุ่น 15)"""
    if "เมืองหลวง" in type_desc:
        return dict(strictness=90, title="ฮ่องเต้", faction="ราชสำนัก", name="หมิงหยวนตี้", realm=6)
    if "ชายแดน" in type_desc:
        return dict(strictness=80, title="แม่ทัพใหญ่", faction="กองทัพทหารม้าเหล็ก", name="เฉินเฟิง", realm=5)
    if "หน้าด่านสำนัก" in type_desc:
        return dict(strictness=40, title="ตัวแทนสำนัก", faction="พันธมิตรยุทธ", name="เย่ฟาน", realm=7)
    if "ลับแล" in type_desc or "เถื่อน" in type_desc or "ตลาดมืด" in type_desc:
        return dict(strictness=10, title="ราชาตลาดมืด", faction="สมาคมนักฆ่า", name="เงาทมิฬ", realm=8)
    return dict(strictness=50, title="นายอำเภอ", faction="ราชสำนัก", name="หวังป๋อ", realm=3)


_PLACE_SETS = {}   # ผัง -> frozenset ของสถานที่ (Sim._places_of)
_CENTERS = {}      # ผัง -> สถานที่ศูนย์กลาง (Sim._world_center)
