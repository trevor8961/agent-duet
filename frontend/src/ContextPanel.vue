<script setup>
import { ref, onMounted, watch } from "vue";
import { t, intentLabel } from "./i18n";

const props = defineProps({ id: Number, detail: Object });

const MODES = [
  { value: "readonly", key: "modeReadonly" },
  { value: "plan", key: "modePlan" },
  { value: "guided", key: "modeGuided" },
  { value: "autonomous", key: "modeAutonomous" },
];

const saving = ref(false);
const git = ref(null);

// 块折叠状态持久化（记住用户想看哪些块）
const BLOCKS = ["mode", "info", "git", "turns", "activity"];
const showChanges = ref(false); // 变更列表默认折叠，只显示计数

const openBlocks = ref(
  new Set(JSON.parse(localStorage.getItem("ad-ctx-blocks") || '["mode","info","git","turns"]'))
);
function toggleBlock(b) {
  const next = new Set(openBlocks.value);
  next.has(b) ? next.delete(b) : next.add(b);
  openBlocks.value = next;
  localStorage.setItem("ad-ctx-blocks", JSON.stringify([...next]));
}

async function loadGit() {
  try {
    git.value = await (await fetch(`/api/sessions/${props.id}/git`)).json();
  } catch { /* 面板信息缺失不致命 */ }
}

// 活动摘要：从 messages 的 tool_use 聚合动过的文件与命令
function activity(detail) {
  const files = new Set();
  const commands = [];
  let toolCount = 0;
  for (const m of detail.messages ?? []) {
    if (m.channel !== "tool_use") continue;
    toolCount++;
    try {
      const p = JSON.parse(m.content);
      const input = p.input ?? {};
      if (input.file_path) files.add(input.file_path);
      if (input.command) commands.push({ tool: p.tool, cmd: input.command.split("\n")[0].slice(0, 60) });
      else commands.push({ tool: p.tool, cmd: Object.keys(input).slice(0, 3).join(",") || "…" });
    } catch { /* 坏数据跳过 */ }
  }
  return { files: [...files], commands: commands.slice(-12), toolCount };
}

const STATUS_KEYS = { denied: "stDenied", error: "stError", cancelled: "stCancelled", done: "stDone", running: "stRunning" };
function statusText(s) { return STATUS_KEYS[s] ? t(STATUS_KEYS[s]) : s; }

