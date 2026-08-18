<script setup>
import { ref, onMounted } from "vue";
import { getTheme, setTheme } from "./theme";

const emit = defineEmits(["open"]);

const recents = ref([]); // 最近会话
const byCwd = ref([]); // 按 cwd 聚合
const search = ref("");
const theme = ref(getTheme());
const showTheme = ref(false);

function pickTheme(t) {
  theme.value = t;
  setTheme(t);
  showTheme.value = false;
}

async function load() {
  const r = await fetch("/api/sessions");
  const all = await r.json();
  recents.value = all.slice(0, 8);
  const groups = new Map();
  for (const s of all) {
    if (!groups.has(s.cwd)) groups.set(s.cwd, []);
    groups.get(s.cwd).push(s);
  }
  byCwd.value = [...groups.entries()].map(([cwd, items]) => ({
    cwd,
    short: cwd.split("/").slice(-2).join("/"),
    items,
    total: items.reduce((n, s) => n + s.message_count, 0),
  }));
}

function open(id) {
  emit("open", id);
}

onMounted(load);
defineExpose({ load });
</script>

<template>
  <aside class="nav">
    <div class="brand">agent-duet</div>

    <button class="new" @click="$emit('create')">＋ 新会话</button>

    <div class="section">
      <div class="title">最近</div>
      <div v-for="s in recents" :key="s.id" class="item" @click="open(s.id)">
        <span class="dot" :data-status="s.status"></span>
        <span class="label">{{ s.title }}</span>
      </div>
    </div>

    <div class="section grow">
      <div class="title">按工作目录</div>
      <details v-for="g in byCwd" :key="g.cwd" class="cwd-group" open>
        <summary>
          <code>{{ g.short }}</code>
          <span class="count">{{ g.items.length }}</span>
        </summary>
        <div v-for="s in g.items" :key="s.id" class="item" @click="open(s.id)">
          <span class="dot" :data-status="s.status"></span>
          <span class="label">{{ s.title }}</span>
        </div>
      </details>
    </div>
    <div class="config">
      <button class="gear" @click="showTheme = !showTheme">⚙ 主题：{{ { light: "浅色", dark: "深色", auto: "跟随系统" }[theme] }}</button>
      <div v-if="showTheme" class="theme-pop">
        <button v-for="t in ['light', 'dark', 'auto']" :key="t" :class="{ active: theme === t }" @click="pickTheme(t)">
          {{ { light: "☀️ 浅色", dark: "🌙 深色", auto: "🖥 跟随系统" }[t] }}
        </button>
      </div>
    </div>
  </aside>
</template>

<style scoped>
.config { position: relative; border-top: 1px solid var(--border); padding-top: 10px; }
.gear { width: 100%; text-align: left; padding: 7px 8px; border-radius: 6px; border: none; background: none; color: var(--text-faint); cursor: pointer; font-size: 12px; }
.gear:hover { background: var(--hover); color: var(--text); }
.theme-pop { position: absolute; bottom: 40px; left: 0; right: 0; background: var(--surface); border: 1px solid var(--border); border-radius: 8px; padding: 4px; display: flex; flex-direction: column; gap: 2px; z-index: 5; box-shadow: 0 4px 16px rgb(0 0 0 / 30%); }
.theme-pop button { padding: 7px 8px; border: none; background: none; color: var(--text-dim); cursor: pointer; text-align: left; font-size: 13px; border-radius: 5px; }
.theme-pop button:hover { background: var(--hover); }
.theme-pop button.active { color: var(--text); font-weight: 700; }
.nav { width: 240px; flex-shrink: 0; border-right: 1px solid var(--border); display: flex; flex-direction: column; padding: 14px 10px; gap: 12px; overflow-y: auto; }
.brand { font-weight: 700; font-size: 15px; padding: 0 8px; letter-spacing: .3px; }
.new { padding: 8px; border-radius: 8px; border: 1px solid var(--accent); background: var(--accent); color: #fff; cursor: pointer; font-size: 13px; }
.new:hover { background: var(--accent-hover); }
.section { display: flex; flex-direction: column; gap: 2px; }
.section.grow { flex: 1; }
.title { font-size: 11px; color: var(--text-faint); text-transform: uppercase; letter-spacing: 1px; padding: 4px 8px; }
.item { display: flex; align-items: center; gap: 8px; padding: 6px 8px; border-radius: 6px; cursor: pointer; font-size: 13px; color: var(--text-dim); }
.item:hover { background: var(--hover); color: #fff; }
.dot { width: 7px; height: 7px; border-radius: 50%; background: #455; flex-shrink: 0; }
.dot[data-status="running"] { background: #d9a918; animation: pulse 1s infinite; }
.dot[data-status="error"] { background: #c54444; }
.dot[data-status="done"] { background: #4a9e5c; }
.dot[data-status="cancelled"] { background: #5577aa; }
.label { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.cwd-group summary { display: flex; align-items: center; gap: 6px; padding: 6px 8px; cursor: pointer; font-size: 12px; color: var(--text-dim); list-style: none; }
.cwd-group summary::-webkit-details-marker { display: none; }
.cwd-group summary::before { content: "▸"; color: var(--text-faint); font-size: 10px; }
.cwd-group[open] summary::before { content: "▾"; }
.cwd-group code { font-size: 11px; }
.count { margin-left: auto; font-size: 11px; color: var(--text-faint); background: var(--hover); border-radius: 99px; padding: 0 6px; }
@keyframes pulse { 50% { opacity: .4; } }
</style>
