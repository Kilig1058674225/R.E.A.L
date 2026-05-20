const state = {
  cases: [],
  activeCase: null,
  busy: false,
  decisionState: null,
  brief: null,
  actionPlan: null,
  reviews: [],
};

const $ = (id) => document.getElementById(id);

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(data.detail || `Request failed: ${response.status}`);
  }
  if (response.status === 204) {
    return null;
  }
  const text = await response.text();
  return text ? JSON.parse(text) : null;
}

function renderCases() {
  $("caseCount").textContent = state.cases.length;
  const list = $("caseList");
  list.innerHTML = "";
  state.cases.forEach((item) => {
    const row = document.createElement("div");
    row.className = `case-item ${state.activeCase?.id === item.id ? "active" : ""}`;

    const main = document.createElement("button");
    main.className = "case-main";
    main.type = "button";
    main.innerHTML = `
      <strong>${escapeHtml(item.title)}</strong>
      <span>${escapeHtml(item.classification)} · ${new Date(item.updated_at).toLocaleDateString()}</span>
    `;
    main.onclick = () => selectCase(item.id);

    const actions = document.createElement("div");
    actions.className = "case-actions";
    actions.appendChild(createIconButton("重命名", "rename", () => renameCase(item)));
    actions.appendChild(createIconButton("删除", "delete", () => deleteCase(item)));

    row.appendChild(main);
    row.appendChild(actions);
    list.appendChild(row);
  });
}

function renderCase(item) {
  $("emptyState").classList.toggle("hidden", Boolean(item));
  if (!item) {
    $("caseMeta").textContent = "";
    $("caseName").textContent = "新的决策";
    $("classification").textContent = "";
    $("stakes").textContent = "";
    $("searchRequired").textContent = "";
    $("decisionPanel").classList.add("hidden");
    return;
  }

  $("decisionPanel").classList.remove("hidden");
  $("caseMeta").textContent = `#${item.id} · ${item.status} · ${new Date(item.updated_at).toLocaleString()}`;
  $("caseName").textContent = item.title;
  $("classification").textContent = item.classification;
  $("stakes").textContent = `${item.stakes} / ${item.urgency}`;
  $("searchRequired").textContent = item.search_required ? "可能需要核验" : "先对话澄清";
}

async function renameCase(item) {
  if (state.busy) return;
  const nextTitle = window.prompt("重命名对话", item.title);
  if (nextTitle === null) return;
  const title = nextTitle.trim();
  if (!title || title === item.title) return;

  setBusy(true);
  try {
    const updated = await api(`/api/cases/${item.id}`, {
      method: "PATCH",
      body: JSON.stringify({ title }),
    });
    if (state.activeCase?.id === item.id) {
      state.activeCase = updated;
    }
    await loadCases();
  } catch (error) {
    alert(error.message);
  } finally {
    setBusy(false);
  }
}

async function deleteCase(item) {
  if (state.busy) return;
  const ok = window.confirm(`删除“${item.title}”？这会同时删除这条决策的消息、证据和 Journal。`);
  if (!ok) return;

  setBusy(true);
  try {
    await api(`/api/cases/${item.id}`, { method: "DELETE" });
    if (state.activeCase?.id === item.id) {
      state.activeCase = null;
    }
    await loadCases();
  } catch (error) {
    alert(error.message);
  } finally {
    setBusy(false);
  }
}

async function loadCases() {
  state.cases = await api("/api/cases");
  if (state.activeCase) {
    state.activeCase = state.cases.find((item) => item.id === state.activeCase.id) || null;
  }
  if (!state.activeCase && state.cases.length > 0) {
    state.activeCase = state.cases[0];
  }
  renderCases();
  renderCase(state.activeCase);
  if (state.activeCase) {
    await Promise.all([loadMessages(), loadDecisionPanel()]);
  } else {
    $("messages").innerHTML = "";
    clearDecisionPanel();
  }
}

