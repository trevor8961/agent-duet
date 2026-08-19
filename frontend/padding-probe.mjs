import { chromium } from "playwright";
const b = await chromium.launch();
const page = await b.newPage({ viewport: { width: 1440, height: 900 } });
await page.goto("http://localhost:5173/#/s/2");
await page.waitForTimeout(1500);
const r = await page.evaluate(() => {
  const out = [];
  for (const block of document.querySelectorAll(".ctx .block")) {
    const title = block.querySelector("header span")?.textContent;
    const body = block.querySelector(".body");
    if (!body || body.offsetHeight === 0) continue;
    const br = block.getBoundingClientRect();
    const bodyR = body.getBoundingClientRect();
    out.push({
      title,
      内容底边距块底边: Math.round(br.bottom - bodyR.bottom),
      bodyPaddingBottom: getComputedStyle(body).paddingBottom,
    });
  }
  return out;
});
console.log(JSON.stringify(r, null, 1));
await page.screenshot({ path: "/tmp/ad-padding.png", clip: { x: 900, y: 0, width: 540, height: 400 } });
await b.close();
