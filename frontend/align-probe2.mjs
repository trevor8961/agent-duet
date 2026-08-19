import { chromium } from "playwright";
const b = await chromium.launch();
const page = await b.newPage({ viewport: { width: 1440, height: 900 } });
await page.goto("http://localhost:5173/#/s/2");
await page.waitForTimeout(1500);
// 用 Canvas 实测两段文字的视觉基线（消除行盒差异）
const r = await page.evaluate(() => {
  const label = document.querySelector(".mode-label");
  const chip = document.querySelector(".mode-chip");
  const measure = (el, text) => {
    const cs = getComputedStyle(el);
    const c = document.createElement("canvas").getContext("2d");
    c.font = `${cs.fontWeight} ${cs.fontSize} ${cs.fontFamily}`;
    const m = c.measureText(text);
    // actualBoundingBoxAscent/Descent 给出字形真实上下沿
    return { ascent: m.actualBoundingBoxAscent, descent: m.actualBoundingBoxDescent };
  };
  const labelR = label.getBoundingClientRect();
  const chipR = chip.getBoundingClientRect();
  const lm = measure(label, "Current");
  const cm = measure(chip, chip.value || "Guided");
  // 基线 = 顶 + (盒高-行高)/2 + 行高内偏移；近似取文字盒中心
  const labelCenter = labelR.top + labelR.height / 2;
  const chipCenter = chipR.top + chipR.height / 2;
  return {
    labelCenterY: +labelCenter.toFixed(1),
    chipCenterY: +chipCenter.toFixed(1),
    offset: +(labelCenter - chipCenter).toFixed(1),
    labelH: labelR.height, chipH: chipR.height,
  };
});
console.log(JSON.stringify(r));
await page.screenshot({ path: "/tmp/ad-mode2.png", clip: { x: 900, y: 0, width: 540, height: 120 } });
await b.close();
