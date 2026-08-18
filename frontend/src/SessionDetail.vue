<script setup>
import { nextTick, ref, onMounted, onUnmounted } from "vue";
import { marked } from "marked";
import DOMPurify from "dompurify";
import { t } from "./i18n";

// agent 回复是 Markdown 源码（终端的富渲染来自 claude 自带渲染器），
// 页面负责渲染成 HTML；DOMPurify 消毒防 XSS（agent 输出不可信）
marked.setOptions({ gfm: true, breaks: true });
function renderMarkdown(text) {
  return DOMPurify.sanitize(marked.parse(text ?? ""));
}

const props = defineProps({ id: Number });
const emit = defineEmits(["back", "loaded"]);

const API = "/api";
const detail = ref(null);
const flowEl = ref(null);

// 新内容到达时贴底（对话界面的基本礼仪：跟着最新走）
async function stickToBottom() {
  await nextTick();
  const el = flowEl.value;
  if (el) el.scrollTop = el.scrollHeight;
}
const input = ref("");
const running = ref(false);
let es = null;

// 回复折叠：默认仅最新一条展开；用户手动开/关按 seq 记住
const replyOverrides = ref({});
const retriedTurns = ref(new Set()); // 已重试过的 turn，按钮置灰
const elapsed = ref(0); // 运行耗时（秒）
const thinkingTokens = ref(0); // 最近一次思考进度（来自 thinking_tokens 心跳）
let elapsedTimer = null;

function startWorking() {
  elapsed.value = 0;
  thinkingTokens.value = 0;
  elapsedTimer = setInterval(() => (elapsed.value += 1), 1000);
}
function stopWorking() {
  clearInterval(elapsedTimer);
  elapsedTimer = null;
}
function replyOpen(m) {
  if (m.seq in replyOverrides.value) return replyOverrides.value[m.seq];
  const texts = (detail.value?.messages ?? []).filter((x) => x.channel === "text" && x.role === "assistant");
  const lastSeq = texts.length ? texts[texts.length - 1].seq : -1;
  return m.seq === lastSeq;
}
function turnDenied(turnId) {
  const t = detail.value?.turns?.find((x) => x.id === turnId);
  return t?.status === "denied";
}

function turnFailed(turnId) {
  const t = detail.value?.turns?.find((x) => x.id === turnId);
  return t && ["error", "cancelled", "denied"].includes(t.status);
}

const STATUS_KEYS = { denied: "stDenied", error: "stError", cancelled: "stCancelled", done: "stDone", running: "stRunning" };
function statusText(s) { return STATUS_KEYS[s] ? t(STATUS_KEYS[s]) : s; }

// 轮次级一次性授权：本轮以 autonomous 执行，会话模式不动，授权链留痕
async function grantAndContinue(turnId) {
  if (running.value) return;
  running.value = true;
  startWorking();
  detail.value?.messages.push({
    seq: 9e9 - 1, role: "user", channel: "text",
    content: JSON.stringify({ text: "🔓（已授权本轮文件操作，继续）" }), turn_id: -1,
  });
  stickToBottom();
  subscribe();
  await fetch(`${API}/sessions/${props.id}/messages`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text: "继续执行刚才被拒的文件操作", mode_override: "autonomous", granted_from: turnId }),
  });
}

async function retryTurn(turnId) {
  // 取该 turn 的用户原文，作为新一轮重新发起（--resume 续上下文）
  const first = detail.value?.messages?.find((m) => m.turn_id === turnId && m.role === "user");
  if (!first || running.value) return;
  retriedTurns.value = new Set([...retriedTurns.value, turnId]);
  input.value = parseContent(first).text ?? "";
  await send();
}

