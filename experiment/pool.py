"""Пул из 100 инструментов для эксперимента «выбор из N».

* own (6) — инструменты сервера consult_mcp, описания и схемы берутся из него;
* near (25) — сгенерированные отвлекающие, близкие по смыслу (учёба, расписание,
  календари, запись и бронирование);
* public (69) — описания инструментов публичных MCP-серверов (reference servers
  modelcontextprotocol/servers и популярные сторонние: filesystem, git, github,
  slack, sqlite, postgres, memory, fetch, brave-search, puppeteer, google-maps,
  time, sequential-thinking, notion, linear, sentry, gdrive). Имена инструментов
  настоящие; тексты описаний — пересказ по памяти, сокращённый до 1–2 фраз.
  Инструменты не исполняются, используются только описания.

Запуск: python experiment/pool.py  ->  experiment/data/tool_pool.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from consult_mcp.schemas import TOOL_SPECS  # noqa: E402

S, I, B = "string", "integer", "boolean"

# (name, description, {param: (type, description)}, required)
NEAR = [
    ("course_get_lecture_schedule", "Возвращает расписание лекций и семинаров курса на неделю: время, аудитория, лектор.",
     {"week": (I, "Номер учебной недели")}, ["week"]),
    ("course_get_deadlines", "Показывает дедлайны домашних заданий и проекта курса.",
     {"student_id": (S, "Идентификатор студента")}, []),
    ("course_get_grades", "Возвращает оценки и баллы студента по заданиям курса.",
     {"student_id": (S, "Идентификатор студента")}, ["student_id"]),
    ("course_submit_homework", "Загружает решение домашнего задания студента на проверку.",
     {"student_id": (S, "Студент"), "assignment_id": (S, "Номер задания"), "file_url": (S, "Ссылка на файл")},
     ["student_id", "assignment_id", "file_url"]),
    ("course_list_materials", "Список материалов курса: слайды лекций, конспекты, записи занятий.",
     {"lecture": (I, "Номер лекции")}, []),
    ("course_message_teacher", "Отправляет преподавателю курса письменный вопрос в учебный чат; ответ приходит асинхронно.",
     {"teacher": (S, "Преподаватель"), "text": (S, "Текст вопроса")}, ["teacher", "text"]),
    ("course_get_teacher_contacts", "Возвращает контакты преподавателей курса: почту, кафедру, кабинет.",
     {"teacher": (S, "Фамилия преподавателя")}, []),
    ("course_regrade_request", "Создаёт апелляцию на пересмотр оценки за задание.",
     {"student_id": (S, "Студент"), "assignment_id": (S, "Задание"), "reason": (S, "Причина")},
     ["student_id", "assignment_id", "reason"]),
    ("exam_get_schedule", "Расписание экзаменов сессии: дата, аудитория, экзаменатор.",
     {"course": (S, "Курс")}, []),
    ("exam_register", "Регистрирует студента на экзамен или пересдачу в выбранную дату.",
     {"student_id": (S, "Студент"), "exam_id": (S, "Экзамен"), "date": (S, "Дата")},
     ["student_id", "exam_id", "date"]),
    ("room_search_free", "Ищет свободные учебные аудитории на дату и время для самостоятельных занятий.",
     {"date": (S, "Дата YYYY-MM-DD"), "capacity": (I, "Вместимость")}, ["date"]),
    ("room_book", "Бронирует учебную аудиторию на интервал времени для группы студентов.",
     {"room_id": (S, "Аудитория"), "date": (S, "Дата"), "start": (S, "Начало"), "end": (S, "Конец")},
     ["room_id", "date", "start", "end"]),
    ("room_cancel_booking", "Отменяет бронь учебной аудитории.",
     {"reservation_id": (S, "Номер брони аудитории")}, ["reservation_id"]),
    ("calendar_list_events", "Показывает события личного календаря пользователя за период.",
     {"from": (S, "Начало периода"), "to": (S, "Конец периода")}, ["from", "to"]),
    ("calendar_create_event", "Создаёт событие в личном календаре пользователя с напоминанием.",
     {"title": (S, "Название"), "start": (S, "Начало ISO"), "end": (S, "Конец ISO")}, ["title", "start", "end"]),
    ("calendar_find_free_time", "Находит общее свободное время нескольких участников в их календарях.",
     {"emails": (S, "Адреса участников через запятую"), "date": (S, "Дата")}, ["emails", "date"]),
    ("calendar_delete_event", "Удаляет событие из личного календаря.",
     {"event_id": (S, "Идентификатор события")}, ["event_id"]),
    ("clinic_find_appointments", "Ищет свободное время приёма врача в студенческой поликлинике.",
     {"specialty": (S, "Специальность врача"), "date": (S, "Дата")}, ["specialty"]),
    ("clinic_book_appointment", "Записывает пациента на приём к врачу поликлиники.",
     {"slot_id": (S, "Слот приёма"), "patient_id": (S, "Пациент")}, ["slot_id", "patient_id"]),
    ("clinic_cancel_appointment", "Отменяет запись к врачу поликлиники.",
     {"appointment_id": (S, "Номер записи")}, ["appointment_id"]),
    ("tutor_marketplace_search", "Ищет платных репетиторов на внешней площадке по предмету и цене.",
     {"subject": (S, "Предмет"), "max_price": (I, "Цена за час")}, ["subject"]),
    ("library_reserve_book", "Бронирует книгу в университетской библиотеке.",
     {"isbn": (S, "ISBN"), "student_id": (S, "Читатель")}, ["isbn", "student_id"]),
    ("meeting_create_video_link", "Создаёт ссылку на видеовстречу (Zoom/Meet) на заданное время.",
     {"topic": (S, "Тема"), "start": (S, "Начало")}, ["topic", "start"]),
    ("reminder_create", "Создаёт напоминание пользователю на указанное время.",
     {"text": (S, "Текст"), "at": (S, "Время ISO")}, ["text", "at"]),
    ("student_get_profile", "Возвращает профиль студента: группа, курс, контакты, статус обучения.",
     {"student_id": (S, "Студент")}, ["student_id"]),
]

PUBLIC = [
    # filesystem
    ("read_file", "Read the complete contents of a file from the file system.", {"path": (S, "File path")}, ["path"]),
    ("read_multiple_files", "Read the contents of multiple files simultaneously.", {"paths": (S, "Comma-separated paths")}, ["paths"]),
    ("write_file", "Create a new file or completely overwrite an existing file with new content.", {"path": (S, "File path"), "content": (S, "Content")}, ["path", "content"]),
    ("edit_file", "Make line-based edits to a text file and return a git-style diff.", {"path": (S, "File path"), "edits": (S, "Edits as JSON")}, ["path", "edits"]),
    ("create_directory", "Create a new directory or ensure it exists.", {"path": (S, "Directory path")}, ["path"]),
    ("list_directory", "Get a detailed listing of all files and directories in a path.", {"path": (S, "Directory path")}, ["path"]),
    ("directory_tree", "Get a recursive tree view of files and directories as JSON.", {"path": (S, "Root path")}, ["path"]),
    ("move_file", "Move or rename files and directories.", {"source": (S, "Source"), "destination": (S, "Destination")}, ["source", "destination"]),
    ("search_files", "Recursively search for files and directories matching a pattern.", {"path": (S, "Root"), "pattern": (S, "Glob pattern")}, ["path", "pattern"]),
    ("get_file_info", "Retrieve metadata about a file or directory: size, times, permissions.", {"path": (S, "Path")}, ["path"]),
    # git
    ("git_status", "Shows the working tree status of a git repository.", {"repo_path": (S, "Repository path")}, ["repo_path"]),
    ("git_diff_unstaged", "Shows changes in the working directory that are not yet staged.", {"repo_path": (S, "Repository path")}, ["repo_path"]),
    ("git_commit", "Records changes to the repository with a commit message.", {"repo_path": (S, "Repository path"), "message": (S, "Message")}, ["repo_path", "message"]),
    ("git_log", "Shows the commit logs of a repository.", {"repo_path": (S, "Repository path"), "max_count": (I, "Limit")}, ["repo_path"]),
    ("git_create_branch", "Creates a new branch from an optional base branch.", {"repo_path": (S, "Repository path"), "branch_name": (S, "Branch")}, ["repo_path", "branch_name"]),
    # github
    ("create_issue", "Create a new issue in a GitHub repository.", {"owner": (S, "Owner"), "repo": (S, "Repo"), "title": (S, "Title")}, ["owner", "repo", "title"]),
    ("list_issues", "List and filter issues in a GitHub repository.", {"owner": (S, "Owner"), "repo": (S, "Repo"), "state": (S, "open/closed")}, ["owner", "repo"]),
    ("create_pull_request", "Create a new pull request in a GitHub repository.", {"owner": (S, "Owner"), "repo": (S, "Repo"), "head": (S, "Head"), "base": (S, "Base")}, ["owner", "repo", "head", "base"]),
    ("search_repositories", "Search for GitHub repositories.", {"query": (S, "Query")}, ["query"]),
    ("get_file_contents", "Get the contents of a file or directory from a GitHub repository.", {"owner": (S, "Owner"), "repo": (S, "Repo"), "path": (S, "Path")}, ["owner", "repo", "path"]),
    ("add_issue_comment", "Add a comment to an existing GitHub issue.", {"owner": (S, "Owner"), "repo": (S, "Repo"), "issue_number": (I, "Issue"), "body": (S, "Comment")}, ["owner", "repo", "issue_number", "body"]),
    ("list_commits", "Get list of commits of a branch in a GitHub repository.", {"owner": (S, "Owner"), "repo": (S, "Repo")}, ["owner", "repo"]),
    ("fork_repository", "Fork a GitHub repository to your account or organization.", {"owner": (S, "Owner"), "repo": (S, "Repo")}, ["owner", "repo"]),
    # slack
    ("slack_list_channels", "List public channels in the Slack workspace.", {"limit": (I, "Limit")}, []),
    ("slack_post_message", "Post a new message to a Slack channel.", {"channel_id": (S, "Channel"), "text": (S, "Text")}, ["channel_id", "text"]),
    ("slack_reply_to_thread", "Reply to a specific message thread in Slack.", {"channel_id": (S, "Channel"), "thread_ts": (S, "Thread"), "text": (S, "Text")}, ["channel_id", "thread_ts", "text"]),
    ("slack_add_reaction", "Add a reaction emoji to a Slack message.", {"channel_id": (S, "Channel"), "timestamp": (S, "Message"), "reaction": (S, "Emoji")}, ["channel_id", "timestamp", "reaction"]),
    ("slack_get_channel_history", "Get recent messages from a Slack channel.", {"channel_id": (S, "Channel")}, ["channel_id"]),
    ("slack_get_users", "Get a list of all users in the Slack workspace with profile information.", {"limit": (I, "Limit")}, []),
    # sqlite / postgres
    ("read_query", "Execute a SELECT query on the SQLite database.", {"query": (S, "SQL")}, ["query"]),
    ("write_query", "Execute an INSERT, UPDATE, or DELETE query on the SQLite database.", {"query": (S, "SQL")}, ["query"]),
    ("create_table", "Create a new table in the SQLite database.", {"query": (S, "CREATE TABLE statement")}, ["query"]),
    ("list_tables", "List all tables in the SQLite database.", {}, []),
    ("describe_table", "Get the schema information for a specific table.", {"table_name": (S, "Table")}, ["table_name"]),
    ("query", "Run a read-only SQL query against a PostgreSQL database.", {"sql": (S, "SQL")}, ["sql"]),
    # memory
    ("create_entities", "Create multiple new entities in the knowledge graph.", {"entities": (S, "Entities JSON")}, ["entities"]),
    ("create_relations", "Create multiple new relations between entities in the knowledge graph.", {"relations": (S, "Relations JSON")}, ["relations"]),
    ("add_observations", "Add new observations to existing entities in the knowledge graph.", {"observations": (S, "Observations JSON")}, ["observations"]),
    ("search_nodes", "Search for nodes in the knowledge graph based on a query.", {"query": (S, "Query")}, ["query"]),
    ("read_graph", "Read the entire knowledge graph.", {}, []),
    ("delete_entities", "Delete multiple entities and their relations from the knowledge graph.", {"entityNames": (S, "Names")}, ["entityNames"]),
    # fetch / search / browser
    ("fetch", "Fetch a URL from the internet and extract its contents as markdown.", {"url": (S, "URL")}, ["url"]),
    ("brave_web_search", "Perform a web search using the Brave Search API.", {"query": (S, "Query")}, ["query"]),
    ("brave_local_search", "Search for local businesses and places using Brave's Local Search API.", {"query": (S, "Query")}, ["query"]),
    ("puppeteer_navigate", "Navigate the browser to a URL.", {"url": (S, "URL")}, ["url"]),
    ("puppeteer_screenshot", "Take a screenshot of the current page or a specific element.", {"name": (S, "Name")}, ["name"]),
    ("puppeteer_click", "Click an element on the page.", {"selector": (S, "CSS selector")}, ["selector"]),
    ("puppeteer_fill", "Fill out an input field on the page.", {"selector": (S, "CSS selector"), "value": (S, "Value")}, ["selector", "value"]),
    ("puppeteer_evaluate", "Execute JavaScript in the browser console.", {"script": (S, "JavaScript")}, ["script"]),
    # maps / time / thinking
    ("maps_geocode", "Convert an address into geographic coordinates.", {"address": (S, "Address")}, ["address"]),
    ("maps_directions", "Get directions between two points.", {"origin": (S, "Origin"), "destination": (S, "Destination")}, ["origin", "destination"]),
    ("maps_search_places", "Search for places using Google Places API.", {"query": (S, "Query")}, ["query"]),
    ("maps_distance_matrix", "Calculate travel distance and time for multiple origins and destinations.", {"origins": (S, "Origins"), "destinations": (S, "Destinations")}, ["origins", "destinations"]),
    ("get_current_time", "Get current time in a specific timezone.", {"timezone": (S, "IANA timezone")}, ["timezone"]),
    ("convert_time", "Convert time between timezones.", {"time": (S, "HH:MM"), "source_timezone": (S, "From"), "target_timezone": (S, "To")}, ["time", "source_timezone", "target_timezone"]),
    ("sequentialthinking", "A tool for dynamic and reflective step-by-step problem solving through thoughts.", {"thought": (S, "Current thought"), "nextThoughtNeeded": (B, "More thoughts needed")}, ["thought", "nextThoughtNeeded"]),
    # notion / linear / sentry / gdrive / misc
    ("notion_search", "Search pages and databases in a Notion workspace by title.", {"query": (S, "Query")}, ["query"]),
    ("notion_create_page", "Create a new page in Notion under a parent page or database.", {"parent_id": (S, "Parent"), "title": (S, "Title")}, ["parent_id", "title"]),
    ("notion_append_block_children", "Append content blocks to a Notion page.", {"block_id": (S, "Page or block"), "children": (S, "Blocks JSON")}, ["block_id", "children"]),
    ("linear_create_issue", "Create a new issue in Linear.", {"title": (S, "Title"), "teamId": (S, "Team")}, ["title", "teamId"]),
    ("linear_search_issues", "Search Linear issues with flexible filters.", {"query": (S, "Query")}, ["query"]),
    ("get_sentry_issue", "Retrieve and analyze a Sentry issue by ID or URL.", {"issue_id_or_url": (S, "Issue")}, ["issue_id_or_url"]),
    ("gdrive_search", "Search for files in Google Drive.", {"query": (S, "Query")}, ["query"]),
    ("gsheets_read", "Read data from a Google Spreadsheet range.", {"spreadsheetId": (S, "Spreadsheet"), "range": (S, "A1 range")}, ["spreadsheetId"]),
    ("gmail_send_email", "Send an email via Gmail.", {"to": (S, "Recipient"), "subject": (S, "Subject"), "body": (S, "Body")}, ["to", "subject", "body"]),
    ("gmail_search_emails", "Search emails in Gmail using query syntax.", {"query": (S, "Query")}, ["query"]),
    ("everart_generate_image", "Generate images using EverArt models.", {"prompt": (S, "Prompt")}, ["prompt"]),
    ("youtube_get_transcript", "Get the transcript of a YouTube video.", {"url": (S, "Video URL")}, ["url"]),
    ("weather_get_forecast", "Get the weather forecast for a location.", {"latitude": (I, "Latitude"), "longitude": (I, "Longitude")}, ["latitude", "longitude"]),
]


def _schema(params: dict, required: list[str]) -> dict:
    return {"type": "object",
            "properties": {k: {"type": t, "description": d} for k, (t, d) in params.items()},
            "required": required, "additionalProperties": False}


def build_pool() -> list[dict]:
    pool = [{"name": n, "kind": "own", "description": s["description"], "parameters": s["input_schema"]}
            for n, s in TOOL_SPECS.items()]
    pool += [{"name": n, "kind": "near", "description": d, "parameters": _schema(p, r)} for n, d, p, r in NEAR]
    pool += [{"name": n, "kind": "public", "description": d, "parameters": _schema(p, r)} for n, d, p, r in PUBLIC]
    names = [t["name"] for t in pool]
    assert len(pool) == 100 and len(set(names)) == 100, (len(pool), len(set(names)))
    return pool


if __name__ == "__main__":
    out = ROOT / "experiment" / "data" / "tool_pool.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    pool = build_pool()
    out.write_text(json.dumps(pool, ensure_ascii=False, indent=1), encoding="utf-8")
    print(out, {k: sum(t["kind"] == k for t in pool) for k in ("own", "near", "public")})
