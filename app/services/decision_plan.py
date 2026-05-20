from __future__ import annotations

import sqlite3
from datetime import UTC, date, datetime, timedelta

from app import repository
from app.models import DecisionActionPlan, JournalCreate, JournalEntry
from app.services.decision_brief import build_decision_brief


TIMEBOX_BY_ACTION = {
    "reject": 30,
    "observe": 7,
    "small_experiment": 7,
    "stage_gated_increase": 14,
}

COMMITMENT_BY_ACTION = {
    "reject": "none",
    "observe": "low",
    "small_experiment": "low_to_medium",
    "stage_gated_increase": "medium_stage_gated",
}


def build_action_plan(conn: sqlite3.Connection, case_id: int) -> DecisionActionPlan:
    brief = build_decision_brief(conn, case_id)
    days = TIMEBOX_BY_ACTION[brief.recommended_action]
    review_date = (date.today() + timedelta(days=days)).isoformat()
    next_steps = usable_next_steps(brief.next_steps)
    if not next_steps:
        next_steps = default_next_steps(brief.recommended_action, bool(brief.information_gaps))

    return DecisionActionPlan(
        case_id=case_id,
        action=brief.recommended_action,
        commitment_level=COMMITMENT_BY_ACTION[brief.recommended_action],
        timebox_days=days,
        review_date=review_date,
        success_signals=success_signals_for(brief.recommended_action),
        failure_signals=failure_signals_for(brief.recommended_action, brief.information_gaps),
        stop_conditions=brief.stop_conditions,
        next_steps=next_steps,
        journal_rationale=build_rationale(brief),
    )


def create_journal_from_brief(conn: sqlite3.Connection, case_id: int) -> JournalEntry:
    plan = build_action_plan(conn, case_id)
    for existing in repository.list_journals(conn, case_id):
        if (
            existing.final_action == plan.action
            and existing.follow_up_date == plan.review_date
            and not existing.outcome.strip()
        ):
            return existing

    payload = JournalCreate(
        final_action=plan.action,
        rationale=plan.journal_rationale,
        stop_conditions="\n".join(f"- {item}" for item in plan.stop_conditions),
        follow_up_date=plan.review_date,
        outcome="",
    )
    return repository.add_journal(conn, case_id, payload)


def success_signals_for(action: str) -> list[str]:
    if action == "reject":
        return ["没有继续投入时间、金钱或承诺。", "没有出现新的高质量反证需要重开判断。"]
    if action == "observe":
        return ["关键问题得到回答。", "新增证据足以让选择从观察进入小试，或明确拒绝。"]
    if action == "small_experiment":
        return ["实验在时间/金钱上限内完成。", "出现可观察的正反馈或学习收益。", "风险没有越过止损线。"]
    return ["达到上一阶段设定的成功信号。", "风险和机会成本仍可控。", "有证据支持进入下一阶段。"]


def failure_signals_for(action: str, information_gaps: list[str]) -> list[str]:
    signals = []
    if information_gaps:
        signals.append("复盘时关键问题仍没有得到回答。")
    if action in {"small_experiment", "stage_gated_increase"}:
        signals.extend(["投入超过预设上限。", "没有正反馈却想继续加码。"])
    if action == "reject":
        signals.append("仍被同一诱因反复拉回，但没有新增证据。")
    if not signals:
        signals.append("复盘时仍无法说明下一步为什么值得做。")
    return signals


def default_next_steps(action: str, has_information_gaps: bool) -> list[str]:
    if action == "reject":
        return ["拒绝当前高风险版本。", "只保留低接触、可退出的信息观察。"]
    if action == "observe":
        steps = ["先补齐最关键的 1-3 个信息缺口。"]
        if has_information_gaps:
            steps.append("把待澄清问题逐个回答后再评估。")
        return steps
    if action == "small_experiment":
        return ["设计一个 7 天以内、低成本、可停止的小实验。", "提前写清楚成功信号和停止条件。"]
    return ["只按阶段加码，不一次性重投入。", "每阶段结束后检查证据、风险和机会成本。"]


def usable_next_steps(steps: list[str]) -> list[str]:
    blocked_fragments = [
        "我会优先关注",
        "哪些信息",
        "现在应该",
        "当前动作类型",
        "当前动作",
        "我无法直接",
        "你能接受",
        "你希望",
        "你每周",
    ]
    result = []
    for step in steps:
        cleaned = step.strip(" -。；")
        if not cleaned:
            continue
        if cleaned.endswith(("：", ":")):
            continue
        if cleaned.endswith(("？", "?")):
            continue
        if any(fragment in cleaned for fragment in blocked_fragments):
            continue
        if len(cleaned) < 6:
            continue
        result.append(f"{cleaned}。")
        if len(result) >= 5:
            break
    return result


def build_rationale(brief) -> str:
    lines = [
        f"Recommended action: {brief.recommended_action}",
        f"Confidence: {brief.confidence}",
        f"Summary: {brief.summary}",
    ]
    if brief.reality_checks:
        lines.append("Reality checks:")
        lines.extend(f"- {item}" for item in brief.reality_checks)
    if brief.risk_flags:
        lines.append(f"Risk flags: {', '.join(brief.risk_flags)}")
    if brief.information_gaps:
        lines.append("Information gaps:")
        lines.extend(f"- {item}" for item in brief.information_gaps)
    if brief.next_steps:
        lines.append("Next steps:")
        lines.extend(f"- {item}" for item in brief.next_steps)
    lines.append(f"Created at: {datetime.now(UTC).isoformat()}")
    return "\n".join(lines)
