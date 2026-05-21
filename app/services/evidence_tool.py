from __future__ import annotations

import re
import sqlite3
from typing import Any

from app import repository
from app.db import json_dumps
from app.models import EvidenceRunRequest, EvidenceRunResponse
from app.services.decision_brief import build_decision_brief
from app.services.decision_memory import build_decision_state
from app.services.smart_search import SmartSearchError, run_fetch, run_search


FACTUAL_TERMS = [
    "市场",
    "价格",
    "成本",
    "竞品",
    "法规",
    "政策",
    "合同",
    "风险",
    "收入",
    "付费",
    "用户",
    "数据",
    "趋势",
    "平台",
    "工具",
    "城市",
    "产品",
]


def build_evidence_queries(conn: sqlite3.Connection, case_id: int, focus: str = "", limit: int = 3) -> list[str]:
    case = repository.get_case(conn, case_id)
    state = build_decision_state(conn, case_id)
    brief = build_decision_brief(conn, case_id)
    candidates: list[str] = []

    if focus.strip():
        candidates.append(focus.strip())
    candidates.extend(question for question in brief.information_gaps if is_factual_question(question))
    candidates.extend(question for question in state.open_questions if is_factual_question(question))
    if state.summary:
        candidates.append(f"{state.summary} 需要核验的事实")
    candidates.append(f"{case.title} {case.user_goal} {case.current_question}".strip())

    queries = []
    for candidate in candidates:
        query = normalize_query(candidate)
        if not query or query in queries:
            continue
        queries.append(query)
        if len(queries) >= limit:
            break
    return queries


def run_evidence_tool(
    conn: sqlite3.Connection,
    case_id: int,
    payload: EvidenceRunRequest,
) -> EvidenceRunResponse:
    repository.get_case(conn, case_id)
    queries = build_evidence_queries(conn, case_id, payload.focus, payload.max_queries)
    all_items = []
    notes = []
    fetched_count = 0
    candidate_count = 0
    remaining_fetches = payload.fetch_sources

    if not queries:
        notes.append("没有形成可执行的证据查询。")
        return EvidenceRunResponse(notes=notes)

    for query in queries:
        try:
            search_data = run_search(query, extra_sources=2)
        except SmartSearchError as exc:
            all_items.append(
                repository.add_evidence(
                    conn,
                    case_id,
                    query=query,
                    title="smart-search search failed",
                    source_type="metadata",
                    fetched_text=str(exc),
                    confidence="error",
                )
            )
            notes.append(f"搜索失败：{query}")
            continue

        candidates = repository.store_search_result(conn, case_id, query, search_data)
        all_items.extend(candidates)
        candidate_count += len(candidates)

        for source in source_candidates(search_data):
            if remaining_fetches <= 0:
                break
            url = source.get("url", "").strip()
            if not url or repository.fetched_evidence_url_exists(conn, case_id, url):
                continue
            try:
                fetch_data = run_fetch(url)
            except SmartSearchError as exc:
                all_items.append(
                    repository.add_evidence(
                        conn,
                        case_id,
                        query=query,
                        url=url,
                        title=source.get("title", "") or url,
                        source_type="fetch_error",
                        fetched_text=str(exc),
                        confidence="error",
                    )
                )
                notes.append(f"抓取失败：{url}")
                remaining_fetches -= 1
                continue

            item = repository.add_evidence(
                conn,
                case_id,
                query=query,
                url=url,
                title=fetch_title(fetch_data, source),
                source_type="fetched_page",
                fetched_text=fetch_text(fetch_data),
                confidence="fetched",
            )
            all_items.append(item)
            fetched_count += 1
            remaining_fetches -= 1

        if remaining_fetches <= 0:
            break

    if fetched_count == 0:
        notes.append("已保存候选来源，但还没有成功抓取可引用页面。")
    return EvidenceRunResponse(
        queries=queries,
        fetched_count=fetched_count,
        candidate_count=candidate_count,
        evidence_items=all_items,
        notes=notes,
    )


def source_candidates(data: dict[str, Any]) -> list[dict[str, Any]]:
    sources = []
    for key in ("primary_sources", "extra_sources", "sources"):
        value = data.get(key) or []
        if isinstance(value, list):
            sources.extend(item for item in value if isinstance(item, dict))

    seen = set()
    unique = []
    for source in sources:
        url = source.get("url", "")
        if not url or url in seen:
            continue
        seen.add(url)
        unique.append(source)
    return unique


def fetch_title(data: dict[str, Any], fallback: dict[str, Any]) -> str:
    for key in ("title", "name"):
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()[:300]
    return (fallback.get("title") or fallback.get("url") or "Fetched source")[:300]


def fetch_text(data: dict[str, Any]) -> str:
    for key in ("content", "markdown", "text", "raw_content"):
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()[:8000]
    return json_dumps(data)[:8000]


def normalize_query(value: str) -> str:
    query = re.sub(r"\s+", " ", value).strip(" -。；:")
    query = query.replace("还没有外部证据或事实核验", "").strip(" -。；:")
    return query[:300]


def is_factual_question(value: str) -> bool:
    if "还没有外部证据" in value:
        return False
    return any(term in value for term in FACTUAL_TERMS)
