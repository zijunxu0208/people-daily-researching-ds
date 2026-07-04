#!/usr/bin/env python3
"""Extract People's Daily e-paper article summaries for one date.

Usage:
    python3 scripts/extract_people_daily.py 20260630 --out outputs
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen


USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36"
)


@dataclass
class Article:
    page: str
    title: str
    summary: str
    pdf: str
    url: str


@dataclass
class Page:
    node: str
    label: str
    url: str
    pdf: str
    articles: list[dict[str, str]]
    ok: bool = True
    error: str = ""


class PeopleDailyHTMLParser(HTMLParser):
    """Small HTML extractor tailored to the People's Daily e-paper pages."""

    def __init__(self, base_url: str):
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.links: list[dict[str, str]] = []
        self.paragraphs: list[str] = []
        self.body_text_parts: list[str] = []
        self.h1 = ""
        self.title = ""
        self._ignore_depth = 0
        self._link: dict[str, object] | None = None
        self._p_parts: list[str] | None = None
        self._h1_parts: list[str] | None = None
        self._title_parts: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = {k.lower(): v or "" for k, v in attrs}
        tag = tag.lower()
        if tag in {"script", "style", "noscript"}:
            self._ignore_depth += 1
            return
        if self._ignore_depth:
            return
        if tag == "a":
            self._link = {"href": urljoin(self.base_url, attrs_dict.get("href", "")), "parts": []}
        elif tag == "p":
            self._p_parts = []
        elif tag == "h1":
            self._h1_parts = []
        elif tag == "title":
            self._title_parts = []

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in {"script", "style", "noscript"} and self._ignore_depth:
            self._ignore_depth -= 1
            return
        if self._ignore_depth:
            return
        if tag == "a" and self._link is not None:
            text = normalize_text("".join(self._link["parts"]))  # type: ignore[index]
            href = str(self._link["href"])
            self.links.append({"text": text, "href": href})
            self._link = None
        elif tag == "p" and self._p_parts is not None:
            text = normalize_text("".join(self._p_parts))
            if text:
                self.paragraphs.append(text)
            self._p_parts = None
        elif tag == "h1" and self._h1_parts is not None:
            text = normalize_text("".join(self._h1_parts))
            if text:
                self.h1 = text
            self._h1_parts = None
        elif tag == "title" and self._title_parts is not None:
            text = normalize_text("".join(self._title_parts))
            if text:
                self.title = text
            self._title_parts = None

    def handle_data(self, data: str) -> None:
        if self._ignore_depth:
            return
        if self._link is not None:
            self._link["parts"].append(data)  # type: ignore[index,union-attr]
        if self._p_parts is not None:
            self._p_parts.append(data)
        if self._h1_parts is not None:
            self._h1_parts.append(data)
        if self._title_parts is not None:
            self._title_parts.append(data)
        if data.strip():
            self.body_text_parts.append(data)

    @property
    def body_text(self) -> str:
        return normalize_text("\n".join(self.body_text_parts))


def normalize_text(value: str) -> str:
    return re.sub(r"\n{2,}", "\n", re.sub(r"[ \t\r\f\u3000\xa0]+", " ", value)).strip()


def parse_date(raw: str) -> tuple[str, str, str, str]:
    digits = re.findall(r"\d+", raw)
    if len(digits) == 1 and re.fullmatch(r"\d{8}", digits[0]):
        dt = datetime.strptime(digits[0], "%Y%m%d")
    elif len(digits) >= 3:
        dt = datetime(int(digits[0]), int(digits[1]), int(digits[2]))
    else:
        raise ValueError("date must look like 20260630, 2026-06-30, or 2026年6月30日")
    return dt.strftime("%Y"), dt.strftime("%m"), dt.strftime("%d"), dt.strftime("%Y%m%d")


def fetch(url: str, timeout: int, retries: int) -> str:
    last_error: Exception | None = None
    for attempt in range(retries + 1):
        try:
            req = Request(url, headers={"User-Agent": USER_AGENT})
            with urlopen(req, timeout=timeout) as resp:
                data = resp.read()
                content_type = resp.headers.get("Content-Type", "")
            charset_match = re.search(r"charset=([\w-]+)", content_type, re.I)
            encodings = [charset_match.group(1)] if charset_match else []
            encodings.extend(["utf-8", "gb18030"])
            for encoding in encodings:
                try:
                    return data.decode(encoding)
                except UnicodeDecodeError:
                    pass
            return data.decode("utf-8", errors="replace")
        except (HTTPError, URLError, TimeoutError, OSError) as exc:
            last_error = exc
            if attempt < retries:
                time.sleep(0.8 * (attempt + 1))
    raise RuntimeError(f"failed to fetch {url}: {last_error}")


def parse_html(text: str, base_url: str) -> PeopleDailyHTMLParser:
    parser = PeopleDailyHTMLParser(base_url)
    parser.feed(text)
    parser.close()
    return parser


def layout_url(year: str, month: str, day: str, node: str = "01") -> str:
    return f"https://paper.people.com.cn/rmrb/pc/layout/{year}{month}/{day}/node_{node}.html"


