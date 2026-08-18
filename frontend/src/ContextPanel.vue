<script setup>
import { ref, onMounted, watch } from "vue";

const props = defineProps({ id: Number, detail: Object });

const MODES = [
  { value: "readonly", label: "只读" },
  { value: "plan", label: "计划" },
  { value: "guided", label: "引导" },
  { value: "autonomous", label: "自主" },
];

const saving = ref(false);
const git = ref(null);

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

async function switchMode(mode) {
  saving.value = true;
  await fetch(`/api/sessions/${props.id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ mode }),
  });
  saving.value = false;
}

defineExpose({});
</script>

<template>
  <aside class="ctx" v-if="detail">
    <div class="block">
      <div class="title">档案</div>
      <div class="kv"><span>目录</span><code>{{ detail.cwd }}</code></div>
      <div class="kv"><span>状态</span><b :data-status="detail.status">{{ detail.status }}</b></div>
      <div class="kv"><span>会话</span><span>{{ detail.agent_session_id ? "已关联" : "未关联" }}</span></div>
    </div>

    <div class="block">
      <div class="title">工作区</div>
      <template v-if="git?.is_repo">
        <div class="kv"><span>分支</span><b class="branch">{{ git.branch }}</b></div>
        <div class="kv"><span>变更</span><span>{{ git.changes.length }} 个文件</span></div>
        <div v-if="git.changes.length" class="changes">
          <div v-for="c in git.changes.slice(0, 8)" :key="c.path" class="chg" :data-st="c.status">
            <code>{{ c.path.split("/").pop() }}</code><i>{{ c.status }}</i>
          </div>
          <div v-if="git.changes.length > 8" class="more">…还有 {{ git.changes.length - 8 }} 个</div>
        </div>
      </template>
      <div v-else class="none">非 git 仓库</div>
    </div>

    <div class="block">
      <div class="title">模式</div>
      <div class="modes">
        <button v-for="m in MODES" :key="m.value" :class="{ active: detail.mode === m.value }"
          :disabled="saving" @click="switchMode(m.value)">{{ m.label }}</button>
      </div>
    </div>

    <div class="block grow">
      <div class="title">节目单（{{ detail.turns.length }} 轮）</div>
      <div v-for="t in detail.turns" :key="t.id" class="turn" :data-status="t.status">
        <span class="intent">{{ t.intent }}</span>
        <span class="t-status">{{ t.status }}</span>
        <span class="t-meta" v-if="t.duration_ms">{{ (t.duration_ms / 1000).toFixed(1) }}s</span>
        <span class="t-meta" v-if="t.total_cost_usd">${{ t.total_cost_usd.toFixed(2) }}</span>
      </div>
      <div v-if="!detail.turns.length" class="none">还没有轮次</div>
    </div>

    <div class="block">
      <div class="title">活动（{{ activity(detail).toolCount }} 次工具）</div>
      <div v-if="activity(detail).files.length" class="files">
        <code v-for="f in activity(detail).files" :key="f" :title="f">{{ f.split("/").pop() }}</code>
      </div>
      <div class="cmds">
        <div v-for="(c, i) in activity(detail).commands" :key="i" class="cmd">$ {{ c.cmd }}</div>
      </div>
      <div v-if="!activity(detail).toolCount" class="none">尚未动过手</div>
    </div>
  </aside>
</template>

<style scoped>
.ctx { width: 260px; flex-shrink: 0; border-left: 1px solid var(--border); padding: 14px 12px; display: flex; flex-direction: column; gap: 14px; overflow-y: auto; }
.title { font-size: 11px; color: var(--text-faint); text-transform: uppercase; letter-spacing: 1px; margin-bottom: 6px; }
.block.grow { flex: 1; }
.kv { display: flex; justify-content: space-between; gap: 8px; font-size: 12px; padding: 2px 0; color: #aaa; }
.kv span:first-child { color: var(--text-faint); }
.kv code { font-size: 11px; color: #8899aa; max-width: 170px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.kv b[data-status="running"] { color: #d9a918; }
.kv b[data-status="error"] { color: #c54444; }
.kv b[data-status="done"] { color: #4a9e5c; }
.branch { color: var(--text); font-family: ui-monospace, Menlo, monospace; font-size: 12px; }
.changes { display: flex; flex-direction: column; gap: 2px; margin-top: 4px; }
.chg { display: flex; align-items: center; gap: 6px; font-size: 12px; }
.chg code { color: var(--text-dim); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.chg i { margin-left: auto; font-style: normal; font-size: 10px; padding: 0 5px; border-radius: 4px; }
.chg[data-st="M"] i { background: rgb(204 125 94 / 25%); color: #b96a4a; }
.chg[data-st="A"] i { background: rgb(74 158 92 / 25%); color: #4a9e5c; }
.chg[data-st="??"] i { background: rgb(85 119 170 / 30%); color: #7a9ac9; }
.chg[data-st="D"] i { background: rgb(197 68 68 / 25%); color: #c54444; }
.more { color: var(--text-faint); font-size: 11px; }
.modes { display: grid; grid-template-columns: 1fr 1fr; gap: 6px; }
.modes button { padding: 6px; border-radius: 6px; border: 1px solid var(--border-2); background: var(--hover); color: var(--text-dim); cursor: pointer; font-size: 12px; }
.modes button.active { border-color: var(--accent); background: #1c3a5e; color: #fff; }
.turn { display: flex; align-items: center; gap: 6px; font-size: 12px; padding: 4px 6px; border-radius: 6px; }
.turn:hover { background: var(--hover); }
.intent { color: #b89a5e; }
.t-status { color: var(--text-faint); font-size: 11px; }
.t-meta { margin-left: auto; color: var(--text-faint); font-size: 11px; }
.none { color: var(--text-faint); font-size: 12px; padding: 6px; }
.files { display: flex; flex-wrap: wrap; gap: 4px; margin-bottom: 6px; }
.files code { background: #1e2430; padding: 1px 6px; border-radius: 4px; font-size: 11px; color: #8fb0d9; }
.cmds { display: flex; flex-direction: column; gap: 2px; }
.cmd { font-family: ui-monospace, monospace; font-size: 10px; color: var(--text-faint); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
</style>
