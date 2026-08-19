import { chromium } from "playwright";
const b = await chromium.launch();
const page = await b.newPage({ viewport: { width: 1440, height: 900 } });
await page.goto("http://localhost:5173/#/s/2");
await page.waitForTimeout(1500);
const r = await page.evaluate(() => {
  const label = document.querySelector(".mode-label");
  const chip = document.querySelector(".mode-chip");
  const lr = label.getBoundingClientRect(), cr = chip.getBoundingClientRect();
  const c = document.createElement("canvas").getContext("2d");
  const cs = getComputedStyle(label);
  c.font = `${cs.fontWeight} ${cs.fontSize} ${cs.fontFamily}`;
  const m = c.measureText("Current");
  const labelTextBottom = lr.top + lr.height / 2 + m.actualBoundingBoxDescent;
  return {
    行盒中线偏差: +Math.abs((lr.top + lr.height / 2) - (cr.top + cr.height / 2)).toFixed(1),
    labelH: lr.height, chipH: cr.height,
    胶囊盒底比字形底突出: +(cr.bottom - labelTextBottom).toFixed(1),
  };
});
console.log(JSON.stringify(r, null, 1));
await b.close();
