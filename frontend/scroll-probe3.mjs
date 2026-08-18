import { chromium } from "playwright";
const b = await chromium.launch();
// 小视口：22vh = 61px，changes 内容 146px 必然溢出
const page = await b.newPage({ viewport: { width: 1200, height: 280 } });
await page.goto("http://localhost:5173/#/s/2");
await page.waitForTimeout(1500);
const gitBlock = page.locator(".ctx .block", { hasText: "工作区" });
await gitBlock.locator(".chg-toggle").click();
await page.waitForTimeout(200);
const r = await page.evaluate(() => {
  const el = document.querySelector(".changes");
  return { scrollH: el.scrollHeight, clientH: el.clientHeight,
           canScroll: el.scrollHeight > el.clientHeight,
           scrollbarWidth: el.offsetWidth - el.clientWidth };
});
console.log(JSON.stringify(r));
const visible = await page.locator(".changes").screenshot({ path: "/tmp/ad-changes-overflow.png" });
await b.close();