def discover_pages(first_parser: PeopleDailyHTMLParser, year: str, month: str, day: str) -> list[dict[str, str]]:
    pattern = re.compile(rf"/rmrb/pc/layout/{year}{month}/{day}/node_(\d{{2}})\.html$")
    pages: dict[str, dict[str, str]] = {}
    for link in first_parser.links:
        match = pattern.search(link["href"])
        if not match:
            continue
        text = link["text"]
        if "版" not in text:
            continue
        node = match.group(1)
        pages[node] = {"node": node, "label": text, "url": link["href"]}
    if not pages:
        pages["01"] = {"node": "01", "label": "第01版", "url": layout_url(year, month, day, "01")}
    return [pages[node] for node in sorted(pages)]


def page_label(parser: PeopleDailyHTMLParser, fallback: str) -> str:
    match = re.search(r"第?\d{2}版[:：][^\n]+", parser.body_text)
    if match:
        text = match.group(0)
        return text if text.startswith("第") else "第" + text
    return fallback


def extract_page(info: dict[str, str], year: str, month: str, day: str, timeout: int, retries: int) -> Page:
    try:
        text = fetch(info["url"], timeout, retries)
        parser = parse_html(text, info["url"])
        pdf = next(
            (link["href"] for link in parser.links if ".pdf" in link["href"].lower() or "PDF" in link["text"].upper()),
            "",
        )
        article_re = re.compile(rf"/rmrb/pc/content/{year}{month}/{day}/content_\d+\.html$")
        seen: set[str] = set()
        articles: list[dict[str, str]] = []
        for link in parser.links:
            if not article_re.search(link["href"]):
                continue
            title = link["text"].lstrip("· ").strip()
            if not title or link["href"] in seen:
                continue
            seen.add(link["href"])
            articles.append({"title": title, "url": link["href"]})
        return Page(
            node=info["node"],
            label=page_label(parser, info["label"]),
            url=info["url"],
            pdf=pdf,
            articles=articles,
        )
    except Exception as exc:  # Keep the run going when one page fails.
        return Page(
            node=info["node"],
            label=info["label"],
            url=info["url"],
            pdf="",
            articles=[],
            ok=False,
            error=str(exc),
        )


def is_noise_paragraph(text: str, expected_title: str, doc_title: str) -> bool:
    if len(text) < 8:
        return True
    if text in {expected_title, doc_title}:
        return True
    noise_patterns = [
        r"^(日报|周报|杂志|本版新闻|返回目录|放大|缩小|全文复制|上一篇|下一篇|版权声明)",
        r"^第\d{2}版[:：]",
        r"^人民日报\s*\d{4}年\d{2}月\d{2}日",
        r"^《人民日报》\s*（?\(?\d{4}年\d{2}月\d{2}日",
        r"^人 民 网 版 权 所 有",
        r"^Copyright ",
    ]
    if any(re.search(pattern, text) for pattern in noise_patterns):
        return True
    if (text.endswith("摄") or re.search(r"摄$", text)) and len(text) < 120:
        return True
    if re.search(r"记者\s*[\u4e00-\u9fff]{2,4}摄$", text) and len(text) < 160:
        return True
    return False


def summarize(text: str, limit: int = 200) -> str:
    text = normalize_text(text).lstrip("　 ")
    return "".join(list(text)[:limit]) if text else "无法提取文本"


def extract_article_summary(article: dict[str, str], timeout: int, retries: int) -> tuple[str, str]:
    text = fetch(article["url"], timeout, retries)
    parser = parse_html(text, article["url"])
    doc_title = parser.h1 or parser.title or article["title"]
    seen: set[str] = set()
    for para in parser.paragraphs:
        para = normalize_text(para)
        if not para or para in seen:
            continue
        seen.add(para)
        if not is_noise_paragraph(para, article["title"], doc_title):
            return doc_title, summarize(para)
    for part in parser.body_text.splitlines():
        part = normalize_text(part)
        if part and not is_noise_paragraph(part, article["title"], doc_title):
            return doc_title, summarize(part)
    return doc_title, "无法提取文本"


