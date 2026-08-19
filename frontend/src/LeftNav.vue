<script setup>
import { ref, onMounted } from "vue";
import { t } from "./i18n";
import SessionCard from "./SessionCard.vue";
import Block from "./Block.vue";

const props = defineProps({ activeId: Number });
const emit = defineEmits(["open"]);

const search = ref(""); // 按 title 搜索
const recents = ref([]); // 最近会话
const byCwd = ref([]); // 按 cwd 聚合
const confirmDelete = ref(null);

async function remove(id) {
  confirmDelete.value = null;
  await fetch(`/api/sessions/${id}`, { method: "DELETE" });
  load();
}

async function load() {
  const r = await fetch("/api/sessions");
  const all = await r.json();
  const kw = search.value.trim().toLowerCase();
  const matched = kw ? all.filter((s) => (s.title || "").toLowerCase().includes(kw)) : all;
  recents.value = matched.slice(0, 8);
  const groups = new Map();
  for (const s of matched) {
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
    <input v-model="search" class="search" :placeholder="t('searchPh')" @input="load" />

    <Block :title="t('recent')" block-key="nav-recent">
      <SessionCard v-for="s in recents" :key="s.id" :s="s" :active="s.id === props.activeId"
        @open="open" @delete="remove" />
    </Block>

    <Block :title="t('byCwd')" block-key="nav-cwd">
      <details v-for="g in byCwd" :key="g.cwd" class="cwd-group" open>
        <summary>
          <code>{{ g.short }}</code>
          <span class="count">{{ g.items.length }}</span>
        </summary>
        <SessionCard v-for="s in g.items" :key="s.id" :s="s" :active="s.id === props.activeId"
          @open="open" @delete="remove" />
      </details>
    </Block>

    <button class="new" @click="$emit('create')">{{ t("newSession") }}</button>
  </aside>
</template>

<style scoped>
.nav { width: 100%; flex-shrink: 0; border-right: 1px solid var(--border);
  display: flex; flex-direction: column; padding: 12px 10px; gap: 10px;
  height: 100%; min-height: 0; overflow: hidden; }
.search { flex-shrink: 0; padding: 8px 12px; border-radius: 8px; border: 1px solid var(--border-2);
  background: var(--input-bg); color: var(--text); font-size: 14px; outline: none; }
.search:focus { border-color: var(--accent); }
.search::placeholder { color: var(--text-faint); }
.new { padding: 8px; border-radius: 8px; border: 1px solid var(--accent);
  background: var(--accent); color: #fff; cursor: pointer; font-size: 14px; flex-shrink: 0; }
.new:hover { background: var(--accent-hover); }

/* widget 折叠时按内容（只剩标题栏）收缩，展开时占用剩余高度；
   都展开则平分，各自内部滚动（滚动作用域限于 widget 内部） */
.nav :deep(.block) { display: flex; flex-direction: column; overflow: hidden; min-height: 0; }
.nav :deep(.block[data-open="false"]) { flex: 0 0 auto; }
.nav :deep(.block[data-open="true"]) { flex: 1 1 0; }
.nav :deep(.block-body) { flex: 1; min-height: 0; overflow-y: auto; }

.cwd-group summary { display: flex; align-items: center; gap: 6px; padding: 6px 8px;
  cursor: pointer; font-size: 14px; color: var(--text-dim); list-style: none; }
.cwd-group summary::-webkit-details-marker { display: none; }
.cwd-group summary::before { content: "▸"; color: var(--text-faint); font-size: 12px; }
.cwd-group[open] summary::before { content: "▾"; }
.cwd-group code { font-size: 13px; }
.count { margin-left: auto; font-size: 13px; color: var(--text-faint);
  background: var(--hover); border-radius: 99px; padding: 0 6px; }
</style>
