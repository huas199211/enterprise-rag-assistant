let conversationId = null;
let currentMessageId = null;

const $ = (id) => document.getElementById(id);

async function api(path, options = {}) {
  const response = await fetch(path, options);
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(data.detail || response.statusText);
  }
  return response.json();
}

async function loadConfig() {
  const config = await api("/api/config");
  $("chunkSize").value = config.chunk_size;
  $("chunkOverlap").value = config.chunk_overlap;
  $("topK").value = config.top_k;
  $("minScore").value = config.min_score;
  $("chatModel").value = config.chat_model;
  $("embeddingProvider").value = config.embedding_provider;
  $("embeddingModel").value = config.embedding_model;
  $("embeddingDimensions").value = config.embedding_dimensions;
  $("rerankProvider").value = config.rerank_provider;
  $("rerankBaseUrl").value = config.rerank_base_url;
  $("rerankModel").value = config.rerank_model;
  $("rerank").checked = Boolean(config.rerank);
}

async function loadDocuments() {
  const docs = await api("/api/documents");
  $("documentList").innerHTML = docs.map((doc) => `
    <div class="doc" data-document-id="${doc.id}">
      <strong>${escapeHtml(doc.filename)}</strong>
      <p>${statusLabel(doc.status)} · ${doc.chunk_count} 个片段 · ${new Date(doc.created_at).toLocaleString()}</p>
      ${doc.error_message ? `<p class="error">${escapeHtml(doc.error_message)}</p>` : ""}
      <button class="secondary reindex" type="button">重建索引</button>
    </div>
  `).join("") || '<p class="muted">暂无文档</p>';
}

async function loadLogs() {
  const logs = await api("/api/logs?limit=10");
  $("logs").innerHTML = logs.map((item) => `
    <div class="log">
      <strong>${escapeHtml(item.question)}</strong>
      <p>${escapeHtml(item.answer).slice(0, 220)}</p>
      <p>${item.latency_ms} 毫秒 · ${new Date(item.created_at).toLocaleString()}</p>
    </div>
  `).join("") || '<p class="muted">暂无记录</p>';
}

$("uploadForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  const file = $("fileInput").files[0];
  if (!file) return;
  $("uploadStatus").textContent = "正在解析、切分、向量化...";
  const formData = new FormData();
  formData.append("file", file);
  try {
    const result = await api("/api/documents/upload", { method: "POST", body: formData });
    $("uploadStatus").textContent = `已入库：${result.filename}，${result.chunk_count} 个片段`;
    $("fileInput").value = "";
    await loadDocuments();
  } catch (error) {
    $("uploadStatus").textContent = error.message;
  }
});

$("documentList").addEventListener("click", async (event) => {
  const button = event.target.closest(".reindex");
  if (!button) return;
  const doc = event.target.closest(".doc");
  const documentId = doc.dataset.documentId;
  button.disabled = true;
  button.textContent = "重建中...";
  try {
    await api(`/api/documents/${documentId}/reindex`, { method: "POST" });
    await loadDocuments();
  } catch (error) {
    button.textContent = error.message;
  } finally {
    button.disabled = false;
  }
});

$("saveConfig").addEventListener("click", async () => {
  const payload = {
    chunk_size: Number($("chunkSize").value),
    chunk_overlap: Number($("chunkOverlap").value),
    top_k: Number($("topK").value),
    min_score: Number($("minScore").value),
    chat_model: $("chatModel").value.trim(),
    embedding_provider: $("embeddingProvider").value.trim(),
    embedding_model: $("embeddingModel").value.trim(),
    embedding_dimensions: Number($("embeddingDimensions").value),
    rerank_provider: $("rerankProvider").value.trim(),
    rerank_base_url: $("rerankBaseUrl").value.trim(),
    rerank_model: $("rerankModel").value.trim(),
    rerank: $("rerank").checked,
  };
  await api("/api/config", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  await loadConfig();
});

$("askButton").addEventListener("click", async () => {
  const question = $("question").value.trim();
  if (!question) return;
  $("askButton").disabled = true;
  $("answer").textContent = "正在检索知识库并生成回答...";
  $("sources").innerHTML = "";
  $("latency").textContent = "";
  $("feedbackButtons").classList.add("hidden");
  try {
    const result = await api("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question, conversation_id: conversationId }),
    });
    conversationId = result.conversation_id;
    currentMessageId = result.message_id;
    $("answer").textContent = result.answer;
    $("latency").textContent = `${result.latency_ms} 毫秒`;
    $("feedbackButtons").classList.remove("hidden");
    renderSources(result.sources);
    await loadLogs();
  } catch (error) {
    $("answer").textContent = error.message;
  } finally {
    $("askButton").disabled = false;
  }
});

$("feedbackButtons").addEventListener("click", async (event) => {
  const button = event.target.closest("button");
  if (!button || !currentMessageId) return;
  await api("/api/feedback", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message_id: currentMessageId, rating: button.dataset.rating }),
  });
  button.textContent = "已记录";
});

$("newConversation").addEventListener("click", () => {
  conversationId = null;
  currentMessageId = null;
  $("question").value = "";
  $("answer").textContent = "已开启新会话。";
  $("sources").innerHTML = "";
  $("latency").textContent = "";
  $("feedbackButtons").classList.add("hidden");
});

$("runEval").addEventListener("click", async () => {
  $("evalResult").textContent = "正在运行评估...";
  try {
    const result = await api("/api/evaluate", { method: "POST" });
    const fallbackLatency = result.p95_latency_ms ?? result.avg_latency_ms ?? result.latency_ms;
    $("evalResult").textContent = [
      `${result.count} 条`,
      `答案关键词命中 ${formatMetric(result.avg_keyword_score)}`,
      `来源关键词覆盖 ${formatMetric(result.avg_source_keyword_score)}`,
      `召回命中率 ${formatMetric(result.retrieval_hit_rate)}`,
      `拒答率 ${formatMetric(result.refusal_rate)}`,
      `P95 耗时 ${formatMetric(fallbackLatency)} 毫秒`,
    ].join(" · ");
  } catch (error) {
    $("evalResult").textContent = error.message;
  }
});

function renderSources(sources) {
  $("sources").innerHTML = sources.map((source, index) => `
    <div class="source">
      <strong>[${index + 1}] ${escapeHtml(source.metadata.filename)} · 相关度 ${source.score.toFixed(3)}</strong>
      <p>${escapeHtml(source.text).slice(0, 700)}</p>
    </div>
  `).join("") || '<p class="muted">没有召回来源片段</p>';
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function formatMetric(value) {
  return value === undefined || value === null ? "暂无数据" : value;
}

function statusLabel(status) {
  const labels = {
    uploaded: "已上传",
    parsing: "解析中",
    chunking: "切分中",
    embedding: "向量化中",
    indexed: "已入库",
    failed: "失败",
  };
  return labels[status] || status || "未知";
}

loadConfig();
loadDocuments();
loadLogs();
