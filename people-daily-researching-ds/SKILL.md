---
name: people-daily-researching-ds
description: "Extract and research People's Daily / 人民日报 e-paper reports for a date using a low-resource browser workflow: discover fixed layout pages, read layout article titles and article URLs, judge relevance from titles with a loose screen, and output linked-title tables without opening article/PDF pages. Use when the user asks to 提取/抓取/整理/汇总人民日报电子版, 人民日报某天报道, People's Daily e-paper, title/link extraction, or industry screening for 人民日报."
---

# People Daily Researching DS

Use this skill when the agent has limited execution ability: short Python only, limited browser tabs, and no reliable local file manipulation. Prefer browser navigation and page snapshots over shell, downloads, OCR, or many parallel tabs.

## Inputs

- Accept `YYYYMMDD`, `YYYY-MM-DD`, `YYYY年M月D日`, or a `paper.people.com.cn/rmrb` URL.
- If no date or URL is given, ask exactly:
  `请提供要提取的人民日报日期（格式：YYYYMMDD）或完整的URL。`
- People's Daily PC paths use `YYYYMM/DD`, not `YYYY/MM/DD`.
- First page URL:
  `https://paper.people.com.cn/rmrb/pc/layout/YYYYMM/DD/node_01.html`

Short date conversion code if needed:

```python
import re
from datetime import datetime

def normalize_date(raw):
    parts = re.findall(r"\d+", raw)
    if len(parts) == 1 and len(parts[0]) == 8:
        d = datetime.strptime(parts[0], "%Y%m%d")
    else:
        d = datetime(int(parts[0]), int(parts[1]), int(parts[2]))
    return d.strftime("%Y%m%d"), d.strftime("%Y%m"), d.strftime("%d")
```

## Fast Path

Do not discuss step counts or whether to continue. Follow the fixed caps below and keep moving. Do not attempt article-page crawling.

This anti-stall workflow is the default and preferred behavior. When uncertain, follow it instead of inventing a new plan: if the user has said `默认`, use default terms; if title links are available, rank titles; if progress repeats or tool output is truncated, stop navigating and output the collected table.

Anti-stall rules:

- If the user already wrote `默认`, `默认筛选`, `旅游`, `美妆`, or `日化` in the initial request, do not ask the industry follow-up question again. Treat it as confirmation to use the default criteria.
- Do not inspect page source, search source code, or reason about whether content is hidden if visible title links can already be extracted from the layout page. Use the layout page anchors and continue.
- Do not say you will batch open many pages, article pages, or PDFs. Open layout pages one by one only to collect title/link pairs.
- Do not open article pages. The article URL is used only as the `文章标题` hyperlink.
- Do not open PDFs. Set `PDF链接` to `未打开PDF`.
- If you catch yourself repeating the same plan twice, or if a tool result is truncated, stop navigation and output a partial table from already collected title/link records.
- If no related title is found after 10 kept layout pages, output `未筛选到相关消息` with the terms used and the pages checked. Do not continue searching indefinitely.

Execution template:

1. Normalize date.
2. Open `node_01.html`.
3. Extract all page labels and layout URLs from `node_01.html`.
4. Ask the industry follow-up question immediately after the page list is known, unless the user already said `默认` or provided terms.
5. Decide terms: user terms or default terms.
6. Apply a loose first-pass negative filter using page labels only.
7. Visit first-pass kept layout pages and read their visible article titles plus article URLs, capped at 10 pages.
8. Rank article links from titles only: high, medium, uncertain, low, or skip. Be loose.
9. Do not open article links by default. Record the title and article URL for high/medium/uncertain records.
10. Produce one linked-title table. Prefer HTML if easy; otherwise return a chat table.
11. Final response.

If the user explicitly requires more detailed extraction, say this DS skill is for title/link screening only and ask whether to switch to a fuller workflow.

## Core Browser Workflow

Use no more than two browser tabs at a time:

- One layout tab for `node_XX.html` pages.
- Reuse tabs. Do not open article pages or PDFs.

### Step 1: Discover Layout Pages

Open `node_01.html` once. From the DOM, collect anchors whose `href` matches:

`/rmrb/pc/layout/YYYYMM/DD/node_XX.html`

Keep only links whose visible text contains `版`, such as `01版：要闻`. At this stage, collect page labels and layout URLs first. Article titles from `node_01.html` are useful, but do not open PDFs yet.

If discovery fails, try `node_01.html` through `node_12.html` sequentially and stop after two consecutive missing pages.

