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
const taEl = ref(null);

// 输入框自适应增高：内容超 min 高时随内容增长，上限 1/3 视口高，再超则框内滚动
function autoResize() {
  const el = taEl.value;
  if (!el) return;
  el.style.height = "auto";
  const max = Math.floor(window.innerHeight / 3);
  el.style.height = Math.min(el.scrollHeight, max) + "px";
}

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
const permission = ref(null); // 挂起中的权限请求（事中授权）
const permLeft = ref(0); // 倒计时剩余秒
let permTimer = null;

function onPermission(ev) {
  const d = JSON.parse(ev.data).data;
  setPermission(d);
}

function setPermission(d) {
  permission.value = d;
  stopPermTimer();
  if (d?.timeout_at) {
    const end = new Date(String(d.timeout_at).replace(" ", "T")).getTime();
    permTimer = setInterval(() => {
      permLeft.value = Math.max(0, Math.round((end - Date.now()) / 1000));
      if (permLeft.value <= 0) { stopPermTimer(); permission.value = null; }
    }, 1000);
    permLeft.value = Math.max(0, Math.round((end - Date.now()) / 1000));
  }
}

function stopPermTimer() { clearInterval(permTimer); permTimer = null; }

async function decidePermission(decision) {
  const rid = permission.value?.request_id;
  if (!rid) return;
  await fetch(`${API}/sessions/${props.id}/permission/${rid}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ decision }),
  });
  stopPermTimer();
  permission.value = null;
}

// 恢复挂起的权限请求（页面重开）
async function recoverPermissions() {
  try {
    const rows = await (await fetch(`${API}/sessions/${props.id}/permissions`)).json();
    if (rows?.length) setPermission(rows[0]);
  } catch { /* 忽略 */ }
}

// 授权状态从数据推导：任何 turn 的 granted_from 指向它，即已被授权过
function turnGranted(turnId) {
  return (detail.value?.turns ?? []).some((t) => t.granted_from === turnId);
}
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

// 幕后行卡的展开状态（内存态：会话内保持，刷新回默认折叠）
const bkOpenMap = ref({});
function bkOpen(seq) { return !!bkOpenMap.value[seq]; }
function toggleBk(seq) { bkOpenMap.value = { ...bkOpenMap.value, [seq]: !bkOpenMap.value[seq] }; }

function bkIcon(kind) {
  return { thinking: "💭", narration: "🗣", tool: "🔧" }[kind] ?? "·";
}

function bkToolLabel(payload) {
  return `${payload.tool} · ${payload.input?.description || "…"}`;
}

function bkPreview(item) {
  const text = item.kind === "tool" ? bkToolLabel(item.payload)
    : (parseContent(item.m).text ?? "").split("\n").map((l) => l.trim()).filter(Boolean)[0] || "";
  return text.replace(/[#*`>|]/g, "").slice(0, 70);
}

function turnStatusOf(turnId) {
  const t = (detail.value?.turns ?? []).find((x) => x.id === turnId);
  return t?.status;
}

function turnAbnormal(turnId) {
  return ["denied", "error", "cancelled"].includes(turnStatusOf(turnId));
}

// 本轮是否有"未授权"的交互（denied/timeout）——决定「授权并继续」按钮是否出现
function turnHadAuthBlock(turnId) {
  return (detail.value?.permissions ?? []).some(
    (p) => p.turn_id === turnId && ["denied", "timeout"].includes(p.status)
  );
}

function turnFailed(turnId) {
  // 「失败/已终止」才给重试；「未完成」的正确动作是授权（grant）
  const t = detail.value?.turns?.find((x) => x.id === turnId);
  return t && ["error", "cancelled"].includes(t.status);
}

const STATUS_KEYS = { done: "stDone", denied: "stIncomplete", error: "stError", cancelled: "stTerminated", running: "stRunning" };
function statusText(s) { return STATUS_KEYS[s] ? t(STATUS_KEYS[s]) : s; }

// 轮次级一次性授权：本轮以 autonomous 执行，会话模式不动，授权链留痕
async function grantAndContinue(turnId) {
  if (running.value) return;
  running.value = true;
  startWorking();
  detail.value?.messages.push({
    seq: 9e9 - 1, role: "system", channel: "text",
    content: JSON.stringify({ text: "🔓 " + t("grantedAndRetrying") }), turn_id: -1,
  });
  stickToBottom();
  subscribe();
  await fetch(`${API}/sessions/${props.id}/messages`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text: t("grantPrompt"), mode_override: "autonomous", granted_from: turnId }),
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

