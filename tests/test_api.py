from __future__ import annotations

import importlib

from fastapi.testclient import TestClient


def build_client(monkeypatch, tmp_path) -> TestClient:
    monkeypatch.setenv("REAL_DATABASE_PATH", str(tmp_path / "test.db"))
    import app.db
    import app.main

    importlib.reload(app.db)
    importlib.reload(app.main)
    return TestClient(app.main.app)


def test_create_case_and_message(monkeypatch, tmp_path):
    client = build_client(monkeypatch, tmp_path)
    with client:
        response = client.post(
            "/api/cases",
            json={
                "title": "是否先试一个流程改进",
                "user_goal": "想减少重复操作，但不想打断当前安排。",
                "current_question": "是否先用一周做小范围试行？",
            },
        )
        assert response.status_code == 200
        case = response.json()
        assert case["id"] > 0
        assert case["classification"] in {"clarify_first", "analyzable"}

        response = client.post(
            f"/api/cases/{case['id']}/messages",
            json={"role": "user", "content": "我现在最担心的是试用期风险。"},
        )
        assert response.status_code == 200

        response = client.get(f"/api/cases/{case['id']}/messages")
        assert response.status_code == 200
        assert len(response.json()) == 2


def test_llm_config_status(monkeypatch, tmp_path):
    monkeypatch.setenv("LLM_BASE_URL", "https://example.test/v1")
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    monkeypatch.setenv("LLM_MODEL", "test-model")
    client = build_client(monkeypatch, tmp_path)
    with client:
        response = client.get("/api/llm/config")
        assert response.status_code == 200
        data = response.json()
        assert data["configured"] is True
        assert data["model"] == "test-model"


def test_optional_access_token_auth(monkeypatch, tmp_path):
    monkeypatch.setenv("REAL_ACCESS_TOKEN", "secret-token")
    client = build_client(monkeypatch, tmp_path)
    with client:
        status = client.get("/api/auth/status")
        assert status.status_code == 200
        assert status.json() == {"required": True}

        assert client.get("/api/health").status_code == 200
        assert client.get("/api/cases").status_code == 401
        assert client.get("/api/cases", headers={"Authorization": "Bearer wrong"}).status_code == 401

        authorized = client.post(
            "/api/cases",
            headers={"Authorization": "Bearer secret-token"},
            json={
                "title": "需要保护的决策",
                "user_goal": "部署到手机访问时不想裸奔。",
                "current_question": "是否加访问令牌？",
            },
        )
        assert authorized.status_code == 200

        via_header = client.get("/api/cases", headers={"X-REAL-Token": "secret-token"})
        assert via_header.status_code == 200
        assert via_header.json()[0]["title"] == "需要保护的决策"