async function selectCase(id) {
  state.activeCase = await api(`/api/cases/${id}`);
  renderCases();
  renderCase(state.activeCase);
  await Promise.all([loadMessages(), loadDecisionPanel()]);
}

async function loadMessages() {
  if (!state.activeCase) return;
  const messages = await api(`/api/cases/${state.activeCase.id}/messages`);
  const box = $("messages");
  box.innerHTML = "";
  $("emptyState").classList.toggle("hidden", messages.length > 0);
  messages.forEach((message) => {
    box.appendChild(createMessageNode(message.role, message.content));
  });
  document.querySelector(".chat-scroll").scrollTop = document.querySelector(".chat-scroll").scrollHeight;
}

async function handleComposer(event) {
  event.preventDefault();
  if (state.busy) return;
  const content = $("composerInput").value.trim();
  if (!content) return;

  setBusy(true);
  try {
    $("composerInput").value = "";
    if (!state.activeCase) {
      const created = await api("/api/cases", {
        method: "POST",
        body: JSON.stringify({
          title: deriveTitle(content),
          user_goal: content,
          current_question: content,
        }),
      });
      state.activeCase = created;
      renderCase(created);
      await loadCases();
      await streamAssistant(`/api/cases/${created.id}/agent/respond/stream`, { note: content });
    } else {
      appendLocalMessage("user", content);
      await streamAssistant(`/api/cases/${state.activeCase.id}/agent/message/stream`, { content });
    }
    await loadCases();
  } catch (error) {
    alert(error.message);
  } finally {
    setBusy(false);
  }
}

function createMessageNode(role, content, options = {}) {
  const node = document.createElement("article");
  node.className = `message ${role}${options.streaming ? " streaming" : ""}`;
  const body =
    role === "assistant"
      ? renderAssistantMessage(content, { detailOpen: Boolean(options.detailOpen) })
      : renderPlainText(content);
  node.innerHTML = `
    <div class="avatar">${role === "assistant" ? "R" : "你"}</div>
    <div class="message-content">
      <div class="role">${role === "assistant" ? "REAL" : "你"}</div>
      <div class="message-body">${body}</div>
    </div>
  `;
  return node;
}

function appendLocalMessage(role, content, options = {}) {
  $("emptyState").classList.add("hidden");
  const node = createMessageNode(role, content, options);
  $("messages").appendChild(node);
  scrollChatToBottom();
  return node;
}

async function streamAssistant(path, payload) {
  const assistantNode = appendLocalMessage("assistant", "", { streaming: true });
  const body = assistantNode.querySelector(".message-body");
  let content = "";

  await readEventStream(path, payload, {
    delta(chunk) {
      content += chunk;
      body.innerHTML = renderAssistantMessage(content, { detailOpen: true });
      scrollChatToBottom();
    },
    error(detail) {
      throw new Error(detail || "流式响应失败");
    },
  });

  assistantNode.classList.remove("streaming");
  body.innerHTML = renderAssistantMessage(content, { detailOpen: true });
  await loadDecisionPanel();
}

async function loadDecisionPanel() {
  if (!state.activeCase) {
    clearDecisionPanel();
    return;
  }
  const caseId = state.activeCase.id;
  const [decisionState, brief, actionPlan, reviews] = await Promise.all([
    api(`/api/cases/${caseId}/state`),
    api(`/api/cases/${caseId}/brief`),
    api(`/api/cases/${caseId}/action-plan`),
    api(`/api/cases/${caseId}/reviews`),
  ]);
  state.decisionState = decisionState;
  state.brief = brief;
  state.actionPlan = actionPlan;
  state.reviews = reviews;
  renderDecisionPanel();
}

