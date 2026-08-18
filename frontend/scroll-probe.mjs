// 探针：右栏滚动区的真实布局状态
import { chromium } from "playwright";

const b = await chromium.launch();
const page = await b.newPage({ viewport: { width: 1440, height: 900 } });
await page.goto("http://localhost:5173/#/s/2");
await page.waitForTimeout(1500);

const report = await page.evaluate(() => {
  const out = [];
  for (const el of document.querySelectorAll(".ctx .block")) {
    const title = el.querySelector("header span")?.textContent;
    const body = el.querySelector(".body, .modes, .mode-select");
    const r = { title, blockH: el.offsetHeight, bodyH: body?.offsetHeight };
    if (body) {
      r.scrollH = body.scrollHeight;
      r.clientH = body.clientHeight;
      r.overflowY = getComputedStyle(body).overflowY;
      r.maxHeight = getComputedStyle(body).maxHeight;
      r.cls = body.className;
    }
    out.push(r);
  }
  const ctx = document.querySelector(".ctx");
  return { blocks: out, ctx: ctx ? { scrollH: ctx.scrollHeight, clientH: ctx.clientHeight, overflow: getComputedStyle(ctx).overflowY } : null };
});
console.log(JSON.stringify(report, null, 1));
await page.screenshot({ path: "/tmp/ad-probe.png", fullPage: false });
await b.close();