function onReplyToggle(m, e) {
  replyOverrides.value = { ...replyOverrides.value, [m.seq]: e.target.open };
}
function replySnippet(m) {
  return (parseContent(m).text ?? "").replace(/[#*`>|\n]/g, " ").trim().slice(0, 50) || "回复";
}

// 前端按 channel 分声部渲染：条目按 seq 排序，工具块插回真实时序位置
// （实测 agent 会并行发多个工具调用、回复和工具交替出现，渲染必须尊重 seq）
function groupMessages(messages) {
  try {
    const byId = new Map(messages.map((m) => [m.seq, m]));
    const used = new Set();
    const items = [];
    for (const m of messages) {
      if (m.channel === "tool_use") {
        const payload = parseContent(m);
        const result = messages.find(
          (x) => x.channel === "tool_result" && x.tool_use_id === payload.tool_use_id
        );
        if (result) used.add(result.seq);
        items.push({ kind: "tool", seq: m.seq, payload, result });
      } else if (m.channel === "tool_result") {
        if (!used.has(m.seq)) items.push({ kind: "tool_result_orphan", seq: m.seq, m });
      } else {
        items.push({ kind: m.channel === "thinking" ? "thinking" : "bubble", seq: m.seq, m });
      }
    }
    items.sort((a, b) => a.seq - b.seq);
    return [{ items }];
  } catch {
    return [{ items: messages.map((m) => ({ kind: m.channel === "thinking" ? "thinking" : "bubble", seq: m.seq, m })) }];
  }
}

function toolTitle(p) {
  // 标题用 agent 自己写的 description（它对这次动作的意图说明）
  return p.input?.description || p.tool;
}

function toolCommand(p) {
  return p.input?.command || null;
}

function parseContent(m) {
  try { return JSON.parse(m.content); } catch { return {}; }
}

async function load() {
  try {
    const r = await fetch(`${API}/sessions/${props.id}`);
    if (!r.ok) return;
    detail.value = await r.json();
    running.value = detail.value.status === "running";
    emit("loaded", detail.value);
  } catch {
    // 网络瞬断等场景：不清空已有内容，下次 turn_done/手动操作再刷新
  }
}

function subscribe() {
  es?.close();
  es = new EventSource(`${API}/sessions/${props.id}/events`);
  es.addEventListener("line", async (ev) => {
    try {
      const e = JSON.parse(ev.data).data;
      const line = JSON.parse(e);
      if (!detail.value) await load();
      if (line.type === "system" && line.subtype === "thinking_tokens") {
        thinkingTokens.value = line.estimated_tokens ?? thinkingTokens.value;
        return;
      }
      if (line.type === "assistant") {
        // 实时低声部/主旋律：先本地展示，turn_done 后以 DB 为准刷新
        for (const block of line.message?.content ?? []) {
          if (block.type === "thinking" || block.type === "text") {
            detail.value?.messages.push({
              seq: 9e9, role: "assistant", channel: block.type,
              content: JSON.stringify({ text: block.text || block.thinking }),
              turn_id: -1,
            });
            stickToBottom();
          }
        }
      }
    } catch { /* 未知行忽略，与后端解析器同一原则 */ }
  });
  es.addEventListener("turn_done", () => {
    es?.close(); es = null;
    stopWorking();
    load().then(stickToBottom);
  });
}

function onKeydown(e) {
  // 仅 ⌘/Ctrl+Enter 发送；Enter 留给换行与输入法选词
  if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
    e.preventDefault(); // 阻止换行，但不拦组合期（IME 下组合键不会触发提交语义）
    if (!(e.isComposing || e.keyCode === 229)) send();
  }
}

async function send() {
  const text = input.value.trim();
  if (!text || running.value) return;
  if (!detail.value) await load(); // HMR/加载竞态兜底：没有详情就先拉
  if (!detail.value) return;
  input.value = "";
  running.value = true;
  startWorking();
  detail.value?.messages.push({
    seq: 9e9 - 1, role: "user", channel: "text",
    content: JSON.stringify({ text }), turn_id: -1,
  });
  stickToBottom();
  subscribe();
  await fetch(`${API}/sessions/${props.id}/messages`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text }),
  });
}

async function cancel() {
  await fetch(`${API}/sessions/${props.id}/cancel`, { method: "POST" });
}

onMounted(async () => {
  await load();
  await stickToBottom();
  // 刷新/中途进入正在运行的会话：接上实时流
  if (detail.value?.status === "running") subscribe();
});
onUnmounted(() => { es?.close(); stopWorking(); });
</script>

