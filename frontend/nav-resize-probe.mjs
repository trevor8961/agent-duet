import { chromium } from "playwright";
const b = await chromium.launch();
const page = await b.newPage({ viewport: { width: 1200, height: 800 } });
await page.goto("http://localhost:5173/");
await page.waitForTimeout(1200);
// 拖拽左栏分隔条到 x=450（超过 1/3=400 应被钳制）
const divider = page.locator(".divider").first();
await divider.hover();
await page.mouse.down();
await page.mouse.move(450, 400, { steps: 5 });
await page.mouse.up();
await page.waitForTimeout(200);
const r = await page.evaluate(() => ({
  左栏宽: document.querySelector(".nav").offsetWidth,
  三分之一: Math.floor(innerWidth / 3),
}));
console.log(JSON.stringify(r));
await b.close();
