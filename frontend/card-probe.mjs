import { chromium } from "playwright";
const b = await chromium.launch();
const page = await b.newPage({ viewport: { width: 1440, height: 900 } });
await page.goto("http://localhost:5173/");
await page.waitForTimeout(1500);
const r = await page.evaluate(() => {
  const card = document.querySelector(".nav .card");
  if (!card) return { ok: false };
  const del = card.querySelector(".del");
  return { ok: true,
    行1: card.querySelector(".row1")?.innerText.replace(/\n/g, " | "),
    行2: card.querySelector(".row2")?.innerText.replace(/\n/g, " "),
    删除按钮存在: !!del,
    删除默认隐藏: del && getComputedStyle(del).display === "none",
    卡片边框: getComputedStyle(card).borderRadius };
});
console.log(JSON.stringify(r, null, 1));
await page.screenshot({ path: "/tmp/ad-card.png", clip: { x: 0, y: 0, width: 260, height: 400 } });
await b.close();
