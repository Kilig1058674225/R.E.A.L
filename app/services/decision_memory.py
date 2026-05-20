from __future__ import annotations

import re
import sqlite3

from app import repository
from app.db import utc_now
from app.models import ActionType, DecisionState


ACTION_BY_LABEL: dict[str, ActionType] = {
    "拒绝": "reject",
    "观察": "observe",
    "小试": "small_experiment",
    "分阶段加码": "stage_gated_increase",
    "加码": "stage_gated_increase",
    "reject": "reject",
    "observe": "observe",
    "small_experiment": "small_experiment",
    "stage_gated_increase": "stage_gated_increase",
}

ACTION_SUMMARY_LABEL: dict[ActionType, str] = {
    "reject": "拒绝",
    "observe": "观察",
    "small_experiment": "小试",
    "stage_gated_increase": "分阶段加码",
}

CONCERN_TERMS = ["担心", "害怕", "怕", "顾虑", "风险", "压力", "焦虑", "不想", "但是", "困难", "卡住"]
OPTION_TERMS = ["方案", "选择", "路径", "做法", "可以", "尝试", "小试", "观察", "拒绝", "加码"]
NEXT_STEP_TERMS = ["下一步", "先", "试", "观察", "记录", "验证", "问", "找", "设定", "停止", "退出"]
PRIMARY_GOAL_TERMS = ["我想", "想要", "希望", "打算", "准备", "目标", "赚钱", "副业"]
QUESTION_GOAL_TERMS = ["是否", "要不要", "该不该"]
LOW_SIGNAL_PATTERNS = [
    r"^(你好|您好|在吗|hi|hello)[。！!？?]*$",
    r"你是什么模型",
    r"帮我搜",
    r"帮我找",
    r"搜索",
    r"查一下",
]


def build_decision_state(conn: sqlite3.Connection, case_id: int) -> DecisionState:
    case = repository.get_case(conn, case_id)
    messages = repository.list_messages(conn, case_id)
    evidence_count = len(repository.list_evidence(conn, case_id))

    user_texts = [message.content for message in messages if message.role == "user"]
    assistant_texts = [message.content for message in messages if message.role == "assistant"]

    current_action = extract_current_action(assistant_texts)
    concerns = unique_tail(extract_lines(user_texts, CONCERN_TERMS), 8)
    candidate_options = unique_tail(extract_lines(user_texts + assistant_texts, OPTION_TERMS), 8)
    open_questions = unique_tail(extract_questions(assistant_texts), 8)
    next_steps = unique_tail(extract_lines(assistant_texts, NEXT_STEP_TERMS), 6)
    summary = make_summary(case.user_goal, user_texts, current_action, concerns)

    return DecisionState(
        case_id=case.id,
        title=case.title,
        summary=summary,
        current_action=current_action,
        concerns=concerns,
        open_questions=open_questions,
        candidate_options=candidate_options,
        next_steps=next_steps,
        evidence_count=evidence_count,
        message_count=len(messages),
        updated_at=case.updated_at,
    )


def refresh_case_summary(conn: sqlite3.Connection, case_id: int) -> None:
    state = build_decision_state(conn, case_id)
    conn.execute(
        "UPDATE decision_cases SET summary = ?, updated_at = ? WHERE id = ?",
        (state.summary, utc_now(), case_id),
    )


def state_context_text(state: DecisionState) -> str:
    lines = [
        "当前决策状态快照：",
        f"- 摘要：{state.summary}",
        f"- 当前动作类型：{state.current_action or '未知'}",
        f"- 已有证据数量：{state.evidence_count}",
    ]
    if state.concerns:
        lines.append(f"- 主要担心：{'；'.join(state.concerns[:4])}")
    if state.candidate_options:
        lines.append(f"- 候选方案：{'；'.join(state.candidate_options[:4])}")
    if state.open_questions:
        lines.append(f"- 待澄清问题：{'；'.join(state.open_questions[:4])}")
    if state.next_steps:
        lines.append(f"- 最近建议动作：{'；'.join(state.next_steps[:3])}")
    return "\n".join(lines)


