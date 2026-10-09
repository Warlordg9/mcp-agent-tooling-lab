"""Хранилище слотов и броней.

Сервер не хранит сессий: всё состояние лежит здесь и адресуется явными
handle-аргументами (`booking_id`, `student_id`, `cursor`). Любой запрос можно
повторить на любом экземпляре сервера, если у них общий файл состояния.
"""

from __future__ import annotations

import json
import os
import threading
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path

from .data import Slot, generate_slots


@dataclass
class Booking:
    booking_id: str
    slot_id: str
    student_id: str
    topic: str
    idempotency_key: str
    status: str  # active | cancelled


class DomainError(Exception):
    """Ошибка предметной области: текст уходит модели как результат с isError."""

    def __init__(self, problem: str, fix: str):
        super().__init__(f"{problem} Как исправить: {fix}")


def _overlaps(a: Slot, b: Slot) -> bool:
    """Интервалы [s, s + d): соседние слоты не пересекаются."""
    if a.date != b.date:
        return False
    a0 = int(a.start[:2]) * 60 + int(a.start[3:])
    b0 = int(b.start[:2]) * 60 + int(b.start[3:])
    return a0 < b0 + b.duration_min and b0 < a0 + a.duration_min


class Store:
    def __init__(self, state_file: str | os.PathLike[str] | None = None, seed: int = 2026):
        self._lock = threading.Lock()
        self.slots: dict[str, Slot] = generate_slots(seed)
        self.bookings: dict[str, Booking] = {}
        self._state_file = Path(state_file) if state_file else None
        if self._state_file and self._state_file.exists():
            self._load()

    # --- persistence -----------------------------------------------------
    def _load(self) -> None:
        raw = json.loads(self._state_file.read_text(encoding="utf-8"))
        self.bookings = {b["booking_id"]: Booking(**b) for b in raw["bookings"]}
        for b in self.bookings.values():
            if b.status == "active":
                self.slots[b.slot_id].booked += 1

    def _save(self) -> None:
        if self._state_file:
            data = {"bookings": [asdict(b) for b in self.bookings.values()]}
            self._state_file.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")

    # --- queries ---------------------------------------------------------
    def get_slot(self, slot_id: str) -> Slot:
        slot = self.slots.get(slot_id)
        if slot is None:
            raise DomainError(
                f"Слот {slot_id!r} не найден.",
                "возьмите slot_id из результата consult_search_slots (формат s-MMDD-xxx-HHMM, например s-1014-iva-1000).",
            )
        return slot

    def get_booking(self, booking_id: str, student_id: str) -> Booking:
        booking = self.bookings.get(booking_id)
        if booking is None:
            raise DomainError(
                f"Бронь {booking_id!r} не найдена.",
                "используйте booking_id из ответа consult_book или consult_list_bookings.",
            )
        if booking.student_id != student_id:
            raise DomainError(
                f"Бронь {booking_id!r} принадлежит другому студенту.",
                "работать можно только со своими бронями: передайте student_id владельца или найдите свои брони через consult_list_bookings.",
            )
        return booking

    # --- commands --------------------------------------------------------
    def book(self, slot_id: str, student_id: str, topic: str, idempotency_key: str) -> tuple[Booking, bool]:
        """Возвращает (бронь, created). Повтор с тем же ключом не создаёт дубль."""
        with self._lock:
            for b in self.bookings.values():
                if b.idempotency_key == idempotency_key:
                    if (b.slot_id, b.student_id, b.topic) == (slot_id, student_id, topic):
                        return b, False
                    raise DomainError(
                        f"idempotency_key {idempotency_key!r} уже использован для другой брони ({b.booking_id}).",
                        "для новой брони сгенерируйте новый ключ; для повтора той же брони передайте те же slot_id, student_id и topic.",
                    )
            slot = self.get_slot(slot_id)
            if topic not in slot.topics:
                raise DomainError(
                    f"Тема {topic!r} не принимается в слоте {slot_id}.",
                    f"выберите одну из тем слота: {', '.join(slot.topics)}, или найдите слот с этой темой через consult_search_slots(topic={topic!r}).",
                )
            if slot.free <= 0:
                raise DomainError(
                    f"В слоте {slot_id} нет свободных мест.",
                    "вызовите consult_search_slots на ту же дату и выберите слот со свободными местами.",
                )
            for b in self.bookings.values():
                if b.student_id == student_id and b.status == "active":
                    if b.slot_id == slot_id:
                        raise DomainError(
                            f"Студент {student_id} уже записан на {slot_id} (бронь {b.booking_id}).",
                            "повторная запись не нужна; проверьте её через consult_get_booking.",
                        )
                    if _overlaps(self.slots[b.slot_id], slot):
                        raise DomainError(
                            f"Слот {slot_id} пересекается по времени с бронью {b.booking_id} ({b.slot_id}).",
                            "выберите другое время или сначала отмените старую бронь (consult_cancel) с согласия студента.",
                        )
            booking = Booking(
                booking_id=f"b-{uuid.uuid4().hex[:8]}", slot_id=slot_id, student_id=student_id,
                topic=topic, idempotency_key=idempotency_key, status="active",
            )
            self.bookings[booking.booking_id] = booking
            slot.booked += 1
            self._save()
            return booking, True

    def cancel(self, booking_id: str, student_id: str) -> Booking:
        with self._lock:
            booking = self.get_booking(booking_id, student_id)
            if booking.status == "cancelled":
                raise DomainError(
                    f"Бронь {booking_id} уже отменена.",
                    "повторная отмена не нужна; актуальные брони покажет consult_list_bookings.",
                )
            booking.status = "cancelled"
            self.slots[booking.slot_id].booked -= 1
            self._save()
            return booking
