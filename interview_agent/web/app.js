"use strict";

// 页面状态只保存展示所需数据；业务真相始终以服务端 SQLite 会话为准。
const state = {
  health: null,
  sessionId: null,
  progress: { answered: 0, total: 0 },
  pendingNextQuestion: null,
  pendingReport: null,
  studyConversationId: null,
  studyTopic: null,
};

const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];

// 所有来自模型和用户的数据在插入 HTML 前转义，防止脚本注入。
function escapeHtml(value) {
  const element = document.createElement("div");
  element.textContent = String(value ?? "");
  return element.innerHTML;
}

function showView(viewId) {
  $$(".view").forEach((view) => view.classList.toggle("active", view.id === viewId));
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function setLoading(visible, text = "面试官正在思考…") {
  $("#loading-text").textContent = text;
  $("#loading-overlay").classList.toggle("hidden", !visible);
}

let toastTimer;
function showToast(message) {
  const toast = $("#toast");
  toast.textContent = message;
  toast.classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => toast.classList.remove("show"), 4500);
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: { "Content-Type": "application/json; charset=utf-8", ...(options.headers || {}) },
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(data.detail || `请求失败（HTTP ${response.status}）`);
  }
  return data;
}

function renderTopicOptions(topics) {
  const defaults = new Set(["Java", "Spring", "数据库", "缓存"]);
  $("#topic-options").innerHTML = topics.map((topic) => `
    <label class="topic-option">
      <input type="checkbox" name="topics" value="${escapeHtml(topic)}" ${defaults.has(topic) ? "checked" : ""}>
      <span>${escapeHtml(topic)}</span>
    </label>
  `).join("");
  $$("input[name='topics']").forEach((input) => input.addEventListener("change", updateQuestionLimit));
  updateQuestionLimit();
}

function renderStudyTopics(topics) {
  $("#study-topic-options").innerHTML = ["综合", ...topics].map((topic) => `
    <button type="button" class="study-topic-button ${topic === "综合" ? "active" : ""}"
      data-study-topic="${escapeHtml(topic)}">${escapeHtml(topic)}</button>
  `).join("");
  $$('[data-study-topic]').forEach((button) => button.addEventListener("click", () => {
    $$('[data-study-topic]').forEach((item) => item.classList.remove("active"));
    button.classList.add("active");
    state.studyTopic = button.dataset.studyTopic === "综合" ? null : button.dataset.studyTopic;
  }));
}

function updateQuestionLimit() {
  if (!state.health) return;
  const selected = $$("input[name='topics']:checked").map((input) => input.value);
  const total = selected.reduce((sum, topic) => sum + (state.health.topic_counts?.[topic] || 0), 0);
  const range = $("#question-count");
  range.max = Math.max(1, Math.min(20, total));
  if (Number(range.value) > Number(range.max)) range.value = range.max;
  $("#question-count-label").textContent = range.value;
}

async function initialize() {
  const savedCandidate = localStorage.getItem("interviewCandidateId");
  if (savedCandidate) $("#candidate-id").value = savedCandidate;
  try {
    state.health = await api("/health");
    renderTopicOptions(state.health.supported_topics);
    renderStudyTopics(state.health.supported_topics);
    const status = $("#service-status");
    status.classList.add("online");
    status.querySelector("span").textContent = `${state.health.agent_mode === "offline" ? "离线模式" : state.health.model} · 已连接`;
    await loadCandidate(false);
  } catch (error) {
    const status = $("#service-status");
    status.classList.add("error");
    status.querySelector("span").textContent = "服务异常";
    showToast(error.message);
  }
}

