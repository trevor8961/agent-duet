import { chromium } from "playwright";
const b = await chromium.launch();
const page = await b.newPage({ viewport: { width: 1440, height: 900 } });
await page.goto("http://localhost:5173/#/s/2");
await page.waitForTimeout(1500);
const r = await page.evaluate(() => {
  const row = document.querySelector(".mode-row");
  const chip = document.querySelector(".mode-chip");
  if (!row || !chip) return { ok: false };
  const rr = row.getBoundingClientRect(), cr = chip.getBoundingClientRect();
  return { ok: true,
    labelText: row.querySelector(".mode-label")?.textContent,
    chipValue: chip.value,
    chipInsideRow: cr.right <= rr.right && cr.left >= rr.left,
    chipRightAligned: (rr.right - cr.right) < 40 };
});
console.log(JSON.stringify(r));
await b.close();
