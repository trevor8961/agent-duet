<script setup>
import { ref } from "vue";

const props = defineProps({
  title: String, // 标题（可含计数，由调用方拼好）
  blockKey: String, // 折叠状态持久化的键
  defaultOpen: { type: Boolean, default: true },
});

// 折叠状态：按 blockKey 全局持久化（ad-blocks），左右栏共用一套记忆
const store = JSON.parse(localStorage.getItem("ad-blocks") || "{}");
const open = ref(props.blockKey in store ? !!store[props.blockKey] : props.defaultOpen);

function toggle() {
  open.value = !open.value;
  store[props.blockKey] = open.value;
  localStorage.setItem("ad-blocks", JSON.stringify(store));
}
</script>

<template>
  <section class="block" :data-open="open">
    <header @click="toggle"><span>{{ title }}</span><i></i></header>
    <div v-show="open" class="block-body"><slot /></div>
  </section>
</template>

<style scoped>
.block { border: 1px solid var(--border); border-radius: 10px; background: var(--panel); overflow: hidden; }
.block header { display: flex; align-items: center; justify-content: space-between; padding: 9px 14px; cursor: pointer; user-select: none; font-size: 15px; font-weight: 700; color: var(--text); letter-spacing: .3px; }
.block header:hover { color: var(--text); }
.block header i { width: 0; height: 0; border-left: 4px solid transparent; border-right: 4px solid transparent; border-top: 5px solid var(--text-faint); transition: transform .15s; flex-shrink: 0; }
.block[data-open="true"] header i { transform: rotate(180deg); }
.block-body { padding: 8px 14px 16px; display: flex; flex-direction: column; gap: 8px; }
</style>
