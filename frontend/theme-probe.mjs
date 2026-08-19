import { chromium } from "playwright";
const b = await chromium.launch();
const page = await b.newPage({ viewport: { width: 1440, height: 900 } });
await page.goto("http://localhost:5173/#/s/2");
await page.waitForTimeout(1800);
// 展开最新的回复
const heads = page.locator(".reply-head");
if (await heads.count()) await heads.last().click();
await page.waitForTimeout(300);
const r = await page.evaluate(() => {
  const card = document.querySelector(".bubble.agent.md");
  if (!card) return { ok: false };
  const cs = getComputedStyle(card);
  const table = card.querySelector("table th");
  const code = card.querySelector("code");
  return { ok: true,
    纸面底色: cs.backgroundColor, 圆角: cs.borderRadius,
    表头有底无竖线: table ? (getComputedStyle(table).borderBottomStyle !== "none" && getComputedStyle(table).borderRightWidth === "0px") : "无表格",
    行内代码底色: code ? getComputedStyle(code).backgroundColor : "无代码",
  };
});
console.log(JSON.stringify(r, null, 1));
await page.screenshot({ path: "/tmp/ad-hekouwang.png" });
await b.close();
