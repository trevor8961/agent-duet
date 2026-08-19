import { chromium } from "playwright";
const b = await chromium.launch();
const page = await b.newPage({ viewport: { width: 1440, height: 900 } });
await page.goto("http://localhost:5173/#/s/2");
await page.waitForTimeout(1500);
const r = await page.evaluate(() => {
  const label = document.querySelector(".mode-label");
  const chip = document.querySelector(".mode-chip");
  const block = label.closest(".block");
  const c = document.createElement("canvas").getContext("2d");
  const cs = getComputedStyle(label);
  c.font = `${cs.fontWeight} ${cs.fontSize} ${cs.fontFamily}`;
  const m = c.measureText("Current");
  const lr = label.getBoundingClientRect();
  const labelTextBottom = lr.top + lr.height / 2 + m.actualBoundingBoxDescent;
  const chipBottom = chip.getBoundingClientRect().bottom;
  const blockBottom = block.getBoundingClientRect().bottom;
  return {
    Current字形距块底: +(blockBottom - labelTextBottom).toFixed(1),
    胶囊盒距块底: +(blockBottom - chipBottom).toFixed(1),
    视觉差: +(chipBottom - labelTextBottom).toFixed(1),
  };
});
console.log(JSON.stringify(r, null, 1));
await b.close();
