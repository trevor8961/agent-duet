import { chromium } from "playwright";
const b = await chromium.launch();
const page = await b.newPage({ viewport: { width: 1440, height: 900 } });
await page.goto("http://localhost:5173/#/s/2");
await page.waitForTimeout(1500);
const r = await page.evaluate(() => {
  const out = [];
  for (const block of document.querySelectorAll(".ctx .block")) {
    const title = block.querySelector("header span")?.textContent;
    // 找块内最靠下的真实内容元素（chip/文本行）
    const items = [...block.querySelectorAll(".mode-chip, .kv, .turn, .chg, .cmd, .more, .none, .mode-label")]
      .filter((e) => e.offsetHeight > 0);
    if (!items.length) continue;
    const lowest = Math.max(...items.map((e) => e.getBoundingClientRect().bottom));
    out.push({ title, 内容到块底边: Math.round(block.getBoundingClientRect().bottom - lowest) });
  }
  return out;
});
console.log(JSON.stringify(r, null, 1));
await b.close();