def test_agent_message_records_user_and_assistant(monkeypatch, tmp_path):
    monkeypatch.setenv("LLM_BASE_URL", "https://example.test/v1")
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    monkeypatch.setenv("LLM_MODEL", "test-model")
    client = build_client(monkeypatch, tmp_path)

    def fake_chat_completion(settings, *, messages, temperature=0.2, max_tokens=900):
        assert settings.llm_configured is True
        assert any("REAL 决策 Agent" in item["content"] for item in messages)
        assert any("当前决策状态快照" in item["content"] for item in messages)
        assert any("当前决策简报" in item["content"] for item in messages)
        return "## 简洁结论\n先观察，不要重投入。\n\n**当前动作类型：观察**\n\n## 详细分析\n- 主要担心：占用时间。\n- 下一步：先记录一周耗时。"

    monkeypatch.setattr("app.services.decision_agent.chat_completion", fake_chat_completion)

    with client:
        case = client.post(
            "/api/cases",
            json={
                "title": "是否先试一个流程改进",
                "user_goal": "想减少重复操作，但不想打断当前安排。",
                "current_question": "是否先用一周做小范围试行？",
            },
        ).json()
        response = client.post(
            f"/api/cases/{case['id']}/agent/message",
            json={"content": "我担心试行会占用太多时间。"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["user_message"]["role"] == "user"
        assert data["assistant_message"]["role"] == "assistant"
        assert "当前动作类型" in data["assistant_message"]["content"]

        state = client.get(f"/api/cases/{case['id']}/state").json()
        assert state["current_action"] == "observe"
        assert state["evidence_count"] == 0
        assert any("担心" in item for item in state["concerns"])
        assert "正在判断：" in state["summary"]


def test_agent_message_stream_records_assistant(monkeypatch, tmp_path):
    monkeypatch.setenv("LLM_BASE_URL", "https://example.test/v1")
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    monkeypatch.setenv("LLM_MODEL", "test-model")
    client = build_client(monkeypatch, tmp_path)

    def fake_chat_completion_stream(settings, *, messages, temperature=0.2, max_tokens=900):
        yield "## 简洁结论\n建议先观察。"
        yield "\n\n## 详细分析\n- 信息还不够。"

    monkeypatch.setattr("app.services.decision_agent.chat_completion_stream", fake_chat_completion_stream)

    with client:
        case = client.post(
            "/api/cases",
            json={
                "title": "是否先试一个流程改进",
                "user_goal": "想减少重复操作，但不想打断当前安排。",
                "current_question": "是否先用一周做小范围试行？",
            },
        ).json()
        with client.stream(
            "POST",
            f"/api/cases/{case['id']}/agent/message/stream",
            json={"content": "我担心试行会占用太多时间。"},
        ) as response:
            assert response.status_code == 200
            body = "".join(response.iter_text())
            assert "event: delta" in body
            assert "event: done" in body

        messages = client.get(f"/api/cases/{case['id']}/messages").json()
        assert messages[-1]["role"] == "assistant"
        assert "## 简洁结论" in messages[-1]["content"]
        assert "## 详细分析" in messages[-1]["content"]

        case_after = client.get(f"/api/cases/{case['id']}").json()
        assert "当前建议" in case_after["summary"]


def test_case_state_extracts_questions_and_options(monkeypatch, tmp_path):
    client = build_client(monkeypatch, tmp_path)
    with client:
        case = client.post(
            "/api/cases",
            json={
                "title": "是否投入一个小项目",
                "user_goal": "想验证一个副业想法。",
                "current_question": "要不要本周开始？",
            },
        ).json()
        client.post(
            f"/api/cases/{case['id']}/messages",
            json={"role": "user", "content": "我担心晚上太累，但是想先小试。"},
        )
        client.post(
            f"/api/cases/{case['id']}/messages",
            json={
                "role": "assistant",
                "content": "## 简洁结论\n建议小试。\n\n当前动作类型：小试\n\n## 详细分析\n- 方案：先做 3 天验证。\n- 你能接受每天 30 分钟吗？\n- 下一步：先记录精力。",
            },
        )

        response = client.get(f"/api/cases/{case['id']}/state")
        assert response.status_code == 200
        state = response.json()
        assert state["current_action"] == "small_experiment"
        assert any("担心" in item for item in state["concerns"])
        assert any("方案" in item for item in state["candidate_options"])
        assert any(item.endswith("吗？") for item in state["open_questions"])


def test_case_state_ignores_greeting_when_extracting_subject(monkeypatch, tmp_path):
    client = build_client(monkeypatch, tmp_path)
    with client:
        case = client.post(
            "/api/cases",
            json={
                "title": "你好",
                "user_goal": "你好",
                "current_question": "你好",
            },
        ).json()
        client.post(
            f"/api/cases/{case['id']}/messages",
            json={"role": "user", "content": "你是什么模型？"},
        )
        client.post(
            f"/api/cases/{case['id']}/messages",
            json={"role": "user", "content": "我想做副业赚钱，但只有晚上和周末有时间。"},
        )
        client.post(
            f"/api/cases/{case['id']}/messages",
            json={
                "role": "assistant",
                "content": "## 简洁结论\n建议小试。\n\n当前动作类型：小试\n\n## 详细分析\n- 下一步：先核验 10 个竞品。\n- 你每周大概能拿出多少小时？",
            },
        )

        state = client.get(f"/api/cases/{case['id']}/state").json()
        assert "正在判断：我想做副业赚钱" in state["summary"]
        assert "目标：你好" not in state["summary"]
        assert all("当前动作类型" not in item for item in state["next_steps"])


def test_decision_brief_downgrades_ruin_risk(monkeypatch, tmp_path):
    client = build_client(monkeypatch, tmp_path)
    with client:
        case = client.post(
            "/api/cases",
            json={
                "title": "是否加入一个组织",
                "user_goal": "想找归属感。",
                "current_question": "对方要求交钱、服从、不能质疑，要不要加入？",
            },
        ).json()
        client.post(
            f"/api/cases/{case['id']}/messages",
            json={"role": "user", "content": "我担心被控制，退出不了，还可能借钱交费。"},
        )
        client.post(
            f"/api/cases/{case['id']}/messages",
            json={
                "role": "assistant",
                "content": "## 简洁结论\n不要加入。\n\n当前动作类型：拒绝\n\n## 详细分析\n- 方案：拒绝当前版本。",
            },
        )

        response = client.get(f"/api/cases/{case['id']}/brief")
        assert response.status_code == 200
        brief = response.json()
        assert brief["recommended_action"] == "reject"
        assert "debt" in brief["risk_flags"]
        assert "freedom" in brief["risk_flags"]
        assert brief["premortem"]
        assert brief["stop_conditions"]


def test_decision_brief_supports_small_experiment(monkeypatch, tmp_path):
    client = build_client(monkeypatch, tmp_path)
    with client:
        case = client.post(
            "/api/cases",
            json={
                "title": "是否试一个小项目",
                "user_goal": "想验证一个轻量副业想法。",
                "current_question": "要不要先做一周？",
            },
        ).json()
        client.post(
            f"/api/cases/{case['id']}/messages",
            json={
                "role": "assistant",
                "content": "## 简洁结论\n建议小试。\n\n当前动作类型：小试\n\n## 详细分析\n- 下一步：设计 7 天实验。\n- 你能接受每天 30 分钟吗？",
            },
        )

        brief = client.get(f"/api/cases/{case['id']}/brief").json()
        assert brief["recommended_action"] == "small_experiment"
        assert any("复盘" in item or "上限" in item for item in brief["stop_conditions"])
        assert brief["information_gaps"]


def test_action_plan_and_journal_from_brief(monkeypatch, tmp_path):
    client = build_client(monkeypatch, tmp_path)
    with client:
        case = client.post(
            "/api/cases",
            json={
                "title": "是否试一个小项目",
                "user_goal": "想验证一个轻量副业想法。",
                "current_question": "要不要先做一周？",
            },
        ).json()
        client.post(
            f"/api/cases/{case['id']}/messages",
            json={
                "role": "assistant",
                "content": "## 简洁结论\n建议小试。\n\n当前动作类型：小试\n\n## 详细分析\n- 下一步：设计 7 天实验。\n- 你能接受每天 30 分钟吗？",
            },
        )

        plan_response = client.get(f"/api/cases/{case['id']}/action-plan")
        assert plan_response.status_code == 200
        plan = plan_response.json()
        assert plan["action"] == "small_experiment"
        assert plan["timebox_days"] == 7
        assert plan["review_date"]
        assert plan["success_signals"]
        assert plan["failure_signals"]
        assert "Recommended action" in plan["journal_rationale"]

        journal_response = client.post(f"/api/cases/{case['id']}/journal/from-brief")
        assert journal_response.status_code == 200
        journal = journal_response.json()
        assert journal["final_action"] == "small_experiment"
        assert journal["follow_up_date"] == plan["review_date"]
        assert "Recommended action" in journal["rationale"]

        duplicate_response = client.post(f"/api/cases/{case['id']}/journal/from-brief")
        assert duplicate_response.status_code == 200
        duplicate = duplicate_response.json()
        assert duplicate["id"] == journal["id"]

        journals = client.get(f"/api/cases/{case['id']}/journal").json()
        assert len(journals) == 1


def test_journal_review_and_outcome_update(monkeypatch, tmp_path):
    client = build_client(monkeypatch, tmp_path)
    with client:
        case = client.post(
            "/api/cases",
            json={
                "title": "是否试一个小项目",
                "user_goal": "想验证一个轻量想法。",
                "current_question": "要不要先做三天？",
            },
        ).json()
        journal = client.post(
            f"/api/cases/{case['id']}/journal",
            json={
                "final_action": "small_experiment",
                "rationale": "先做一个很小的验证。",
                "stop_conditions": "- 超过时间上限就停。",
                "follow_up_date": "2000-01-01",
                "outcome": "",
            },
        ).json()

        due_response = client.get("/api/reviews/due")
        assert due_response.status_code == 200
        due_items = due_response.json()
        assert len(due_items) == 1
        assert due_items[0]["journal"]["id"] == journal["id"]
        assert due_items[0]["status"] == "overdue"
        assert "逾期" in due_items[0]["review_prompt"]

        patch_response = client.patch(
            f"/api/cases/{case['id']}/journal/{journal['id']}",
            json={"outcome": "成功做到了三天，确实有帮助。"},
        )
        assert patch_response.status_code == 200
        updated = patch_response.json()
        assert "成功做到了" in updated["outcome"]

        due_after = client.get("/api/reviews/due").json()
        assert due_after == []

        reviews = client.get(f"/api/cases/{case['id']}/reviews").json()
        assert reviews[0]["status"] == "completed"
        assert "偏正面" in reviews[0]["learning_summary"]


def test_case_rename_delete_and_journal_delete(monkeypatch, tmp_path):
    client = build_client(monkeypatch, tmp_path)
    with client:
        case = client.post(
            "/api/cases",
            json={
                "title": "临时决策",
                "user_goal": "测试重命名和删除。",
                "current_question": "是否保留？",
            },
        ).json()

        rename_response = client.patch(
            f"/api/cases/{case['id']}",
            json={"title": "重命名后的决策"},
        )
        assert rename_response.status_code == 200
        assert rename_response.json()["title"] == "重命名后的决策"

        journal = client.post(
            f"/api/cases/{case['id']}/journal",
            json={
                "final_action": "observe",
                "rationale": "先观察。",
                "stop_conditions": "",
                "follow_up_date": "2099-01-01",
                "outcome": "",
            },
        ).json()
        delete_journal_response = client.delete(f"/api/cases/{case['id']}/journal/{journal['id']}")
        assert delete_journal_response.status_code == 204
        assert client.get(f"/api/cases/{case['id']}/journal").json() == []

        delete_case_response = client.delete(f"/api/cases/{case['id']}")
        assert delete_case_response.status_code == 204
        missing_response = client.get(f"/api/cases/{case['id']}")
        assert missing_response.status_code == 404


def test_evidence_tool_searches_and_fetches_sources(monkeypatch, tmp_path):
    client = build_client(monkeypatch, tmp_path)

    def fake_run_search(query, extra_sources=2):
        return {
            "_command": f"smart-search search {query}",
            "_output_path": "C:/tmp/fake-search.json",
            "source_warning": "fetch before claim",
            "primary_sources": [
                {
                    "url": "https://example.com/source-a",
                    "title": "Source A",
                    "description": "candidate snippet",
                }
            ],
        }

    def fake_run_fetch(url):
        return {
            "_command": f"smart-search fetch {url}",
            "_output_path": "C:/tmp/fake-fetch.json",
            "title": "Fetched Source A",
            "content": "This is fetched page text that can be cited by the decision agent.",
        }

    monkeypatch.setattr("app.services.evidence_tool.run_search", fake_run_search)
    monkeypatch.setattr("app.services.evidence_tool.run_fetch", fake_run_fetch)

    with client:
        case = client.post(
            "/api/cases",
            json={
                "title": "是否做一个小服务",
                "user_goal": "我想了解市场上有没有竞品。",
                "current_question": "需要核验竞品和付费情况。",
            },
        ).json()

        response = client.post(
            f"/api/cases/{case['id']}/evidence/run",
            json={"focus": "竞品 付费 市场", "max_queries": 1, "fetch_sources": 1},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["queries"] == ["竞品 付费 市场"]
        assert data["fetched_count"] == 1
        assert data["candidate_count"] == 1

        evidence = client.get(f"/api/cases/{case['id']}/evidence").json()
        assert any(item["confidence"] == "fetched" for item in evidence)
        assert any(item["source_type"] == "metadata" for item in evidence)
        fetched = [item for item in evidence if item["confidence"] == "fetched"][0]
        assert fetched["url"] == "https://example.com/source-a"
        assert "fetched page text" in fetched["fetched_text"]


def test_evaluate_anti_ruin_gate(monkeypatch, tmp_path):
    client = build_client(monkeypatch, tmp_path)
    with client:
        case = client.post(
            "/api/cases",
            json={
                "title": "是否加入高控制组织",
                "user_goal": "想找归属感，但不想失去判断力。",
                "current_question": "要不要交钱加入？",
            },
        ).json()
        response = client.post(
            f"/api/cases/{case['id']}/evaluate",
            json={
                "options": [
                    {
                        "option_label": "直接加入",
                        "outcomes": [
                            {"label": "good", "probability": 0.4, "utility": 8},
                            {"label": "bad", "probability": 0.6, "utility": -8},
                        ],
                        "reversibility": 0.1,
                        "control_cost": 0.9,
                        "ruin_flags": ["judgment"],
                        "information_value": 0.7,
                    }
                ]
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["best_action"] == "reject"
        assert data["results"][0]["risk_level"] == "ruin"
