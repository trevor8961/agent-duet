// 主题状态：light / dark / auto（跟随系统），localStorage 持久化。
// auto 模式监听系统切换实时生效。

const KEY = "agent-duet-theme";

export function getTheme() {
  return localStorage.getItem(KEY) || "auto";
}

function apply() {
  const mode = getTheme();
  const resolved =
    mode === "auto"
      ? window.matchMedia("(prefers-color-scheme: dark)").matches
        ? "dark"
        : "light"
      : mode;
  document.documentElement.dataset.theme = resolved;
}

export function setTheme(mode) {
  localStorage.setItem(KEY, mode);
  apply();
}

export function initTheme() {
  apply();
  window
    .matchMedia("(prefers-color-scheme: dark)")
    .addEventListener("change", () => {
      if (getTheme() === "auto") apply();
    });
}
