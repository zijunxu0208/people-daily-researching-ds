#!/usr/bin/env python3
"""
Extract People's Daily Overseas Edition (人民日报海外版) e-paper reports for a given date.
Produces:
  - 人民日报海外版_YYYYMMDD_报道摘要.json
  - 人民日报海外版_YYYYMMDD_报道摘要.html
"""
import argparse
import json
import os
import re
import urllib.request
from urllib.parse import urljoin
from html import escape

BASE_URL = "https://paper.people.com.cn/rmrbhwb/pc"


def fetch(url, timeout=20):
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = resp.read()
        try:
            return data.decode("utf-8")
        except UnicodeDecodeError:
            return data.decode("gbk", errors="ignore")


def parse_date(date_str):
    m = re.match(r"(\d{4})(\d{2})(\d{2})$", date_str)
    if m:
        return m.group(1), m.group(2), m.group(3)
    m = re.match(r"(\d{4})-(\d{1,2})-(\d{1,2})$", date_str)
    if m:
        return m.group(1), m.group(2).zfill(2), m.group(3).zfill(2)
    m = re.match(r"(\d{4})年(\d{1,2})月(\d{1,2})日$", date_str)
    if m:
        return m.group(1), m.group(2).zfill(2), m.group(3).zfill(2)
    raise ValueError(f"Unsupported date format: {date_str}")


def discover_nodes(layout_url):
    html = fetch(layout_url)
    nodes = []
    seen = set()
    for href in re.findall(r'href=["\']?([^"\'>\s]*node_\d+\.html)["\']?', html):
        abs_href = urljoin(layout_url, href)
        name = os.path.basename(abs_href)
        if name not in seen and "/rmrbhwb/pc/layout/" in abs_href:
            seen.add(name)
            nodes.append((name, abs_href))
    nodes.sort(key=lambda x: int(re.search(r"node_(\d+)", x[0]).group(1)))
    return nodes


def extract_page_name(html, node_name):
    page_num = re.search(r"node_(\d+)", node_name).group(1)
    slides = re.findall(
        r'<div[^>]*class=["\'][^"\']*swiper-slide[^"\']*["\'][^>]*>(.*?)</div>',
        html,
        re.S | re.I,
    )
    for s in slides:
        text = re.sub(r"<[^>]+>", "", s).strip()
        if text.startswith(page_num):
            return text
    return f"第{int(page_num)}版"


def extract_pdf_url(html, base_url):
    pdfs = re.findall(r'href=["\']?([^"\'>\s]*\.pdf)["\']?', html, re.I)
    for p in pdfs:
        abs_pdf = urljoin(base_url, p)
        if "/rmrbhwb/pc/" in abs_pdf:
            return abs_pdf
    return "无PDF"


def extract_article_links(html, base_url):
    links = []
    seen = set()
    for href in re.findall(r'href=["\']?([^"\'>\s]*content_\d+\.html)["\']?', html):
        abs_href = urljoin(base_url, href)
        if abs_href not in seen and "/rmrbhwb/pc/content/" in abs_href:
            seen.add(abs_href)
            links.append(abs_href)
    return links