### Step 2: Ask For Screening Terms And First-Pass Exclude Pages

After collecting page labels, ask exactly, unless the user already said `默认` or provided screening words in the initial request:

`是否搜集“旅游”、“美妆”、“日化”行业相关消息？若不搜索上述消息，请给出您的筛选词：___`

If the user gives custom terms, use them. If the user gives no usable terms, only confirms, or already said `默认`, use the default criteria in the Industry Follow-up Step and continue without another confirmation.

Before collecting article titles, judge each page label with a loose first-pass negative filter, not a strict keyword gate:

- Must keep: page label contains a screening term.
- Usually keep: broad labels such as `要闻`, `产经`, `消费`, `社会`, `地方`, `广告`, `文化`, `科技`, `国际`, `教育`, `副刊`; industry-relevant small items may hide there.
- Skip only if obviously unrelated: labels dominated by `党建`, `理论`, `文件`, `评论`, `政法`, `军事`, `人大`, `政协`, `组织人事`, `学习贯彻`, `党史`, `纪检`, `监察`, and there is no screening-term hit.
- If unsure, keep the page. It is better to open one extra broad page than to miss a small industry item.

Short scoring code if Python is available:

```python
def kept_pages(pages, terms):
    kept, skipped = [], []
    broad_labels = ("要闻", "产经", "消费", "社会", "地方", "广告", "文化", "科技", "国际", "教育", "副刊")
    negative_labels = ("党建", "理论", "文件", "评论", "政法", "军事", "人大", "政协", "组织人事", "党史", "纪检", "监察")
    negative_title_markers = ("学习贯彻", "党建", "党史", "理论", "纪律", "纪检", "监察")
    for p in pages:
        text = " ".join([p.get("label", ""), p.get("pageLabel", ""), " ".join(p.get("titles", []))])
        hits = [t for t in terms if t in text]
        if hits:
            p["matched_terms"] = hits
            kept.append(p)
        elif any(x in text for x in broad_labels):
            kept.append(p)
        elif any(x in text for x in negative_labels) or sum(x in text for x in negative_title_markers) >= 2:
            skipped.append(p)
        else:
            kept.append(p)
    return kept[:10], skipped + kept[10:]
```

### Step 3: Read Titles On Kept Layout Pages And Rank Article Links

For first-pass kept pages, open each layout page one at a time and read only visible article titles and article URLs. Do not open PDFs. Cap this title-reading pass at 10 layout pages.

Rank article links from titles only before ranking whole pages. Use a loose judgment: include plausible industry-adjacent titles instead of demanding exact keyword hits. If a title is hard to judge but not clearly unrelated, list it as `uncertain article` instead of dropping it.

- `high article`: title contains a screening term, close synonym, brand/category term, or concrete industry signal.
- `medium article`: title suggests policy, market, consumption, travel, retail, health, services, company, platform, product, or local economic news but has no exact term hit.
- `uncertain article`: title is broad, vague, or context-dependent, but could plausibly involve the requested industry or adjacent consumer/services topics.
- `low article`: no keyword or adjacent signal after reading the title.
- `skip article`: clearly unrelated party theory, documents, personnel, discipline inspection, military, legal procedure, or formal notices with no screening-term hit.

Do not open article pages. For every `high article`, `medium article`, and `uncertain article`, record the title and article URL from the layout page. The article URL is only used to make the title clickable.

After ranking articles, mark a page as:

- `high page`: has at least one high article.
- `medium page`: has at least one medium/uncertain article or broad page label worth checking.
- `low page`: only low articles.
- `skip page`: only skip articles and no broad label.

Optional title collection snippet:

```js
(() => [...document.querySelectorAll("a")]
  .map(a => ({ text: (a.innerText || a.textContent || "").trim(), href: a.href || "" }))
  .filter(l => /\/rmrb\/pc\/content\/\d{6}\/\d{2}\/content_\d+\.html$/.test(l.href) && l.text)
  .map(l => ({ title: l.text.replace(/^·\s*/, "").trim(), url: l.href }))
)();
```

If this snippet returns titles, continue directly to ranking. Do not inspect source code, PDF, or article pages just to prove the titles exist.

### Step 4: Create Title-Based Records Without Opening Articles

Prefer title/link extraction over opening article pages. For each selected high/medium/uncertain article link, create a record directly from the layout page.

Create one record per selected title:

