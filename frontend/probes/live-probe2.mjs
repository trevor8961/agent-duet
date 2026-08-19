import { chromium } from "playwright";
const b = await chromium.launch();
const page = await b.newPage({ viewport: { width: 1440, height: 900 } });
page.on("pageerror", (e) => console.log("PAGE ERR:", e.message.slice(0, 150)));
await page.goto("http://localhost:5173/#/s/2");
await page.waitForTimeout(1500);
await page.fill("textarea", "创建 empty-probe2.txt");
await page.click("footer button.primary");
for (let i = 0; i < 14; i++) {
  await page.waitForTimeout(1000);
  const s = await page.evaluate(async () => {
    const api = await (await fetch(`/api/sessions/2`)).json();
    return {
      bar: document.querySelector(".working")?.innerText.replace(/\n/g, " ") ?? "—",
      runningFlag: (() => { const i = document.querySelector(".user-row")?.__vueParentComponent; return null; })(),
      apiStatus: api.status,
      lastTurnStatus: api.turns[api.turns.length - 1]?.status,
    };
  });
  console.log(`[${i + 1}s]`, JSON.stringify(s));
}
await b.close();
