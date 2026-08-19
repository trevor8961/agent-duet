import { chromium } from "playwright";
const b = await chromium.launch();
const page = await b.newPage({ viewport: { width: 1440, height: 900 } });
await page.goto("http://localhost:5173/#/s/2");
await page.waitForTimeout(1800);
const heads = page.locator(".reply-head");
if (await heads.count()) await heads.last().click();
await page.waitForTimeout(300);
const r = await page.evaluate(() => {
  const card = document.querySelector(".bubble.agent.md");
  if (!card) return { ok: false };
  const gaps = [];
  // 找所有 h* 与其下一个元素的真实视觉间隙
  for (const h of card.querySelectorAll("h1,h2,h3,h4")) {
    const next = h.nextElementSibling;
    if (!next || next.tagName === "HR") continue;
    const gap = next.getBoundingClientRect().top - h.getBoundingClientRect().bottom;
    gaps.push({ 标题: h.tagName, 下个元素: next.tagName, 视觉间隙px: +gap.toFixed(1),
      h的marginBottom: getComputedStyle(h).marginBottom, next的marginTop: getComputedStyle(next).marginTop });
  }
  const li = card.querySelector("li");
  const liNext = li?.nextElementSibling;
  const liGap = li && liNext ? liNext.getBoundingClientRect().top - li.getBoundingClientRect().bottom : null;
  const p = card.querySelector("p");
  return { gaps, bullet间隙px: liGap ? +liGap.toFixed(1) : null,
    正文行高: p ? getComputedStyle(p).lineHeight : null };
});
console.log(JSON.stringify(r, null, 1));
await b.close();
