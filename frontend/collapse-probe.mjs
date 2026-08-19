import { chromium } from "playwright";
const b = await chromium.launch();
const page = await b.newPage({ viewport: { width: 1440, height: 900 } });
await page.goto("http://localhost:5173/#/s/2");
await page.waitForTimeout(1800);
const r = await page.evaluate(() => {
  const bs = [...document.querySelectorAll(".backstage")];
  return bs.map((x) => {
    const s = x.querySelector("summary").getBoundingClientRect();
    const body = x.querySelector(".bs-body");
    return {
      open: x.open,
      折叠条高: +s.height.toFixed(0),
      body可见高: body ? body.offsetHeight : 0,
      hasOpenAttr: x.hasAttribute("open"),
      summary文本: x.querySelector("summary").innerText.replace(/\n/g, " "),
    };
  });
});
console.log(JSON.stringify(r, null, 1));
await b.close();
