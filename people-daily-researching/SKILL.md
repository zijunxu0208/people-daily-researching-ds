---
name: people-daily-researching
description: Extract all page reports from the People's Daily / 人民日报 e-paper or its Overseas Edition / 人民日报海外版 for a specific date, including 版面, article titles, short summaries, and PDF links, then optionally filter beauty/cosmetics, daily chemical, personal care, household care, regulatory, or custom industry keywords. Use when the user asks to 提取/抓取/整理/汇总人民日报电子版, 人民日报海外版, 人民日报某天所有版面报道, People's Daily e-paper, or provides a paper.people.com.cn/rmrb or paper.people.com.cn/rmrbhwb URL, YYYYMMDD date, or Chinese date for this purpose.
install_method: upload
---

# People Daily E-paper Extraction

Extract People's Daily e-paper reports for one date and produce:

- `人民日报_YYYYMMDD_报道摘要.html`
- `人民日报_YYYYMMDD_报道摘要.json`
- `人民日报海外版_YYYYMMDD_报道摘要.html`
- `人民日报海外版_YYYYMMDD_报道摘要.json`
- `人民日报_YYYYMMDD_海内外报道摘要.html` (combined domestic + overseas edition)
- after filtering, `人民日报_YYYYMMDD_海内外行业筛选.html` (combined)
- when practical, individual `人民日报_YYYYMMDD_行业筛选.json` and `人民日报海外版_YYYYMMDD_行业筛选.json`

Each record must preserve:

- `版面`
- `文章标题`
- `摘要`
- `PDF链接`
- original article URL

## Date And URL Rules

- Accept `YYYYMMDD`, `YYYY-MM-DD`, `YYYY年M月D日`, or a full `paper.people.com.cn` URL.
- The e-paper PC path uses `YYYYMM/DD`, not `YYYY/MM/DD`.

### People's Daily / 人民日报

- First layout page:
  `https://paper.people.com.cn/rmrb/pc/layout/YYYYMM/DD/node_01.html`
- Layout pages:
  `https://paper.people.com.cn/rmrb/pc/layout/YYYYMM/DD/node_XX.html`
- Article pages:
  `https://paper.people.com.cn/rmrb/pc/content/YYYYMM/DD/content_*.html`

### People's Daily Overseas Edition / 人民日报海外版

- First layout page:
  `https://paper.people.com.cn/rmrbhwb/pc/layout/YYYYMM/DD/node_01.html`
- Layout pages:
  `https://paper.people.com.cn/rmrbhwb/pc/layout/YYYYMM/DD/node_XX.html`
- Article pages:
  `https://paper.people.com.cn/rmrbhwb/pc/content/YYYYMM/DD/content_*.html`

- If the user gives no date or URL, ask exactly:
  `请提供要提取的人民日报日期（格式：YYYYMMDD）或完整的URL。`

## Execution Priority

Use the Codex in-app browser path first when `browser:control-in-app-browser` is available. This is the default for Codex Desktop and other sandboxed environments where shell/Python network access can fail due to DNS or approval restrictions.

Use the Python script only when direct Python network access is already known to work, or when the in-app browser is unavailable.

Do not rewrite extraction scripts into the workspace. Reuse the bundled scripts in `scripts/`.

## Browser Path

Use this path when a bundled browser script (`scripts/extract_people_daily_browser.mjs` or `scripts/extract_people_daily_hwb_browser.mjs`) is present in this skill folder.

1. Read and follow `browser:control-in-app-browser`.
2. Select a browser for the first layout URL with `agent.browsers.getForUrl(...)`.
3. Import the appropriate bundled `.mjs` script from this skill folder in the Node REPL.
4. Call `extractPeopleDailyWithBrowser({ browser, date, outDir })` for the domestic edition or `extractPeopleDailyHwbdWithBrowser({ browser, date, outDir })` for the overseas edition.
5. The script discovers all visible `node_XX.html` layout pages from `node_01.html`, so it supports ordinary dates with 8-20 pages without hardcoded page counts.
6. After main extraction, run industry filtering as described below.

If the browser script is missing, use the Python fallback below.

Example Node REPL call for the domestic edition, replacing the script path with this skill's actual absolute path:

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

Use the Python scripts only when direct Python network access is already known to work, or when the in-app browser is unavailable.

### Default: combined domestic + overseas edition

Run one command to extract both editions and merge them into a single combined HTML:

```bash
python3 /absolute/path/to/people-daily-researching/scripts/extract_people_daily_combined.py 20260706 --out outputs
```

