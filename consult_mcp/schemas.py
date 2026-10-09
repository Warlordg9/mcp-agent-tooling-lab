"""Описания и JSON-схемы инструментов `consult_*`.

Схемы написаны вручную: у каждого поля есть description, закрытые множества
заданы через enum, у каждого объекта additionalProperties: false. Эти же схемы
middleware сервера применяет к аргументам до вызова инструмента.
"""

from __future__ import annotations

from .data import FORMATS, TEACHER_IDS, TOPICS

DATE = {"type": "string", "pattern": r"^\d{4}-\d{2}-\d{2}$",
        "description": "День консультации в формате YYYY-MM-DD, например 2026-10-14. Расписание есть на 2026-10-12 — 2026-10-23."}
SLOT_ID = {"type": "string", "pattern": r"^s-\d{4}-[a-z]{3}-\d{4}$",
           "description": "Идентификатор слота из результата consult_search_slots, например s-1014-iva-1000."}
STUDENT_ID = {"type": "string", "pattern": r"^st-\d{4}$",
              "description": "Идентификатор студента, от чьего имени действует агент, например st-1001."}
BOOKING_ID = {"type": "string", "pattern": r"^b-[0-9a-f]{8}$",
              "description": "Handle брони, который вернул consult_book или consult_list_bookings, например b-1a2b3c4d."}
RESPONSE_FORMAT = {"type": "string", "enum": ["concise", "detailed"], "default": "concise",
                   "description": "concise — короткие строки с идентификаторами (по умолчанию, экономит токены); detailed — JSON со всеми полями: аудитория или ссылка, темы, вместимость, правила."}


def _obj(properties: dict, required: list[str]) -> dict:
    return {"type": "object", "properties": properties, "required": required, "additionalProperties": False}


TOOL_SPECS: dict[str, dict] = {
    "consult_search_slots": {
        "title": "Поиск слотов консультаций",
        "description": (
            "Ищет слоты консультаций преподавателей курса на один день с фильтрами по формату, теме и преподавателю. "
            "Используй, когда студент хочет найти свободное время консультации или выбрать слот перед записью. "
            "Не используй для записи (consult_book), для просмотра своих броней (consult_list_bookings) "
            "и для вопросов о расписании лекций, дедлайнах и оценках — этих данных здесь нет. "
            "Если на день ничего нет, ответ подскажет ближайшие дни со слотами."
        ),
        "annotations": {"readOnlyHint": True, "idempotentHint": True, "openWorldHint": False},
        "input_schema": _obj({
            "date": DATE,
            "format": {"type": "string", "enum": list(FORMATS),
                       "description": "Формат встречи: online (видеосвязь) или offline (аудитория). Не указывай, если формат не важен."},
            "topic": {"type": "string", "enum": list(TOPICS),
                      "description": "Тема: homework — домашние задания, project — курсовой проект, exam — подготовка к экзамену, lecture — вопросы по лекциям."},
            "teacher": {"type": "string", "enum": list(TEACHER_IDS),
                        "description": "Преподаватель по фамилии латиницей: ivanova, petrov, sidorova, kuznetsov, smirnova."},
            "only_free": {"type": "boolean", "default": True,
                          "description": "true — только слоты со свободными местами (по умолчанию); false — все слоты дня."},
            "limit": {"type": "integer", "minimum": 1, "maximum": 20, "default": 5,
                      "description": "Сколько слотов вернуть за раз, 1–20 (по умолчанию 5)."},
            "cursor": {"type": "string", "minLength": 1,
                       "description": "Handle следующей страницы (next_cursor из прошлого ответа с теми же фильтрами). Для первой страницы не передавай."},
            "response_format": RESPONSE_FORMAT,
        }, ["date"]),
    },
    "consult_get_slot": {
        "title": "Карточка слота",
        "description": (
            "Возвращает карточку одного слота по slot_id: время, длительность, формат, аудиторию или ссылку, темы и свободные места. "
            "Используй, чтобы уточнить детали уже найденного слота перед записью. "
            "Не используй для поиска по дате или преподавателю (consult_search_slots) и для статуса брони (consult_get_booking)."
        ),
        "annotations": {"readOnlyHint": True, "idempotentHint": True, "openWorldHint": False},
        "input_schema": _obj({"slot_id": SLOT_ID, "response_format": RESPONSE_FORMAT}, ["slot_id"]),
    },
    "consult_book": {
        "title": "Записать студента на слот",
        "description": (
            "Записывает студента на выбранный слот и возвращает booking_id и статус active. "
            "Используй только после того, как студент явно выбрал слот и подтвердил запись. "
            "Не используй для поиска времени (consult_search_slots), переноса без отмены старой брони и записи другого студента. "
            "Повтор с тем же idempotency_key не создаёт дубль."
        ),
        "annotations": {"readOnlyHint": False, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
        "input_schema": _obj({
            "slot_id": SLOT_ID,
            "student_id": STUDENT_ID,
            "topic": {"type": "string", "enum": list(TOPICS),
                      "description": "Тема консультации; должна входить в темы слота: homework, project, exam или lecture."},
            "idempotency_key": {"type": "string", "minLength": 8, "maxLength": 64,
                                "description": "Уникальная строка на одну попытку записи (8–64 символа). При повторе той же записи передай тот же ключ."},
            "response_format": RESPONSE_FORMAT,
        }, ["slot_id", "student_id", "topic", "idempotency_key"]),
    },
    "consult_get_booking": {
        "title": "Статус брони",
        "description": (
            "Возвращает бронь студента по booking_id: слот, тему и статус (active или cancelled). "
            "Используй, чтобы проверить результат consult_book или consult_cancel. "
            "Не используй для поиска свободных слотов и для списка всех броней (consult_list_bookings)."
        ),
        "annotations": {"readOnlyHint": True, "idempotentHint": True, "openWorldHint": False},
        "input_schema": _obj({"booking_id": BOOKING_ID, "student_id": STUDENT_ID, "response_format": RESPONSE_FORMAT},
                             ["booking_id", "student_id"]),
    },
    "consult_list_bookings": {
        "title": "Брони студента",
        "description": (
            "Показывает брони консультаций одного студента с фильтром по статусу. "
            "Используй, когда студент спрашивает, на какие консультации он записан, или нужно найти booking_id для отмены. "
            "Не используй для поиска свободного времени (consult_search_slots) и для броней других студентов."
        ),
        "annotations": {"readOnlyHint": True, "idempotentHint": True, "openWorldHint": False},
        "input_schema": _obj({
            "student_id": STUDENT_ID,
            "status": {"type": "string", "enum": ["active", "cancelled", "all"], "default": "active",
                       "description": "active — действующие брони (по умолчанию), cancelled — отменённые, all — все."},
            "response_format": RESPONSE_FORMAT,
        }, ["student_id"]),
    },
    "consult_cancel": {
        "title": "Отменить бронь",
        "description": (
            "Отменяет бронь студента по booking_id и освобождает место. "
            "Используй только по явной просьбе студента отменить свою запись. "
            "Не используй для чужих броней, для проверки статуса (consult_get_booking) и как первый шаг переноса без согласия студента."
        ),
        "annotations": {"readOnlyHint": False, "destructiveHint": True, "idempotentHint": False, "openWorldHint": False},
        "input_schema": _obj({"booking_id": BOOKING_ID, "student_id": STUDENT_ID, "response_format": RESPONSE_FORMAT},
                             ["booking_id", "student_id"]),
    },
}
