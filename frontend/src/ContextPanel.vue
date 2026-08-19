<script setup>
import { ref, onMounted, watch } from "vue";
import { t, intentLabel } from "./i18n";
import Block from "./Block.vue";

const props = defineProps({ id: Number, detail: Object });
const emit = defineEmits(["locate"]);

const MODES = [
  { value: "readonly", key: "modeReadonly" },
  { value: "plan", key: "modePlan" },
  { value: "guided", key: "modeGuided" },
  { value: "autonomous", key: "modeAutonomous" },
];

const saving = ref(false);
const git = ref(null);

const showChanges = ref(false); // 变更列表默认折叠，只显示计数

async function loadGit() {
  try {
    git.value = await (await fetch(`/api/sessions/${props.id}/git`)).json();
  } catch { /* 面板信息缺失不致命 */ }
}

// 每轮的思考/工具次数（从 messages 数，数据驱动）
function turnCounts(turnId) {
  let think = 0, tool = 0;
  for (const m of props.detail?.messages ?? []) {
    if (m.turn_id !== turnId) continue;
    if (m.channel === "thinking") think++;
    else if (m.channel === "tool_use") tool++;
  }
  return { think, tool };
}

// 智能耗时：<1min 显秒，>=1min 显分秒
function fmtDuration(ms) {
  if (ms == null) return "";
  const s = ms / 1000;
  if (s < 60) return s.toFixed(1) + "s";
  const m = Math.floor(s / 60);
  const r = Math.round(s % 60);
  return m + "m" + r + "s";
}

const STATUS_KEYS = { denied: "stDenied", error: "stError", cancelled: "stCancelled", done: "stDone", running: "stRunning" };
function statusText(s) { return STATUS_KEYS[s] ? t(STATUS_KEYS[s]) : s; }

