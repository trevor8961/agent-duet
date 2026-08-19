<script setup>
import { ref } from "vue";
import { t } from "./i18n";

defineProps({ s: Object });
const emit = defineEmits(["open", "delete"]);

const confirmDelete = ref(null);

function fmtTime(raw) {
  if (!raw) return "";
  const d = new Date(String(raw).replace(" ", "T"));
  if (isNaN(d)) return raw;
  const pad = (n) => String(n).padStart(2, "0");
  const same = d.getFullYear() === new Date().getFullYear();
  const md = `${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
  return same ? md : `${d.getFullYear()}-${md}`;
}
</script>

<template>
  <div class="card" @click="confirmDelete === s.id || emit('open', s.id)">
    <div class="row1">
      <span class="label">{{ s.title }}</span>
      <button v-if="confirmDelete !== s.id" class="del" :title="t('delete')"
        @click.stop="confirmDelete = s.id">🗑</button>
      <div class="del-confirm" v-else @click.stop>
        <button class="yes" @click="emit('delete', s.id)">{{ t('confirmDelete') }}</button>
        <button class="no" @click="confirmDelete = null">{{ t('cancel') }}</button>
      </div>
    </div>
    <div class="row2">
      <span class="dot" :data-status="s.status"></span>
      <span class="mode-chip-sm">{{ s.mode }}</span>
      <span class="git-info"><span class="git-ico">⑂</span>{{ s.branch || "—" }}</span>
    </div>
    <div class="row3">
      <span>{{ fmtTime(s.created_at) }}</span>
      <span>{{ fmtTime(s.updated_at) }}</span>
    </div>
  </div>
</template>

<style scoped>
.card { position: relative; padding: 8px 10px; border-radius: 8px; border: 1px solid var(--border); background: var(--panel); cursor: pointer; display: flex; flex-direction: column; gap: 4px; }
.card:hover { border-color: var(--border-2); }
.card:hover .del { visibility: visible; }
.del { visibility: hidden; flex-shrink: 0; padding: 2px 6px; border: none; background: none; color: var(--text-faint); cursor: pointer; font-size: 14px; border-radius: 4px; }
.del:hover { color: #c54444; background: rgb(197 68 68 / 12%); }
.del-confirm { display: flex; gap: 6px; margin-left: auto; }
.del-confirm .yes { padding: 3px 10px; border-radius: 6px; border: 1px solid #c54444; background: rgb(197 68 68 / 15%); color: #c54444; cursor: pointer; font-size: 14px; }
.del-confirm .no { padding: 3px 10px; border-radius: 6px; border: 1px solid var(--border-2); background: var(--surface); color: var(--text-dim); cursor: pointer; font-size: 14px; }
.row1 { display: flex; align-items: center; gap: 8px; }
.row1 .label { color: var(--text); font-weight: 600; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; flex: 1; }
.row2 { display: flex; align-items: center; gap: 8px; font-size: 14px; }
.mode-chip-sm { color: var(--text-dim); border: 1px solid var(--border-2); padding: 0 8px; border-radius: 99px; }
.git-info { margin-left: auto; color: var(--text-faint); display: inline-flex; gap: 4px; align-items: center; overflow: hidden; text-overflow: ellipsis; }
.git-ico { color: var(--accent); }
.row3 { display: flex; justify-content: space-between; color: var(--text-faint); font-size: 14px; }
.dot { width: 7px; height: 7px; border-radius: 50%; background: #455; flex-shrink: 0; }
.dot[data-status="running"] { background: #d9a918; animation: pulse 1s infinite; }
.dot[data-status="error"], .dot[data-status="denied"] { background: #c54444; }
.dot[data-status="done"] { background: #4a9e5c; }
.dot[data-status="cancelled"] { background: #5577aa; }
@keyframes pulse { 50% { opacity: .4; } }
</style>
