// 轻量 i18n：字典 + 响应式语言。设置持久化在 localStorage。
import { reactive } from "vue";

const DICT = {
  zh: {
    newSession: "＋ 新会话", recent: "最近", byCwd: "按工作目录",
    theme: "主题", light: "浅色", dark: "深色", auto: "跟随系统", language: "语言",
    homeTitle: "agent-duet", homeSub: "你和 agent 的二重唱 —— 主旋律与低声部分明，每场演出都有档案。",
    homeHint: "从左侧选择会话，或点「新会话」开始。",
    createSession: "新建会话", topic: "话题（用于检索）", topicPh: "比如：修复登录超时",
    cwdLabel: "工作目录", cwdPh: "/Users/you/project", agent: "Agent", mode: "模式",
    currentMode: "Current",
    modeReadonly: "只读", modePlan: "计划", modeGuided: "引导", modeAutonomous: "自主",
    modeGuidedFull: "引导（逐步确认）", modeAutonomousFull: "自主（放手干）",
    cancel: "取消", start: "开始",
    delete: "删除", confirmDelete: "确认删除",
    basicInfo: "基本信息", topicShort: "话题", cwdShort: "目录", status: "状态",
    linked: "已关联", unlinked: "未关联", workspace: "工作区", branch: "分支", upstream: "远端",
    changes: "变更", filesChanged: "个文件", notGit: "非 git 仓库", dirtyPrefix: "",
    playbill: "节目单", rounds: "轮", noTurns: "还没有轮次", activity: "活动",
    toolCalls: "次工具", noActivity: "尚未动过手",
    intentAsk: "询问", intentExplore: "探索", intentVerify: "验证", intentPlan: "计划", intentImpl: "实施",
    stDone: "完成", stRunning: "进行中", stError: "失败", stCancelled: "已取消", stDenied: "需授权",
    inputPh: "向 agent 提问…（⌘/Ctrl+Enter 发送）", send: "发送", stop: "■ 停止",
    thinking: "低声部（思考）",
    narration: "过程旁白",
    backToTop: "回到开头",
    collapse: "collapse", expand: "expand",
    replied: "Replied:",
    replied: "已回复:", retry: "重试", retried: "已重试",
    deniedHint: "权限不足",
    grant: "授权并继续",
    granted: "已授权",
    working: "agent 工作中", emptyFlow: "这个会话还没有内容（可能是发出后即被取消，或尚未提问）",
  },
  en: {
    newSession: "＋ New Session", recent: "Recent", byCwd: "By Directory",
    theme: "Theme", light: "Light", dark: "Dark", auto: "Follow System", language: "Language",
    homeTitle: "agent-duet", homeSub: "A duet between you and your agent — melody and murmur, separated.",
    homeHint: "Pick a session from the left, or start a new one.",
    createSession: "New Session", topic: "Topic (for search)", topicPh: "e.g. fix login timeout",
    cwdLabel: "Working Directory", cwdPh: "/Users/you/project", agent: "Agent", mode: "Mode",
    currentMode: "Current",
    modeReadonly: "Readonly", modePlan: "Plan", modeGuided: "Guided", modeAutonomous: "Autonomous",
    modeGuidedFull: "Guided (confirm each step)", modeAutonomousFull: "Autonomous (hands-off)",
    cancel: "Cancel", start: "Start",
    delete: "Delete", confirmDelete: "Confirm",
    basicInfo: "Info", topicShort: "Topic", cwdShort: "Dir", status: "Status",
    linked: "Linked", unlinked: "Not linked", workspace: "Workspace", branch: "Branch", upstream: "Remote",
    changes: "Changes", filesChanged: "files", notGit: "Not a git repo", dirtyPrefix: "",
    playbill: "Playbill", rounds: "turns", noTurns: "No turns yet", activity: "Activity",
    toolCalls: "tool calls", noActivity: "No tools used yet",
    intentAsk: "Ask", intentExplore: "Explore", intentVerify: "Verify", intentPlan: "Plan", intentImpl: "Implement",
    stDone: "Done", stRunning: "Running", stError: "Failed", stCancelled: "Cancelled", stDenied: "Auth needed",
    inputPh: "Ask the agent… (⌘/Ctrl+Enter to send)", send: "Send", stop: "■ Stop",
    thinking: "Murmur (thinking)",
    narration: "Narration",
    backToTop: "Back to top",
    collapse: "collapse", expand: "expand",
    replied: "Replied:",
    replied: "已回复:", retry: "Retry", retried: "Retried",
    deniedHint: "Permission denied",
    grant: "Grant & continue",
    granted: "Granted",
    working: "agent working", emptyFlow: "Nothing here yet (cancelled before output, or no question asked)",
  },
};

export const i18n = reactive({ lang: localStorage.getItem("ad-lang") || "zh" });

export function setLang(lang) {
  i18n.lang = lang;
  localStorage.setItem("ad-lang", lang);
}

export function t(key) {
  return (DICT[i18n.lang] ?? DICT.zh)[key] ?? key;
}

export function intentLabel(v) {
  return { 询问: t("intentAsk"), 探索: t("intentExplore"), 验证: t("intentVerify"),
           计划: t("intentPlan"), 实施: t("intentImpl") }[v] ?? v;
}