async function startInterview(event) {
  event.preventDefault();
  const topics = $$("input[name='topics']:checked").map((input) => input.value);
  if (!topics.length) return showToast("请至少选择一个技术领域");
  const candidateId = $("#candidate-id").value.trim();
  if (!candidateId) return showToast("请输入候选人 ID");

  const payload = {
    candidate_id: candidateId,
    candidate_name: $("#candidate-name").value.trim() || "候选人",
    topics,
    difficulty: $("#difficulty").value,
    total_questions: Number($("#question-count").value),
  };
  localStorage.setItem("interviewCandidateId", candidateId);
  setLoading(true, "正在生成面试方案…");
  try {
    const result = await api("/api/v1/interviews", { method: "POST", body: JSON.stringify(payload) });
    state.sessionId = result.session_id;
    localStorage.setItem("activeInterviewSession", result.session_id);
    renderQuestion(result.question, result.progress);
    showView("interview-view");
  } catch (error) {
    showToast(error.message);
  } finally {
    setLoading(false);
  }
}

function renderQuestion(question, progress) {
  state.progress = progress;
  state.pendingNextQuestion = null;
  $("#session-short-id").textContent = state.sessionId?.slice(0, 10) || "—";
  $("#question-topic").textContent = question.topic;
  $("#question-difficulty").textContent = question.difficulty;
  $("#question-text").textContent = question.question;
  $("#question-number").textContent = `QUESTION ${String(progress.answered + 1).padStart(2, "0")}`;
  $("#progress-label").textContent = `第 ${progress.answered + 1} 题 / 共 ${progress.total} 题`;
  const percent = Math.round(progress.answered / progress.total * 100);
  $("#progress-percent").textContent = `${percent}%`;
  $("#progress-bar").style.width = `${percent}%`;
  $("#follow-up-hint").classList.toggle("hidden", !question.follow_up);
  $("#answer-input").value = "";
  $("#answer-input").disabled = false;
  $("#submit-answer").disabled = false;
  $("#answer-length").textContent = "0 / 20000";
  $("#evaluation-panel").classList.add("hidden");
  $("#answer-input").focus();
}

async function submitAnswer() {
  const answer = $("#answer-input").value.trim();
  if (!answer) return showToast("请先填写回答内容");
  if (answer.length < 5) return showToast("回答过短，请尽量说明你的理解");
  setLoading(true);
  $("#submit-answer").disabled = true;
  try {
    const result = await api(`/api/v1/interviews/${state.sessionId}/answers`, {
      method: "POST",
      body: JSON.stringify({ answer }),
    });
    state.pendingNextQuestion = result.next_question || null;
    state.pendingReport = result.report || null;
    state.progress = result.progress || { answered: state.progress.total, total: state.progress.total };
    renderEvaluation(result.evaluation, result.completed);
    if (result.completed) localStorage.removeItem("activeInterviewSession");
  } catch (error) {
    $("#submit-answer").disabled = false;
    showToast(error.message);
  } finally {
    setLoading(false);
  }
}

function renderList(elementId, values, fallback) {
  const valuesToRender = values?.length ? values : [fallback];
  $(elementId).innerHTML = valuesToRender.map((value) => `<li>${escapeHtml(value)}</li>`).join("");
}

function renderEvaluation(evaluation, completed) {
  $("#answer-input").disabled = true;
  $("#score-value").textContent = evaluation.score;
  $("#score-ring").style.setProperty("--score", evaluation.score);
  $("#feedback-text").textContent = evaluation.feedback;
  $("#suggested-answer-text").textContent = evaluation.suggested_answer;
  renderList("#strength-list", evaluation.strengths, "本题暂无明确亮点，请参考建议答案完善。");
  renderList("#weakness-list", evaluation.weaknesses, "回答完整，可继续补充实践边界。");
  $("#continue-button").textContent = completed ? "查看完整面试报告 →" : "进入下一题 →";
  $("#evaluation-panel").classList.remove("hidden");
  $("#evaluation-panel").scrollIntoView({ behavior: "smooth", block: "start" });
}