function clearDecisionPanel() {
  state.decisionState = null;
  state.brief = null;
  state.actionPlan = null;
  state.reviews = [];
  $("panelAction").textContent = "-";
  $("panelActionHint").textContent = "";
  $("panelSummary").textContent = "暂无决策状态。";
  $("panelConfidence").textContent = "-";
  $("panelEvidence").textContent = "-";
  $("panelReviewDate").textContent = "-";
  $("panelPlanHint").textContent = "";
  $("panelReviewStatus").textContent = "";
  $("panelGapsHint").textContent = "";
  $("panelJournalHint").textContent = "";
  renderList("panelNextSteps", []);
  renderList("panelRisks", []);
  renderList("panelStops", []);
  renderList("panelGaps", []);
  renderJournalList([]);
}

function renderDecisionPanel() {
  const brief = state.brief;
  const actionPlan = state.actionPlan;
  const decisionState = state.decisionState;
  if (!brief || !actionPlan || !decisionState) return;

  $("panelAction").textContent = actionLabel(brief.recommended_action);
  $("panelActionHint").textContent = "这是系统当前给你的动作档位，不是最终判决。";
  $("panelSummary").textContent = brief.summary || decisionState.summary || "暂无摘要。";
  $("panelConfidence").textContent = confidenceLabel(brief.confidence);
  $("panelEvidence").textContent = `${decisionState.evidence_count || 0} 条`;
  $("panelReviewDate").textContent = actionPlan.review_date ? `复盘日 ${actionPlan.review_date}` : "-";
  $("panelPlanHint").textContent = "这里是可以先执行的小步动作；遇到不确定的，就回到聊天框继续说。";
  $("panelReviewStatus").textContent = reviewStatusText(state.reviews[0]);
  renderList("panelNextSteps", actionPlan.next_steps);
  renderList("panelRisks", brief.risk_flags.length ? brief.risk_flags : ["暂无明确风险标记"]);
  renderList("panelStops", actionPlan.stop_conditions);
  $("panelGapsHint").textContent = brief.information_gaps.length
    ? "这些问题可以现在直接回答；拿不准也可以先按上面的小步动作验证。"
    : "暂时没有必须补充的问题。";
  renderList("panelGaps", brief.information_gaps);
  $("panelJournalHint").textContent = "点“记录当前计划”后，到复盘日再填写结果。";
  renderJournalList(state.reviews);
}

function renderList(id, items) {
  const box = $(id);
  box.innerHTML = "";
  (items || []).slice(0, 6).forEach((item) => {
    const li = document.createElement("li");
    li.textContent = item;
    box.appendChild(li);
  });
}

function renderJournalList(reviews) {
  $("panelJournalCount").textContent = reviews.length;
  const box = $("panelJournalList");
  box.innerHTML = "";
  if (!reviews.length) {
    box.innerHTML = `<p class="empty-mini">还没有记录计划。</p>`;
    return;
  }
  reviews.slice(0, 3).forEach((review) => {
    const item = review.journal;
    const node = document.createElement("div");
    node.className = `journal-item ${review.status}`;
    node.innerHTML = `
      <div class="journal-head">
        <div>
          <strong>${actionLabel(item.final_action)}</strong>
          <span>${escapeHtml(statusLabel(review))}</span>
        </div>
        ${iconButtonMarkup("删除", "delete", "journal-delete-btn")}
      </div>
      <p>${escapeHtml(review.review_prompt)}</p>
    `;
    node.querySelector(".journal-delete-btn").onclick = () => deleteJournal(item.id);
    if (item.outcome) {
      const outcome = document.createElement("p");
      outcome.className = "journal-outcome";
      outcome.textContent = item.outcome;
      node.appendChild(outcome);
      if (review.learning_summary) {
        const learning = document.createElement("p");
        learning.className = "journal-learning";
        learning.textContent = review.learning_summary;
        node.appendChild(learning);
      }
    } else {
      const textarea = document.createElement("textarea");
      textarea.rows = 2;
      textarea.placeholder = "复盘结果：发生了什么？达到成功信号了吗？";
      textarea.className = "journal-outcome-input";
      const button = document.createElement("button");
      button.className = "journal-save-btn";
      button.type = "button";
      button.textContent = "记录结果";
      button.onclick = () => saveJournalOutcome(item.id, textarea.value);
      node.appendChild(textarea);
      node.appendChild(button);
    }
    box.appendChild(node);
  });
}

