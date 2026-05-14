<template>
  <main v-if="!isAuthenticated" class="login-page">
    <section class="login-card">
      <div class="brand login-brand">
        <div class="brand-mark">知</div>
        <div>
          <h1>企业知识库</h1>
          <p>检索增强工作台</p>
        </div>
      </div>

      <form class="login-form" @submit.prevent="login">
        <label>用户名 <input v-model.trim="loginForm.username" type="text" autocomplete="username" /></label>
        <label>密码 <input v-model="loginForm.password" type="password" autocomplete="current-password" /></label>
        <button type="submit" :disabled="loggingIn">{{ loggingIn ? "登录中..." : "登录" }}</button>
      </form>
      <p v-if="loginStatus" class="login-message">{{ loginStatus }}</p>
    </section>
  </main>

  <div v-else class="shell">
    <aside class="sidebar">
      <div class="brand">
        <div class="brand-mark">知</div>
        <div>
          <h1>企业知识库</h1>
          <p>检索增强工作台</p>
        </div>
      </div>

      <section class="panel">
        <h2>文档入库</h2>
        <form @submit.prevent="uploadDocument">
          <input ref="fileInputRef" type="file" accept=".pdf,.doc,.docx,.md,.markdown,.txt" @change="handleFileChange" />
          <button type="submit" :disabled="uploading">{{ uploading ? "处理中..." : "上传并向量化" }}</button>
        </form>
        <div class="muted">{{ uploadStatus }}</div>
        <div class="list">
          <article v-for="doc in paginatedDocuments" :key="doc.id" class="doc">
            <strong>{{ doc.filename }}</strong>
            <p>{{ statusLabel(doc.status) }} · {{ doc.chunk_count }} 个片段 · {{ formatDate(doc.created_at) }}</p>
            <p v-if="doc.error_message" class="error">{{ doc.error_message }}</p>
            <button class="secondary" type="button" :disabled="reindexingId === doc.id" @click="reindexDocument(doc.id)">
              {{ reindexingId === doc.id ? "重建中..." : "重建索引" }}
            </button>
          </article>
          <p v-if="!documents.length" class="muted">暂无文档</p>
          <div v-if="documents.length > docPageSize" class="pagination">
            <button class="secondary inline" type="button" :disabled="docPage <= 1" @click="docPage--">上一页</button>
            <span class="page-info">{{ docPage }} / {{ docTotalPages }}</span>
            <button class="secondary inline" type="button" :disabled="docPage >= docTotalPages" @click="docPage++">下一页</button>
          </div>
        </div>
      </section>

      <section class="panel">
        <h2>文档清洗</h2>
        <form @submit.prevent="runClean">
          <input ref="cleanFileInputRef" type="file" accept=".pdf,.doc,.docx,.md,.markdown,.txt" @change="handleCleanFileChange" />
          <div class="clean-toggles">
            <label class="check"><input v-model="cleanConfig.encoding_fix" type="checkbox" /> 编码修复</label>
            <label class="check"><input v-model="cleanConfig.text_normalize" type="checkbox" /> 格式统一</label>
            <label class="check"><input v-model="cleanConfig.noise_filter" type="checkbox" /> 噪声过滤</label>
            <label class="check"><input v-model="cleanConfig.sensitive_mask" type="checkbox" /> 敏感信息脱敏</label>
            <label class="check"><input v-model="cleanConfig.deduplication" type="checkbox" /> 文档去重</label>
            <label class="check"><input v-model="cleanConfig.table_preserve" type="checkbox" /> 表格保留</label>
            <label class="check"><input v-model="cleanConfig.structure_parse" type="checkbox" /> 结构解析</label>
          </div>
          <button type="submit" :disabled="cleaning">{{ cleaning ? "清洗中..." : "开始清洗" }}</button>
        </form>
        <div class="muted">{{ cleanStatus }}</div>
        <div v-if="cleanResult" class="clean-result">
          <div class="clean-stats">
            <span>原始 {{ cleanResult.original_length }} 字符 → 清洗后 {{ cleanResult.cleaned_length }} 字符</span>
            <span v-if="cleanResult.stats">({{ Object.keys(cleanResult.stats).length }} 个处理步骤)</span>
          </div>
          <pre class="clean-preview">{{ cleanResult.preview }}</pre>
          <button type="button" :disabled="!cleanResult.task_id" @click="downloadCleaned">下载清洗后文件</button>
        </div>
      </section>

      <section class="panel">
        <h2>后台配置</h2>
        <label>片段长度 <input v-model.number="config.chunk_size" type="number" min="100" max="3000" /></label>
        <label>片段重叠长度 <input v-model.number="config.chunk_overlap" type="number" min="0" max="800" /></label>
        <label>召回数量 <input v-model.number="config.top_k" type="number" min="1" max="20" /></label>
        <label>最低相关度 <input v-model.number="config.min_score" type="number" min="0" max="1" step="0.01" /></label>
        <label>对话模型 <input v-model.trim="config.chat_model" type="text" /></label>
        <button type="button" @click="saveConfig">保存配置</button>
        <div class="muted">{{ configStatus }}</div>
      </section>

      <section class="panel">
        <h2>访问上下文</h2>
        <label>用户 ID <input v-model.trim="requestContext.userId" type="text" /></label>
        <label>用户姓名 <input v-model.trim="requestContext.userName" type="text" /></label>
        <label>用户角色 <input v-model.trim="requestContext.userRole" type="text" /></label>
        <label>部门 ID <input v-model="requestContext.departmentId" type="number" min="1" /></label>
      </section>

      <section class="panel">
        <h2>质量评估</h2>
        <button type="button" :disabled="evaluating" @click="runEvaluation">{{ evaluating ? "评估中..." : "运行测试集" }}</button>
        <div class="muted">{{ evalResult }}</div>
      </section>
    </aside>

    <main class="workspace">
      <header class="topbar">
        <div>
          <h2>知识检索问答</h2>
          <p>基于已入库片段回答，保留引用、耗时和反馈记录。</p>
        </div>
        <div class="user-actions">
          <span class="user-pill">{{ requestContext.userName }} · {{ requestContext.userRole }}</span>
          <button class="secondary inline" type="button" @click="logout">退出</button>
          <button type="button" @click="newConversation">新会话</button>
        </div>
      </header>

      <section class="ask">
        <textarea v-model.trim="question" rows="4" placeholder="输入企业知识库问题，例如：报销审批需要哪些材料？"></textarea>
        <div class="ask-actions">
          <button type="button" :disabled="asking" @click="askQuestion">{{ asking ? "生成中..." : "检索并回答" }}</button>
          <span class="muted">{{ latencyText }}</span>
        </div>
      </section>

      <section class="answer-area">
        <div class="answer-header">
          <h3>回答</h3>
          <div v-if="currentMessageId" class="feedback">
            <button type="button" @click="sendFeedback('up')">有帮助</button>
            <button type="button" @click="sendFeedback('down')">需改进</button>
          </div>
        </div>
        <pre id="answer">{{ answer }}</pre>
        <div class="muted">{{ feedbackStatus }}</div>
      </section>

      <section class="sources-area">
        <h3>引用来源片段</h3>
        <div class="sources">
          <article v-for="(source, index) in sources" :key="source.chunk_id || index" class="source">
            <strong>[{{ index + 1 }}] {{ source.metadata?.filename || "未知文件" }} · 相关度 {{ Number(source.score || 0).toFixed(3) }}</strong>
            <p>{{ String(source.text || "").slice(0, 700) }}</p>
          </article>
          <p v-if="!sources.length" class="muted">没有召回来源片段</p>
        </div>
      </section>

      <section class="logs-area">
        <h3>最近问答记录</h3>
        <div class="logs">
          <article v-for="item in logs" :key="item.id || item.created_at" class="log">
            <strong>{{ item.question }}</strong>
            <p>{{ String(item.answer || "").slice(0, 220) }}</p>
            <p>{{ item.latency_ms }} 毫秒 · {{ formatDate(item.created_at) }}</p>
          </article>
          <p v-if="!logs.length" class="muted">暂无记录</p>
        </div>
      </section>
    </main>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from "vue";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "";

