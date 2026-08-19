import { chromium } from "playwright";
const b = await chromium.launch();
const page = await b.newPage({ viewport: { width: 1440, height: 900 } });
await page.goto("http://localhost:5173/#/s/2");
await page.waitForTimeout(1500);
const r = await page.evaluate(() => {
  const block = [...document.querySelectorAll(".ctx .block")].find((x) => x.textContent.includes("Current") || x.textContent.includes("模式"));
  const label = document.querySelector(".mode-label");
  const chip = document.querySelector(".mode-chip");
  const measureGlyph = (el, text) => {
    const cs = getComputedStyle(el);
    const c = document.createElement("canvas").getContext("2d");
    c.font = `${cs.fontWeight} ${cs.fontSize} ${cs.fontFamily}`;
    return c.measureText(text);
  };
  const lm = measureGlyph(label, "Current");
  const cm = measureGlyph(chip, "Guided");
  const lr = label.getBoundingClientRect(), cr = chip.getBoundingClientRect();
  const labelCenter = lr.top + lr.height / 2;
  const labelTextBottom = labelCenter + lm.actualBoundingBoxDescent;
  const chipTextBottom = cr.top + cr.height / 2 + cm.actualBoundingBoxDescent;
  return {
    行盒底到块底: null,
    label字形底边: +labelTextBottom.toFixed(1),
    chip字形底边: +chipTextBottom.toFixed(1),
    chip盒底边: +cr.bottom.toFixed(1),
    label字形底_vs_chip盒底: +(cr.bottom - labelTextBottom).toFixed(1),
  };
});
console.log(JSON.stringify(r, null, 1));
await b.close();