- `版面`: use the page label collected from the layout page.
- `文章标题`: layout title.
- `链接`: article URL from the layout page.
- `PDF链接`: `未打开PDF`.
- `匹配依据`: matched screening terms or a short reason such as `消费/出行/服务业相关标题`; use `标题相关性待核验` for uncertain records.

如果判断困难，只要标题不是明显无关，就保留下来。标为 `uncertain article`，并在 `匹配依据` 中说明 `标题相关性待核验`。

In HTML output, make `文章标题` itself a hyperlink to the article URL, for example `<a href="ARTICLE_URL" target="_blank" rel="noopener">文章标题</a>`. In Markdown/chat table output, use `[文章标题](ARTICLE_URL)`. Do not rely on a separate plain URL column for the user to click.

For all records, keep the title-based record:

- `版面`: page label
- `文章标题`: layout title; hyperlink it to the article URL if available
- `链接`: article URL if already known, otherwise `无链接`
- `PDF链接`: `未打开PDF`

For skipped pages, do not create article records. Keep only a short internal skipped count and skipped page labels for the final response.

## Deliverables

Prefer HTML output when the environment can create or render it easily. If HTML output is not practical, return the same table in chat. Do not stall or retry just to force HTML.

The HTML table must contain:

- `版面`
- `文章标题` as a hyperlink to the article URL whenever a URL is available
- `PDF链接`
- `匹配依据`

Include a separate `链接` column only if the environment cannot render clickable titles or the user explicitly asks for raw URLs. Do not include an `摘要` column.

Continue on partial failures. Default records are title-based. Record failed page visits as `访问失败`.

## Industry Follow-up Step

In this DS version, ask this question after discovering layout pages, before title-ranking:

`是否搜集“旅游”、“美妆”、“日化”行业相关消息？若不搜索上述消息，请给出您的筛选词：___`

Then filter the extracted or fallback records:

- If the customer provides custom screening words, split them on whitespace, Chinese/English commas, semicolons, slashes, and newlines.
- If the customer does not provide usable terms, or answers only yes/confirm/blank, use the default criteria below.
- Match against article titles.
- Preserve page, clickable title, article link, PDF status, and matched terms.
- If there are no matches, report `未筛选到相关消息` and state which screening terms were used.
- The screening terms must drive first-pass page keep/skip decisions and second-pass article-title relevance ranking. Use loose negative filtering: skip only obviously unrelated pages, keep broad pages such as `要闻`, and record relevant or uncertain title/link pairs directly.

Default criteria:

```text
旅游: 旅游, 文旅, 景区, 景点, 酒店, 民宿, 旅行, 游客, 出行, 航旅, 航空, 机场, 高铁, 铁路, 邮轮, 度假, 假日, 入境游, 出境游, 乡村旅游
美妆: 美妆, 化妆品, 护肤, 彩妆, 香水, 口红, 面膜, 美容, 医美, 个护, 国货美妆, 化妆品监管
日化: 日化, 洗护, 洗涤, 清洁, 家清, 个护, 洗发, 沐浴, 牙膏, 牙刷, 纸品, 卫生巾, 消毒, 清洁用品
```

Short filter code if Python is available:

```python
import re

DEFAULT_TERMS = "旅游 文旅 景区 景点 酒店 民宿 旅行 游客 出行 航旅 航空 机场 高铁 铁路 邮轮 度假 假日 入境游 出境游 乡村旅游 美妆 化妆品 护肤 彩妆 香水 口红 面膜 美容 医美 个护 国货美妆 化妆品监管 日化 洗护 洗涤 清洁 家清 洗发 沐浴 牙膏 牙刷 纸品 卫生巾 消毒 清洁用品".split()

def screening_terms(answer):
    terms = [x.strip() for x in re.split(r"[\s,，;；/、\n]+", answer or "") if x.strip()]
    weak_yes = {"是", "需要", "要", "好", "可以", "yes", "y", "ok", "默认"}
    return DEFAULT_TERMS if not terms or all(x.lower() in weak_yes for x in terms) else terms

def match_records(records, terms):
    out = []
    for r in records:
        text = " ".join(str(r.get(k, "")) for k in ("版面", "page", "文章标题", "title"))
        hits = [t for t in terms if t in text]
        if hits:
            item = dict(r)
            item["matched_terms"] = hits
            out.append(item)
    return out
```

## Final Response

Report:

- extraction date
- processed page count
- skipped page count
- extracted article count
- failed page count
- matched count
- HTML output location, or the complete chat table if HTML was not practical