const accessToken = ref(localStorage.getItem("accessToken") || "");
const initialUser = restoreInitialUser(accessToken.value);
const isAuthenticated = computed(() => Boolean(accessToken.value && requestContext.userId));
const conversationId = ref(null);
const currentMessageId = ref(null);
const selectedFile = ref(null);
const fileInputRef = ref(null);

const documents = ref([]);
const logs = ref([]);
const sources = ref([]);
const question = ref("");
const answer = ref("请先上传文档，然后开始提问。");
const latencyText = ref("");
const uploadStatus = ref("");
const loginStatus = ref("");
const configStatus = ref("");
const evalResult = ref("");
const feedbackStatus = ref("");

const uploading = ref(false);
const asking = ref(false);
const evaluating = ref(false);
const loggingIn = ref(false);
const reindexingId = ref(null);

const docPage = ref(1);
const docPageSize = 5;
const docTotalPages = computed(() => Math.max(1, Math.ceil(documents.value.length / docPageSize)));
const paginatedDocuments = computed(() => {
  const start = (docPage.value - 1) * docPageSize;
  return documents.value.slice(start, start + docPageSize);
});

const cleaning = ref(false);
const cleanSelectedFile = ref(null);
const cleanFileInputRef = ref(null);
const cleanResult = ref(null);
const cleanStatus = ref("");
const cleanConfig = reactive({
  encoding_fix: true,
  text_normalize: true,
  noise_filter: true,
  sensitive_mask: true,
  deduplication: true,
  table_preserve: true,
  structure_parse: true,
});

