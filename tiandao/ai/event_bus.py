# -*- coding: utf-8 -*-
"""Event Bus แบบ pub/sub เบาๆ — ห่อเข้ากับ Sim.emit() จุดเดียว (tiandao/sim.py) โดยไม่แตะจุดที่เรียก
self.emit(...) อีก ~40 จุดทั่ว sim.py เลย

Subscriber ทำงานหลังจาก event ถูก log แล้วเสมอ ถ้า handler ใดพัง จะไม่ทำให้ step() หลักของซิมพัง
ตามไปด้วย — log ข้อผิดพลาดแล้วให้ subscriber ตัวถัดไปทำงานต่อ
"""
import logging
from typing import TYPE_CHECKING, Callable, List

if TYPE_CHECKING:
    from ..models import Event
    from ..sim import Sim

logger = logging.getLogger(__name__)

EventHandler = Callable[["Event", "Sim"], None]


class EventBus:
    def __init__(self) -> None:
        self._subscribers: List[EventHandler] = []

    def subscribe(self, handler: EventHandler) -> None:
        """ลงทะเบียน handler(event, sim) — เรียกทุกครั้งที่มี event ใหม่ถูก publish"""
        self._subscribers.append(handler)

    def publish(self, event: "Event", sim: "Sim") -> None:
        for handler in self._subscribers:
            try:
                handler(event, sim)
            except Exception:
                logger.exception(
                    "event_bus: handler ล้มเหลวสำหรับ event kind=%s (seq=%s)",
                    event.kind, event.seq,
                )