<template>
  <div class="wrap" v-if="detail">
    <header>
      <strong>{{ detail.title }}</strong>
      <span class="badge" :data-status="detail.status">{{ statusText(detail.status) }}</span>
      <code class="cwd">{{ detail.cwd }}</code>
      <span class="mode">{{ detail.mode }}</span>
    </header>

    <div class="flow" ref="flowEl">
      <div v-if="!detail.messages.length" class="empty">
        {{ t('emptyFlow') }}
      </div>
      <template v-for="(turn, ti) in groupMessages(detail.messages)" :key="ti">
        <template v-for="item in turn.items" :key="item.seq">
          <div v-if="item.kind === 'bubble' && item.m.role === 'user'" class="user-row">
            <span v-if="turnDenied(item.m.turn_id)" class="denied-hint">{{ t('deniedHint') }}</span>
            <button v-if="turnDenied(item.m.turn_id)" class="grant" @click="grantAndContinue(item.m.turn_id)">🔓 {{ t('grant') }}</button>
            <button v-if="turnFailed(item.m.turn_id)" class="retry"
              :class="{ used: retriedTurns.has(item.m.turn_id) }"
              :disabled="retriedTurns.has(item.m.turn_id) || running"
              :title="retriedTurns.has(item.m.turn_id) ? t('retried') : t('retry')"
              @click="retryTurn(item.m.turn_id)">↻ {{ retriedTurns.has(item.m.turn_id) ? t('retried') : t('retry') }}</button>
            <div class="bubble user">{{ parseContent(item.m).text }}</div>
          </div>

          <details v-else-if="item.kind === 'thinking'" class="thinking">
            <summary>💭 {{ t("thinking") }}</summary>
            <div class="thinking-body md-inline" v-html="renderMarkdown(parseContent(item.m).text)"></div>
          </details>

          <details v-else-if="item.kind === 'bubble'" class="reply" :open="replyOpen(item.m)"
            @toggle="onReplyToggle(item.m, $event)">
            <summary class="reply-head">📄 {{ replySnippet(item.m) }}…</summary>
            <div class="bubble agent md">
              <!-- eslint-disable-next-line vue/no-v-html -- 已 DOMPurify 消毒 -->
              <div v-html="renderMarkdown(parseContent(item.m).text)"></div>
            </div>
          </details>

          <details v-else-if="item.kind === 'tool'" class="tool">
            <summary>🔧 {{ toolTitle(item.payload) }}</summary>
            <div class="term">
              <div class="term-bar"><i></i><i></i><i></i><span>{{ item.payload.tool }}</span></div>
              <pre v-if="toolCommand(item.payload)" class="term-io">$ {{ toolCommand(item.payload) }}</pre>
              <pre v-else class="term-io">$ {{ item.payload.tool }} {{ JSON.stringify(item.payload.input) }}</pre>
              <pre v-if="item.result" class="term-io" :data-err="parseContent(item.result).is_error">{{ parseContent(item.result).content }}</pre>
            </div>
          </details>
        </template>
      </template>
      <div v-if="running" class="working">
        <span class="pulse"></span>
        <span>{{ t('working') }} · {{ elapsed }}s</span>
        <span v-if="thinkingTokens" class="tk">💭 {{ thinkingTokens }} tokens</span>
      </div>
    </div>

    <footer>
      <textarea v-model="input" :disabled="running" :placeholder="t('inputPh')"
        @keydown="onKeydown"></textarea>
      <button v-if="running" class="danger" @click="cancel">{{ t("stop") }}</button>
      <button v-else class="primary" @click="send" :disabled="!input.trim()">{{ t("send") }}</button>
    </footer>
  </div>
</template>

