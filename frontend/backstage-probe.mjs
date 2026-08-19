import { chromium } from "playwright";
const b = await chromium.launch();
const page = await b.newPage({ viewport: { width: 1440, height: 900 } });
await page.goto("http://localhost:5173/#/s/2");
await page.waitForTimeout(1800);
const r = await page.evaluate(() => {
  const bs = [...document.querySelectorAll(".backstage")];
  return {
    幕后块数: bs.length,
    折叠态摘要: bs.slice(0, 4).map((x) => x.querySelector("summary")?.innerText.replace(/\n/g, " ")),
    默认全折叠: bs.every((x) => !x.open),
  };
});
console.log(JSON.stringify(r, null, 1));
await b.close();
