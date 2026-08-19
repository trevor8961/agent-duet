import { chromium } from "playwright";
const b = await chromium.launch();
const page = await b.newPage({ viewport: { width: 1440, height: 900 } });
await page.goto("http://localhost:5173/#/s/2");
await page.waitForTimeout(1500);
const r = await page.evaluate(() => {
  const label = document.querySelector(".mode-label");
  const chip = document.querySelector(".mode-chip");
  const lr = label.getBoundingClientRect(), cr = chip.getBoundingClientRect();
  return {
    labelCenterY: +lr.top + lr.height / 2,
    chipCenterY: +cr.top + cr.height / 2,
    centerOffsetPx: Math.abs((lr.top + lr.height / 2) - (cr.top + cr.height / 2)),
    labelH: lr.height, chipH: cr.height,
    labelBaseline: getComputedStyle(label).lineHeight,
    chipFont: getComputedStyle(chip).font,
    chipLineHeight: getComputedStyle(chip).lineHeight,
    chipDisplay: getComputedStyle(chip).display,
  };
});
console.log(JSON.stringify(r, null, 1));
await page.screenshot({ path: "/tmp/ad-mode.png", clip: { x: 900, y: 0, width: 540, height: 120 } });
await b.close();
