from __future__ import annotations

import sqlite3
from typing import Any

from app.db import json_dumps, json_loads, utc_now
from app.models import (
    ConversationMessage,
    DecisionCase,
    DecisionCaseCreate,
    DecisionCaseUpdate,
    DecisionOption,
    EvidenceItem,
    JournalCreate,
    JournalEntry,
    JournalUpdate,
    MessageCreate,
    OptionCreate,
)
from app.services.decision_engine import classify_problem


def row_to_case(row: sqlite3.Row) -> DecisionCase:
    return DecisionCase(
        id=row["id"],
        title=row["title"],
        status=row["status"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        user_goal=row["user_goal"],
        current_question=row["current_question"],
        classification=row["classification"],
        urgency=row["urgency"],
        stakes=row["stakes"],
        search_required=bool(row["search_required"]),
        summary=row["summary"],
    )


def create_case(conn: sqlite3.Connection, payload: DecisionCaseCreate) -> DecisionCase:
    now = utc_now()
    classification = classify_problem(f"{payload.title}\n{payload.user_goal}\n{payload.current_question}")
    cursor = conn.execute(
        """
        INSERT INTO decision_cases (
            title, status, created_at, updated_at, user_goal, current_question,
            classification, urgency, stakes, search_required, summary
        ) VALUES (?, 'active', ?, ?, ?, ?, ?, ?, ?, ?, '')
        """,
        (
            payload.title,
            now,
            now,
            payload.user_goal,
            payload.current_question,
            classification["classification"],
            classification["urgency"],
            classification["stakes"],
            1 if classification["search_required"] else 0,
        ),
    )
    case_id = cursor.lastrowid
    initial_content = payload.user_goal
    if payload.current_question and payload.current_question != payload.user_goal:
        initial_content = f"Goal: {payload.user_goal}\nQuestion: {payload.current_question}"
    add_message(
        conn,
        case_id,
        MessageCreate(role="user", content=initial_content),
    )
    return get_case(conn, case_id)


def list_cases(conn: sqlite3.Connection) -> list[DecisionCase]:
    rows = conn.execute("SELECT * FROM decision_cases ORDER BY updated_at DESC").fetchall()
    return [row_to_case(row) for row in rows]


def get_case(conn: sqlite3.Connection, case_id: int) -> DecisionCase:
    row = conn.execute("SELECT * FROM decision_cases WHERE id = ?", (case_id,)).fetchone()
    if row is None:
        raise KeyError(case_id)
    return row_to_case(row)


def update_case(conn: sqlite3.Connection, case_id: int, payload: DecisionCaseUpdate) -> DecisionCase:
    existing = get_case(conn, case_id)
    data = payload.model_dump(exclude_unset=True)
    if not data:
        return existing

    assignments = []
    values: list[Any] = []
    for key, value in data.items():
        assignments.append(f"{key} = ?")
        values.append(value)
    assignments.append("updated_at = ?")
    values.append(utc_now())
    values.append(case_id)
    conn.execute(f"UPDATE decision_cases SET {', '.join(assignments)} WHERE id = ?", values)
    return get_case(conn, case_id)


def delete_case(conn: sqlite3.Connection, case_id: int) -> None:
    get_case(conn, case_id)
    conn.execute("DELETE FROM decision_cases WHERE id = ?", (case_id,))


def touch_case(conn: sqlite3.Connection, case_id: int) -> None:
    conn.execute("UPDATE decision_cases SET updated_at = ? WHERE id = ?", (utc_now(), case_id))


def add_message(conn: sqlite3.Connection, case_id: int, payload: MessageCreate) -> ConversationMessage:
    get_case(conn, case_id)
    cursor = conn.execute(
        "INSERT INTO conversation_messages (case_id, role, content, created_at) VALUES (?, ?, ?, ?)",
        (case_id, payload.role, payload.content, utc_now()),
    )
    touch_case(conn, case_id)
    return get_message(conn, cursor.lastrowid)


def get_message(conn: sqlite3.Connection, message_id: int) -> ConversationMessage:
    row = conn.execute("SELECT * FROM conversation_messages WHERE id = ?", (message_id,)).fetchone()
    if row is None:
        raise KeyError(message_id)
    return ConversationMessage(**dict(row))


def list_messages(conn: sqlite3.Connection, case_id: int) -> list[ConversationMessage]:
    get_case(conn, case_id)
    rows = conn.execute(
        "SELECT * FROM conversation_messages WHERE case_id = ? ORDER BY id ASC",
        (case_id,),
    ).fetchall()
    return [ConversationMessage(**dict(row)) for row in rows]


def add_option(conn: sqlite3.Connection, case_id: int, payload: OptionCreate) -> DecisionOption:
    get_case(conn, case_id)
    cursor = conn.execute(
        """
        INSERT INTO decision_options (
            case_id, label, description, expected_value, mcda_score, risk_notes, reversibility, evidence_links
        ) VALUES (?, ?, ?, NULL, NULL, '', NULL, '[]')
        """,
        (case_id, payload.label, payload.description),
    )
    touch_case(conn, case_id)
    return get_option(conn, cursor.lastrowid)


def get_option(conn: sqlite3.Connection, option_id: int) -> DecisionOption:
    row = conn.execute("SELECT * FROM decision_options WHERE id = ?", (option_id,)).fetchone()
    if row is None:
        raise KeyError(option_id)
    data = dict(row)
    data["evidence_links"] = json_loads(data["evidence_links"], [])
    return DecisionOption(**data)


def list_options(conn: sqlite3.Connection, case_id: int) -> list[DecisionOption]:
    get_case(conn, case_id)
    rows = conn.execute("SELECT * FROM decision_options WHERE case_id = ? ORDER BY id ASC", (case_id,)).fetchall()
    options = []
    for row in rows:
        data = dict(row)
        data["evidence_links"] = json_loads(data["evidence_links"], [])
        options.append(DecisionOption(**data))
    return options


def add_evidence(
    conn: sqlite3.Connection,
    case_id: int,
    *,
    query: str,
    url: str = "",
    title: str = "",
    source_type: str = "search",
    fetched_text: str = "",
    confidence: str = "candidate",
) -> EvidenceItem:
    get_case(conn, case_id)
    cursor = conn.execute(
        """
        INSERT INTO evidence_items (
            case_id, query, url, title, source_type, fetched_text, confidence, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (case_id, query, url, title, source_type, fetched_text, confidence, utc_now()),
    )
    touch_case(conn, case_id)
    return get_evidence(conn, cursor.lastrowid)


def get_evidence(conn: sqlite3.Connection, evidence_id: int) -> EvidenceItem:
    row = conn.execute("SELECT * FROM evidence_items WHERE id = ?", (evidence_id,)).fetchone()
    if row is None:
        raise KeyError(evidence_id)
    return EvidenceItem(**dict(row))


def list_evidence(conn: sqlite3.Connection, case_id: int) -> list[EvidenceItem]:
    get_case(conn, case_id)
    rows = conn.execute("SELECT * FROM evidence_items WHERE case_id = ? ORDER BY id DESC", (case_id,)).fetchall()
    return [EvidenceItem(**dict(row)) for row in rows]


def add_journal(conn: sqlite3.Connection, case_id: int, payload: JournalCreate) -> JournalEntry:
    get_case(conn, case_id)
    cursor = conn.execute(
        """
        INSERT INTO journal_entries (
            case_id, final_action, rationale, stop_conditions, follow_up_date, outcome, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            case_id,
            payload.final_action,
            payload.rationale,
            payload.stop_conditions,
            payload.follow_up_date,
            payload.outcome,
            utc_now(),
        ),
    )
    touch_case(conn, case_id)
    return get_journal(conn, cursor.lastrowid)


def get_journal(conn: sqlite3.Connection, journal_id: int) -> JournalEntry:
    row = conn.execute("SELECT * FROM journal_entries WHERE id = ?", (journal_id,)).fetchone()
    if row is None:
        raise KeyError(journal_id)
    return JournalEntry(**dict(row))


def update_journal(
    conn: sqlite3.Connection,
    case_id: int,
    journal_id: int,
    payload: JournalUpdate,
) -> JournalEntry:
    get_case(conn, case_id)
    existing = get_journal(conn, journal_id)
    if existing.case_id != case_id:
        raise KeyError(journal_id)

    data = payload.model_dump(exclude_unset=True)
    if not data:
        return existing

    assignments = []
    values: list[Any] = []
    for key, value in data.items():
        assignments.append(f"{key} = ?")
        values.append(value or "")
    values.append(journal_id)
    conn.execute(f"UPDATE journal_entries SET {', '.join(assignments)} WHERE id = ?", values)
    touch_case(conn, case_id)
    return get_journal(conn, journal_id)


def delete_journal(conn: sqlite3.Connection, case_id: int, journal_id: int) -> None:
    get_case(conn, case_id)
    existing = get_journal(conn, journal_id)
    if existing.case_id != case_id:
        raise KeyError(journal_id)
    conn.execute("DELETE FROM journal_entries WHERE id = ?", (journal_id,))
    touch_case(conn, case_id)


def list_journals(conn: sqlite3.Connection, case_id: int) -> list[JournalEntry]:
    get_case(conn, case_id)
    rows = conn.execute("SELECT * FROM journal_entries WHERE case_id = ? ORDER BY id DESC", (case_id,)).fetchall()
    return [JournalEntry(**dict(row)) for row in rows]


def list_due_journals(conn: sqlite3.Connection, today_iso: str) -> list[JournalEntry]:
    rows = conn.execute(
        """
        SELECT * FROM journal_entries
        WHERE follow_up_date != ''
          AND follow_up_date <= ?
          AND TRIM(outcome) = ''
        ORDER BY follow_up_date ASC, id ASC
        """,
        (today_iso,),
    ).fetchall()
    return [JournalEntry(**dict(row)) for row in rows]


def store_search_result(conn: sqlite3.Connection, case_id: int, query: str, data: dict[str, Any]) -> list[EvidenceItem]:
    items: list[EvidenceItem] = []
    sources = data.get("primary_sources") or data.get("sources") or []
    for source in sources[:8]:
        items.append(
            add_evidence(
                conn,
                case_id,
                query=query,
                url=source.get("url", ""),
                title=source.get("title", ""),
                source_type="search",
                fetched_text=source.get("description", "") or source.get("snippet", ""),
                confidence="candidate",
            )
        )
    command_note = {
        "command": data.get("_command", ""),
        "output_path": data.get("_output_path", ""),
        "source_warning": data.get("source_warning", ""),
    }
    add_evidence(
        conn,
        case_id,
        query=query,
        title="smart-search command metadata",
        source_type="metadata",
        fetched_text=json_dumps(command_note),
        confidence="metadata",
    )
    return items