function statusLabel(review) {
  if (!review) return "-";
  if (review.status === "completed") return "已复盘";
  if (review.status === "overdue") return `逾期 ${review.days_delta} 天`;
  if (review.status === "due_today") return "今天复盘";
  if (review.status === "upcoming") return review.journal.follow_up_date || "未到期";
  return "未设复盘日";
}

function reviewStatusText(review) {
  if (!review) return "";
  if (review.status === "completed") return "最近一条计划已复盘。";
  if (review.status === "overdue" || review.status === "due_today") return review.review_prompt;
  if (review.status === "upcoming") return `下一次复盘：${review.journal.follow_up_date}`;
  return review.review_prompt || "";
}

async function savePlanToJournal() {
  if (!state.activeCase || state.busy) return;
  setBusy(true);
  try {
    await api(`/api/cases/${state.activeCase.id}/journal/from-brief`, { method: "POST" });
    await loadDecisionPanel();
  } catch (error) {
    alert(error.message);
  } finally {
    setBusy(false);
  }
}

async function saveJournalOutcome(journalId, value) {
  const outcome = value.trim();
  if (!state.activeCase || !outcome) {
    alert("先写一点复盘结果。");
    return;
  }
  setBusy(true);
  try {
    await api(`/api/cases/${state.activeCase.id}/journal/${journalId}`, {
      method: "PATCH",
      body: JSON.stringify({ outcome }),
    });
    await loadDecisionPanel();
  } catch (error) {
    alert(error.message);
  } finally {
    setBusy(false);
  }
}

async function deleteJournal(journalId) {
  if (!state.activeCase || state.busy) return;
  const ok = window.confirm("删除这条 Journal 计划记录？");
  if (!ok) return;

  setBusy(true);
  try {
    await api(`/api/cases/${state.activeCase.id}/journal/${journalId}`, { method: "DELETE" });
    await loadDecisionPanel();
  } catch (error) {
    alert(error.message);
  } finally {
    setBusy(false);
  }
}

async function readEventStream(path, payload, handlers) {
  const response = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(data.detail || `Request failed: ${response.status}`);
  }
  if (!response.body) {
    throw new Error("浏览器不支持流式响应。");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const events = buffer.split("\n\n");
    buffer = events.pop() || "";
    for (const rawEvent of events) {
      handleSseEvent(rawEvent, handlers);
    }
  }
  if (buffer.trim()) {
    handleSseEvent(buffer, handlers);
  }
}

function handleSseEvent(rawEvent, handlers) {
  const lines = rawEvent.split(/\r?\n/);
  let eventType = "message";
  const dataLines = [];
  lines.forEach((line) => {
    if (line.startsWith("event:")) {
      eventType = line.slice(6).trim();
    } else if (line.startsWith("data:")) {
      dataLines.push(line.slice(5).trimStart());
    }
  });
  if (!dataLines.length) return;
  const data = JSON.parse(dataLines.join("\n"));
  if (eventType === "delta") {
    handlers.delta?.(data.content || "");
  } else if (eventType === "error") {
    handlers.error?.(data.detail || "流式响应失败");
  }
}

function newCase() {
  state.activeCase = null;
  renderCases();
  renderCase(null);
  $("messages").innerHTML = "";
  $("composerInput").focus();
}

function setBusy(value) {
  state.busy = value;
  $("sendBtn").disabled = value;
  $("composerInput").disabled = value;
  $("sendBtn").textContent = value ? "思考中" : "发送";
}

function scrollChatToBottom() {
  const scroll = document.querySelector(".chat-scroll");
  scroll.scrollTop = scroll.scrollHeight;
}

