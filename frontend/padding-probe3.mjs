import { chromium } from "playwright";
const b = await chromium.launch();
const page = await b.newPage({ viewport: { width: 1440, height: 900 } });
await page.goto("http://localhost:5173/#/s/2");
await page.waitForTimeout(2000);
const r = await page.evaluate(() => {
  const block = [...document.querySelectorAll(".ctx .block")].find((x) => x.textContent.includes("节目单"));
  const body = block.querySelector(".body");
  const turns = [...block.querySelectorAll(".turn")];
  const lowest = Math.max(...turns.map((e) => e.getBoundingClientRect().bottom));
  const kids = [...body.children].map((e) => ({
    tag: e.tagName, cls: e.className, h: e.offsetHeight,
    bottom: Math.round(e.getBoundingClientRect().bottom),
  }));
  return { kids, blockBottom: Math.round(block.getBoundingClientRect().bottom) };
});
console.log(JSON.stringify(r));
await b.close();
