import { chromium } from "playwright";
const b = await chromium.launch();
const page = await b.newPage({ viewport: { width: 1440, height: 900 } });
await page.goto("http://localhost:5173/#/s/2");
await page.waitForTimeout(1800);
const r = await page.evaluate(() => {
  const flow = document.querySelector(".flow").getBoundingClientRect();
  const pos = (el) => {
    const r = el.getBoundingClientRect();
    return { left: +(r.left - flow.left).toFixed(0), rightGap: +(flow.right - r.right).toFixed(0), w: +r.width.toFixed(0) };
  };
  const user = [...document.querySelectorAll(".user-row")].pop();
  const bs = [...document.querySelectorAll(".backstage")].pop();
  const reply = [...document.querySelectorAll(".reply")].pop();
  return {
    用户气泡: user && pos(user),
    幕后折叠条: bs && pos(bs),
    回复纸卡: reply && pos(reply),
    宽度互异: new Set([bs?.offsetWidth, reply?.offsetWidth]).size === 2,
  };
});
console.log(JSON.stringify(r, null, 1));
await page.screenshot({ path: "/tmp/ad-layout.png" });
await b.close();
