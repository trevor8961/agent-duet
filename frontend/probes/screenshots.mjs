import { chromium } from "playwright";
const b = await chromium.launch();
const page = await b.newPage({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2 });

// 浅色主题
await page.goto("http://localhost:5173/");
await page.waitForTimeout(1500);
await page.evaluate(() => { localStorage.setItem("agent-duet-theme", "light"); });
await page.reload();
await page.waitForTimeout(1800);

// 1) 首页/列表视图
await page.screenshot({ path: "../docs/images/home.png" });

// 2) 会话详情（用户真实测试）
await page.goto("http://localhost:5173/#/s/2");
await page.waitForTimeout(2500);
await page.screenshot({ path: "../docs/images/session.png" });

// 3) 展开一个幕后块 + 回复纸卡（内容更丰富）
await page.evaluate(() => {
  const bs = [...document.querySelectorAll(".backstage")].find((x) => x.querySelector("summary")?.textContent.includes("💭"));
  if (bs && !bs.open) bs.querySelector("summary").click();
  const replies = document.querySelectorAll(".reply-card");
  if (replies.length) { /* 最新默认展开 */ }
});
await page.waitForTimeout(400);
await page.screenshot({ path: "../docs/images/session-detail.png" });

console.log("screenshots done");
await b.close();
