from __future__ import annotations

import sqlite3
from typing import Iterator

from app import repository
from app.config import get_settings
from app.models import AgentReplyRequest, ConversationMessage, EvidenceRunRequest, MessageCreate
from app.services.decision_brief import brief_context_text, build_decision_brief
from app.services.decision_engine import classify_problem
from app.services.decision_memory import build_decision_state, refresh_case_summary, state_context_text
from app.services.evidence_tool import run_evidence_tool
from app.services.llm import chat_completion, chat_completion_stream
from app.services.smart_search import SmartSearchError


SYSTEM_PROMPT = """你是 REAL 决策 Agent，不是普通聊天助手。

你的任务是帮助用户把犹豫转成可执行的下一步。必须使用 REAL 流程：
Reality 现实检验、Expected Value 期望、多准则评分、Anti-ruin 防毁灭风险、Premortem 前摄失败、Information Value 小成本买信息、Leverage 投入比例。

交互方式：
- 用户通常一开始说不清楚，不要要求用户自己填表。
- 你要从自然语言里提取：目标、选项、约束、担心、证据缺口、基本盘风险、可逆性、可小试动作。
- 信息不足时，先给“我已提取到什么”，再问 2 到 4 个关键问题。
- 信息足够时，再给粗略测算；概率、权重、风险必须标注为“暂定假设”，并允许用户修正。
- 你所在系统已经接入 smart-search 证据工具层，具备联网检索和网页抓取能力。
- 如果用户问你是否能联网搜索，要如实回答：可以通过系统的 smart-search 证据工具进行联网检索、抓取关键网页、保存证据，但不是任意实时浏览器操控。
- 不要说“我不能联网搜索”“我没有实时浏览能力”“只能基于已知知识”，除非系统明确返回搜索失败。
- 如果需要外部事实，不要让用户自己想搜索词；你应说明要核验什么，系统会在后台检索、抓取并记录证据。

输出要求：
- 用中文，简洁，像一个谨慎的决策教练。
- 使用 Markdown，小标题和列表要清楚。
- 每次回复必须分成两个顶层部分：
  1. `## 简洁结论`：默认可见，控制在 120-220 字；先给结论、当前动作类型、1-3 个下一步动作。
  2. `## 详细分析`：放推理、REAL 各模块、粗略测算、证据缺口、前摄失败、止损线。
- 不要把关键结论只放在详细分析里。
- 不要假装确定未知事实；需要事实时明确指出需要搜索或核验。
- 不要直接鼓励重仓或不可逆承诺。
- 每次回复最后都给出“当前动作类型”：拒绝、观察、小试、分阶段加码。信息不足时通常是“观察”或“小试”。
- 给出 1 到 3 个下一步动作，尽量可逆、低成本。
"""


def generate_reply(conn: sqlite3.Connection, case_id: int, payload: AgentReplyRequest) -> ConversationMessage:
    settings = get_settings()
    content = chat_completion(settings, messages=build_llm_messages(conn, case_id, payload))
    message = repository.add_message(conn, case_id, MessageCreate(role="assistant", content=content))
    refresh_case_summary(conn, case_id)
    return message


def prepare_evidence_for_reply(conn: sqlite3.Connection, case_id: int, payload: AgentReplyRequest):
    messages = repository.list_messages(conn, case_id)[-payload.recent_message_limit :]
    return maybe_search(conn, case_id, payload.note, messages)


def generate_reply_stream(conn: sqlite3.Connection, case_id: int, payload: AgentReplyRequest) -> Iterator[str]:
    chunks: list[str] = []
    for chunk in stream_reply_content(conn, case_id, payload):
        chunks.append(chunk)
        yield chunk
    content = "".join(chunks).strip()
    if content:
        repository.add_message(conn, case_id, MessageCreate(role="assistant", content=content))
        refresh_case_summary(conn, case_id)


def stream_reply_content(conn: sqlite3.Connection, case_id: int, payload: AgentReplyRequest) -> Iterator[str]:
    settings = get_settings()
    yield from chat_completion_stream(settings, messages=build_llm_messages(conn, case_id, payload))


def build_llm_messages(conn: sqlite3.Connection, case_id: int, payload: AgentReplyRequest) -> list[dict[str, str]]:
    case = repository.get_case(conn, case_id)
    messages = repository.list_messages(conn, case_id)[-payload.recent_message_limit :]
    maybe_search(conn, case_id, payload.note, messages)
    evidence = repository.list_evidence(conn, case_id)[:6]
    state = build_decision_state(conn, case_id)
    brief = build_decision_brief(conn, case_id)

    user_context = [
        "工具能力：本系统已接入 smart-search 证据工具层，可联网检索、抓取关键网页、保存候选/已抓取证据，并把证据摘要提供给你。你不能声称自己没有联网搜索能力；应说明能力边界是通过证据工具检索和抓取，而不是直接操作浏览器。",
        f"决策标题：{case.title}",
        f"目标：{case.user_goal}",
        f"当前问题：{case.current_question}",
        f"问题类型：{case.classification}",
        f"风险/紧急程度：{case.stakes}/{case.urgency}",
        f"系统判断是否需要外部搜索：{'是' if case.search_required else '否'}",
        state_context_text(state),
        brief_context_text(brief),
    ]
    if payload.note:
        user_context.append(f"用户本次附加说明：{payload.note}")
    if evidence:
        user_context.append("已有证据摘要：")
        for item in evidence:
            title = item.title or item.url or item.query
            user_context.append(f"- {title} | {item.confidence} | {item.fetched_text[:300]}")
    else:
        user_context.append("已有证据摘要：暂无。")

    llm_messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    llm_messages.append({"role": "user", "content": "\n".join(user_context)})
    for message in messages:
        llm_messages.append({"role": message.role, "content": message.content})
    return llm_messages


def maybe_search(
    conn: sqlite3.Connection,
    case_id: int,
    note: str,
    messages: list[ConversationMessage],
) -> object | None:
    if repository.list_evidence(conn, case_id):
        return None

    latest_user_text = note.strip()
    if not latest_user_text:
        for message in reversed(messages):
            if message.role == "user":
                latest_user_text = message.content
                break

    if not latest_user_text:
        return None

    classification = classify_problem(latest_user_text)
    if not classification["search_required"]:
        return None

    query = latest_user_text[:300]
    try:
        return run_evidence_tool(
            conn,
            case_id,
            EvidenceRunRequest(focus=query, max_queries=1, fetch_sources=2),
        )
    except SmartSearchError as exc:
        repository.add_evidence(
            conn,
            case_id,
            query=query,
            title="smart-search failed",
            source_type="metadata",
            fetched_text=str(exc),
            confidence="error",
        )
    return None