<style scoped>
.wrap { flex: 1; min-width: 0; padding: 16px 20px; display: flex; flex-direction: column; height: 100%; }
header { display: flex; align-items: center; gap: 10px; margin-bottom: 12px; }
.cwd { color: var(--text-faint); font-size: 12px; }
.mode { color: var(--text-faint); font-size: 12px; border: 1px solid var(--border-2); padding: 1px 8px; border-radius: 99px; }
.badge { font-size: 12px; padding: 2px 8px; border-radius: 99px; background: #263; color: #9f9; }
.badge[data-status="running"] { background: #441; color: #ff9; }
.badge[data-status="error"] { background: #411; color: #f99; }
.badge[data-status="cancelled"] { background: #234; color: #99f; }
.flow { flex: 1; overflow-y: auto; display: flex; flex-direction: column; gap: 8px; padding-right: 6px; }
.empty { color: var(--text-faint); text-align: center; padding: 40px; }
.bubble { padding: 10px 14px; border-radius: 12px; max-width: 80%; white-space: pre-wrap; }
.user-row { align-self: flex-end; display: flex; align-items: center; gap: 8px; max-width: 85%; }
.user-row .bubble.user { background: #2b5387; color: #fff; max-width: none; flex: 1; min-width: 0; }
.retry { padding: 4px 10px; border-radius: 99px; border: 1px solid var(--border-2); background: var(--surface); color: var(--text-dim); cursor: pointer; font-size: 12px; flex-shrink: 0; }
.retry:hover:not(:disabled) { border-color: var(--accent); color: var(--text); }
.retry.used, .retry:disabled { opacity: .45; cursor: default; }
.denied-hint { font-size: 11px; color: #b98a4a; }
.grant { padding: 4px 12px; border-radius: 99px; border: 1px solid #b98a4a; background: rgb(185 138 74 / 12%); color: #b98a4a; cursor: pointer; font-size: 12px; flex-shrink: 0; }
.grant:hover:not(:disabled) { background: rgb(185 138 74 / 25%); }
.badge[data-status="denied"] { background: #463; color: #ffb84d; }
.bubble.agent { align-self: flex-start; background: #1e2227; border: 1px solid #2c313a; }
.bubble pre { margin: 0; font-family: inherit; white-space: pre-wrap; }
.reply { align-self: stretch; }
.reply-head { cursor: pointer; color: var(--text-faint); font-size: 12px; padding: 4px 6px; border-radius: 6px; list-style: none; }
.reply-head::-webkit-details-marker { display: none; }
.reply-head::before { content: "▸ "; }
.reply[open] > .reply-head::before { content: "▾ "; }
.reply-head:hover { background: var(--hover); color: var(--text-dim); }
.reply .bubble { margin-top: 4px; }
/* ---- claude-like Markdown 移植（色板取自 Xv-Bowen/claude-like-typora-theme）----
   暗色舞台 + 米色纸卡：agent 回复是一张"纸" */
.bubble.agent.md {
  --paper-bg: #f9f9f7;
  --paper-surface: #f4f4f2;
  --paper-text: #2d2d2b;
  --paper-muted: #6b6b67;
  --paper-border: rgb(45 45 43 / 14%);
  --accent: #cc7d5e;
  --accent-text: #a95639;
  background: var(--paper-bg);
  color: var(--paper-text);
  border: 0.5px solid var(--paper-border);
  border-radius: 0.75rem;
  padding: 4px 18px;
  font-size: 14.5px;
  line-height: 1.55;
}
.md :deep(h1) { font-size: 1.4rem; line-height: 1.9rem; font-weight: 700; margin: .6rem 0 .1rem; padding-bottom: .3rem; border-bottom: 1px solid var(--paper-border); }
.md :deep(h2) { font-size: 1.2rem; line-height: 1.65rem; font-weight: 700; margin: .55rem 0 .1rem; }
.md :deep(h3) { font-size: 1.05rem; line-height: 1.5rem; font-weight: 700; margin: .45rem 0 .1rem; }
.md :deep(h4), .md :deep(h5), .md :deep(h6) { font-size: .95rem; font-weight: 700; margin: .5rem 0 .1rem; }
.md :deep(p) { margin: .25rem 0; }
.md :deep(a) { color: var(--accent-text); text-decoration: underline; text-underline-offset: 2px; }
.md :deep(strong) { font-weight: 700; color: #1f1f1d; }
.md :deep(table) { border-collapse: collapse; width: 100%; margin: .75rem 0; font-variant-numeric: tabular-nums; font-size: .875rem; }
.md :deep(th), .md :deep(td) { border: 1px solid var(--paper-border); padding: .4rem .7rem; text-align: left; }
.md :deep(th) { background: #ecece9; font-weight: 700; }
.md :deep(tr:nth-child(even) td) { background: rgb(45 45 43 / 3%); }
.md :deep(code) { background: var(--paper-surface); border: 0.5px solid var(--paper-border); padding: .1rem .35rem; border-radius: .3rem; font-size: .85em; font-family: ui-monospace, "SF Mono", Menlo, monospace; }
.md :deep(pre) { background: var(--paper-surface); border: 0.5px solid var(--paper-border); border-radius: .5rem; padding: .875rem; margin: .75rem 0; overflow-x: auto; }
.md :deep(pre code) { background: none; border: none; padding: 0; font-size: .85rem; }
.md :deep(blockquote) { border-left: 3px solid var(--accent); background: rgb(204 125 94 / 8%); margin: .6rem 0; padding: .3rem .9rem; color: var(--paper-muted); border-radius: 0 .35rem .35rem 0; }
.md :deep(hr) { border: none; border-top: 1px solid var(--paper-border); margin: 1rem 0; }
.md :deep(ul), .md :deep(ol) { padding-left: 1.4rem; margin: .5rem 0; }
.md :deep(li) { margin: .25rem 0; }
.md :deep(img) { max-width: 100%; border-radius: .5rem; }
.thinking { align-self: flex-start; font-size: 13px; color: #8a7f6f; max-width: 90%; }
.thinking summary { cursor: pointer; color: #6f6a5f; }
.thinking pre { margin: 6px 0 0; padding: 8px; background: #17150f; border-radius: 8px; white-space: pre-wrap; color: #a89c85; }
.tool { align-self: flex-start; font-size: 12px; max-width: 90%; border: 1px dashed #3a4a5c; border-radius: 8px; padding: 4px 10px; margin-left: 0; }
.tool summary { cursor: pointer; color: #7a8aa0; }
/* 终端窗口：刻意固定深色（终端隐喻不随主题），浅色主题下黑终端反而准确 */
.term { margin: 6px 0 0; border-radius: 8px; overflow: hidden; background: #0b0e12; border: 1px solid #1e2430; }
.term-bar { display: flex; align-items: center; gap: 6px; padding: 6px 10px; background: #141922; border-bottom: 1px solid #1e2430; }
.term-bar i { width: 10px; height: 10px; border-radius: 50%; }
.term-bar i:nth-child(1) { background: #ff5f57; }
.term-bar i:nth-child(2) { background: #febc2e; }
.term-bar i:nth-child(3) { background: #28c840; }
.term-bar span { margin-left: 6px; font-size: 11px; color: #5c6a7a; font-family: ui-monospace, Menlo, monospace; }
.term-io { margin: 0; padding: 10px 12px; white-space: pre-wrap; word-break: break-all; color: #b8c4d0; font-family: ui-monospace, "SF Mono", Menlo, monospace; font-size: 12px; line-height: 1.5; }
.term-io[data-err="true"] { color: #ff8a80; }
.working { display: flex; align-items: center; gap: 10px; padding: 8px 12px; border-radius: 8px; background: var(--surface); border: 1px solid var(--border); font-size: 13px; color: var(--text-dim); }
.pulse { width: 9px; height: 9px; border-radius: 50%; background: var(--accent); animation: pulse 1.2s infinite; }
.tk { color: var(--text-faint); font-size: 12px; }
footer { display: flex; gap: 8px; margin-top: 12px; }
textarea { flex: 1; height: 64px; padding: 10px; border-radius: 8px; border: 1px solid var(--border-2); background: var(--input-bg); color: var(--text); resize: none; font-family: inherit; }
button { padding: 6px 16px; border-radius: 8px; border: 1px solid var(--border-2); background: var(--border); color: var(--text); cursor: pointer; }
button.primary { background: var(--accent); border-color: var(--accent); color: #fff; }
button.danger { background: #7a2b2b; border-color: #7a2b2b; color: #fff; }
button:disabled { opacity: .5; }
</style>
