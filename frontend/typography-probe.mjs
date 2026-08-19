// 验收探针：全站可见文本的字号下限必须 ≥14px
import { chromium } from "playwright";
const b = await chromium.launch();
const page = await b.newPage({ viewport: { width: 1440, height: 900 } });
await page.goto("http://localhost:5173/#/s/2");
await page.waitForTimeout(1500);
// 展开全部折叠块，覆盖更多文本
for (const h of await page.locator(".ctx .block header").all()) await h.click().catch(() => {});
const gitBlock = page.locator(".ctx .block", { hasText: "工作区" });
await gitBlock.locator(".chg-toggle").click().catch(() => {});
await page.waitForTimeout(300);

const r = await page.evaluate(() => {
  const sizes = [];
  for (const el of document.querySelectorAll("body *")) {
    if (!el.textContent.trim() || el.children.length > 0) continue;
    const cs = getComputedStyle(el);
    if (cs.display === "none" || cs.visibility === "hidden") continue;
    sizes.push({ size: +cs.fontSize.slice(0, -2), sample: el.textContent.trim().slice(0, 14) });
  }
  sizes.sort((a, b) => a.size - b.size);
  const min = sizes[0]?.size;
  return { min, 最小的5个: sizes.slice(0, 5), 分布: sizes.reduce((m, s) => (m[s.size] = (m[s.size] || 0) + 1, m), {}) };
});
console.log(JSON.stringify(r, null, 1));
await b.close();
