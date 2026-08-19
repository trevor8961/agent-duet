<script setup>
import { ref } from "vue";
import { getTheme, setTheme } from "./theme";
import { t, i18n, setLang } from "./i18n";

const theme = ref(getTheme());
const lang = ref(i18n.lang);
const showTheme = ref(false);
const showLang = ref(false);

const REPO = { owner: "trevor8961", name: "agent-duet" };

function pickTheme(t) {
  theme.value = t;
  setTheme(t);
  showTheme.value = false;
}

function pickLang(l) {
  lang.value = l;
  setLang(l);
  showLang.value = false;
}
</script>

<template>
  <header class="topnav">
    <div class="left">
      <span class="logo">🎼</span>
      <span class="app-name">agent-duet</span>
      <a class="repo" :href="`https://github.com/${REPO.owner}/${REPO.name}`"
        target="_blank" rel="noopener" :title="`github.com/${REPO.owner}/${REPO.name}`">
        ⑂ {{ REPO.owner }}/{{ REPO.name }}
      </a>
    </div>

    <div class="right">
      <div class="setting">
        <button class="set-btn" @click="showTheme = !showTheme; showLang = false">
          {{ { light: "☀️", dark: "🌙", auto: "🖥" }[theme] }} {{ t("theme") }}
        </button>
        <div v-if="showTheme" class="pop">
          <button v-for="th in ['light', 'dark', 'auto']" :key="th" :class="{ active: theme === th }" @click="pickTheme(th)">
            {{ { light: "☀️", dark: "🌙", auto: "🖥" }[th] }} {{ t(th) }}
          </button>
        </div>
      </div>
      <div class="setting">
        <button class="set-btn" @click="showLang = !showLang; showTheme = false">
          🌐 {{ lang === "zh" ? "中文" : "English" }}
        </button>
        <div v-if="showLang" class="pop">
          <button v-for="l in ['zh', 'en']" :key="l" :class="{ active: lang === l }" @click="pickLang(l)">
            {{ l === "zh" ? "🀄 中文" : "🔤 English" }}
          </button>
        </div>
      </div>
    </div>
  </header>
</template>

<style scoped>
.topnav { display: flex; align-items: center; justify-content: space-between;
  height: 48px; padding: 0 14px; border-bottom: 1px solid var(--border);
  background: var(--panel); flex-shrink: 0; }
.left { display: flex; align-items: baseline; gap: 12px; min-width: 0; }
.logo { font-size: 16px; }
.app-name { font-weight: 700; font-size: 16px; color: var(--text); letter-spacing: .3px; }
.repo { color: var(--text-dim); font-size: 14px; text-decoration: none; font-family: ui-monospace, Menlo, monospace; }
.repo:hover { color: var(--accent); text-decoration: underline; }
.right { display: flex; align-items: center; gap: 8px; }
.setting { position: relative; }
.set-btn { padding: 5px 12px; border-radius: 6px; border: 1px solid var(--border);
  background: none; color: var(--text-dim); cursor: pointer; font-size: 14px; }
.set-btn:hover { color: var(--text); border-color: var(--border-2); }
.pop { position: absolute; top: 38px; right: 0; background: var(--surface);
  border: 1px solid var(--border); border-radius: 8px; padding: 4px; z-index: 20;
  display: flex; flex-direction: column; gap: 2px; box-shadow: 0 6px 20px rgb(0 0 0 / 35%); min-width: 130px; }
.pop button { padding: 7px 10px; border: none; background: none; color: var(--text-dim);
  cursor: pointer; text-align: left; font-size: 14px; border-radius: 5px; white-space: nowrap; }
.pop button:hover { background: var(--hover); }
.pop button.active { color: var(--text); font-weight: 700; }
</style>