const loginForm = reactive({
  username: "admin",
  password: "admin123",
});

const requestContext = reactive({
  userId: initialUser?.id || "",
  userName: initialUser?.name || "",
  userRole: initialUser?.role || "",
  departmentId: initialUser?.department_id || "",
});

const config = reactive({
  chunk_size: 800,
  chunk_overlap: 120,
  top_k: 5,
  min_score: 0.08,
  chat_model: "",
  embedding_provider: "",
  embedding_model: "",
  embedding_dimensions: 1024,
});

async function api(path, options = {}) {
  const response = await fetch(`${API_BASE_URL}${path}`, withRequestContext(options));
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(data.detail || response.statusText);
  }
  return response.json();
}

function withRequestContext(options = {}) {
  const headers = new Headers(options.headers || {});
  if (accessToken.value) {
    headers.set("Authorization", `Bearer ${accessToken.value}`);
  }
  headers.set("X-User-Id", encodeURIComponent(requestContext.userId || "system"));
  headers.set("X-User-Name", encodeURIComponent(requestContext.userName || "系统用户"));
  headers.set("X-User-Role", encodeURIComponent(requestContext.userRole || "admin"));
  if (requestContext.departmentId) {
    headers.set("X-Department-Id", String(requestContext.departmentId));
  }
  return { ...options, headers };
}

async function loadConfig() {
  const data = await api("/api/config");
  Object.assign(config, data);
}

async function loadDocuments() {
  documents.value = await api("/api/documents");
  docPage.value = 1;
}

async function loadLogs() {
  logs.value = await api("/api/logs?limit=10");
}

async function initializeWorkspace() {
  await Promise.all([loadConfig(), loadDocuments(), loadLogs()]);
}

function handleFileChange(event) {
  selectedFile.value = event.target.files?.[0] || null;
}

