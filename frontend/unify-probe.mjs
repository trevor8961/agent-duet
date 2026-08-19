import { chromium } from "playwright";
const b = await chromium.launch();
const page = await b.newPage({ viewport: { width: 1440, height: 900 } });
await page.goto("http://localhost:5173/#/s/2");
await page.waitForTimeout(1500);
const r = await page.evaluate(() => {
  const blocks = [...document.querySelectorAll(".block")];
  const style = (el) => {
    const cs = getComputedStyle(el);
    return cs.borderRadius + "/" + cs.border.replace(/, /g, " ").split(" ").slice(-3).join(" ");
  };
  return {
    左栏块数: blocks.filter((x) => x.closest(".nav")).length,
    右栏块数: blocks.filter((x) => x.closest(".ctx")).length,
    折叠箭头数: document.querySelectorAll('.block header i').length,
    样式一致: new Set(blocks.map(style)).size === 1,
    块标题示例: [...document.querySelectorAll(".block header span")].slice(0, 7).map((e) => e.textContent),
  };
});
console.log(JSON.stringify(r, null, 1));
await b.close();
