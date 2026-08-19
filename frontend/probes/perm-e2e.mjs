import { chromium } from "playwright";
const b = await chromium.launch();
const page = await b.newPage({ viewport: { width: 1440, height: 900 } });
page.on("pageerror", (e) => console.log("PAGE ERR:", e.message.slice(0, 150)));
await page.goto("http://localhost:5173/");
await page.waitForTimeout(1500);
// 新建会话
await page.click(".nav .new");
await page.waitForTimeout(300);
await page.fill(".modal-box input[placeholder*='login'], .modal-box label input", "perm-e2e");
await page.evaluate(() => {
  const inputs = document.querySelectorAll(".modal-box input");
  inputs[0].value = "perm-e2e-验证";
  inputs[1].value = "/tmp/agent-duet-test";
  const ev = new Event("input", { bubbles: true });
  inputs[0].dispatchEvent(ev); inputs[1].dispatchEvent(ev);
});
await page.waitForTimeout(200);
// 点开始（disabled 状态由 v-model 决定，直接 evaluate 提交更稳）
await page.evaluate(async () => {
  const r = await fetch("/api/sessions", { method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title: "perm-e2e-验证", cwd: "/tmp/agent-duet-test", agent_id: 1, mode: "guided" }) });
  const s = await r.json();
  location.hash = "#/s/" + s.id;
  // 关闭新建弹窗
  document.querySelector(".modal .actions button")?.click();
});
await page.waitForTimeout(2000);
await page.fill("textarea", "创建 /tmp/agent-duet-test/perm-ui.txt 文件");
await page.click("footer button.primary");
// 等待权限卡片出现（最多 40s）
let card = null;
for (let i = 0; i < 20; i++) {
  await page.waitForTimeout(2000);
  card = await page.evaluate(() => {
    const c = document.querySelector(".perm-card");
    return c ? { title: c.querySelector(".perm-title")?.textContent, tool: c.querySelector(".perm-tool code")?.textContent } : null;
  });
  if (card) break;
}
console.log("权限卡片:", JSON.stringify(card));
if (card) {
  await page.click(".perm-allow");
  await page.waitForTimeout(3000);
  const cards = await page.evaluate(() => document.querySelectorAll(".perm-card").length);
  console.log("点批准后剩余卡片:", cards);
}
await b.close();