function deriveTitle(content) {
  const compact = content.replace(/\s+/g, " ").trim();
  return compact.length > 28 ? `${compact.slice(0, 28)}...` : compact || "新的决策";
}

function createIconButton(label, icon, onClick) {
  const button = document.createElement("button");
  button.className = "icon-action-btn";
  button.type = "button";
  button.title = label;
  button.setAttribute("aria-label", label);
  button.innerHTML = iconSvg(icon);
  button.onclick = (event) => {
    event.stopPropagation();
    onClick();
  };
  return button;
}

function iconButtonMarkup(label, icon, className = "") {
  return `
    <button class="icon-action-btn ${className}" type="button" title="${escapeHtml(label)}" aria-label="${escapeHtml(label)}">
      ${iconSvg(icon)}
    </button>
  `;
}

function iconSvg(icon) {
  const icons = {
    rename:
      '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 20h9" /><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4Z" /></svg>',
    delete:
      '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 6h18" /><path d="M8 6V4h8v2" /><path d="M19 6l-1 14H6L5 6" /><path d="M10 11v5" /><path d="M14 11v5" /></svg>',
  };
  return icons[icon] || "";
}

function actionLabel(action) {
  return {
    reject: "拒绝",
    observe: "观察",
    small_experiment: "小试",
    stage_gated_increase: "分阶段加码",
  }[action] || action || "-";
}

function confidenceLabel(value) {
  return {
    low: "低",
    low_to_medium: "中低",
    medium: "中",
    high_for_downgrade: "高：风险降级",
  }[value] || value || "-";
}

function renderMarkdown(value) {
  const lines = escapeHtml(value).split(/\r?\n/);
  const html = [];
  let listType = "";
  let inCode = false;
  let codeLines = [];
  let paragraph = [];

  const flushParagraph = () => {
    if (paragraph.length) {
      html.push(`<p>${formatInline(paragraph.join(" "))}</p>`);
      paragraph = [];
    }
  };

  const closeList = () => {
    if (listType) {
      html.push(`</${listType}>`);
      listType = "";
    }
  };

  const openList = (type) => {
    if (listType === type) return;
    closeList();
    html.push(`<${type}>`);
    listType = type;
  };

  let index = 0;
  while (index < lines.length) {
    const line = lines[index];
    if (line.trim().startsWith("```")) {
      if (inCode) {
        html.push(`<pre><code>${codeLines.join("\n")}</code></pre>`);
        codeLines = [];
      } else {
        flushParagraph();
        closeList();
      }
      inCode = !inCode;
      index += 1;
      continue;
    }

    if (inCode) {
      codeLines.push(line);
      index += 1;
      continue;
    }

    const trimmed = line.trim();
    if (!trimmed) {
      flushParagraph();
      closeList();
      index += 1;
      continue;
    }

    if (/^\|(.+)\|$/.test(trimmed) && index + 1 < lines.length && isTableSeparator(lines[index + 1].trim())) {
      flushParagraph();
      closeList();
      const tableRows = [trimmed];
      index += 2;
      while (index < lines.length && /^\|(.+)\|$/.test(lines[index].trim())) {
        tableRows.push(lines[index].trim());
        index += 1;
      }
      html.push(renderTable(tableRows));
      continue;
    }

    if (/^---+$/.test(trimmed)) {
      flushParagraph();
      closeList();
      html.push("<hr />");
      index += 1;
      continue;
    }

    if (trimmed.startsWith("### ")) {
      flushParagraph();
      closeList();
      html.push(`<h4>${formatInline(trimmed.slice(4))}</h4>`);
      index += 1;
      continue;
    }
    if (trimmed.startsWith("## ")) {
      flushParagraph();
      closeList();
      html.push(`<h3>${formatInline(trimmed.slice(3))}</h3>`);
      index += 1;
      continue;
    }
    if (trimmed.startsWith("# ")) {
      flushParagraph();
      closeList();
      html.push(`<h3>${formatInline(trimmed.slice(2))}</h3>`);
      index += 1;
      continue;
    }
    if (trimmed.startsWith("&gt; ")) {
      flushParagraph();
      closeList();
      html.push(`<blockquote>${formatInline(trimmed.slice(5))}</blockquote>`);
      index += 1;
      continue;
    }
    if (/^[-*]\s+/.test(trimmed)) {
      flushParagraph();
      openList("ul");
      html.push(`<li>${formatInline(trimmed.replace(/^[-*]\s+/, ""))}</li>`);
      index += 1;
      continue;
    }
    if (/^\d+\.\s+/.test(trimmed)) {
      flushParagraph();
      openList("ol");
      html.push(`<li>${formatInline(trimmed.replace(/^\d+\.\s+/, ""))}</li>`);
      index += 1;
      continue;
    }

    paragraph.push(trimmed);
    index += 1;
  }

  flushParagraph();
  closeList();
  if (inCode && codeLines.length) {
    html.push(`<pre><code>${codeLines.join("\n")}</code></pre>`);
  }
  return html.join("");
}

