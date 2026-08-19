<script setup>
import { ref, onMounted } from "vue";
import { getTheme, setTheme } from "./theme";
import { t, i18n, setLang } from "./i18n";
import SessionCard from "./SessionCard.vue";
import Block from "./Block.vue";

const emit = defineEmits(["open"]);

const recents = ref([]); // 最近会话
const byCwd = ref([]); // 按 cwd 聚合
const search = ref("");
const theme = ref(getTheme());
const lang = ref(i18n.lang);
const showTheme = ref(false);
const showLang = ref(false);
const confirmDelete = ref(null);

async function remove(id) {
  confirmDelete.value = null;
  await fetch(`/api/sessions/${id}`, { method: "DELETE" });
  load();
}

function pickTheme(t) {
  theme.value = t;
  setTheme(t);
  showTheme.value = false; // 选择即收起
}

function pickLang(l) {
  lang.value = l;
  setLang(l);
  showLang.value = false;
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

    <button class="new" @click="$emit('create')">{{ t("newSession") }}</button>

    <Block :title="t('recent')" block-key="nav-recent">
      <SessionCard v-for="s in recents" :key="s.id" :s="s"
        @open="open" @delete="remove" />
    </Block>

    <Block :title="t('byCwd')" block-key="nav-cwd" class="grow">
      <details v-for="g in byCwd" :key="g.cwd" class="cwd-group" open>
        <summary>
          <code>{{ g.short }}</code>
          <span class="count">{{ g.items.length }}</span>
        </summary>
        <SessionCard v-for="s in g.items" :key="s.id" :s="s"
          @open="open" @delete="remove" />
      </details>
    </Block>
    <div class="config">
      <div class="config-row">
        <button class="gear" @click="showTheme = !showTheme; showLang = false">⚙ {{ t("theme") }}：{{ t(theme) }}</button>
        <div v-if="showTheme" class="pop">
          <button v-for="th in ['light', 'dark', 'auto']" :key="th" :class="{ active: theme === th }" @click="pickTheme(th)">
            {{ { light: "☀️", dark: "🌙", auto: "🖥" }[th] }} {{ t(th) }}
          </button>
        </div>
      </div>
      <div class="config-row">
        <button class="gear" @click="showLang = !showLang; showTheme = false">⚙ {{ t("language") }}：{{ lang === "zh" ? "中文" : "English" }}</button>
        <div v-if="showLang" class="pop">
          <button v-for="l in ['zh', 'en']" :key="l" :class="{ active: lang === l }" @click="pickLang(l)">
            {{ l === "zh" ? "🀄 中文" : "🔤 English" }}
          </button>
        </div>
      </div>
    </div>
  </aside>
</template>

<style scoped>
.config { border-top: 1px solid var(--border); padding-top: 10px; display: flex; flex-direction: column; gap: 2px; }
.config-row { position: relative; }
.gear { width: 100%; text-align: left; padding: 7px 8px; border-radius: 6px; border: none; background: none; color: var(--text-faint); cursor: pointer; font-size: 14px; }
.gear:hover { background: var(--hover); color: var(--text); }
.pop { position: absolute; bottom: 36px; left: 0; right: 0; background: var(--surface); border: 1px solid var(--border); border-radius: 8px; padding: 4px; display: flex; flex-direction: column; gap: 2px; z-index: 5; box-shadow: 0 4px 16px rgb(0 0 0 / 30%); }
.pop button { padding: 7px 8px; border: none; background: none; color: var(--text-dim); cursor: pointer; text-align: left; font-size: 14px; border-radius: 5px; }
.pop button:hover { background: var(--hover); }
.pop button.active { color: var(--text); font-weight: 700; }
.nav { width: 100%; flex-shrink: 0; border-right: 1px solid var(--border); display: flex; flex-direction: column; padding: 14px 10px; gap: 12px; overflow-y: auto; }
.brand { font-weight: 700; font-size: 17px; padding: 0 8px; letter-spacing: .3px; }
.new { padding: 8px; border-radius: 8px; border: 1px solid var(--accent); background: var(--accent); color: #fff; cursor: pointer; font-size: 14px; }
.new:hover { background: var(--accent-hover); }
.section { display: flex; flex-direction: column; gap: 2px; }
.section.grow { flex: 1; }
.title { font-size: 14px; font-weight: 600; color: var(--text-faint); text-transform: uppercase; letter-spacing: 1px; padding: 4px 8px; }
</style>
