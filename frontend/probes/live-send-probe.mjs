import { chromium } from "playwright";
const b = await chromium.launch();
const page = await b.newPage({ viewport: { width: 1440, height: 900 } });
page.on("pageerror", (e) => console.log("PAGE ERR:", e.message.slice(0, 200)));
page.on("console", (m) => m.type() === "error" && console.log("CONSOLE:", m.text().slice(0, 200)));
await page.goto("http://localhost:5173/#/s/2");
await page.waitForTimeout(1800);

// 填入并发送（⌘+Enter）
await page.fill("textarea", "创建一个 empty-probe.txt 空文件");
await page.click("footer button.primary");

// 每 1.5s 采样状态条与运行态
for (let i = 0; i < 8; i++) {
  await page.waitForTimeout(1500);
  const s = await page.evaluate(() => ({
    t: document.querySelector(".working")?.innerText.replace(/\n/g, " ") ?? null,
    running: (() => { const el = document.querySelector("textarea"); return el?.disabled; })(),
  }));
  console.log(`[${i * 1.5}s]`, JSON.stringify(s));
}
await b.close();