function continueInterview() {
  if (state.pendingReport) {
    renderReport(state.pendingReport);
    return;
  }
  if (state.pendingNextQuestion) {
    renderQuestion(state.pendingNextQuestion, state.progress);
    window.scrollTo({ top: 0, behavior: "smooth" });
  }
}

async function resumeSession(sessionId) {
  setLoading(true, "正在恢复面试上下文…");
  try {
    const result = await api(`/api/v1/interviews/${sessionId}`);
    state.sessionId = sessionId;
    if (result.session.status === "completed") {
      renderReport(await api(`/api/v1/interviews/${sessionId}/report`));
      return;
    }
    localStorage.setItem("activeInterviewSession", sessionId);
    renderQuestion(result.current_question, {
      answered: result.session.current_index,
      total: result.session.total_questions,
    });
    showView("interview-view");
  } catch (error) {
    showToast(error.message);
  } finally {
    setLoading(false);
  }
}

async function loadCandidate(showErrors = true) {
  const candidateId = $("#candidate-id").value.trim();
  if (!candidateId) return showErrors && showToast("请先输入候选人 ID");
  try {
    const data = await api(`/api/v1/candidates/${encodeURIComponent(candidateId)}`);
    renderProfile(data);
  } catch (error) {
    if (showErrors) showToast(error.message);
  }
}

function renderProfile(data) {
  const hasData = data.profile || data.sessions.length || data.study_conversations?.length;
  $("#profile-empty").classList.toggle("hidden", Boolean(hasData));
  $("#profile-content").classList.toggle("hidden", !hasData);
  renderStudyHistory(data.study_conversations || []);
  if (!hasData) return;
  const profile = data.profile || {};
  const weakTopics = Object.entries(profile.weak_topics || {}).filter(([, count]) => count > 0).map(([topic]) => topic);
  $("#profile-stats").innerHTML = [
    ["累计答题", profile.total_answers || 0, "题"],
    ["历史均分", profile.average_score || 0, "分"],
    ["目标级别", profile.target_level || "—", ""],
    ["待加强", weakTopics.join("、") || "暂无", ""],
  ].map(([label, value, suffix]) => `<div class="stat-card surface"><span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong><small>${escapeHtml(suffix)}</small></div>`).join("");

  $("#session-history").innerHTML = data.sessions.length ? data.sessions.map((session) => `
    <div class="session-item">
      <div><strong>${escapeHtml(session.topics.join(" · "))}</strong><small>${formatDate(session.updated_at)} · ${escapeHtml(session.difficulty)}</small></div>
      <div><strong>${session.answered_questions} / ${session.total_questions}</strong><small>答题进度</small></div>
      <span class="status-tag ${session.status === "completed" ? "done" : ""}">${session.status === "completed" ? `已完成 · ${session.average_score}分` : "进行中"}</span>
      <button type="button" data-session-id="${escapeHtml(session.session_id)}">${session.status === "completed" ? "查看报告" : "继续面试"}</button>
    </div>
  `).join("") : "<p class='empty-state'>暂无历史会话</p>";
  $$("[data-session-id]").forEach((button) => button.addEventListener("click", () => resumeSession(button.dataset.sessionId)));
}

function renderStudyHistory(conversations) {
  const container = $("#study-history");
  container.innerHTML = conversations.length ? conversations.map((conversation) => `
    <button type="button" data-conversation-id="${escapeHtml(conversation.conversation_id)}"
      title="${escapeHtml(conversation.title)}">${escapeHtml(conversation.title)}</button>
  `).join("") : "<span>暂无复习对话</span>";
  $$('[data-conversation-id]').forEach((button) => button.addEventListener("click", () => {
    restoreStudyConversation(button.dataset.conversationId);
  }));
}

async function openStudy() {
  showView("study-view");
  await loadCandidate(false);
  $("#study-question").focus();
}