function renderAssistantMessage(value, options = {}) {
  const sections = splitSummaryAndDetail(value);
  if (!sections.detail) {
    return renderMarkdown(value);
  }

  const openAttribute = options.detailOpen ? " open" : "";
  return `
    <div class="answer-summary">${renderMarkdown(sections.summary)}</div>
    <details class="answer-detail"${openAttribute}>
      <summary>详细分析</summary>
      <div class="detail-body">${renderMarkdown(sections.detail)}</div>
    </details>
  `;
}

function splitSummaryAndDetail(value) {
  const normalized = String(value).replace(/\r\n/g, "\n");
  const detailPattern = /^##\s*详细(?:分析|说明|推理|展开)\s*$/im;
  const match = detailPattern.exec(normalized);
  if (!match || match.index <= 0) {
    return { summary: normalized, detail: "" };
  }

  const summary = normalized.slice(0, match.index).trim();
  const detail = normalized.slice(match.index + match[0].length).trim();
  return {
    summary: summary.replace(/^##\s*简洁结论\s*$/im, "").trim() || "请展开查看详细分析。",
    detail,
  };
}

function formatInline(value) {
  return value
    .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
    .replace(/\*([^*]+)\*/g, "<em>$1</em>")
    .replace(/`([^`]+)`/g, "<code>$1</code>")
    .replace(
      /(https?:\/\/[^\s<]+)/g,
      '<a href="$1" target="_blank" rel="noreferrer">$1</a>',
    );
}

function renderPlainText(value) {
  return `<p>${escapeHtml(value).replace(/\r?\n/g, "<br />")}</p>`;
}

function isTableSeparator(line) {
  return /^\|?[\s:-]+\|[\s|:-]+\|?$/.test(line);
}

function renderTable(rows) {
  const cells = rows.map((row) =>
    row
      .replace(/^\|/, "")
      .replace(/\|$/, "")
      .split("|")
      .map((cell) => formatInline(cell.trim())),
  );
  if (!cells.length) return "";
  const head = cells[0].map((cell) => `<th>${cell}</th>`).join("");
  const body = cells
    .slice(1)
    .map((row) => `<tr>${row.map((cell) => `<td>${cell}</td>`).join("")}</tr>`)
    .join("");
  return `<div class="table-wrap"><table><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table></div>`;
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

$("composerForm").addEventListener("submit", handleComposer);
$("newCaseBtn").addEventListener("click", newCase);
$("refreshBtn").addEventListener("click", loadCases);
$("savePlanBtn").addEventListener("click", savePlanToJournal);
$("composerInput").addEventListener("keydown", (event) => {
  if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) {
    $("composerForm").requestSubmit();
  }
});

loadCases().catch((error) => {
  console.error(error);
  alert(error.message);
});
