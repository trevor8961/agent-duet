<script setup>
import { ref, onMounted } from "vue";
import SessionDetail from "./SessionDetail.vue";

const currentId = ref(null);

function syncRoute() {
  const m = location.hash.match(/^#\/s\/(\d+)/);
  currentId.value = m ? Number(m[1]) : null;
  if (!currentId.value) loadSessions();
}
window.addEventListener("hashchange", syncRoute);

const API = "/api";

const sessions = ref([]);
const agents = ref([]);
const search = ref("");
const showCreate = ref(false);
const form = ref({ title: "", cwd: "", agent_id: null, mode: "guided" });

const MODES = [
  { value: "readonly", label: "只读" },
  { value: "plan", label: "计划" },
  { value: "guided", label: "引导（逐步确认）" },
  { value: "autonomous", label: "自主（放手干）" },
];

async function loadSessions() {
  const q = search.value ? `?q=${encodeURIComponent(search.value)}` : "";
  const r = await fetch(`${API}/sessions${q}`);
  sessions.value = await r.json();
}

async function createSession() {
  const r = await fetch(`${API}/sessions`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(form.value),
  });
  if (r.ok) {
    showCreate.value = false;
    await loadSessions();
    const s = await r.json();
    openSession(s.id);
  }
}

function openSession(id) {
  location.hash = `#/s/${id}`;
}

onMounted(async () => {
  syncRoute();
  agents.value = await (await fetch(`${API}/agents`)).json();
  if (agents.value.length) form.value.agent_id = agents.value[0].id;
  await loadSessions();
});
</script>

<template>
  <SessionDetail v-if="currentId" :id="currentId" @back="location.hash = '#'" />
  <div class="wrap" v-else>
    <header>
      <h1>agent-duet</h1>
      <span class="sub">你和 agent 的二重唱</span>
      <button class="primary" @click="showCreate = true">＋ 新会话</button>
    </header>

    <div class="toolbar">
      <input v-model="search" placeholder="搜索话题 / 目录…" @input="loadSessions" />
    </div>

    <div class="list">
      <div v-for="s in sessions" :key="s.id" class="card" @click="openSession(s.id)">
        <div class="card-head">
          <strong>{{ s.title }}</strong>
          <span class="badge" :data-status="s.status">{{ s.status }}</span>
        </div>
        <div class="meta">
          <code>{{ s.cwd }}</code>
          <span>· {{ s.mode }}</span>
          <span>· {{ s.message_count }} 条</span>
        </div>
        <div class="preview">{{ s.last_preview || "（还没有回复）" }}</div>
      </div>
      <div v-if="!sessions.length" class="empty">还没有会话，点「新会话」开始第一场合唱</div>
    </div>

    <div v-if="showCreate" class="modal" @click.self="showCreate = false">
      <div class="modal-box">
        <h2>新建会话</h2>
        <label>话题（用于检索）<input v-model="form.title" placeholder="比如：修复登录超时" /></label>
        <label>工作目录<input v-model="form.cwd" placeholder="/Users/you/project" /></label>
        <label>Agent
          <select v-model="form.agent_id">
            <option v-for="a in agents" :key="a.id" :value="a.id">{{ a.name }}</option>
          </select>
        </label>
        <label>模式
          <select v-model="form.mode">
            <option v-for="m in MODES" :key="m.value" :value="m.value">{{ m.label }}</option>
          </select>
        </label>
        <div class="actions">
          <button @click="showCreate = false">取消</button>
          <button class="primary" @click="createSession" :disabled="!form.title || !form.cwd">开始</button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.wrap { max-width: 760px; margin: 0 auto; padding: 24px 16px; }
header { display: flex; align-items: baseline; gap: 12px; margin-bottom: 16px; }
header h1 { font-size: 22px; margin: 0; }
.sub { color: #888; flex: 1; }
.toolbar input { width: 100%; padding: 8px 12px; border-radius: 8px; border: 1px solid #333; background: #1a1a1a; color: #eee; }
.list { display: flex; flex-direction: column; gap: 10px; margin-top: 14px; }
.card { border: 1px solid #2a2a2a; border-radius: 10px; padding: 12px 14px; cursor: pointer; background: #141414; }
.card:hover { border-color: #4a9eff; }
.card-head { display: flex; justify-content: space-between; align-items: center; }
.badge { font-size: 12px; padding: 2px 8px; border-radius: 99px; background: #263; color: #9f9; }
.badge[data-status="running"] { background: #441; color: #ff9; }
.badge[data-status="error"] { background: #411; color: #f99; }
.badge[data-status="cancelled"] { background: #234; color: #99f; }
.meta { color: #777; font-size: 12px; margin: 6px 0 4px; display: flex; gap: 6px; flex-wrap: wrap; }
.preview { color: #aaa; font-size: 13px; }
.empty { color: #666; text-align: center; padding: 40px; }
.modal { position: fixed; inset: 0; background: rgba(0,0,0,.6); display: flex; align-items: center; justify-content: center; }
.modal-box { background: #181818; border: 1px solid #333; border-radius: 12px; padding: 20px; width: 420px; display: flex; flex-direction: column; gap: 12px; }
.modal-box h2 { margin: 0 0 4px; font-size: 16px; }
label { display: flex; flex-direction: column; gap: 4px; font-size: 13px; color: #999; }
label input, label select { padding: 8px; border-radius: 6px; border: 1px solid #333; background: #111; color: #eee; }
.actions { display: flex; justify-content: flex-end; gap: 8px; }
button { padding: 6px 14px; border-radius: 6px; border: 1px solid #333; background: #222; color: #ddd; cursor: pointer; }
button.primary { background: #2b6cb0; border-color: #2b6cb0; color: #fff; }
button:disabled { opacity: .5; }
</style>