function newStudyConversation() {
  state.studyConversationId = null;
  $("#chat-messages").innerHTML = `
    <div class="welcome-message">
      <span class="assistant-avatar">AI</span>
      <div><h2>今天想复习什么？</h2><p>你可以询问概念原理、源码机制、场景选型，也可以让我对比技术方案或整理面试回答。</p></div>
    </div>
    <div id="quick-questions" class="quick-questions">
      <button type="button">JVM 内存区域与常见 OOM 有哪些？</button>
      <button type="button">Spring 事务为什么会失效？</button>
      <button type="button">Redis 缓存一致性应该怎么保证？</button>
      <button type="button">LangGraph 如何实现多轮状态管理？</button>
    </div>`;
  bindQuickQuestions();
  $("#study-question").value = "";
  $("#study-question").focus();
}

function bindQuickQuestions() {
  $$("#quick-questions button").forEach((button) => button.addEventListener("click", () => {
    $("#study-question").value = button.textContent;
    sendStudyQuestion();
  }));
}

function appendStudyMessage(role, content, answerData = null) {
  const welcome = $("#chat-messages .welcome-message");
  const quick = $("#quick-questions");
  if (welcome) welcome.remove();
  if (quick) quick.remove();
  const wrapper = document.createElement("div");
  wrapper.className = `chat-message ${role}`;
  const details = answerData ? `
    <span class="message-topic">${escapeHtml(answerData.topic || "技术复习")}</span>
    ${answerData.matched_questions?.length ? `<span class="match-meta">知识库匹配 ${Math.round((answerData.confidence || 0) * 100)}% · ${escapeHtml(answerData.matched_questions[0])}</span>` : ""}
    <div>${escapeHtml(content)}</div>
    ${answerData.key_points?.length ? `<ul class="answer-points">${answerData.key_points.map((point) => `<li>${escapeHtml(point)}</li>`).join("")}</ul>` : ""}
    ${answerData.follow_up_questions?.length ? `<div class="follow-up-chips">${answerData.follow_up_questions.map((item) => `<button type="button">${escapeHtml(item)}</button>`).join("")}</div>` : ""}
  ` : escapeHtml(content);
  wrapper.innerHTML = `${role === "assistant" ? '<span class="assistant-avatar">AI</span>' : ""}<div class="message-bubble">${details}</div>`;
  $("#chat-messages").appendChild(wrapper);
  wrapper.querySelectorAll(".follow-up-chips button").forEach((button) => button.addEventListener("click", () => {
    $("#study-question").value = button.textContent;
    sendStudyQuestion();
  }));
  $("#chat-messages").scrollTop = $("#chat-messages").scrollHeight;
}

async function sendStudyQuestion() {
  const input = $("#study-question");
  const question = input.value.trim();
  if (question.length < 2) return showToast("请输入要复习的问题");
  const candidateId = $("#candidate-id").value.trim() || "demo-user";
  input.value = "";
  appendStudyMessage("user", question);
  $("#send-study-question").disabled = true;
  setLoading(true, "复习助手正在整理答案…");
  try {
    const result = await api("/api/v1/study/ask", {
      method: "POST",
      body: JSON.stringify({
        candidate_id: candidateId,
        question,
        conversation_id: state.studyConversationId,
        topic: state.studyTopic,
      }),
    });
    state.studyConversationId = result.conversation_id;
    appendStudyMessage("assistant", result.answer, result);
    await loadCandidate(false);
  } catch (error) {
    appendStudyMessage("assistant", `暂时无法回答：${error.message}`);
    showToast(error.message);
  } finally {
    setLoading(false);
    $("#send-study-question").disabled = false;
    input.focus();
  }
}

async function restoreStudyConversation(conversationId) {
  const candidateId = $("#candidate-id").value.trim() || "demo-user";
  setLoading(true, "正在恢复复习上下文…");
  try {
    const data = await api(`/api/v1/study/conversations/${conversationId}?candidate_id=${encodeURIComponent(candidateId)}`);
    state.studyConversationId = conversationId;
    $("#chat-messages").innerHTML = "";
    data.messages.forEach((message) => {
      const structured = message.role === "assistant" ? message.metadata : null;
      appendStudyMessage(message.role, message.content, structured);
    });
    showView("study-view");
  } catch (error) {
    showToast(error.message);
  } finally {
    setLoading(false);
  }
}