async function uploadDocument() {
  if (!selectedFile.value) return;
  uploading.value = true;
  uploadStatus.value = "正在解析、切分、向量化...";
  const formData = new FormData();
  formData.append("file", selectedFile.value);
  try {
    const result = await api("/api/documents/upload", { method: "POST", body: formData });
    uploadStatus.value = `已入库：${result.filename}，${result.chunk_count} 个片段`;
    selectedFile.value = null;
    if (fileInputRef.value) fileInputRef.value.value = "";
    await loadDocuments();
  } catch (error) {
    uploadStatus.value = error.message;
  } finally {
    uploading.value = false;
  }
}

async function reindexDocument(documentId) {
  reindexingId.value = documentId;
  try {
    await api(`/api/documents/${documentId}/reindex`, { method: "POST" });
    await loadDocuments();
  } catch (error) {
    uploadStatus.value = error.message;
  } finally {
    reindexingId.value = null;
  }
}

async function saveConfig() {
  configStatus.value = "正在保存...";
  try {
    await api("/api/config", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(config),
    });
    await loadConfig();
    configStatus.value = "配置已保存";
  } catch (error) {
    configStatus.value = error.message;
  }
}

async function login() {
  if (!loginForm.username || !loginForm.password) {
    loginStatus.value = "请输入用户名和密码";
    return;
  }
  loggingIn.value = true;
  loginStatus.value = "正在登录...";
  try {
    const result = await api("/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(loginForm),
    });
    accessToken.value = result.access_token;
    localStorage.setItem("accessToken", accessToken.value);
    localStorage.setItem("currentUser", JSON.stringify(result.user));
    applyUser(result.user);
    loginStatus.value = "";
    await initializeWorkspace();
  } catch (error) {
    loginStatus.value = error.message;
  } finally {
    loggingIn.value = false;
  }
}

function logout() {
  accessToken.value = "";
  localStorage.removeItem("accessToken");
  localStorage.removeItem("currentUser");
  applyUser(null);
  clearWorkspaceData();
  loginStatus.value = "已退出登录";
}

function applyUser(user) {
  requestContext.userId = user?.id || "";
  requestContext.userName = user?.name || "";
  requestContext.userRole = user?.role || "";
  requestContext.departmentId = user?.department_id || "";
}

function clearWorkspaceData() {
  documents.value = [];
  logs.value = [];
  sources.value = [];
  conversationId.value = null;
  currentMessageId.value = null;
  question.value = "";
  answer.value = "请先上传文档，然后开始提问。";
  latencyText.value = "";
  uploadStatus.value = "";
  configStatus.value = "";
  evalResult.value = "";
  feedbackStatus.value = "";
}

async function askQuestion() {
  if (!question.value) return;
  asking.value = true;
  answer.value = "正在检索知识库并生成回答...";
  sources.value = [];
  latencyText.value = "";
  feedbackStatus.value = "";
  currentMessageId.value = null;
  try {
    const result = await api("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question: question.value, conversation_id: conversationId.value }),
    });
    conversationId.value = result.conversation_id;
    currentMessageId.value = result.message_id;
    answer.value = result.answer;
    latencyText.value = `${result.latency_ms} 毫秒`;
    sources.value = result.sources || [];
    await loadLogs();
  } catch (error) {
    answer.value = error.message;
  } finally {
    asking.value = false;
  }
}

async function sendFeedback(rating) {
  if (!currentMessageId.value) return;
  await api("/api/feedback", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message_id: currentMessageId.value, rating }),
  });
  feedbackStatus.value = "反馈已记录";
}

function newConversation() {
  conversationId.value = null;
  currentMessageId.value = null;
  question.value = "";
  answer.value = "已开启新会话。";
  sources.value = [];
  latencyText.value = "";
  feedbackStatus.value = "";
}

