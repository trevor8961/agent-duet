import { chromium } from "playwright";
const b = await chromium.launch();
const page = await b.newPage({ viewport: { width: 1200, height: 800 } });
await page.goto("http://localhost:5173/");
await page.waitForTimeout(1200);
const r = await page.evaluate(() => {
  const nav = document.querySelector(".nav");
  return {
    styleAttr: nav.getAttribute("style"),
    computedWidth: getComputedStyle(nav).width,
    offset: nav.offsetWidth,
    flexShrink: getComputedStyle(nav).flexShrink,
    parentDisplay: getComputedStyle(nav.parentElement).display,
  };
});
console.log(JSON.stringify(r));
await b.close();
