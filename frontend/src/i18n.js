// 轻量 i18n：字典 + 响应式语言。设置持久化在 localStorage。
import { reactive } from "vue";

const DICT = {
  zh: {
    newSession: "＋ 新会话",
    searchPh: "搜索会话…", recent: "最近", byCwd: "按工作目录",
    theme: "主题", light: "浅色", dark: "深色", auto: "跟随系统", language: "语言",
    homeTitle: "agent-duet", homeSub: "让 agent 的思考与行动清晰可见，每场会话都有档案。",
    homeHint: "从左侧选择会话，或点「新会话」开始。",
    createSession: "新建会话", topic: "话题（用于检索）", topicPh: "比如：修复登录超时",
    cwdLabel: "工作目录", cwdPh: "/Users/you/project", agent: "Agent", mode: "模式",
    currentMode: "当前",
    modeReadonly: "只读", modePlan: "计划", modeGuided: "引导", modeAutonomous: "自主",
    modeGuidedFull: "引导（逐步确认）", modeAutonomousFull: "自主（放手干）",
    cancel: "取消", start: "开始",
    delete: "删除", confirmDelete: "确认删除",
    basicInfo: "基本信息", topicShort: "话题", cwdShort: "目录", status: "状态",
    linked: "已关联", unlinked: "未关联", git: "Git", branch: "分支", upstream: "远端",
    changes: "变更", filesChanged: "个文件", notGit: "非 git 仓库",
    newFile: "新增", dirtyPrefix: "",
    playbill: "请求", rounds: "轮", noTurns: "还没有轮次", activity: "活动",
    toolCalls: "次工具", noActivity: "尚未动过手",
    intentAsk: "询问", intentExplore: "探索", intentVerify: "验证", intentPlan: "计划", intentImpl: "实施",
    stDone: "完成", stRunning: "进行中", stError: "失败", stCancelled: "已终止", stDenied: "需授权",
    stIncomplete: "未完成", stTerminated: "已终止",
    inputPh: "向 agent 提问…（⌘/Ctrl+Enter 发送）", send: "发送", stop: "■ 停止",
    thinking: "思考过程",
    narration: "过程旁白",
    collapse: "collapse", expand: "expand",
    replied: "Replied:",
    permTitle: "Permission needed", deny: "Deny", allow: "Allow",
    approved: "Approved", deniedVerdict: "Denied", timeout: "Timed out",
    replied: "已回复:",
    permTitle: "需要授权", deny: "拒绝", allow: "批准",
    approved: "已批准", deniedVerdict: "已拒绝", timeout: "超时未响应", retry: "重试", retried: "已重试",
    deniedHint: "权限不足",
    grant: "授权并继续",
    grantPrompt: "继续执行刚才被拒的文件操作", grantedAndRetrying: "已授权（autonomous）重新执行",
    granted: "已授权",
    working: "agent 工作中", emptyFlow: "这个会话还没有内容（可能是发出后即被取消，或尚未提问）",
  },
  en: {
    newSession: "＋ New Session",
    searchPh: "Search sessions…", recent: "Recent", byCwd: "By Directory",
    theme: "Theme", light: "Light", dark: "Dark", auto: "Follow System", language: "Language",
    homeTitle: "agent-duet", homeSub: "Make your agent's thinking and actions visible, with a record for every session.",
    homeHint: "Pick a session from the left, or start a new one.",
    createSession: "New Session", topic: "Topic (for search)", topicPh: "e.g. fix login timeout",
    cwdLabel: "Working Directory", cwdPh: "/Users/you/project", agent: "Agent", mode: "Mode",
    currentMode: "当前",
    modeReadonly: "Readonly", modePlan: "Plan", modeGuided: "Guided", modeAutonomous: "Autonomous",
    modeGuidedFull: "Guided (confirm each step)", modeAutonomousFull: "Autonomous (hands-off)",
    cancel: "Cancel", start: "Start",
    delete: "Delete", confirmDelete: "Confirm",
    basicInfo: "Info", topicShort: "Topic", cwdShort: "Dir", status: "Status",
    linked: "Linked", unlinked: "Not linked", git: "Git", branch: "Branch", upstream: "Remote",
    changes: "Changes", filesChanged: "files", notGit: "Not a git repo",
    newFile: "New", dirtyPrefix: "",
    playbill: "Requests", rounds: "turns", noTurns: "No turns yet", activity: "Activity",
    toolCalls: "tool calls", noActivity: "No tools used yet",
    intentAsk: "Ask", intentExplore: "Explore", intentVerify: "Verify", intentPlan: "Plan", intentImpl: "Implement",
    stDone: "Done", stRunning: "Running", stError: "Failed", stCancelled: "Terminated", stDenied: "Auth needed",
    stIncomplete: "Incomplete", stTerminated: "Terminated",
    inputPh: "Ask the agent… (⌘/Ctrl+Enter to send)", send: "Send", stop: "■ Stop",
    thinking: "Thinking",
    narration: "Narration",
    collapse: "collapse", expand: "expand",
    replied: "Replied:",
    permTitle: "Permission needed", deny: "Deny", allow: "Allow",
    approved: "Approved", deniedVerdict: "Denied", timeout: "Timed out",
    replied: "已回复:",
    permTitle: "需要授权", deny: "拒绝", allow: "批准",
    approved: "已批准", deniedVerdict: "已拒绝", timeout: "超时未响应", retry: "Retry", retried: "Retried",
    deniedHint: "Permission denied",
    grant: "Grant & continue",
    grantPrompt: "Continue the previously rejected file operation", grantedAndRetrying: "Authorized (autonomous), retrying",
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