def extract_article(url):
    try:
        html = fetch(url)
    except Exception as e:
        return {"title": "访问失败", "summary": f"访问失败: {e}", "url": url}

    title = ""
    m = re.search(r"<title[^>]*>(.*?)</title>", html, re.S | re.I)
    if m:
        title = re.sub(r"<[^>]+>", "", m.group(1)).strip()
    m = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.S | re.I)
    if m:
        h1 = re.sub(r"<[^>]+>", "", m.group(1)).strip()
        if h1:
            title = h1

    summary = ""
    m = re.search(
        r'id=["\']articleContent["\'][^>]*>(.*?)</div>', html, re.S | re.I
    )
    if m:
        text = re.sub(r"<[^>]+>", " ", m.group(1))
        text = re.sub(r"&nbsp;", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        text = re.sub(r"^[>\s]+", "", text)
        sentences = re.split(r"(?<=[。！？])", text)
        for s in sentences:
            summary += s
            if len(summary) >= 100:
                break
        if not summary:
            summary = text[:300]
    if not summary:
        summary = title or "无摘要"

    return {"title": title or "无标题", "summary": summary, "url": url}


def build_html(records, date_str):
    lines = [
        "<!DOCTYPE html>",
        '<html lang="zh-CN">',
        "<head>",
        '<meta charset="UTF-8">',
        f"<title>人民日报海外版 {date_str} 报道摘要</title>",
        "<style>"
        "body{font-family:SimSun,Microsoft YaHei,sans-serif;max-width:900px;margin:0 auto;padding:20px;}"
        "h1{text-align:center;}"
        "h2{border-bottom:1px solid #ccc;}"
        ".article{margin:10px 0;padding:10px;border-left:3px solid #c00;}"
        ".summary{color:#333;}"
        ".meta{color:#666;font-size:0.9em;}"
        "</style>",
        "</head>",
        "<body>",
        f"<h1>人民日报海外版 {date_str} 报道摘要</h1>",
    ]
    current_page = None
    for r in records:
        if r["版面"] != current_page:
            current_page = r["版面"]
            lines.append(f"<h2>{escape(current_page)}</h2>")
        lines.append('<div class="article">')
        lines.append(
            f'<h3><a href="{r["文章链接"]}" target="_blank">{escape(r["文章标题"])}</a></h3>'
        )
        lines.append(f'<p class="summary">{escape(r["摘要"])}</p>')
        pdf = r["PDF链接"]
        lines.append(
            f'<p class="meta">PDF链接：<a href="{pdf}" target="_blank">{pdf}</a></p>'
        )
        lines.append("</div>")
    lines.extend(["</body>", "</html>"])
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("date", help="Date in YYYYMMDD, YYYY-MM-DD or YYYY年M月D日")
    parser.add_argument("--out", default="outputs", help="Output directory")
    args = parser.parse_args()

    year, month, day = parse_date(args.date)
    date_path = f"{year}{month}/{day}"
    date_str = f"{year}{month}{day}"

    out_dir = args.out
    os.makedirs(out_dir, exist_ok=True)

    first_layout = f"{BASE_URL}/layout/{date_path}/node_01.html"
    nodes = discover_nodes(first_layout)

    records = []
    failures = 0

    for node_name, node_url in nodes:
        page_num = re.search(r"node_(\d+)", node_name).group(1)
        try:
            html = fetch(node_url)
        except Exception as e:
            failures += 1
            records.append(
                {
                    "版面": f"第{int(page_num)}版（访问失败）",
                    "文章标题": "访问失败",
                    "摘要": str(e),
                    "PDF链接": "无PDF",
                    "文章链接": node_url,
                }
            )
            continue

        page_name = extract_page_name(html, node_name)
        pdf_url = extract_pdf_url(html, node_url)
        article_urls = extract_article_links(html, node_url)

        if not article_urls:
            records.append(
                {
                    "版面": page_name,
                    "文章标题": "（无文章）",
                    "摘要": "",
                    "PDF链接": pdf_url,
                    "文章链接": node_url,
                }
            )

        for art_url in article_urls:
            art = extract_article(art_url)
            if art["title"] == "访问失败":
                failures += 1
            records.append(
                {
                    "版面": page_name,
                    "文章标题": art["title"],
                    "摘要": art["summary"],
                    "PDF链接": pdf_url,
                    "文章链接": art_url,
                }
            )

    json_path = os.path.join(out_dir, f"人民日报海外版_{date_str}_报道摘要.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)

    html_path = os.path.join(out_dir, f"人民日报海外版_{date_str}_报道摘要.html")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(build_html(records, date_str))

    article_count = len(
        [
            r
            for r in records
            if r["文章标题"] not in ("访问失败", "（无文章）")
        ]
    )
    print(f"Extraction complete: {date_str}")
    print(f"Pages: {len(nodes)}, Articles: {article_count}, Failures: {failures}")
    print(f"JSON: {json_path}")
    print(f"HTML: {html_path}")


if __name__ == "__main__":
    main()