This produces individual JSON/HTML files for each edition **and** a merged `人民日报_YYYYMMDD_海内外报道摘要.html`.

### Single edition only

If you only need the domestic edition:

```bash
python3 /absolute/path/to/people-daily-researching/scripts/extract_people_daily.py 20260706 --out outputs
```

If you only need the overseas edition:

```bash
python3 /absolute/path/to/people-daily-researching/scripts/extract_people_daily_hwb.py 20260706 --out outputs
```

The Python scripts use only the standard library. They discover layout pages from `node_01.html`, extract each page PDF link, visit article HTML pages, take the first meaningful paragraph as a summary, and continue on partial failures.

## Industry Follow-Up Step

After the main HTML and JSON are generated, ask the customer exactly unless they already said `默认` or provided screening terms:

`是否搜集“美妆”、“日化”等行业相关消息？若不搜索上述消息，请给出您的筛选词：___`

If the user answers `默认`, answers only yes/confirm/blank, or already requested default filtering, use the built-in industry terms. If the user gives custom terms, split them on whitespace, Chinese/English commas, semicolons, slashes, `、`, and newlines.

Run the matching filter script. By default, filter both editions and merge the results into one combined HTML:

### Default: combined domestic + overseas edition

```bash
python3 /absolute/path/to/people-daily-researching/scripts/filter_people_daily_industry_combined.py 20260706 --response 默认 --out outputs
```

This produces individual filtered JSON/HTML files for each edition **and** a merged `人民日报_YYYYMMDD_海内外行业筛选.html`.

## Self-Improvement / Keyword Learning

After presenting the filtered HTML, ask the customer exactly:

`是否有遗漏的消息？若有，您可以给我网址URL。我将学习本篇关键词并注入策略中……`

If the customer provides one or more URLs, run the learning script for each URL:

```bash
python3 /absolute/path/to/people-daily-researching/scripts/learn_keywords.py <URL>
```

The script downloads the page, detects which categories (美妆 / 日化 / 监管) are relevant, extracts co-occurring candidate terms, and appends them to `scripts/keywords.json`.

After all URLs are processed, re-run the combined filter script with `--response 默认` so the newly learned keywords are applied immediately:

```bash
python3 /absolute/path/to/people-daily-researching/scripts/filter_people_daily_industry_combined.py 20260706 --response 默认 --out outputs
```

`filter_people_daily_industry.py` and `filter_people_daily_industry_hwb.py` automatically load `keywords.json` on every run and merge learned terms with the built-in defaults. If `keywords.json` is missing or empty, filtering falls back to the built-in terms exactly as before.

### Single edition only

Domestic edition:

```bash
python3 /absolute/path/to/people-daily-researching/scripts/filter_people_daily_industry.py outputs/人民日报_YYYYMMDD_报道摘要.json --response 默认 --out outputs
```

Overseas edition:

```bash
python3 /absolute/path/to/people-daily-researching/scripts/filter_people_daily_industry_hwb.py outputs/人民日报海外版_YYYYMMDD_报道摘要.json --response 默认 --out outputs
```

Default industry criteria (used by both domestic and overseas filter scripts):

```text
美妆: 美妆, 化妆品, 护肤, 彩妆, 香水, 口红, 面膜, 美容, 医美, 个护, 国货美妆, 化妆品监管, 欧莱雅, 联合利华, 资生堂, 上海家化, 雅诗兰黛, Olay, OLAY, SK-II
日化: 日化, 洗护, 洗涤, 清洁, 家清, 个护, 洗发, 沐浴, 牙膏, 牙刷, 纸品, 卫生巾, 消毒, 清洁用品, 护舒宝, 丹碧丝, 佳洁士, 欧乐B, 当妮, 汰渍, 碧浪, 舒肤佳, 飘柔, 潘婷, 海飞丝, 吉列, 博朗, 帮宝适, 原料, 纸尿裤, 婴幼, 剃须
监管: 原料, 法律, 化妆品监管, 抽检, 备案, 广告宣传, 质量安全, 召回, 虚假宣传, 消费投诉, 价格监管, 进口化妆品, 规定, 新规, 药监局
```

## Output Requirements

- Continue on partial failures.
- Record missing PDFs as `无PDF`.
- Record failed page or article visits as `访问失败`.
- Preserve original article URLs and PDF URLs.
- Prefer structured article HTML over PDF text/OCR.
- Report extraction date, page count, article count, failure count, and generated paths.
- If no industry records match, report `未筛选到相关消息` and state which terms were used.
