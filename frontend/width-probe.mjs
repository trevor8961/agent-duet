import { chromium } from "playwright";
const b = await chromium.launch();
const page = await b.newPage({ viewport: { width: 1440, height: 900 } });
await page.goto("http://localhost:5173/#/s/2");
await page.waitForTimeout(1800);
await page.evaluate(() => [...document.querySelectorAll(".backstage")].pop().querySelector("summary").click());
await page.waitForTimeout(300);
const r = await page.evaluate(() => {
  const flow = document.querySelector(".flow");
  const flowW = flow.clientWidth;
  const pct = (el) => (el ? Math.round((el.getBoundingClientRect().width / flowW) * 100) : null);
  const body = [...document.querySelectorAll(".backstage .bs-body")].pop();
  const lastBs = [...document.querySelectorAll(".backstage")].pop();
  return {
    中栏宽: flowW,
    用户气泡占比: pct([...document.querySelectorAll(".user-row")].pop()),
    回复纸卡占比: pct([...document.querySelectorAll(".reply")].pop()),
    幕后body无滚动: body ? getComputedStyle(body).overflowY === "visible" : null,
    回到开头按钮: !!lastBs?.querySelector(".bs-top"),
  };
});
console.log(JSON.stringify(r, null, 1));
await b.close();
