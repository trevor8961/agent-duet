import { chromium } from "playwright";
const b = await chromium.launch();
const page = await b.newPage({ viewport: { width: 1440, height: 800 } });
await page.goto("http://localhost:5173/#/s/2");
await page.waitForTimeout(1500);

// 展开活动块
await page.locator(".ctx .block", { hasText: "活动" }).locator("header").click();
// 展开 changes
const gitBlock = page.locator(".ctx .block", { hasText: "工作区" });
await gitBlock.locator(".chg-toggle").click();
await page.waitForTimeout(300);

const report = await page.evaluate(() => {
  const probe = (el, name) => {
    if (!el) return { name, missing: true };
    const cs = getComputedStyle(el);
    return { name, cls: el.className, h: el.offsetHeight, scrollH: el.scrollHeight,
             clientH: el.clientHeight, overflowY: cs.overflowY, maxH: cs.maxHeight,
             display: cs.display };
  };
  return [
    probe(document.querySelector(".cmds"), "活动-命令列表"),
    probe(document.querySelector(".changes"), "工作区-changes"),
    probe(document.querySelector(".ctx"), "整个右栏"),
  ];
});
console.log(JSON.stringify(report, null, 1));
await page.screenshot({ path: "/tmp/ad-probe2.png" });
await b.close();
