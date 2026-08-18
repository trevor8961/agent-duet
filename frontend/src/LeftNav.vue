<script setup>
import { ref, onMounted } from "vue";

const emit = defineEmits(["open"]);

const recents = ref([]); // 最近会话
const byCwd = ref([]); // 按 cwd 聚合
const search = ref("");

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
  </aside>
</template>

<style scoped>
.nav { width: 240px; flex-shrink: 0; border-right: 1px solid #222; display: flex; flex-direction: column; padding: 14px 10px; gap: 12px; overflow-y: auto; }
.brand { font-weight: 700; font-size: 15px; padding: 0 8px; letter-spacing: .3px; }
.new { padding: 8px; border-radius: 8px; border: 1px solid #2b6cb0; background: #2b6cb0; color: #fff; cursor: pointer; font-size: 13px; }
.new:hover { background: #3681cf; }
.section { display: flex; flex-direction: column; gap: 2px; }
.section.grow { flex: 1; }
.title { font-size: 11px; color: #666; text-transform: uppercase; letter-spacing: 1px; padding: 4px 8px; }
.item { display: flex; align-items: center; gap: 8px; padding: 6px 8px; border-radius: 6px; cursor: pointer; font-size: 13px; color: #bbb; }
.item:hover { background: #1a1a1a; color: #fff; }
.dot { width: 7px; height: 7px; border-radius: 50%; background: #455; flex-shrink: 0; }
.dot[data-status="running"] { background: #d9a918; animation: pulse 1s infinite; }
.dot[data-status="error"] { background: #c54444; }
.dot[data-status="done"] { background: #4a9e5c; }
.dot[data-status="cancelled"] { background: #5577aa; }
.label { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.cwd-group summary { display: flex; align-items: center; gap: 6px; padding: 6px 8px; cursor: pointer; font-size: 12px; color: #888; list-style: none; }
.cwd-group summary::-webkit-details-marker { display: none; }
.cwd-group summary::before { content: "▸"; color: #555; font-size: 10px; }
.cwd-group[open] summary::before { content: "▾"; }
.cwd-group code { font-size: 11px; }
.count { margin-left: auto; font-size: 11px; color: #555; background: #1a1a1a; border-radius: 99px; padding: 0 6px; }
@keyframes pulse { 50% { opacity: .4; } }
</style>
