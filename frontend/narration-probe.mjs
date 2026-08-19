import { chromium } from "playwright";
const b = await chromium.launch();
const page = await b.newPage({ viewport: { width: 1440, height: 900 } });
await page.goto("http://localhost:5173/#/s/2");
await page.waitForTimeout(1800);
const r = await page.evaluate(() => {
  const bs = [...document.querySelectorAll(".backstage")];
  return bs.map((x) => x.querySelector("summary").innerText.replace(/\n/g, " "));
});
// 每轮的纸卡数应 ≤1（中间旁白不再单独成卡）
const replies = await page.evaluate(() => {
  const groups = [...document.querySelectorAll(".backstage")];
  return document.querySelectorAll(".reply").length;
});
console.log(JSON.stringify({ 幕后摘要: r, 回复纸卡数: replies }, null, 1));
await b.close();
