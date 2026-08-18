<script setup>
import { ref, onMounted, onUnmounted } from "vue";
import { marked } from "marked";
import DOMPurify from "dompurify";

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
const input = ref("");
const running = ref(false);
let es = null;

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
  es.addEventListener("line", (ev) => {
    try {
      const e = JSON.parse(ev.data).data;
      const line = JSON.parse(e);
      if (line.type === "assistant") {
        // 实时低声部/主旋律：先本地展示，turn_done 后以 DB 为准刷新
        for (const block of line.message?.content ?? []) {
          if (block.type === "thinking" || block.type === "text") {
            detail.value?.messages.push({
              seq: 9e9, role: "assistant", channel: block.type,
              content: JSON.stringify({ text: block.text || block.thinking }),
              turn_id: -1,
            });
          }
        }
      }
    } catch { /* 未知行忽略，与后端解析器同一原则 */ }
  });
  es.addEventListener("turn_done", () => { es?.close(); es = null; load(); });
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
  input.value = "";
  running.value = true;
  detail.value?.messages.push({
    seq: 9e9 - 1, role: "user", channel: "text",
    content: JSON.stringify({ text }), turn_id: -1,
  });
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

onMounted(load);
onUnmounted(() => es?.close());
</script>

<template>
  <div class="wrap" v-if="detail">
    <header>
      <strong>{{ detail.title }}</strong>
      <span class="badge" :data-status="detail.status">{{ detail.status }}</span>
      <code class="cwd">{{ detail.cwd }}</code>
      <span class="mode">{{ detail.mode }}</span>
    </header>

    <div class="flow">
      <div v-if="!detail.messages.length" class="empty">
        这个会话还没有内容（可能是发出后即被取消，或尚未提问）
      </div>
      <template v-for="(turn, ti) in groupMessages(detail.messages)" :key="ti">
        <template v-for="item in turn.items" :key="item.seq">
          <div v-if="item.kind === 'bubble' && item.m.role === 'user'" class="bubble user">
            {{ parseContent(item.m).text }}
          </div>

          <details v-else-if="item.kind === 'thinking'" class="thinking">
            <summary>💭 低声部（思考）</summary>
            <pre>{{ parseContent(item.m).text }}</pre>
          </details>

          <div v-else-if="item.kind === 'bubble'" class="bubble agent md">
            <!-- eslint-disable-next-line vue/no-v-html -- 已 DOMPurify 消毒 -->
            <div v-html="renderMarkdown(parseContent(item.m).text)"></div>
          </div>

          <details v-else-if="item.kind === 'tool'" class="tool">
            <summary>🔧 {{ item.payload.tool }}</summary>
            <pre class="tool-io">→ {{ JSON.stringify(item.payload.input, null, 2) }}</pre>
            <pre v-if="item.result" class="tool-io" :data-err="parseContent(item.result).is_error">
              ← {{ parseContent(item.result).content }}</pre>
          </details>
        </template>
      </template>
    </div>

    <footer>
      <textarea v-model="input" :disabled="running" placeholder="向 agent 提问…（⌘/Ctrl+Enter 发送）"
        @keydown="onKeydown"></textarea>
      <button v-if="running" class="danger" @click="cancel">■ 停止</button>
      <button v-else class="primary" @click="send" :disabled="!input.trim()">发送</button>
    </footer>
  </div>
</template>

<style scoped>
.wrap { flex: 1; min-width: 0; padding: 16px 20px; display: flex; flex-direction: column; height: 100%; }
header { display: flex; align-items: center; gap: 10px; margin-bottom: 12px; }
.cwd { color: #777; font-size: 12px; }
.mode { color: #777; font-size: 12px; border: 1px solid #333; padding: 1px 8px; border-radius: 99px; }
.badge { font-size: 12px; padding: 2px 8px; border-radius: 99px; background: #263; color: #9f9; }
.badge[data-status="running"] { background: #441; color: #ff9; }
.badge[data-status="error"] { background: #411; color: #f99; }
.badge[data-status="cancelled"] { background: #234; color: #99f; }
.flow { flex: 1; overflow-y: auto; display: flex; flex-direction: column; gap: 8px; padding-right: 6px; }
.empty { color: #666; text-align: center; padding: 40px; }
.bubble { padding: 10px 14px; border-radius: 12px; max-width: 80%; white-space: pre-wrap; }
.bubble.user { align-self: flex-end; background: #2b5387; color: #fff; }
.bubble.agent { align-self: flex-start; background: #1e2227; border: 1px solid #2c313a; }
.bubble pre { margin: 0; font-family: inherit; white-space: pre-wrap; }
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
  line-height: 1.6;
}
.md :deep(h1) { font-size: 1.4rem; line-height: 2rem; font-weight: 700; margin: .9rem 0 .15rem; padding-bottom: .3rem; border-bottom: 1px solid var(--paper-border); }
.md :deep(h2) { font-size: 1.2rem; line-height: 1.75rem; font-weight: 700; margin: .8rem 0 .15rem; }
.md :deep(h3) { font-size: 1.05rem; line-height: 1.6rem; font-weight: 700; margin: .65rem 0 .15rem; }
.md :deep(h4), .md :deep(h5), .md :deep(h6) { font-size: .95rem; font-weight: 700; margin: .5rem 0 .1rem; }
.md :deep(p) { margin: .5rem 0; }
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
.tool-io { margin: 6px 0 0; white-space: pre-wrap; color: #9aa; }
.tool-io[data-err="true"] { color: #f99; }
footer { display: flex; gap: 8px; margin-top: 12px; }
textarea { flex: 1; height: 64px; padding: 10px; border-radius: 8px; border: 1px solid #333; background: #141414; color: #eee; resize: none; font-family: inherit; }
button { padding: 6px 16px; border-radius: 8px; border: 1px solid #333; background: #222; color: #ddd; cursor: pointer; }
button.primary { background: #2b6cb0; border-color: #2b6cb0; color: #fff; }
button.danger { background: #7a2b2b; border-color: #7a2b2b; color: #fff; }
button:disabled { opacity: .5; }
</style>
