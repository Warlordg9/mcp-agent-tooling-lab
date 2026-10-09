"""Вымышленное расписание консультаций курса (детерминированная генерация).

Две учебные недели: пн 2026-10-12 — пт 2026-10-23. У каждого преподавателя
свои дни, формат и темы. Слоты — интервалы [start, start + duration).
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import date, timedelta

TOPICS = ("homework", "project", "exam", "lecture")
TOPIC_TITLES = {
    "homework": "домашние задания",
    "project": "курсовой проект",
    "exam": "подготовка к экзамену",
    "lecture": "вопросы по лекциям",
}
FORMATS = ("online", "offline")

FIRST_DAY = date(2026, 10, 12)
LAST_DAY = date(2026, 10, 23)


@dataclass(frozen=True)
class Teacher:
    teacher_id: str
    name: str
    weekdays: tuple[int, ...]  # 0 = понедельник
    formats: tuple[str, ...]
    topics: tuple[str, ...]
    room: str
    starts: tuple[str, ...]
    duration_min: int
    capacity: int


TEACHERS: tuple[Teacher, ...] = (
    Teacher("ivanova", "Иванова Анна Сергеевна", (0, 2), ("online", "offline"),
            ("homework", "lecture"), "ауд. 1201", ("10:00", "10:30", "11:00"), 30, 2),
    Teacher("petrov", "Петров Борис Николаевич", (1, 3), ("offline",),
            ("project", "exam"), "ауд. 914", ("14:00", "14:30", "15:00", "15:30"), 30, 1),
    Teacher("sidorova", "Сидорова Вера Игоревна", (0, 3, 4), ("online",),
            ("homework", "exam", "lecture"), "", ("18:00", "18:20", "18:40"), 20, 3),
    Teacher("kuznetsov", "Кузнецов Глеб Олегович", (2, 4), ("offline", "online"),
            ("project", "homework"), "ауд. 532", ("12:00", "12:45"), 45, 2),
    Teacher("smirnova", "Смирнова Дарья Павловна", (1, 4), ("online",),
            ("lecture", "exam"), "", ("09:00", "09:15", "09:30", "09:45"), 15, 1),
)
TEACHER_IDS = tuple(t.teacher_id for t in TEACHERS)


@dataclass
class Slot:
    slot_id: str
    date: str
    start: str
    duration_min: int
    format: str
    teacher_id: str
    topics: tuple[str, ...]
    capacity: int
    location: str
    booked: int = 0
    notes: str = field(default="")

    @property
    def end(self) -> str:
        h, m = map(int, self.start.split(":"))
        total = h * 60 + m + self.duration_min
        return f"{total // 60:02d}:{total % 60:02d}"

    @property
    def free(self) -> int:
        return self.capacity - self.booked


def generate_slots(seed: int = 2026) -> dict[str, Slot]:
    """Детерминированно строит слоты; часть мест уже занята другими студентами."""
    rng = random.Random(seed)
    slots: dict[str, Slot] = {}
    day = FIRST_DAY
    while day <= LAST_DAY:
        for t in TEACHERS:
            if day.weekday() not in t.weekdays:
                continue
            fmt = t.formats[(day.toordinal() // 7) % len(t.formats)]
            for start in t.starts:
                sid = f"s-{day:%m%d}-{t.teacher_id[:3]}-{start.replace(':', '')}"
                location = (f"https://meet.example.edu/{t.teacher_id}" if fmt == "online" else t.room)
                slots[sid] = Slot(
                    slot_id=sid, date=day.isoformat(), start=start, duration_min=t.duration_min,
                    format=fmt, teacher_id=t.teacher_id, topics=t.topics, capacity=t.capacity,
                    location=location, booked=rng.choice(range(t.capacity + 1)),
                    notes="Возьмите с собой вопросы заранее; опоздание более 5 минут — слот сгорает.",
                )
        day += timedelta(days=1)
    return slots


def teacher_by_id(teacher_id: str) -> Teacher | None:
    return next((t for t in TEACHERS if t.teacher_id == teacher_id), None)