def build_html(date_label: str, pages_count: int, articles: Iterable[Article]) -> str:
    articles = list(articles)
    rows = "\n".join(
        "      <tr>"
        f"<td>{html.escape(article.page)}</td>"
        f"<td><a href=\"{html.escape(article.url)}\" target=\"_blank\" rel=\"noopener\">{html.escape(article.title)}</a></td>"
        f"<td>{html.escape(article.summary)}</td>"
        f"<td>{f'<a href=\"{html.escape(article.pdf)}\" target=\"_blank\" rel=\"noopener\">PDF</a>' if article.pdf else '无PDF'}</td>"
        "</tr>"
        for article in articles
    )
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>人民日报 {date_label} 报道摘要</title>
<style>
  body {{ margin: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; color: #1f2328; background: #f6f8fa; }}
  .wrap {{ max-width: 1240px; margin: 0 auto; padding: 28px 20px 44px; }}
  h1 {{ font-size: 24px; margin: 0 0 8px; }}
  .meta {{ color: #59636e; margin: 0 0 18px; font-size: 14px; }}
  .table-wrap {{ overflow-x: auto; background: #fff; border: 1px solid #d8dee4; border-radius: 8px; }}
  table {{ width: 100%; border-collapse: collapse; table-layout: fixed; }}
  th, td {{ border-bottom: 1px solid #d8dee4; padding: 10px 12px; vertical-align: top; line-height: 1.55; }}
  th {{ background: #f0f3f6; text-align: left; font-size: 14px; cursor: pointer; user-select: none; white-space: nowrap; }}
  tr:last-child td {{ border-bottom: 0; }}
  td:nth-child(1) {{ width: 120px; color: #59636e; }}
  td:nth-child(2) {{ width: 280px; font-weight: 600; }}
  td:nth-child(4) {{ width: 72px; white-space: nowrap; }}
  a {{ color: #0969da; text-decoration: none; }}
  a:hover {{ text-decoration: underline; }}
  @media (max-width: 760px) {{ .wrap {{ padding: 18px 12px 32px; }} table {{ min-width: 860px; }} h1 {{ font-size: 20px; }} }}
</style>
</head>
<body>
<div class="wrap">
  <h1>人民日报 {html.escape(date_label)} 报道摘要</h1>
  <p class="meta">共处理 {pages_count} 个版面，提取 {len(articles)} 篇文章。点击表头可排序。</p>
  <div class="table-wrap">
    <table id="summaryTable">
      <thead><tr><th>版面</th><th>文章标题</th><th>摘要</th><th>PDF链接</th></tr></thead>
      <tbody>
{rows}
      </tbody>
    </table>
  </div>
</div>
<script>
  document.querySelectorAll('th').forEach((th, col) => {{
    th.addEventListener('click', () => {{
      const table = th.closest('table');
      const body = table.tBodies[0];
      const asc = th.dataset.asc !== 'true';
      [...body.rows]
        .sort((a, b) => a.cells[col].innerText.localeCompare(b.cells[col].innerText, 'zh-Hans') * (asc ? 1 : -1))
        .forEach(row => body.appendChild(row));
      document.querySelectorAll('th').forEach(h => delete h.dataset.asc);
      th.dataset.asc = String(asc);
    }});
  }});
</script>
</body>
</html>
"""


def run(args: argparse.Namespace) -> int:
    year, month, day, yyyymmdd = parse_date(args.date)
    first_url = layout_url(year, month, day)
    first_parser = parse_html(fetch(first_url, args.timeout, args.retries), first_url)
    page_infos = discover_pages(first_parser, year, month, day)

    pages = [extract_page(info, year, month, day, args.timeout, args.retries) for info in page_infos]
    articles: list[Article] = []
    failures: list[dict[str, str]] = []

    for page in pages:
        if not page.ok:
            failures.append({"url": page.url, "error": page.error})
            continue
        for article_info in page.articles:
            try:
                doc_title, summary = extract_article_summary(article_info, args.timeout, args.retries)
                articles.append(
                    Article(
                        page=page.label,
                        title=article_info["title"] or doc_title,
                        summary=summary,
                        pdf=page.pdf,
                        url=article_info["url"],
                    )
                )
            except Exception as exc:
                failures.append({"url": article_info["url"], "error": str(exc)})
                articles.append(
                    Article(
                        page=page.label,
                        title=article_info["title"],
                        summary="访问失败",
                        pdf=page.pdf,
                        url=article_info["url"],
                    )
                )

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = f"人民日报_{yyyymmdd}_报道摘要"
    html_path = out_dir / f"{stem}.html"
    json_path = out_dir / f"{stem}.json"
    date_label = f"{year}年{month}月{day}日"

    html_path.write_text(build_html(date_label, len(pages), articles), encoding="utf-8")
    json_path.write_text(
        json.dumps(
            {
                "date": yyyymmdd,
                "first_url": first_url,
                "pages": [asdict(page) for page in pages],
                "records": [asdict(article) for article in articles],
                "failures": failures,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print(f"提取日期: {yyyymmdd}")
    print(f"处理版面: {len(pages)}")
    print(f"提取文章: {len(articles)}")
    print(f"失败记录: {len(failures)}")
    print(f"HTML: {html_path}")
    print(f"JSON: {json_path}")
    return 0 if not failures else 2


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract People's Daily e-paper summaries.")
    parser.add_argument("date", help="Date like 20260630, 2026-06-30, or 2026年6月30日")
    parser.add_argument("--out", default="outputs", help="Output directory, default: outputs")
    parser.add_argument("--timeout", type=int, default=25, help="Network timeout in seconds")
    parser.add_argument("--retries", type=int, default=2, help="Fetch retries per URL")
    args = parser.parse_args()
    try:
        return run(args)
    except KeyboardInterrupt:
        print("Interrupted", file=sys.stderr)
        return 130
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
