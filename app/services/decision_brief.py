from __future__ import annotations

import sqlite3

from app.models import ActionType, DecisionBrief, PremortemItem
from app.services.decision_memory import build_decision_state


RUIN_KEYWORDS = {
    "health": ["健康", "身体", "睡眠", "焦虑", "抑郁", "熬夜"],
    "cashflow": ["现金流", "没钱", "收入", "房租", "生活费"],
    "debt": ["负债", "借钱", "贷款", "信用卡"],
    "legal": ["违法", "法律", "合同", "灰产"],
    "freedom": ["控制", "服从", "退出不了", "不能质疑"],
    "judgment": ["洗脑", "判断力", "不能质疑", "被带节奏"],
}


def build_decision_brief(conn: sqlite3.Connection, case_id: int) -> DecisionBrief:
    state = build_decision_state(conn, case_id)
    risk_flags = detect_risk_flags(state.concerns + state.candidate_options + [state.summary])
    information_gaps = build_information_gaps(state.open_questions, state.evidence_count)
    action = choose_action(state.current_action, risk_flags, state.evidence_count, bool(information_gaps))
    confidence = confidence_level(state.message_count, state.evidence_count, information_gaps, risk_flags)
    next_steps = state.next_steps or default_next_steps(action, bool(information_gaps))
    premortem = build_premortem(state.concerns, risk_flags, action)
    stop_conditions = build_stop_conditions(risk_flags, action)

    return DecisionBrief(
        case_id=case_id,
        recommended_action=action,
        confidence=confidence,
        summary=state.summary,
        reality_checks=build_reality_checks(state.evidence_count, information_gaps, risk_flags),
        risk_flags=risk_flags,
        information_gaps=information_gaps,
        premortem=premortem,
        stop_conditions=stop_conditions,
        next_steps=next_steps[:5],
    )


def brief_context_text(brief: DecisionBrief) -> str:
    lines = [
        "当前决策简报：",
        f"- 建议动作：{brief.recommended_action}",
        f"- 置信度：{brief.confidence}",
        f"- 摘要：{brief.summary}",
    ]
    if brief.risk_flags:
        lines.append(f"- 风险标记：{'；'.join(brief.risk_flags)}")
    if brief.information_gaps:
        lines.append(f"- 信息缺口：{'；'.join(brief.information_gaps[:4])}")
    if brief.stop_conditions:
        lines.append(f"- 止损线：{'；'.join(brief.stop_conditions[:3])}")
    if brief.next_steps:
        lines.append(f"- 下一步：{'；'.join(brief.next_steps[:3])}")
    return "\n".join(lines)


def detect_risk_flags(texts: list[str]) -> list[str]:
    joined = "\n".join(texts)
    flags = []
    for flag, keywords in RUIN_KEYWORDS.items():
        if any(keyword in joined for keyword in keywords):
            flags.append(flag)
    return flags


def build_information_gaps(open_questions: list[str], evidence_count: int) -> list[str]:
    gaps = list(open_questions[:6])
    if evidence_count == 0:
        gaps.append("还没有外部证据或事实核验。")
    return gaps[:8]


def choose_action(
    current_action: ActionType | None,
    risk_flags: list[str],
    evidence_count: int,
    has_information_gaps: bool,
) -> ActionType:
    if any(flag in risk_flags for flag in ["legal", "debt", "freedom", "judgment"]):
        return "reject"
    if risk_flags and current_action == "stage_gated_increase":
        return "small_experiment"
    if current_action:
        return current_action
    if has_information_gaps or evidence_count == 0:
        return "observe"
    return "small_experiment"


def confidence_level(
    message_count: int,
    evidence_count: int,
    information_gaps: list[str],
    risk_flags: list[str],
) -> str:
    if risk_flags and any(flag in risk_flags for flag in ["legal", "debt", "freedom", "judgment"]):
        return "high_for_downgrade"
    if message_count >= 6 and evidence_count > 0 and not information_gaps:
        return "medium"
    if message_count >= 4:
        return "low_to_medium"
    return "low"


def build_reality_checks(evidence_count: int, information_gaps: list[str], risk_flags: list[str]) -> list[str]:
    checks = []
    if evidence_count == 0:
        checks.append("关键事实还没有经过外部证据核验。")
    if information_gaps:
        checks.append("仍有未回答问题，当前结论应视为暂定。")
    if risk_flags:
        checks.append("存在基本盘相关风险，不能让总分覆盖风险门槛。")
    if not checks:
        checks.append("已有对话和证据足以支持低风险下一步，但仍需保留止损线。")
    return checks


def build_premortem(concerns: list[str], risk_flags: list[str], action: ActionType) -> list[PremortemItem]:
    items: list[PremortemItem] = []
    for concern in concerns[:3]:
        items.append(
            PremortemItem(
                reason=concern,
                likelihood="medium",
                impact="medium",
                prevention="先把投入限制在可逆范围，并设置复盘时间。",
            )
        )
    for flag in risk_flags:
        items.append(
            PremortemItem(
                reason=f"{flag} risk affects the basic base",
                likelihood="unknown",
                impact="high",
                prevention="在风险被降级前，不做长期承诺或重投入。",
            )
        )
    if not items:
        items.append(
            PremortemItem(
                reason="高估执行力或低估机会成本",
                likelihood="medium",
                impact="medium",
                prevention="把下一步缩小到 7 天以内的可观察行动。",
            )
        )
    if action == "stage_gated_increase":
        items.append(
            PremortemItem(
                reason="加码过快，导致承诺超过证据",
                likelihood="medium",
                impact="high",
                prevention="只在达到明确证据门槛后进入下一阶段。",
            )
        )
    return items[:6]


def build_stop_conditions(risk_flags: list[str], action: ActionType) -> list[str]:
    conditions = []
    if risk_flags:
        conditions.append("一旦风险触及健康、现金流、信用、法律、自由或判断力，立即降级或停止。")
    if action in {"small_experiment", "stage_gated_increase"}:
        conditions.append("到预设复盘时间仍没有正反馈，就停止加码。")
        conditions.append("投入超过原定时间/金钱上限时，先暂停再重新评估。")
    else:
        conditions.append("如果新增证据没有提高可信度，不进入承诺阶段。")
    return conditions


def default_next_steps(action: ActionType, has_information_gaps: bool) -> list[str]:
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