def extract_current_action(texts: list[str]) -> ActionType | None:
    for text in reversed(texts):
        normalized = text.lower()
        for label, action in ACTION_BY_LABEL.items():
            if re.search(rf"当前动作类型\s*[:：]?\s*{re.escape(label)}", normalized, re.IGNORECASE):
                return action
        for label, action in ACTION_BY_LABEL.items():
            if label in text:
                return action
    return None


def extract_lines(texts: list[str], terms: list[str]) -> list[str]:
    found: list[str] = []
    for text in texts:
        for raw_line in text.splitlines():
            line = clean_line(raw_line)
            if not line:
                continue
            if is_panel_noise(line):
                continue
            if any(term in line for term in terms):
                found.append(line)
    return found


def extract_questions(texts: list[str]) -> list[str]:
    found: list[str] = []
    for text in texts:
        for raw_line in text.splitlines():
            line = clean_line(raw_line)
            if line.endswith(("?", "？")):
                found.append(line)
    return found


def clean_line(value: str) -> str:
    line = value.strip()
    line = re.sub(r"^#{1,6}\s*", "", line)
    line = re.sub(r"^[-*]\s+", "", line)
    line = re.sub(r"^\d+[.)、]\s*", "", line)
    line = re.sub(r"^(Goal|Question|目标|问题)\s*[:：]\s*", "", line, flags=re.IGNORECASE)
    line = re.sub(r"\*\*([^*]+)\*\*", r"\1", line)
    line = line.strip(" >`|")
    if not line or set(line) <= {"-", "|", ":"}:
        return ""
    return line[:180]


def is_panel_noise(value: str) -> bool:
    line = value.strip()
    if not line:
        return True
    if line.startswith(("当前动作类型", "当前动作", "简洁结论", "详细分析")):
        return True
    return any(re.search(pattern, line, re.IGNORECASE) for pattern in LOW_SIGNAL_PATTERNS)


def unique_tail(items: list[str], limit: int) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in reversed(items):
        key = item.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
        if len(result) >= limit:
            break
    return list(reversed(result))


def make_summary(
    goal: str,
    user_texts: list[str],
    action: ActionType | None,
    concerns: list[str],
) -> str:
    subject = extract_decision_subject(goal, user_texts)
    parts = [f"正在判断：{subject[:160]}"]
    if action:
        parts.append(f"当前建议：{ACTION_SUMMARY_LABEL[action]}")
    if concerns:
        parts.append(f"主要担心：{concerns[-1][:100]}")
    return "；".join(parts)[:800]


def extract_decision_subject(goal: str, user_texts: list[str]) -> str:
    candidates = []
    for text in user_texts:
        for raw_line in split_sentences(text):
            line = clean_line(raw_line)
            if not line or is_panel_noise(line):
                continue
            candidates.append(line)

    for line in reversed(candidates):
        if any(term in line for term in PRIMARY_GOAL_TERMS):
            return normalize_subject(line)
    for line in reversed(candidates):
        if any(term in line for term in QUESTION_GOAL_TERMS):
            return normalize_subject(line)
    if candidates:
        return normalize_subject(candidates[-1])

    cleaned_goal = clean_line(goal)
    if cleaned_goal and not is_panel_noise(cleaned_goal):
        return normalize_subject(cleaned_goal)
    return "这个决策还没有说清楚"


def split_sentences(value: str) -> list[str]:
    parts = re.split(r"[\n。！？!?；;]+", value)
    return [part.strip() for part in parts if part.strip()]


def normalize_subject(value: str) -> str:
    line = value.strip()
    line = re.sub(r"^(目标|问题|最新补充)\s*[:：]\s*", "", line)
    line = line.strip(" 。；")
    return line or "这个决策还没有说清楚"
