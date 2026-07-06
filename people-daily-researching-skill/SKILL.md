---
name: people-daily-researching
description: "Extract all page reports from the People's Daily / 人民日报 e-paper for a specific date, including 版面, article titles, short summaries, and PDF links, then optionally filter tourism, beauty/cosmetics, daily chemical, personal care, household care, or custom industry keywords. Use when the user asks to 提取/抓取/整理/汇总人民日报电子版, 人民日报某天所有版面报道, People's Daily e-paper, or provides a paper.people.com.cn/rmrb URL, YYYYMMDD date, or Chinese date for this purpose."
---

# People Daily E-paper Extraction

Extract People's Daily e-paper reports for one date and produce:

- `人民日报_YYYYMMDD_报道摘要.html`
- `人民日报_YYYYMMDD_报道摘要.json`
- after filtering, `人民日报_YYYYMMDD_行业筛选.html`
- when practical, `人民日报_YYYYMMDD_行业筛选.json`

Each record must preserve:

- `版面`
- `文章标题`
- `摘要`
- `PDF链接`
- original article URL

## Date And URL Rules

- Accept `YYYYMMDD`, `YYYY-MM-DD`, `YYYY年M月D日`, or a `paper.people.com.cn/rmrb` URL.
- The People's Daily PC e-paper path uses `YYYYMM/DD`, not `YYYY/MM/DD`.
- First layout page:
  `https://paper.people.com.cn/rmrb/pc/layout/YYYYMM/DD/node_01.html`
- Layout pages:
  `https://paper.people.com.cn/rmrb/pc/layout/YYYYMM/DD/node_XX.html`
- Article pages:
  `https://paper.people.com.cn/rmrb/pc/content/YYYYMM/DD/content_*.html`
- If the user gives no date or URL, ask exactly:
  `请提供要提取的人民日报日期（格式：YYYYMMDD）或完整的URL。`

## Execution Priority

Use the Codex in-app browser path first when `browser:control-in-app-browser` is available. This is the default for Codex Desktop and other sandboxed environments where shell/Python network access can fail due to DNS or approval restrictions.

Use the Python script only when direct Python network access is already known to work, or when the in-app browser is unavailable.

Do not rewrite extraction scripts into the workspace. Reuse the bundled scripts in `scripts/`.

## Browser Path

Use this path by default.

1. Read and follow `browser:control-in-app-browser`.
2. Select a browser for the first layout URL with `agent.browsers.getForUrl(...)`.
3. Import `scripts/extract_people_daily_browser.mjs` from this skill folder in the Node REPL.
4. Call `extractPeopleDailyWithBrowser({ browser, date, outDir })`.
5. The script discovers all visible `node_XX.html` layout pages from `node_01.html`, so it supports ordinary dates with 8-20 pages without hardcoded page counts.
6. After main extraction, run industry filtering as described below.

Example Node REPL call, replacing the script path with this skill's actual absolute path:

```js
const { extractPeopleDailyWithBrowser } = await import("/absolute/path/to/people-daily-researching/scripts/extract_people_daily_browser.mjs");
const result = await extractPeopleDailyWithBrowser({
  browser,
  date: "20260706",
  outDir: "outputs",
});
nodeRepl.write(JSON.stringify(result, null, 2));
```

## Python Fallback

Use `scripts/extract_people_daily.py` only when direct Python network access works:

```bash
python3 /absolute/path/to/people-daily-researching/scripts/extract_people_daily.py 20260706 --out outputs
```

The Python script uses only the standard library. It discovers layout pages from `node_01.html`, extracts each page PDF link, visits article HTML pages, takes the first meaningful paragraph as a summary, and continues on partial failures.

## Industry Follow-Up Step

After the main HTML and JSON are generated, ask the customer exactly unless they already said `默认` or provided screening terms:

`是否搜集“旅游”、“美妆”、“日化”行业相关消息？若不搜索上述消息，请给出您的筛选词：___`

If the user answers `默认`, answers only yes/confirm/blank, or already requested default filtering, use the built-in industry terms. If the user gives custom terms, split them on whitespace, Chinese/English commas, semicolons, slashes, `、`, and newlines.

Run:

```bash
python3 /absolute/path/to/people-daily-researching/scripts/filter_people_daily_industry.py outputs/人民日报_YYYYMMDD_报道摘要.json --response 默认 --out outputs
```

Default industry criteria:

```text
旅游: 旅游, 文旅, 景区, 景点, 酒店, 民宿, 旅行, 游客, 出行, 航旅, 航空, 机场, 高铁, 铁路, 邮轮, 度假, 假日, 入境游, 出境游, 乡村旅游
美妆: 美妆, 化妆品, 护肤, 彩妆, 香水, 口红, 面膜, 美容, 医美, 个护, 国货美妆, 化妆品监管
日化: 日化, 洗护, 洗涤, 清洁, 家清, 个护, 洗发, 沐浴, 牙膏, 牙刷, 纸品, 卫生巾, 消毒, 清洁用品
```

## Output Requirements

- Continue on partial failures.
- Record missing PDFs as `无PDF`.
- Record failed page or article visits as `访问失败`.
- Preserve original article URLs and PDF URLs.
- Prefer structured article HTML over PDF text/OCR.
- Report extraction date, page count, article count, failure count, and generated paths.
- If no industry records match, report `未筛选到相关消息` and state which terms were used.
