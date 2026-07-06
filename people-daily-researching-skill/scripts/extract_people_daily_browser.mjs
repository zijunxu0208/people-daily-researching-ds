import fs from "node:fs/promises";
import path from "node:path";

function esc(value) {
  return String(value ?? "").replace(/[&<>"']/g, (ch) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  })[ch]);
}

function parseDate(raw) {
  const digits = String(raw || "").match(/\d+/g) || [];
  let date;
  if (digits.length === 1 && /^\d{8}$/.test(digits[0])) {
    date = new Date(`${digits[0].slice(0, 4)}-${digits[0].slice(4, 6)}-${digits[0].slice(6, 8)}T00:00:00Z`);
  } else if (digits.length >= 3) {
    date = new Date(`${digits[0].padStart(4, "0")}-${digits[1].padStart(2, "0")}-${digits[2].padStart(2, "0")}T00:00:00Z`);
  } else {
    throw new Error("date must look like 20260706, 2026-07-06, or 2026年7月6日");
  }
  if (Number.isNaN(date.getTime())) {
    throw new Error(`invalid date: ${raw}`);
  }
  const year = String(date.getUTCFullYear());
  const month = String(date.getUTCMonth() + 1).padStart(2, "0");
  const day = String(date.getUTCDate()).padStart(2, "0");
  return { year, month, day, yyyymmdd: `${year}${month}${day}` };
}

function layoutUrl({ year, month, day }, node = "01") {
  return `https://paper.people.com.cn/rmrb/pc/layout/${year}${month}/${day}/node_${node}.html`;
}

function buildSummaryHtml(dateLabel, pagesCount, records) {
  const rows = records.map((article) => (
    `      <tr><td>${esc(article.page)}</td><td><a href="${esc(article.url)}" target="_blank" rel="noopener">${esc(article.title)}</a></td><td>${esc(article.summary)}</td><td>${article.pdf ? `<a href="${esc(article.pdf)}" target="_blank" rel="noopener">PDF</a>` : "无PDF"}</td></tr>`
  )).join("\n");
  return `<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>人民日报 ${esc(dateLabel)} 报道摘要</title>
<style>
  body { margin: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; color: #1f2328; background: #f6f8fa; }
  .wrap { max-width: 1240px; margin: 0 auto; padding: 28px 20px 44px; }
  h1 { font-size: 24px; margin: 0 0 8px; }
  .meta { color: #59636e; margin: 0 0 18px; font-size: 14px; }
  .table-wrap { overflow-x: auto; background: #fff; border: 1px solid #d8dee4; border-radius: 8px; }
  table { width: 100%; border-collapse: collapse; table-layout: fixed; }
  th, td { border-bottom: 1px solid #d8dee4; padding: 10px 12px; vertical-align: top; line-height: 1.55; }
  th { background: #f0f3f6; text-align: left; font-size: 14px; cursor: pointer; user-select: none; white-space: nowrap; }
  tr:last-child td { border-bottom: 0; }
  td:nth-child(1) { width: 120px; color: #59636e; }
  td:nth-child(2) { width: 280px; font-weight: 600; }
  td:nth-child(4) { width: 72px; white-space: nowrap; }
  a { color: #0969da; text-decoration: none; }
  a:hover { text-decoration: underline; }
  @media (max-width: 760px) { .wrap { padding: 18px 12px 32px; } table { min-width: 860px; } h1 { font-size: 20px; } }
</style>
</head>
<body>
<div class="wrap">
  <h1>人民日报 ${esc(dateLabel)} 报道摘要</h1>
  <p class="meta">共处理 ${pagesCount} 个版面，提取 ${records.length} 篇文章。点击表头可排序。</p>
  <div class="table-wrap">
    <table id="summaryTable">
      <thead><tr><th>版面</th><th>文章标题</th><th>摘要</th><th>PDF链接</th></tr></thead>
      <tbody>
${rows}
      </tbody>
    </table>
  </div>
</div>
<script>
  document.querySelectorAll('th').forEach((th, col) => {
    th.addEventListener('click', () => {
      const table = th.closest('table');
      const body = table.tBodies[0];
      const asc = th.dataset.asc !== 'true';
      [...body.rows]
        .sort((a, b) => a.cells[col].innerText.localeCompare(b.cells[col].innerText, 'zh-Hans') * (asc ? 1 : -1))
        .forEach(row => body.appendChild(row));
      document.querySelectorAll('th').forEach(h => delete h.dataset.asc);
      th.dataset.asc = String(asc);
    });
  });
</script>
</body>
</html>
`;
}

async function gotoAndWait(tab, url) {
  await tab.goto(url);
  await tab.playwright.waitForLoadState({ state: "domcontentloaded", timeoutMs: 25000 });
}

async function discoverPages(tab, dateParts) {
  const firstUrl = layoutUrl(dateParts);
  await gotoAndWait(tab, firstUrl);
  return await tab.playwright.evaluate(({ year, month, day, firstUrl }) => {
    const clean = (s) => String(s || "").replace(/\u00a0/g, " ").replace(/[ \t\r\f\u3000]+/g, " ").replace(/\n+/g, "\n").trim();
    const links = [...document.querySelectorAll("a")].map((a) => ({
      text: clean(a.innerText || a.textContent || ""),
      href: a.href || "",
    }));
    const pattern = new RegExp(`/rmrb/pc/layout/${year}${month}/${day}/node_(\\d{2})\\.html$`);
    const pages = {};
    for (const link of links) {
      const match = link.href.match(pattern);
      if (!match || !link.text.includes("版")) continue;
      pages[match[1]] = { node: match[1], label: link.text, url: link.href };
    }
    if (!Object.keys(pages).length) {
      pages["01"] = { node: "01", label: "第01版", url: firstUrl };
    }
    return Object.keys(pages).sort().map((key) => pages[key]);
  }, { ...dateParts, firstUrl }, { timeoutMs: 20000 });
}

async function readLayout(tab, info, dateParts) {
  await gotoAndWait(tab, info.url);
  const layout = await tab.playwright.evaluate(({ year, month, day }) => {
    const clean = (s) => String(s || "").replace(/\u00a0/g, " ").replace(/[ \t\r\f\u3000]+/g, " ").replace(/\n+/g, "\n").trim();
    const links = [...document.querySelectorAll("a")].map((a) => ({
      text: clean(a.innerText || a.textContent || ""),
      href: a.href || "",
    }));
    const pageText = document.body ? document.body.innerText : "";
    const pageLabel = (pageText.match(/第\d+版[:：][^\n]+/) || [""])[0];
    const pdf = links.find((link) => /PDF/i.test(link.text) || /\.pdf(\?|$)/i.test(link.href))?.href || "";
    const articlePattern = new RegExp(`/rmrb/pc/content/${year}${month}/${day}/content_\\d+\\.html$`);
    const articles = links
      .filter((link) => articlePattern.test(link.href) && link.text)
      .filter((link, index, arr) => arr.findIndex((item) => item.href === link.href) === index)
      .map((link) => ({ title: link.text.replace(/^·\s*/, "").trim(), url: link.href }));
    return { pageLabel, pdf, articles };
  }, dateParts, { timeoutMs: 20000 });
  return {
    node: info.node,
    label: layout.pageLabel || info.label,
    url: info.url,
    pdf: layout.pdf,
    articles: layout.articles,
    ok: true,
    error: "",
  };
}

async function readArticle(tab, article) {
  await gotoAndWait(tab, article.url);
  return await tab.playwright.evaluate((expectedTitle) => {
    const clean = (s) => String(s || "").replace(/\u00a0/g, " ").replace(/[ \t\r\f\u3000]+/g, " ").replace(/\n+/g, "\n").trim();
    const docTitle = clean(document.querySelector("h1")?.innerText || document.title || expectedTitle);
    const bad = /^(日报|周报|杂志|本版新闻|返回目录|放大|缩小|全文复制|上一篇|下一篇|版权声明|人民日报图文数据库|人 民 网 版 权 所 有|Copyright)/;
    const isNoise = (p) => (
      p.length < 8 ||
      p === expectedTitle ||
      p === docTitle ||
      bad.test(p) ||
      /^第\d+版[:：]/.test(p) ||
      /^人民日报\s*\d{4}年\d{2}月\d{2}日/.test(p) ||
      /^《人民日报》/.test(p) ||
      ((/摄$/.test(p) || /记者\s*[\u4e00-\u9fff]{2,4}摄$/.test(p)) && p.length < 160)
    );
    const paras = [...document.querySelectorAll("p")]
      .map((p) => clean(p.innerText || p.textContent || ""))
      .filter((p) => p && !isNoise(p));
    return {
      title: docTitle,
      summary: [...(paras[0] || "无法提取文本")].slice(0, 200).join(""),
    };
  }, article.title, { timeoutMs: 20000 });
}

export async function extractPeopleDailyWithBrowser({ browser, tab, date, outDir = "outputs", closeTabs = true }) {
  if (!browser && !tab) {
    throw new Error("pass a selected Codex browser or an existing tab");
  }
  const dateParts = parseDate(date);
  const ownedTab = tab || await browser.tabs.new();
  const pages = [];
  const records = [];
  const failures = [];
  const firstUrl = layoutUrl(dateParts);

  try {
    const pageInfos = await discoverPages(ownedTab, dateParts);
    for (const info of pageInfos) {
      try {
        const page = await readLayout(ownedTab, info, dateParts);
        pages.push(page);
        for (const article of page.articles) {
          try {
            const detail = await readArticle(ownedTab, article);
            records.push({
              page: page.label,
              title: article.title || detail.title,
              summary: detail.summary,
              pdf: page.pdf,
              url: article.url,
            });
          } catch (error) {
            failures.push({ url: article.url, error: String(error?.message || error) });
            records.push({
              page: page.label,
              title: article.title,
              summary: "访问失败",
              pdf: page.pdf,
              url: article.url,
            });
          }
        }
      } catch (error) {
        failures.push({ url: info.url, error: String(error?.message || error) });
        pages.push({
          node: info.node,
          label: info.label,
          url: info.url,
          pdf: "",
          articles: [],
          ok: false,
          error: String(error?.message || error),
        });
      }
    }

    await fs.mkdir(outDir, { recursive: true });
    const dateLabel = `${dateParts.year}年${dateParts.month}月${dateParts.day}日`;
    const stem = `人民日报_${dateParts.yyyymmdd}_报道摘要`;
    const htmlPath = path.join(outDir, `${stem}.html`);
    const jsonPath = path.join(outDir, `${stem}.json`);
    await fs.writeFile(htmlPath, buildSummaryHtml(dateLabel, pages.length, records), "utf8");
    await fs.writeFile(jsonPath, JSON.stringify({
      date: dateParts.yyyymmdd,
      first_url: firstUrl,
      pages,
      records,
      failures,
    }, null, 2), "utf8");

    return {
      date: dateParts.yyyymmdd,
      pages: pages.length,
      records: records.length,
      failures: failures.length,
      htmlPath,
      jsonPath,
    };
  } finally {
    if (closeTabs && browser?.tabs?.finalize) {
      await browser.tabs.finalize({ keep: [] });
    }
  }
}