function formatDate(value) {
  try {
    return new Intl.DateTimeFormat("zh-CN", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" }).format(new Date(value));
  } catch (_) {
    return value;
  }
}

function scoreLevel(score) {
  if (score >= 90) return "专家级表现";
  if (score >= 75) return "基础扎实";
  if (score >= 60) return "达到合格线";
  return "建议系统复习";
}

function renderReport(report) {
  showView("report-view");
  $("#report-score").textContent = report.average_score;
  $("#report-level").textContent = scoreLevel(report.average_score);
  $("#answered-count").textContent = `共完成 ${report.answered_questions} 题`;
  $("#topic-scores").innerHTML = Object.entries(report.topic_scores).map(([topic, score]) => `
    <div class="topic-score-row"><strong>${escapeHtml(topic)}</strong><div class="topic-score-track"><i style="width:${Number(score)}%"></i></div><span>${Number(score).toFixed(0)}</span></div>
  `).join("") || "<p>暂无领域得分</p>";
  renderList("#report-strengths", report.representative_strengths, "继续完成面试以积累优势数据");
  renderList("#report-improvements", report.priority_improvements, "暂无明显短板");
  $("#learning-suggestion").textContent = report.learning_suggestion;
  $("#answer-review").innerHTML = report.detail.map((turn, index) => `
    <details class="review-item">
      <summary><strong>${index + 1}. ${escapeHtml(turn.question)}</strong><span>${turn.evaluation.score} 分</span></summary>
      <div class="review-content"><p><strong>你的回答：</strong>${escapeHtml(turn.answer)}</p><p><strong>面试官反馈：</strong>${escapeHtml(turn.evaluation.feedback)}</p><p><strong>建议思路：</strong>${escapeHtml(turn.evaluation.suggested_answer)}</p></div>
    </details>
  `).join("");
}

async function goHome() {
  showView("setup-view");
  await loadCandidate(false);
}

// 事件集中注册，避免在视图切换时重复绑定。
$("#setup-form").addEventListener("submit", startInterview);
$("#study-nav").addEventListener("click", openStudy);
$("#hero-study-button").addEventListener("click", openStudy);
$("#new-study-chat").addEventListener("click", newStudyConversation);
$("#send-study-question").addEventListener("click", sendStudyQuestion);
$("#study-question").addEventListener("keydown", (event) => {
  if (event.ctrlKey && event.key === "Enter") sendStudyQuestion();
});
$("#question-count").addEventListener("input", updateQuestionLimit);
$("#load-profile").addEventListener("click", () => loadCandidate(true));
$("#candidate-id").addEventListener("change", () => loadCandidate(false));
$("#toggle-topics").addEventListener("click", () => {
  const inputs = $$("input[name='topics']");
  const shouldCheck = inputs.some((input) => !input.checked);
  inputs.forEach((input) => { input.checked = shouldCheck; });
  $("#toggle-topics").textContent = shouldCheck ? "取消全选" : "全选";
  updateQuestionLimit();
});
$("#answer-input").addEventListener("input", (event) => {
  $("#answer-length").textContent = `${event.target.value.length} / 20000`;
});
$("#answer-input").addEventListener("keydown", (event) => {
  if (event.ctrlKey && event.key === "Enter") submitAnswer();
});
$("#submit-answer").addEventListener("click", submitAnswer);
$("#continue-button").addEventListener("click", continueInterview);
$("#restart-button").addEventListener("click", goHome);
$$('[data-action="home"]').forEach((button) => button.addEventListener("click", goHome));

bindQuickQuestions();
initialize();