// 折叠态标题列表：提取 h1/h2 作迷你目录；无标题降级为首行摘要
function replyOutline(m) {
  const text = parseContent(m).text ?? "";
  const heads = text.split("\n")
    .map((l) => l.match(/^#{1,2}\s+(.+)/))
    .filter(Boolean)
    .map((x) => x[1].replace(/[*`]/g, "").trim())
    .slice(0, 4);
  return heads.length ? heads : null;
}

// 每轮三段式：用户气泡 → 幕后收纳（思考+工具）→ 回复纸卡。
// 幕后折叠态只显：思考状态 · 思考次数 · 工具次数（用户实测反馈的收纳需求）
function groupMessages(messages) {
  try {
    const turnMap = new Map();
    for (const m of messages) {
      const key = m.turn_id === -1 ? (turnMap.size ? "__live__" : "__live__") : m.turn_id;
      if (!turnMap.has(key)) turnMap.set(key, []);
      turnMap.get(key).push(m);
    }
    const turns = [];
    for (const [tid, msgs] of turnMap) {
      if (tid === "__live__" && turns.length) {
        // 实时推送并入最近一轮（SSE 本地块无 turn_id）
        const last = turns[turns.length - 1];
        for (const m of msgs) last.raw.push(m);
        continue;
      }
      turns.push({ id: tid, raw: [...msgs] });
    }
    return turns.map((turn) => {
      const seen = new Set();
      const backstage = [];
      let userText = null;
      const replies = [];
      const ordered = [...turn.raw].sort((a, b) => a.seq - b.seq);
      // 最后一个 assistant text 块才是最终答复；中间的 text 是过程旁白，归入幕后
      const lastTextSeq = Math.max(...ordered.filter((m) => m.channel === "text" && m.role === "assistant").map((m) => m.seq), -1);
      const systemMsgs = [];
      for (const m of ordered) {
        if (m.role === "system") { systemMsgs.push(m); continue; }
        if (m.role === "user" && m.channel === "text") userText = m;
        else if (m.channel === "text" && m.role === "assistant" && m.seq !== lastTextSeq) backstage.push({ kind: "narration", seq: m.seq, m });
        else if (m.channel === "text" && m.role === "assistant") replies.push(m);
        else if (m.channel === "thinking" && (parseContent(m).text || "").trim()) backstage.push({ kind: "thinking", seq: m.seq, m });
        else if (m.channel === "tool_use") {
          const payload = parseContent(m);
          const result = turn.raw.find(
            (x) => x.channel === "tool_result" && x.tool_use_id === payload.tool_use_id
          );
          if (result) seen.add(result.seq);
          const perm = (detail.value?.permissions ?? []).find(
            (p) => p.tool_use_id === payload.tool_use_id
          );
          backstage.push({ kind: "tool", seq: m.seq, payload, result, perm: perm?.status || null });
        } // 孤儿 tool_result 忽略（配对已尽）
      }
      const live = turn.id === "__live__";
      const t = live ? null : (detail.value?.turns ?? []).find((x) => x.id === turn.id);
      const perms = (detail.value?.permissions ?? []).filter((p) => p.turn_id === turn.id);
      return {
        id: turn.id, userText, systemMsgs, backstage, replies, perms,
        thinkCount: backstage.filter((b) => b.kind === "thinking").length,
        toolCount: backstage.filter((b) => b.kind === "tool").length,
        narrationCount: backstage.filter((b) => b.kind === "narration").length,
        status: live ? "running" : t?.status,
      };
    });
  } catch {
    return [{ userText: null, systemMsgs: [], backstage: [], replies: messages, thinkCount: 0, toolCount: 0, status: undefined }];
  }
}

// 工具展示：标题用 agent 自己写的 description（它对这次动作的意图说明）
function toolTitle(p) {
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
  es.addEventListener("permission_request", onPermission);
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
  nextTick(autoResize);
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
  recoverPermissions();
  // 刷新/中途进入正在运行的会话：接上实时流 + 启动计时（否则状态条停在 0s）
  if (detail.value?.status === "running") { startWorking(); subscribe(); }
});
onUnmounted(() => { es?.close(); stopWorking(); stopPermTimer(); });

// 节目单点击定位：滚动对话流到对应轮次（App 通过 ref 调用）
function scrollToTurn(turnId) {
  const el = flowEl.value?.querySelector(`[data-turn-id="${turnId}"]`);
  if (el) el.scrollIntoView({ behavior: "smooth", block: "start" });
}

defineExpose({ scrollToTurn });
</script>

<template>
  <div class="wrap" v-if="detail">
    <header>
      <strong class="detail-title">{{ detail.title }}</strong>
    </header>

    <div class="flow" ref="flowEl">
      <div v-if="!detail.messages.length" class="empty">
        {{ t('emptyFlow') }}
      </div>
      <div v-for="(turn, ti) in groupMessages(detail.messages)" :key="ti" class="turn-group" :data-turn-id="turn.id">
        <!-- 用户输入 + 轮次动作（授权/重试） -->
        <div v-if="turn.userText" class="user-row">
          <div class="bubble user">{{ parseContent(turn.userText).text }}</div>
        </div>

        <!-- 系统生成消息（如授权重跑）用系统样式，不冒充用户提问 -->
        <div v-for="sm in turn.systemMsgs" :key="sm.seq" class="system-row">
          {{ parseContent(sm).text }}
        </div>

        <!-- 轮次状态行：状态与动作同处（单一事实来源）；正常完成不显示 -->
        <div v-if="turn.userText && turnAbnormal(turn.id)" class="turn-status" :data-st="turnGranted(turn.id) ? 'granted' : turnStatusOf(turn.id)">
          <span class="ts-label">
            <template v-if="turnGranted(turn.id)">✓ {{ t('granted') }}</template>
            <template v-else>
              <span class="ts-ico">{{ { denied: "▣", error: "✕", cancelled: "■" }[turnStatusOf(turn.id)] || "✕" }}</span>
              {{ statusText(turnStatusOf(turn.id)) }}
            </template>
          </span>
          <span class="ts-actions">
            <button v-if="turnHadAuthBlock(turn.id) && !turnGranted(turn.id)" class="ts-action grant"
              :disabled="running" @click="grantAndContinue(turn.id)">🔓 {{ t('grant') }}</button>
            <button v-if="turnFailed(turn.id) && !turnGranted(turn.id)"
              :class="{ used: retriedTurns.has(turn.id) }"
              :disabled="retriedTurns.has(turn.id) || running"
              @click="retryTurn(turn.id)">↻ {{ retriedTurns.has(turn.id) ? t('retried') : t('retry') }}</button>
          </span>
        </div>

        <!-- 幕后收纳：思考+工具统一进灰色折叠块，折叠态只显三要素 -->
        <details v-if="turn.backstage.length" class="backstage" :open="running && ti === groupMessages(detail.messages).length - 1">
          <summary>
            <span class="bs-count">💭 ×{{ turn.thinkCount }}</span>
            <span class="bs-count">🔧 ×{{ turn.toolCount }}</span>
            <span v-if="turn.narrationCount" class="bs-count">🗣 ×{{ turn.narrationCount }}</span>
          </summary>
          <div class="bs-body">
            <div v-for="item in turn.backstage" :key="item.seq" class="bk-card paper" :class="{ narration: item.kind === 'narration' }">
              <!-- 旁白：直接展示，无折叠 -->
              <div v-if="item.kind === 'narration'" class="bk-text narration-text">
                🗣 <span v-html="renderMarkdown(parseContent(item.m).text)"></span>
              </div>
              <template v-else>
              <div class="reply-top">
                <span class="bk-label" :title="bkPreview(item)">
                  {{ bkIcon(item.kind) }} {{ item.kind === 'tool' ? bkToolLabel(item.payload) : bkPreview(item) }}
                </span>
                <span class="bk-actions">
                  <span v-if="item.perm" class="perm-badge" :data-st="item.perm">
                    {{ { approved: "✓ " + t('approved'), denied: "✕ " + t('deniedVerdict'), timeout: "⏱ " + t('timeout') }[item.perm] }}
                  </span>
                  <button class="reply-toggle" @click.stop="toggleBk(item.seq)">
                    {{ bkOpen(item.seq) ? t("collapse") : t("expand") }}
                  </button>
                </span>
              </div>
              <!-- 思考：纸上斜体批注 -->
              <div v-if="bkOpen(item.seq) && item.kind === 'thinking'" class="bk-text italic"
                v-html="renderMarkdown(parseContent(item.m).text)"></div>
              <!-- 工具：纸上的黑终端 -->
              <div v-if="bkOpen(item.seq) && item.kind === 'tool'" class="term">
                <div class="term-bar"><i></i><i></i><i></i><span>{{ item.payload.tool }}</span></div>
                <pre v-if="toolCommand(item.payload)" class="term-io">$ {{ toolCommand(item.payload) }}</pre>
                <pre v-else class="term-io">$ {{ item.payload.tool }} {{ JSON.stringify(item.payload.input) }}</pre>
                <pre v-if="item.result" class="term-io" :data-err="parseContent(item.result).is_error">{{ parseContent(item.result).content }}</pre>
              </div>
              </template>
            </div>
          </div>
        </details>

        <!-- 主旋律：回复纸卡 -->
        <div v-for="m in turn.replies" :key="m.seq" class="reply-card paper" :class="{ collapsed: !replyOpen(m) }">
          <div class="reply-top">
            <span class="reply-label">{{ t("replied") }}</span>
            <button class="reply-toggle" @click.stop="onReplyToggle(m, { target: { open: !replyOpen(m) } })">
              {{ replyOpen(m) ? t("collapse") : t("expand") }}
            </button>
          </div>
          <!-- eslint-disable-next-line vue/no-v-html -- 已 DOMPurify 消毒 -->
          <div v-if="replyOpen(m)" class="reply-full md" v-html="renderMarkdown(parseContent(m).text)"></div>
          <div v-else class="reply-outline" @click="onReplyToggle(m, { target: { open: true } })">
            <div v-for="(h, hi) in (replyOutline(m) || [replySnippet(m)])" :key="hi" class="outline-item">
              {{ hi === 0 ? "" : "" }}{{ h }}
            </div>
          </div>
        </div>
      </div>
      <div v-if="running" class="working">
        <span class="pulse"></span>
        <span>{{ t('working') }} · {{ elapsed }}s</span>
        <span v-if="thinkingTokens" class="tk">💭 {{ thinkingTokens }} tokens</span>
        <button class="stop-inline" @click="cancel">{{ t('stop') }}</button>
      </div>
    </div>

    <div v-if="permission" class="perm-card">
      <div class="perm-head">
        <span class="perm-title">🔐 {{ t('permTitle') }}</span>
        <span class="perm-count">{{ permLeft }}s</span>
      </div>
      <div class="perm-tool">工具：<code>{{ permission.tool_name }}</code></div>
      <div class="perm-input"><code>{{ JSON.stringify(permission.tool_input) }}</code></div>
      <div class="perm-actions">
        <button class="perm-deny" @click="decidePermission('deny')">{{ t('deny') }}</button>
        <button class="perm-allow" @click="decidePermission('allow')">{{ t('allow') }}</button>
      </div>
    </div>

    <footer>
      <textarea ref="taEl" v-model="input" :disabled="running" :placeholder="t('inputPh')"
        @keydown="onKeydown" @input="autoResize"></textarea>
    </footer>
  </div>
</template>

<style scoped>
.wrap { flex: 1; min-width: 0; padding: 16px 20px; display: flex; flex-direction: column; height: 100%; }
header { display: flex; align-items: center; gap: 10px; margin-bottom: 12px; }
.detail-title { font-size: 17px; font-weight: 700; color: var(--text); }
.cwd { color: var(--text-faint); font-size: 14px; }
.mode { color: var(--text-faint); font-size: 14px; border: 1px solid var(--border-2); padding: 1px 8px; border-radius: 99px; }
.badge { font-size: 14px; padding: 2px 8px; border-radius: 99px; background: #263; color: #9f9; }
.badge[data-status="running"] { background: #441; color: #ff9; }
.badge[data-status="error"] { background: #411; color: #f99; }
.badge[data-status="cancelled"] { background: #234; color: #99f; }
.flow { flex: 1; overflow-y: auto; display: flex; flex-direction: column; gap: 8px; padding-right: 6px; }
.turn-group { display: flex; flex-direction: column; gap: 8px; } /* 包一层便于定位，内部 gap 与 flow 一致，视觉不变 */
.flow > * { flex-shrink: 0; } /* 纵向 flex 子项默认可压缩：内容超高时 widget 被压扁（"时隐时现"的根因） */
.empty { color: var(--text-faint); text-align: center; padding: 40px; }
.bubble { padding: 10px 14px; border-radius: 12px; max-width: 80%; white-space: pre-wrap; }
.turn-status { align-self: flex-start; display: flex; align-items: center; gap: 12px;
  padding: 5px 14px; border-radius: 8px; font-size: 14px; margin-top: -2px; }
.turn-status[data-st="denied"] { background: rgb(85 119 170 / 12%); }
.turn-status[data-st="denied"] .ts-label { color: #7a9ac9; font-weight: 600; }
.turn-status[data-st="error"] { background: rgb(197 68 68 / 8%); }
.turn-status[data-st="error"] .ts-label { color: #c54444; font-weight: 600; }
.turn-status[data-st="cancelled"] { background: var(--surface); }
.turn-status[data-st="cancelled"] .ts-label { color: var(--text-faint); }
.turn-status[data-st="granted"] .ts-label { color: #4a9e5c; font-weight: 600; }
.ts-action { padding: 3px 12px; border-radius: 99px; cursor: pointer; font-size: 14px;
  border: 1px solid #b98a4a; background: rgb(185 138 74 / 12%); color: #b98a4a; }
.ts-action:hover:not(:disabled) { background: rgb(185 138 74 / 25%); }
.ts-action.used, .ts-action:disabled { opacity: .45; cursor: default; }
.ts-ico { font-size: 13px; }
.ts-actions { display: flex; gap: 8px; }
.system-row { align-self: center; padding: 4px 14px; border-radius: 99px; background: var(--surface);
  color: var(--text-dim); font-size: 14px; border: 1px dashed var(--border-2);
  margin: 8px 0; }
.user-row { align-self: flex-end; display: flex; align-items: center; gap: 8px; max-width: 86%; }
.user-row .bubble.user { background: #2b5387; color: #fff; max-width: none; flex: 1; min-width: 0; }
.retry { padding: 4px 10px; border-radius: 99px; border: 1px solid var(--border-2); background: var(--surface); color: var(--text-dim); cursor: pointer; font-size: 14px; flex-shrink: 0; }
.retry:hover:not(:disabled) { border-color: var(--accent); color: var(--text); }
.retry.used, .retry:disabled { opacity: .45; cursor: default; }
.denied-hint { font-size: 14px; color: #b98a4a; }
.grant { padding: 4px 12px; border-radius: 99px; border: 1px solid #b98a4a; background: rgb(185 138 74 / 12%); color: #b98a4a; cursor: pointer; font-size: 14px; flex-shrink: 0; }
.grant:hover:not(:disabled) { background: rgb(185 138 74 / 25%); }
.grant.granted { border-color: #4a9e5c; color: #4a9e5c; background: rgb(74 158 92 / 10%); cursor: default; opacity: .8; }
.badge[data-status="denied"] { background: #463; color: #ffb84d; }
.bubble.agent { align-self: flex-start; background: #1e2227; border: 1px solid #2c313a; }
.bubble pre { margin: 0; font-family: inherit; white-space: pre-wrap; }
.reply { align-self: flex-start; width: fit-content; max-width: 86%; min-width: 160px; }
.reply-card.paper { position: relative; padding: 10px 16px 12px; max-width: 86%; width: fit-content; min-width: 200px;
  display: flex; flex-direction: column; }
.reply-card.collapsed { cursor: pointer; }
.reply-card.collapsed:hover { border-color: var(--border-2); }
.reply-top { display: flex; align-items: center; justify-content: space-between; }
.reply-label { color: var(--paper-muted); font-size: 15px; font-weight: 600; }
.reply-toggle { padding: 2px 12px; border-radius: 99px;
  border: 1px solid var(--paper-hairline); background: var(--paper-sunken); color: var(--paper-muted);
  cursor: pointer; font-size: 14px; }
.reply-toggle:hover { color: var(--paper-ink); border-color: var(--paper-accent); }
.reply-full { color: var(--paper-ink); border: none; background: transparent; padding: 0; }
.reply-outline .outline-item { color: var(--paper-ink); font-weight: 600; font-size: 15px; line-height: 1.7; }
.reply-outline .outline-item:not(:first-child) { font-weight: 400; color: var(--paper-muted); }
.reply-head::-webkit-details-marker { display: none; }
.reply-head::before { content: "▸ "; }
.reply[open] > .reply-head::before { content: "▾ "; }
.reply-head:hover { background: var(--hover); color: var(--text-dim); }
.reply .bubble { margin-top: 4px; }
/* ---- Hekouwang Markdown 移植（huiyonghkw/hekouwang-typora-theme，token 原样提取）----
   纸卡永远亮色（纸的隐喻），暗色主题下是舞台上的纸；亮色主题加投影分层 */
.paper { background: #fdfdfc; border: 1px solid var(--border); border-radius: 10px;
  color: #141413; /* 纸上的墨色，不随主题——纸永远亮色 */
  --paper-ink: #141413;
  --paper-soft: #3d3d3a;
  --paper-muted: #73726c;
  --paper-accent: #d97757;
  --paper-link: #c05d3c;
  --paper-code: #8a5a3c;
  --paper-sunken: #f5f4ed;
  --paper-hairline: rgb(31 30 29 / 12%);
  --paper-line: rgb(31 30 29 / 14%);
  --paper-divider: rgb(31 30 29 / 20%); }
.reply-full.md, .bubble.agent.md {
  --paper-bg: #fdfdfc;
  --paper-sunken: #f5f4ed;
  --paper-ink: #141413;
  --paper-soft: #3d3d3a;
  --paper-muted: #73726c;
  --paper-accent: #d97757;
  --paper-link: #c05d3c;
  --paper-code: #8a5a3c;
  --paper-hairline: rgb(31 30 29 / 10%);
  --paper-line: rgb(31 30 29 / 14%);
  --paper-divider: rgb(31 30 29 / 20%);
  background: var(--paper-bg);
  color: var(--paper-ink);
  border: 1px solid var(--paper-hairline);
  border-radius: 10px;
  padding: 4px 18px;
  font-size: 15px;
  line-height: 1.6;
}
.reply-card .reply-full.md { border: none; background: transparent; padding: 0; } /* 外层卡片已带边框，内层只继承 token */
.md :deep(h1) { font-size: 1.5rem; line-height: 1.1; font-weight: 600; letter-spacing: -.014em; margin: 1.1rem 0 0; }
.md :deep(h2) { font-size: 1.25rem; line-height: 1.1; font-weight: 600; letter-spacing: -.012em; margin: .9rem 0 0; }
.md :deep(h3) { font-size: 1.05rem; line-height: 1.15; font-weight: 600; margin: .7rem 0 0; }
.md :deep(h4), .md :deep(h5), .md :deep(h6) { font-size: 1rem; line-height: 1.2; font-weight: 600; margin: .6rem 0 0; }
.md :deep(p) { margin: .25rem 0; }
.md :deep(h1 + p), .md :deep(h1 + ul), .md :deep(h1 + ol), .md :deep(h1 + table),
.md :deep(h2 + p), .md :deep(h2 + ul), .md :deep(h2 + ol), .md :deep(h2 + table),
.md :deep(h3 + p), .md :deep(h3 + ul), .md :deep(h3 + ol), .md :deep(h3 + table) { margin-top: 0; }
.md :deep(a) { color: var(--paper-link); text-decoration: underline; text-decoration-color: rgb(192 93 60 / 42%); text-underline-offset: .22em; }
.md :deep(strong) { font-weight: 600; color: var(--paper-soft); }
.md :deep(table) { margin: .8rem 0; width: 100%; border-collapse: collapse; font-variant-numeric: tabular-nums; }
.md :deep(th) { font-weight: 650; text-align: left; color: var(--paper-ink);
  background: rgb(31 30 29 / 4%); border-bottom: 1.5px solid var(--paper-divider);
  padding: .55rem .85rem; }
.md :deep(td) { border-bottom: 1px solid var(--paper-hairline); padding: .55rem .85rem; vertical-align: top; }
.md :deep(tbody tr:last-child td) { border-bottom: none; }
.md :deep(tbody tr:hover) { background: rgb(31 30 29 / 4.5%); }
.md :deep(code) { font-family: ui-monospace, "SF Mono", Menlo, monospace; font-size: .9em;
  color: var(--paper-code); background: rgb(217 119 87 / 11%); border: none;
  border-radius: 6px; padding: .14em .4em; word-break: break-word; }
.md :deep(pre) { font-family: ui-monospace, "SF Mono", Menlo, monospace; font-size: .875rem; line-height: 1.65;
  background: var(--paper-sunken); border: 1px solid var(--paper-hairline); border-radius: 10px;
  padding: .88rem 1.05rem; margin: .9rem 0; overflow-x: auto; }
.md :deep(pre code) { background: none; padding: 0; color: var(--paper-ink); font-size: .875rem; }
.md :deep(blockquote) { margin: .8rem 0; padding: .15rem 0 .15rem 1rem;
  border-left: 2px solid var(--paper-divider); background: transparent; color: var(--paper-soft); }
.md :deep(hr) { height: 1px; border: none; background: var(--paper-line); margin: 1.2rem 0; }
.md :deep(ul), .md :deep(ol) { margin: .25rem 0; padding-left: 1.4rem; }
.md :deep(li) { margin: 0; line-height: 1.65; }
.md :deep(img) { max-width: 100%; border-radius: 10px; }
.backstage { align-self: flex-start; max-width: 90%; background: var(--surface-2);
  border: 1px solid var(--border-2); border-radius: 10px; overflow: hidden;
  display: flex; flex-direction: column; width: fit-content; min-width: 220px; }
.backstage[open] { width: min(90%, 860px); }  /* 折叠时窄条，展开后放宽给终端输出空间 */
/* details 上设 display:flex 会破坏其关闭态的原生隐藏（Chromium 坑），显式补回 */
.backstage:not([open]) .bs-body { display: none; }
.backstage summary { display: flex; align-items: center; gap: 14px; padding: 8px 14px; cursor: pointer;
  user-select: none; font-size: 14px; color: var(--text-dim); list-style: none; }
.backstage summary::-webkit-details-marker { display: none; }
.backstage summary::before { content: "▸"; color: var(--text-faint); font-size: 12px; }
.backstage[open] summary::before { content: "▾"; }
.bs-status { font-weight: 600; }
.bs-status[data-st="running"] { color: #d9a918; }
.bs-status[data-st="error"], .bs-status[data-st="denied"] { color: #c54444; }
.bs-status[data-st="done"] { color: #4a9e5c; }
.bs-count { color: var(--text-faint); font-size: 14px; }
.bs-top { align-self: center; margin: 4px 0 10px; padding: 4px 14px; border-radius: 99px;
  border: 1px solid var(--border-2); background: var(--surface-2); color: var(--text-dim);
  cursor: pointer; font-size: 14px; }
.bs-top:hover { color: var(--text); border-color: var(--accent); }
.bs-body { display: flex; flex-direction: column; gap: 8px; padding: 6px 14px 12px; }
.bk-card { padding: 8px 14px 10px; display: flex; flex-direction: column; gap: 6px; max-width: 100%; }
.bk-card.narration { padding: 8px 14px; background: var(--surface); border-style: dashed; color: var(--text-dim); }
.narration-text { color: var(--text-dim); font-size: 15px; line-height: 1.6; }
.narration-text :deep(p) { margin: .2rem 0; display: inline; }
.bk-label { color: var(--paper-ink); font-size: 15px; font-weight: 600; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.bk-actions { display: flex; align-items: center; gap: 8px; flex-shrink: 0; }
.perm-badge { font-size: 14px; font-weight: 600; white-space: nowrap; }
.perm-badge[data-st="approved"] { color: #4a9e5c; }
.perm-badge[data-st="denied"] { color: #c54444; }
.perm-badge[data-st="timeout"] { color: #b98a4a; }
.bk-text { color: var(--paper-soft); padding: 4px 10px; }
.bk-text.italic { font-style: italic; color: var(--paper-muted); }
.bk-text :deep(p) { margin: .25rem 0; }
.bk-text.italic :deep(strong) { font-style: normal; color: var(--text); }
.narration summary { color: #8a9aa0; }
.thinking { align-self: flex-start; font-size: 14px; color: #8a7f6f; max-width: 90%; }
.thinking summary { cursor: pointer; color: #6f6a5f; }
.thinking pre { margin: 6px 0 0; padding: 8px; background: #17150f; border-radius: 8px; white-space: pre-wrap; color: #a89c85; }
.tool { align-self: flex-start; font-size: 14px; max-width: 90%; border: 1px dashed #3a4a5c; border-radius: 8px; padding: 4px 10px; margin-left: 0; }
.tool summary { cursor: pointer; color: #7a8aa0; }
/* 终端窗口：刻意固定深色（终端隐喻不随主题），浅色主题下黑终端反而准确 */
.term { margin: 6px 0 0; border-radius: 8px; overflow: hidden; background: #0b0e12; border: 1px solid #1e2430; }
.term-bar { display: flex; align-items: center; gap: 6px; padding: 6px 10px; background: #141922; border-bottom: 1px solid #1e2430; }
.term-bar i { width: 10px; height: 10px; border-radius: 50%; }
.term-bar i:nth-child(1) { background: #ff5f57; }
.term-bar i:nth-child(2) { background: #febc2e; }
.term-bar i:nth-child(3) { background: #28c840; }
.term-bar span { margin-left: 6px; font-size: 14px; color: #5c6a7a; font-family: ui-monospace, Menlo, monospace; }
.term-io { margin: 0; padding: 10px 12px; white-space: pre-wrap; word-break: break-all; color: #b8c4d0; font-family: ui-monospace, "SF Mono", Menlo, monospace; font-size: 14px; line-height: 1.5; }
.term-io[data-err="true"] { color: #ff8a80; }
.working { display: flex; align-items: center; gap: 10px; padding: 8px 12px; border-radius: 8px; background: var(--surface); border: 1px solid var(--border); font-size: 14px; color: var(--text-dim); }
.pulse { width: 9px; height: 9px; border-radius: 50%; background: var(--accent); animation: pulse 1.2s infinite; }
.tk { color: var(--text-faint); font-size: 14px; }
.perm-card { border: 1px solid #b98a4a; background: rgb(185 138 74 / 10%); border-radius: 10px;
  padding: 10px 14px; margin-top: 12px; display: flex; flex-direction: column; gap: 6px; }
.perm-head { display: flex; align-items: center; justify-content: space-between; }
.perm-title { font-weight: 600; color: #b98a4a; font-size: 15px; }
.perm-count { color: #b98a4a; font-variant-numeric: tabular-nums; font-size: 14px; }
.perm-tool { font-size: 14px; color: var(--text); }
.perm-tool code { color: var(--text-dim); }
.perm-input { font-size: 14px; color: var(--text-faint); }
.perm-input code { font-family: ui-monospace, Menlo, monospace; font-size: 13px; white-space: pre-wrap; word-break: break-all; }
.perm-actions { display: flex; justify-content: flex-end; gap: 8px; }
.perm-deny { padding: 4px 16px; border-radius: 99px; border: 1px solid #c54444; background: rgb(197 68 68 / 12%); color: #c54444; cursor: pointer; font-size: 14px; }
.perm-allow { padding: 4px 16px; border-radius: 99px; border: 1px solid #4a9e5c; background: rgb(74 158 92 / 15%); color: #4a9e5c; cursor: pointer; font-size: 14px; }
footer { display: flex; gap: 8px; margin-top: 12px; }
.stop-inline { margin-left: auto; padding: 3px 14px; border-radius: 99px; border: 1px solid #c54444;
  background: rgb(197 68 68 / 12%); color: #c54444; cursor: pointer; font-size: 14px; flex-shrink: 0; }
.stop-inline:hover { background: rgb(197 68 68 / 22%); }
textarea { flex: 1; min-height: 96px; max-height: 33vh; padding: 10px 12px; border-radius: 8px;
  border: 1px solid var(--border-2); background: var(--input-bg); color: var(--text);
  resize: none; font-family: inherit; line-height: 1.5; overflow-y: auto; }
button { padding: 6px 16px; border-radius: 8px; border: 1px solid var(--border-2); background: var(--border); color: var(--text); cursor: pointer; }
button.primary { background: var(--accent); border-color: var(--accent); color: #fff; }
button.danger { background: #7a2b2b; border-color: #7a2b2b; color: #fff; }
button:disabled { opacity: .5; }
</style>
