import { chromium } from "playwright";
const b = await chromium.launch();
const page = await b.newPage({ viewport: { width: 1440, height: 900 } });
page.on("pageerror", (e) => console.log("PAGE ERR:", e.message.slice(0, 150)));
await page.goto("http://localhost:5173/");
await page.waitForTimeout(1500);
const r = await page.evaluate(() => {
  const tn = document.querySelector(".topnav");
  const brand = tn?.querySelector(".app-name")?.textContent;
  const repo = tn?.querySelector(".repo");
  const setBtns = [...(tn?.querySelectorAll(".set-btn") || [])].map((x) => x.textContent.trim());
  // 左栏两个 widget 平分验证
  const blocks = [...document.querySelectorAll(".nav .block")];
  const navH = document.querySelector(".nav").clientHeight;
  return {
    顶栏存在: !!tn,
    品牌: brand,
    仓库链接: repo?.textContent.trim() + " -> " + repo?.href,
    设置按钮: setBtns,
    左栏widget数: blocks.length,
    widget高度: blocks.map((x) => x.getBoundingClientRect().height),
    平分验证: blocks.length === 2 && Math.abs(blocks[0].getBoundingClientRect().height - blocks[1].getBoundingClientRect().height) < 5,
  };
});
console.log(JSON.stringify(r, null, 1));
await page.screenshot({ path: "/tmp/ad-topnav.png" });
await b.close();
