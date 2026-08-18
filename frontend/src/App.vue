<script setup>
import { ref, onMounted } from "vue";
import LeftNav from "./LeftNav.vue";
import SessionDetail from "./SessionDetail.vue";
import ContextPanel from "./ContextPanel.vue";
import { t } from "./i18n";

const currentId = ref(null);
const detail = ref(null);
const showCreate = ref(false);
const agents = ref([]);
const form = ref({ title: "", cwd: "", agent_id: null, mode: "guided" });
const leftNav = ref(null);

// 右栏宽度：可拖拽，持久化，上限为视口 1/3
const ctxWidth = ref(Math.min(Number(localStorage.getItem("ad-ctx-width")) || 300, Math.floor(window.innerWidth / 3)));
const dragging = ref(false);

function startDrag(e) {
  dragging.value = true;
  const max = Math.floor(window.innerWidth / 3);
  const onMove = (ev) => {
    ctxWidth.value = Math.min(max, Math.max(240, window.innerWidth - ev.clientX));
  };
  const onUp = () => {
    dragging.value = false;
    localStorage.setItem("ad-ctx-width", String(ctxWidth.value));
    window.removeEventListener("mousemove", onMove);
    window.removeEventListener("mouseup", onUp);
  };
  window.addEventListener("mousemove", onMove);
  window.addEventListener("mouseup", onUp);
  e.preventDefault();
}

const MODES = [
  { value: "readonly", key: "modeReadonly" },
  { value: "plan", key: "modePlan" },
  { value: "guided", key: "modeGuidedFull" },
  { value: "autonomous", key: "modeAutonomousFull" },
];

function syncRoute() {
  const m = location.hash.match(/^#\/s\/(\d+)/);
  currentId.value = m ? Number(m[1]) : null;
  detail.value = null;
  leftNav.value?.load();
}
window.addEventListener("hashchange", syncRoute);

function openSession(id) {
  location.hash = `#/s/${id}`;
}

function goHome() {
  location.hash = "";
}

function onLoaded(d) {
  detail.value = d;
}

async function createSession() {
  const r = await fetch("/api/sessions", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(form.value),
  });
  if (r.ok) {
    showCreate.value = false;
    const s = await r.json();
    location.hash = `#/s/${s.id}`;
  }
}

onMounted(async () => {
  syncRoute();
  agents.value = await (await fetch("/api/agents")).json();
  if (agents.value.length) form.value.agent_id = agents.value[0].id;
});
</script>

<template>
  <div class="shell">
    <LeftNav ref="leftNav" @open="openSession" @create="showCreate = true" />

    <main class="center">
      <SessionDetail v-if="currentId" :id="currentId" @loaded="onLoaded" />
      <div v-else class="home">
        <h1>agent-duet</h1>
        <p class="sub">{{ t("homeSub") }}</p>
        <p class="hint">{{ t("homeHint") }}</p>
      </div>
    </main>

    <template v-if="currentId">
      <div class="divider" :class="{ dragging }" @mousedown="startDrag" title="拖拽调整宽度"></div>
      <ContextPanel :id="currentId" :detail="detail" :style="{ width: ctxWidth + 'px' }" />
    </template>

    <div v-if="showCreate" class="modal" @click.self="showCreate = false">
      <div class="modal-box">
        <h2>{{ t("createSession") }}</h2>
        <label>{{ t("topic") }}<input v-model="form.title" :placeholder="t('topicPh')" /></label>
        <label>{{ t("cwdLabel") }}<input v-model="form.cwd" :placeholder="t('cwdPh')" /></label>
        <label>{{ t("agent") }}
          <select v-model="form.agent_id">
            <option v-for="a in agents" :key="a.id" :value="a.id">{{ a.name }}</option>
          </select>
        </label>
        <label>{{ t("mode") }}
          <select v-model="form.mode">
            <option v-for="m in MODES" :key="m.value" :value="m.value">{{ t(m.key) }}</option>
          </select>
        </label>
        <div class="actions">
          <button @click="showCreate = false">{{ t("cancel") }}</button>
          <button class="primary" @click="createSession" :disabled="!form.title || !form.cwd">{{ t("start") }}</button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.shell { display: flex; height: 100vh; overflow: hidden; }
.divider { width: 4px; cursor: col-resize; background: transparent; flex-shrink: 0; transition: background .15s; }
.divider:hover, .divider.dragging { background: var(--accent); }
.center { flex: 1; min-width: 0; display: flex; }
.home { margin: auto; text-align: center; color: var(--text-faint); }
.home h1 { color: var(--text); margin-bottom: 8px; }
.hint { font-size: 13px; color: var(--text-faint); }
.modal { position: fixed; inset: 0; background: rgba(0,0,0,.6); display: flex; align-items: center; justify-content: center; z-index: 10; }
.modal-box { background: var(--surface); border: 1px solid var(--border-2); border-radius: 12px; padding: 20px; width: 420px; display: flex; flex-direction: column; gap: 12px; }
.modal-box h2 { margin: 0 0 4px; font-size: 16px; }
label { display: flex; flex-direction: column; gap: 4px; font-size: 13px; color: var(--text-dim); }
label input, label select { padding: 8px; border-radius: 6px; border: 1px solid var(--border-2); background: var(--panel); color: var(--text); }
.actions { display: flex; justify-content: flex-end; gap: 8px; }
button { padding: 6px 14px; border-radius: 6px; border: 1px solid var(--border-2); background: var(--border); color: var(--text); cursor: pointer; }
button.primary { background: var(--accent); border-color: var(--accent); color: #fff; }
button:disabled { opacity: .5; }
</style>
