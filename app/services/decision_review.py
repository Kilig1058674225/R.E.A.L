from __future__ import annotations

import sqlite3
from datetime import date

from app import repository
from app.models import JournalEntry, JournalReview


def build_journal_review(
    conn: sqlite3.Connection,
    journal: JournalEntry,
    today: date | None = None,
) -> JournalReview:
    today = today or date.today()
    case = repository.get_case(conn, journal.case_id)
    follow_up = parse_follow_up_date(journal.follow_up_date)
    status, days_delta = review_status(journal, follow_up, today)
    return JournalReview(
        journal=journal,
        case_title=case.title,
        status=status,
        days_delta=days_delta,
        review_prompt=review_prompt(journal, status, days_delta),
        learning_summary=learning_summary(journal),
    )


def build_case_reviews(conn: sqlite3.Connection, case_id: int) -> list[JournalReview]:
    repository.get_case(conn, case_id)
    return [build_journal_review(conn, item) for item in repository.list_journals(conn, case_id)]


def build_due_reviews(conn: sqlite3.Connection, today: date | None = None) -> list[JournalReview]:
    today = today or date.today()
    journals = repository.list_due_journals(conn, today.isoformat())
    return [build_journal_review(conn, item, today) for item in journals]


def parse_follow_up_date(value: str) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def review_status(
    journal: JournalEntry,
    follow_up: date | None,
    today: date,
) -> tuple[str, int | None]:
    if journal.outcome.strip():
        return "completed", None
    if follow_up is None:
        return "unscheduled", None
    days_delta = (today - follow_up).days
    if days_delta > 0:
        return "overdue", days_delta
    if days_delta == 0:
        return "due_today", 0
    return "upcoming", days_delta


def review_prompt(journal: JournalEntry, status: str, days_delta: int | None) -> str:
    action = journal.final_action
    if status == "completed":
        return "这条计划已经记录结果，可以用它更新下一次判断。"
    if status == "unscheduled":
        return "这条计划还没有复盘日期。可以补一个日期，避免决定悬空。"
    if status == "upcoming":
        return "还没到复盘日。先按计划执行，到日期再看成功信号、失败信号和止损线。"

    prefix = "今天该复盘这条计划。" if status == "due_today" else f"这条计划已逾期 {days_delta} 天。"
    if action == "reject":
        return f"{prefix} 看看是否真的停止投入，是否有新的高质量反证需要重开判断。"
    if action == "observe":
        return f"{prefix} 看看关键问题是否得到回答，下一步是继续观察、小试，还是拒绝。"
    if action == "small_experiment":
        return f"{prefix} 对照成功信号、失败信号和止损线，决定停止、延长一次，或分阶段加码。"
    return f"{prefix} 确认上一阶段是否达标，只有证据和风险都过关才继续加码。"


def learning_summary(journal: JournalEntry) -> str:
    outcome = journal.outcome.strip()
    if not outcome:
        return ""
    if any(term in outcome for term in ["失败", "没做到", "没有", "超出", "后悔"]):
        return "结果偏负面：下次应降低投入、提前止损，或先补信息。"
    if any(term in outcome for term in ["成功", "有效", "做到了", "值得", "有帮助"]):
        return "结果偏正面：下次可以考虑在风险可控范围内进入下一阶段。"
    return "已记录结果：下次决策时应把这次反馈作为真实证据，而不是只依赖预期。"