async function runEvaluation() {
  evaluating.value = true;
  evalResult.value = "正在运行评估...";
  try {
    const result = await api("/api/evaluate", { method: "POST" });
    const fallbackLatency = result.p95_latency_ms ?? result.avg_latency_ms ?? result.latency_ms;
    evalResult.value = [
      `${result.count} 条`,
      `答案关键词命中 ${formatMetric(result.avg_keyword_score)}`,
      `来源关键词覆盖 ${formatMetric(result.avg_source_keyword_score)}`,
      `引用准确率 ${formatMetric(result.avg_citation_accuracy)}`,
      `召回命中率 ${formatMetric(result.retrieval_hit_rate)}`,
      `拒答率 ${formatMetric(result.refusal_rate)}`,
      `P95 耗时 ${formatMetric(fallbackLatency)} 毫秒`,
    ].join(" · ");
  } catch (error) {
    evalResult.value = error.message;
  } finally {
    evaluating.value = false;
  }
}

function handleCleanFileChange(event) {
  cleanSelectedFile.value = event.target.files?.[0] || null;
  cleanResult.value = null;
  cleanStatus.value = "";
}

async function runClean() {
  if (!cleanSelectedFile.value) {
    cleanStatus.value = "请先选择文件";
    return;
  }
  cleaning.value = true;
  cleanStatus.value = "正在清洗...";
  cleanResult.value = null;
  const formData = new FormData();
  formData.append("file", cleanSelectedFile.value);
  formData.append("enable_encoding_fix", String(cleanConfig.encoding_fix));
  formData.append("enable_text_normalize", String(cleanConfig.text_normalize));
  formData.append("enable_noise_filter", String(cleanConfig.noise_filter));
  formData.append("enable_sensitive_mask", String(cleanConfig.sensitive_mask));
  formData.append("enable_deduplication", String(cleanConfig.deduplication));
  formData.append("enable_table_preserve", String(cleanConfig.table_preserve));
  formData.append("enable_structure_parse", String(cleanConfig.structure_parse));
  try {
    const result = await api("/api/clean", { method: "POST", body: formData });
    cleanResult.value = result;
    cleanStatus.value = `清洗完成，共 ${result.cleaned_length} 字符`;
  } catch (error) {
    cleanStatus.value = error.message;
  } finally {
    cleaning.value = false;
  }
}

async function downloadCleaned() {
  if (!cleanResult.value?.task_id) return;
  const url = `${API_BASE_URL}/api/clean/download/${cleanResult.value.task_id}`;
  try {
    const response = await fetch(url, withRequestContext());
    if (!response.ok) throw new Error("下载失败");
    const blob = await response.blob();
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = `${cleanResult.value.original_filename.replace(/\.[^.]+$/, "")}_cleaned.txt`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(link.href);
  } catch (error) {
    cleanStatus.value = error.message;
  }
}

function formatMetric(value) {
  return value === undefined || value === null ? "暂无数据" : value;
}

function formatDate(value) {
  if (!value) return "";
  return new Date(value).toLocaleString();
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

onMounted(async () => {
  if (!isAuthenticated.value) {
    return;
  }
  try {
    await initializeWorkspace();
  } catch (error) {
    logout();
    loginStatus.value = "登录状态已失效，请重新登录";
  }
});

function restoreInitialUser(token) {
  if (!token) return null;
  const storedUser = localStorage.getItem("currentUser");
  if (storedUser) {
    try {
      return JSON.parse(storedUser);
    } catch {
      localStorage.removeItem("currentUser");
    }
  }
  const payload = decodeTokenPayload(token);
  if (!payload || Number(payload.exp || 0) * 1000 < Date.now()) {
    localStorage.removeItem("accessToken");
    return null;
  }
  return {
    id: payload.sub,
    name: payload.name || payload.sub,
    role: payload.role || "user",
    department_id: payload.department_id || "",
  };
}

function decodeTokenPayload(token) {
  try {
    const payloadText = token.split(".")[0];
    const paddedPayload = payloadText.padEnd(payloadText.length + ((4 - (payloadText.length % 4)) % 4), "=");
    return JSON.parse(decodeURIComponent(escape(atob(paddedPayload.replace(/-/g, "+").replace(/_/g, "/")))));
  } catch {
    return null;
  }
}
</script>
