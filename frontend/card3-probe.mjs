import { chromium } from "playwright";
const b = await chromium.launch();
const page = await b.newPage({ viewport: { width: 1440, height: 900 } });
await page.goto("http://localhost:5173/");
await page.waitForTimeout(1200);
const r = await page.evaluate(() => {
  const card = document.querySelector(".nav .card");
  const del = card.querySelector(".del");
  const dr = del.getBoundingClientRect(), cr = card.getBoundingClientRect();
  // hover 检查删除按钮与 title 不重叠
  const label = card.querySelector(".row1 .label").getBoundingClientRect();
  return {
    行1: card.querySelector(".row1").innerText.replace(/\n/g, " "),
    行3: card.querySelector(".row3").innerText.replace(/\n/g, " | "),
    del与title水平间隔: +(label.right <= dr.left ? dr.left - label.right : -1).toFixed(1),
    del在卡片内: dr.right <= cr.right && dr.top >= cr.top,
  };
});
console.log(JSON.stringify(r, null, 1));
await b.close();
