<script setup>
import { ref, onMounted, onUnmounted } from "vue";

const props = defineProps({ id: Number });
const emit = defineEmits(["back"]);

const API = "/api";
const detail = ref(null);
const input = ref("");
const running = ref(false);
let es = null;

// 前端按 channel 分声部渲染：tool_use/tool_result 靠 id 配对成树
function groupMessages(messages) {
  try {
    return _group(messages);
  } catch {
    return messages.map((m) => ({ msgs: [m], toolPairs: [] }));
  }
}

function _group(messages) {
  const turns = new Map();
  for (const m of messages) {
    if (!turns.has(m.turn_id)) turns.set(m.turn_id, []);
    turns.get(m.turn_id).push(m);
  }
  return [...turns.values()].map((msgs) => {
    const toolPairs = [];
    const seen = new Set();
    for (const m of msgs) {
      if (m.channel === "tool_use") {
        const payload = JSON.parse(m.content);
        const result = msgs.find(
          (x) => x.channel === "tool_result" && x.tool_use_id === payload.tool_use_id
        );
        toolPairs.push({ use: m, payload, result });
        if (result) seen.add(result.seq);
      }
    }
    return {
      intent: null,
      msgs: msgs.filter((m) => !(m.channel === "tool_result" && seen.has(m.seq))),
      toolPairs,
    };
  });
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
      <button class="ghost" @click="emit('back')">← 返回</button>
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
        <template v-for="m in turn.msgs" :key="m.seq">
          <div v-if="m.role === 'user' && m.channel === 'text'" class="bubble user">
            {{ parseContent(m).text }}
          </div>

          <details v-else-if="m.channel === 'thinking'" class="thinking">
            <summary>💭 低声部（思考）</summary>
            <pre>{{ parseContent(m).text }}</pre>
          </details>

          <div v-else-if="m.channel === 'text'" class="bubble agent">
            <pre>{{ parseContent(m).text }}</pre>
          </div>
        </template>

        <details v-for="tp in turn.toolPairs" :key="tp.use.seq" class="tool">
          <summary>🔧 {{ tp.payload.tool }}</summary>
          <pre class="tool-io">→ {{ JSON.stringify(tp.payload.input, null, 2) }}</pre>
          <pre v-if="tp.result" class="tool-io" :data-err="parseContent(tp.result).is_error">
            ← {{ parseContent(tp.result).content }}</pre>
        </details>
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
.wrap { max-width: 860px; margin: 0 auto; padding: 20px 16px; display: flex; flex-direction: column; height: 100vh; }
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
.thinking { align-self: flex-start; font-size: 13px; color: #8a7f6f; max-width: 90%; }
.thinking summary { cursor: pointer; color: #6f6a5f; }
.thinking pre { margin: 6px 0 0; padding: 8px; background: #17150f; border-radius: 8px; white-space: pre-wrap; color: #a89c85; }
.tool { align-self: flex-start; font-size: 12px; max-width: 90%; border: 1px dashed #333; border-radius: 8px; padding: 6px 10px; }
.tool summary { cursor: pointer; color: #7a8aa0; }
.tool-io { margin: 6px 0 0; white-space: pre-wrap; color: #9aa; }
.tool-io[data-err="true"] { color: #f99; }
footer { display: flex; gap: 8px; margin-top: 12px; }
textarea { flex: 1; height: 64px; padding: 10px; border-radius: 8px; border: 1px solid #333; background: #141414; color: #eee; resize: none; font-family: inherit; }
button { padding: 6px 16px; border-radius: 8px; border: 1px solid #333; background: #222; color: #ddd; cursor: pointer; }
button.primary { background: #2b6cb0; border-color: #2b6cb0; color: #fff; }
button.danger { background: #7a2b2b; border-color: #7a2b2b; color: #fff; }
button.ghost { background: transparent; }
button:disabled { opacity: .5; }
</style>