async function switchMode(mode) {
  saving.value = true;
  await fetch(`/api/sessions/${props.id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ mode }),
  });
  saving.value = false;
}

onMounted(loadGit);
watch(() => props.detail?.messages?.length, loadGit);
</script>

<template>
  <aside class="ctx" v-if="detail">
    <!-- 模式：可操作，置顶 -->
    <section class="block" :data-open="openBlocks.has('mode')">
      <header @click="toggleBlock('mode')"><span>{{ t("mode") }}</span><i></i></header>
      <div v-show="openBlocks.has('mode')" class="body">
        <select class="mode-select" :value="detail.mode" :disabled="saving" @change="switchMode($event.target.value)">
          <option v-for="m in MODES" :key="m.value" :value="m.value">{{ t(m.key) }}</option>
        </select>
      </div>
    </section>

    <!-- 基本信息 -->
    <section class="block" :data-open="openBlocks.has('info')">
      <header @click="toggleBlock('info')"><span>{{ t("basicInfo") }}</span><i></i></header>
      <div v-show="openBlocks.has('info')" class="body">
        <div class="kv"><span>{{ t("topicShort") }}</span><b>{{ detail.title }}</b></div>
        <div class="kv"><span>{{ t("cwdShort") }}</span><code :title="detail.cwd">{{ detail.cwd }}</code></div>
        <div class="kv"><span>{{ t("status") }}</span><b :data-status="detail.status">{{ detail.status }}</b></div>
        <div class="kv"><span>会话</span><span>{{ detail.agent_session_id ? t("linked") : t("unlinked") }}</span></div>
      </div>
    </section>

    <!-- 工作区 -->
    <section class="block" :data-open="openBlocks.has('git')">
      <header @click="toggleBlock('git')"><span>{{ t("workspace") }}</span><i></i></header>
      <div v-show="openBlocks.has('git')" class="body">
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
              <code>{{ c.path.split("/").pop() }}</code><i>{{ c.status }}</i>
            </div>
          </div>
        </template>
        <div v-else class="none">{{ t("notGit") }}</div>
      </div>
    </section>

    <!-- 节目单 -->
    <section class="block" :data-open="openBlocks.has('turns')">
      <header @click="toggleBlock('turns')"><span>{{ t("playbill") }} · {{ detail.turns.length }} {{ t("rounds") }}</span><i></i></header>
      <div v-show="openBlocks.has('turns')" class="body scroll-list">
        <div v-for="t in detail.turns" :key="t.id" class="turn" :data-status="t.status">
          <span class="intent">{{ intentLabel(t.intent) }}</span>
          <span class="t-status">{{ statusText(t.status) }}</span>
          <span class="t-meta" v-if="t.duration_ms">{{ (t.duration_ms / 1000).toFixed(1) }}s</span>
          <span class="t-meta" v-if="t.total_cost_usd">${{ t.total_cost_usd.toFixed(2) }}</span>
        </div>
        <div v-if="!detail.turns.length" class="none">{{ t("noTurns") }}</div>
      </div>
    </section>

    <!-- 活动 -->
    <section class="block" :data-open="openBlocks.has('activity')">
      <header @click="toggleBlock('activity')"><span>{{ t("activity") }} · {{ activity(detail).toolCount }} {{ t("toolCalls") }}</span><i></i></header>
      <div v-show="openBlocks.has('activity')" class="body">
        <div v-if="activity(detail).files.length" class="files">
          <code v-for="f in activity(detail).files" :key="f" :title="f">{{ f.split("/").pop() }}</code>
        </div>
        <div class="cmds scroll-list">
          <div v-for="(c, i) in activity(detail).commands" :key="i" class="cmd">$ {{ c.cmd }}</div>
        </div>
        <div v-if="!activity(detail).toolCount" class="none">{{ t("noActivity") }}</div>
      </div>
    </section>
  </aside>
</template>

<style scoped>
.ctx { flex-shrink: 0; border-left: 1px solid var(--border); padding: 12px 12px; display: flex; flex-direction: column; gap: 10px; overflow-y: auto; }

/* 块状组织：标题栏可折叠，折叠状态持久化 */
.block { border: 1px solid var(--border); border-radius: 10px; background: var(--panel); overflow: hidden; }
.block header { display: flex; align-items: center; justify-content: space-between; padding: 9px 14px; cursor: pointer; user-select: none; font-size: 12px; font-weight: 600; color: var(--text-dim); letter-spacing: .5px; }
.block header:hover { color: var(--text); }
.block header i { width: 0; height: 0; border-left: 4px solid transparent; border-right: 4px solid transparent; border-top: 5px solid var(--text-faint); transition: transform .15s; }
.block[data-open="true"] header i { transform: rotate(180deg); }
.block .body { padding: 6px 14px 12px; display: flex; flex-direction: column; gap: 3px; }
.scroll-list { max-height: 240px; overflow-y: auto; padding-bottom: 4px; }
/* macOS 悬叠式滚动条平时不可见，用户无从知道可滚——常显细滚动条 */
.scroll-list::-webkit-scrollbar, .changes::-webkit-scrollbar { width: 6px; }
.scroll-list::-webkit-scrollbar-thumb, .changes::-webkit-scrollbar-thumb { background: var(--border-2); border-radius: 3px; }
.scroll-list::-webkit-scrollbar-thumb:hover, .changes::-webkit-scrollbar-thumb:hover { background: var(--text-faint); }
.scroll-list::-webkit-scrollbar-track, .changes::-webkit-scrollbar-track { background: transparent; }

.kv { display: flex; justify-content: space-between; gap: 8px; font-size: 12px; padding: 2px 0; color: var(--text-dim); align-items: center; }
.kv span:first-child { color: var(--text-faint); }
.kv code { font-size: 11px; color: var(--text-dim); max-width: 60%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.kv b[data-status="running"] { color: #d9a918; }
.kv b[data-status="error"] { color: #c54444; }
.kv b[data-status="done"] { color: #4a9e5c; }

.mode-select { width: 100%; padding: 7px 10px; border-radius: 8px; border: 1px solid var(--border-2); background: var(--input-bg); color: var(--text); cursor: pointer; font-size: 13px; }

.branch { color: var(--text); font-family: ui-monospace, Menlo, monospace; font-size: 12px; }
.upstream { font-family: ui-monospace, Menlo, monospace; font-size: 11px; color: var(--text-dim); display: inline-flex; gap: 4px; align-items: center; }
.ab { font-style: normal; font-size: 10px; padding: 0 5px; border-radius: 4px; }
.ab.ahead { background: rgb(74 158 92 / 22%); color: #4a9e5c; }
.ab.behind { background: rgb(204 125 94 / 22%); color: #b96a4a; }
.chg-toggle { display: flex; align-items: center; gap: 6px; padding: 5px 0 2px; cursor: pointer; font-size: 12px; color: var(--text-dim); user-select: none; }
.chg-toggle:hover { color: var(--text); }
.chg-toggle.dirty .tri { border-top-color: var(--accent); }
.tri { width: 0; height: 0; border-left: 4px solid transparent; border-right: 4px solid transparent; border-top: 5px solid var(--text-faint); transition: transform .15s; flex-shrink: 0; }
.changes { max-height: 22vh; overflow-y: auto; padding-bottom: 4px; }  /* branch/remote 固定两行，changes 占弹性区 */
.changes { display: flex; flex-direction: column; gap: 2px; margin-top: 4px; }
.chg { display: flex; align-items: center; gap: 6px; font-size: 12px; }
.chg code { color: var(--text-dim); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.chg i { margin-left: auto; font-style: normal; font-size: 10px; padding: 0 5px; border-radius: 4px; }
.chg[data-st="M"] i { background: rgb(204 125 94 / 25%); color: #b96a4a; }
.chg[data-st="A"] i { background: rgb(74 158 92 / 25%); color: #4a9e5c; }
.chg[data-st="??"] i { background: rgb(85 119 170 / 30%); color: #7a9ac9; }
.chg[data-st="D"] i { background: rgb(197 68 68 / 25%); color: #c54444; }
.more { color: var(--text-faint); font-size: 11px; }

.turn { display: flex; align-items: center; gap: 6px; font-size: 12px; padding: 4px 6px; border-radius: 6px; }
.turn:hover { background: var(--hover); }
.intent { color: #b89a5e; }
.t-status { color: var(--text-faint); font-size: 11px; }
.t-meta { margin-left: auto; color: var(--text-faint); font-size: 11px; }
.none { color: var(--text-faint); font-size: 12px; padding: 6px; }

.files { display: flex; flex-wrap: wrap; gap: 4px; margin-bottom: 6px; }
.files code { background: var(--surface-2); border: 1px solid var(--border); padding: 1px 6px; border-radius: 4px; font-size: 11px; color: var(--text-dim); }
.cmds { display: flex; flex-direction: column; gap: 2px; }
.cmd { font-family: ui-monospace, monospace; font-size: 10px; color: var(--text-faint); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
</style>