async function switchMode(mode) {
  saving.value = true;
  const r = await fetch(`/api/sessions/${props.id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ mode }),
  });
  saving.value = false;
  if (r.ok && props.detail) {
    // 本地同步：detail 是父组件传入的响应式对象，直接改让下拉框/档案即时刷新
    props.detail.mode = mode;
  }
}

onMounted(loadGit);
watch(() => props.detail?.messages?.length, loadGit);
</script>

<template>
  <aside class="ctx" v-if="detail">
    <!-- 模式：可操作，置顶 -->
    <Block :title="t('mode')" block-key="ctx-mode" static>
      <div>
        <div class="mode-row">
          <span class="mode-label">{{ t("currentMode") }}</span>
          <select class="mode-chip" :value="detail.mode" :disabled="saving" @change="switchMode($event.target.value)">
            <option v-for="m in MODES" :key="m.value" :value="m.value">{{ t(m.key) }}</option>
          </select>
        </div>
      </div>
    </Block>

    <!-- 基本信息 -->
    <Block :title="t('basicInfo')" block-key="ctx-info" static>
      <div class="body">
        <div class="kv"><span>{{ t("topicShort") }}</span><b>{{ detail.title }}</b></div>
        <div class="kv"><span>{{ t("cwdShort") }}</span><code :title="detail.cwd">{{ detail.cwd }}</code></div>
        <div class="kv"><span>{{ t("status") }}</span><b :data-status="detail.status">{{ detail.status }}</b></div>
        <div class="kv"><span>会话</span><span>{{ detail.agent_session_id ? t("linked") : t("unlinked") }}</span></div>
      </div>
    </Block>

    <!-- git 状态 -->
    <Block :title="t('git')" block-key="ctx-git" static :class="{ 'git-off': git && !git.is_repo }">
      <div class="body">
        <template v-if="git?.is_repo">
          <div class="kv"><span>{{ t("branch") }}</span><b class="branch">{{ git.branch }}</b></div>
          <div v-if="git.upstream" class="kv"><span>{{ t("upstream") }}</span>
            <span class="upstream">
              {{ git.upstream }}
              <i v-if="git.ahead" class="ab ahead">↑{{ git.ahead }}</i>
              <i v-if="git.behind" class="ab behind">↓{{ git.behind }}</i>
            </span>
          </div>
          <div class="chg-toggle" :class="{ dirty: git.changes.length }" @click="showChanges = !showChanges">
            <i class="tri"></i>
            <span>{{ t("changes") }} · {{ git.changes.length }} {{ t("filesChanged") }}</span>
          </div>
          <div v-if="showChanges && git.changes.length" class="changes">
            <div v-for="c in git.changes" :key="c.path" class="chg" :data-st="c.status" :title="c.path">
              <code>{{ c.path.split("/").pop() }}</code><i>{{ c.status === "??" ? t("newFile") : c.status }}</i>
            </div>
          </div>
        </template>
        <div v-else class="none">{{ t("notGit") }}</div>
      </div>
    </Block>

    <!-- 请求（Requests） -->
    <Block :title="`${t('playbill')} · ${detail.turns.length} ${t('rounds')}`" block-key="ctx-turns" static>
      <div class="body scroll-list">
        <div v-for="t in detail.turns" :key="t.id" class="turn" :data-status="t.status" @click="emit('locate', t.id)">
          <span class="intent">{{ intentLabel(t.intent) }}</span>
          <span class="t-status">{{ statusText(t.status) }}</span>
          <span class="t-count">💭{{ turnCounts(t.id).think }} 🔧{{ turnCounts(t.id).tool }}</span>
          <span class="t-meta" v-if="t.duration_ms">{{ fmtDuration(t.duration_ms) }}</span>
        </div>
        <div v-if="!detail.turns.length" class="none">{{ t("noTurns") }}</div>
      </div>
    </Block>

  </aside>
</template>

<style scoped>
.ctx { flex-shrink: 0; border-left: 1px solid var(--border); padding: 12px 12px; display: flex; flex-direction: column; gap: 10px; overflow-y: auto; }

/* 块状组织：标题栏可折叠，折叠状态持久化 */
.scroll-list { max-height: 240px; overflow-y: auto; padding-bottom: 16px;
  mask-image: linear-gradient(to bottom, black 82%, transparent 100%);
  -webkit-mask-image: linear-gradient(to bottom, black 82%, transparent 100%); }
/* macOS 悬叠式滚动条平时不可见，用户无从知道可滚——常显细滚动条 */
.scroll-list::-webkit-scrollbar, .changes::-webkit-scrollbar { width: 6px; }
.scroll-list::-webkit-scrollbar-thumb, .changes::-webkit-scrollbar-thumb { background: var(--border-2); border-radius: 3px; }
.scroll-list::-webkit-scrollbar-thumb:hover, .changes::-webkit-scrollbar-thumb:hover { background: var(--text-faint); }
.scroll-list::-webkit-scrollbar-track, .changes::-webkit-scrollbar-track { background: transparent; }

.kv { display: flex; justify-content: space-between; gap: 8px; font-size: 14px; padding: 2px 0; color: var(--text); align-items: center; }
.kv span:first-child { color: var(--text-faint); font-weight: 500; }
.kv span:first-child { color: var(--text-faint); }
.kv code { font-size: 14px; color: var(--text-dim); max-width: 60%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.kv b[data-status="running"] { color: #d9a918; }
.kv b[data-status="error"] { color: #c54444; }
.kv b[data-status="done"] { color: #4a9e5c; }

.mode-row { display: flex; align-items: center; justify-content: space-between; }
.mode-label { font-size: 14px; color: var(--text-faint); line-height: 20px; }
.mode-chip { height: 20px; padding: 0 12px; border-radius: 99px; border: 1px solid var(--accent);
  background: var(--surface-2); color: var(--text); cursor: pointer; font-size: 14px; font-weight: 600;
  line-height: 18px; /* 与 label 行盒同高：中线对齐为第一约束 */
  -webkit-appearance: none; appearance: none; text-align: center; }

.branch { color: var(--text); font-family: ui-monospace, Menlo, monospace; font-size: 14px; }
.upstream { font-family: ui-monospace, Menlo, monospace; font-size: 14px; color: var(--text-dim); display: inline-flex; gap: 4px; align-items: center; }
.ab { font-style: normal; font-size: 14px; padding: 0 5px; border-radius: 4px; }
.ab.ahead { background: rgb(74 158 92 / 22%); color: #4a9e5c; }
.ab.behind { background: rgb(204 125 94 / 22%); color: #b96a4a; }
.chg-toggle { display: flex; align-items: center; gap: 6px; padding: 5px 0 2px; cursor: pointer; font-size: 14px; color: var(--text-dim); user-select: none; }
.chg-toggle:hover { color: var(--text); }
.chg-toggle.dirty .tri { border-top-color: var(--accent); }
.tri { width: 0; height: 0; border-left: 4px solid transparent; border-right: 4px solid transparent; border-top: 5px solid var(--text-faint); transition: transform .15s; flex-shrink: 0; }
.changes { max-height: 22vh; overflow-y: auto; padding-bottom: 16px;
  mask-image: linear-gradient(to bottom, black 82%, transparent 100%);
  -webkit-mask-image: linear-gradient(to bottom, black 82%, transparent 100%); }
.changes { display: flex; flex-direction: column; gap: 2px; margin-top: 4px; }
.chg { display: flex; align-items: center; gap: 6px; font-size: 14px; }
.chg code { color: var(--text-dim); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.chg i { margin-left: auto; font-style: normal; font-size: 14px; padding: 0 5px; border-radius: 4px; }
.chg[data-st="M"] i { background: rgb(204 125 94 / 25%); color: #b96a4a; }
.chg[data-st="A"] i { background: rgb(74 158 92 / 25%); color: #4a9e5c; }
.chg[data-st="??"] i { background: rgb(74 158 92 / 25%); color: #4a9e5c; }
.chg[data-st="D"] i { background: rgb(197 68 68 / 25%); color: #c54444; }
.more { color: var(--text-faint); font-size: 14px; }

.turn { display: flex; align-items: center; gap: 6px; font-size: 14px; padding: 4px 6px; border-radius: 6px; cursor: pointer; }
.turn:hover { background: var(--hover); }
.intent { color: #b89a5e; }
.t-status { color: var(--text-faint); font-size: 14px; }
.t-count { color: var(--text-dim); font-size: 14px; }
.t-meta { margin-left: auto; color: var(--text-faint); font-size: 14px; }
.none { color: var(--text-faint); font-size: 14px; padding: 6px; }
.git-off { opacity: 0.5; }

.files { display: flex; flex-wrap: wrap; gap: 4px; margin-bottom: 6px; }
.files code { background: var(--surface-2); border: 1px solid var(--border); padding: 1px 6px; border-radius: 4px; font-size: 14px; color: var(--text-dim); }
.cmds { display: flex; flex-direction: column; gap: 2px; }
.cmd { font-family: ui-monospace, monospace; font-size: 14px; color: var(--text-faint); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
</style>
