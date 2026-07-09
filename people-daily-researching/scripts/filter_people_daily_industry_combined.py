#!/usr/bin/env python3
"""
Filter both People's Daily domestic edition and Overseas Edition by industry keywords,
produce individual HTML/JSON files for each edition, and merge them into one combined HTML.

Produces:
  - 人民日报_YYYYMMDD_行业筛选.json
  - 人民日报_YYYYMMDD_行业筛选.html
  - 人民日报海外版_YYYYMMDD_行业筛选.json
  - 人民日报海外版_YYYYMMDD_行业筛选.html
  - 人民日报_YYYYMMDD_海内外行业筛选.html
"""
import argparse
import json
import os
import re
import subprocess
import sys
from html import escape

SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))


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


def run_script(script_name, json_file, response, out_dir):
    script_path = os.path.join(SCRIPTS_DIR, script_name)
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    result = subprocess.run(
        [sys.executable, script_path, json_file, "--response", response, "--out", out_dir],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
    )
    return result


def load_json(path):
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def build_combined_html(domestic_records, overseas_records, date_str):
    lines = [
        "<!DOCTYPE html>",
        '<html lang="zh-CN">',
        "<head>",
        '<meta charset="UTF-8">',
        f"<title>人民日报 {date_str} 海内外行业筛选</title>",
        "<style>"
        "body{font-family:SimSun,Microsoft YaHei,sans-serif;max-width:900px;margin:0 auto;padding:20px;}"
        "h1{text-align:center;}"
        "h2{border-bottom:2px solid #c00;margin-top:30px;}"
        ".article{margin:10px 0;padding:10px;border-left:3px solid #c00;}"
        ".summary{color:#333;}"
        ".meta{color:#666;font-size:0.9em;}"
        ".no-match{color:#999;font-style:italic;}"
        "</style>",
        "</head>",
        "<body>",
        f"<h1>人民日报 {date_str} 海内外行业筛选</h1>",
    ]

    sections = [
        ("人民日报", domestic_records),
        ("人民日报海外版", overseas_records),
    ]

    for edition_name, records in sections:
        lines.append(f"<h2>{escape(edition_name)}</h2>")
        if not records:
            lines.append(f'<p class="no-match">{escape(edition_name)}：未筛选到相关消息。</p>')
            continue
        for r in records:
            lines.append('<div class="article">')
            lines.append(
                f'<h3><a href="{r["文章链接"]}" target="_blank">{escape(r["文章标题"])}</a></h3>'
            )
            lines.append(f'<p class="summary">{escape(r["摘要"])}</p>')
            lines.append(
                f'<p class="meta">版面：{escape(r["版面"])} | '
                f'匹配行业：{escape(r["匹配行业"])} | '
                f'匹配关键词：{escape(r["匹配关键词"])}</p>'
            )
            lines.append(
                f'<p class="meta">PDF链接：<a href="{r["PDF链接"]}" target="_blank">{r["PDF链接"]}</a></p>'
            )
            lines.append("</div>")

    lines.extend(["</body>", "</html>"])
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("date", help="Date in YYYYMMDD, YYYY-MM-DD or YYYY年M月D日")
    parser.add_argument("--response", default="默认", help="Filter response: 默认 or custom terms")
    parser.add_argument("--out", default="outputs", help="Output directory")
    args = parser.parse_args()

    year, month, day = parse_date(args.date)
    date_str = f"{year}{month}{day}"

    out_dir = args.out
    os.makedirs(out_dir, exist_ok=True)

    dom_json = os.path.join(out_dir, f"人民日报_{date_str}_报道摘要.json")
    hwb_json = os.path.join(out_dir, f"人民日报海外版_{date_str}_报道摘要.json")

    dom_result = run_script(
        "filter_people_daily_industry.py", dom_json, args.response, out_dir
    )
    hwb_result = run_script(
        "filter_people_daily_industry_hwb.py", hwb_json, args.response, out_dir
    )

    if dom_result.stdout:
        print(dom_result.stdout, end="")
    if dom_result.stderr:
        print(dom_result.stderr, end="", file=sys.stderr)
    if hwb_result.stdout:
        print(hwb_result.stdout, end="")
    if hwb_result.stderr:
        print(hwb_result.stderr, end="", file=sys.stderr)

    dom_filter_json = os.path.join(out_dir, f"人民日报_{date_str}_行业筛选.json")
    hwb_filter_json = os.path.join(out_dir, f"人民日报海外版_{date_str}_行业筛选.json")

    domestic_records = load_json(dom_filter_json)
    overseas_records = load_json(hwb_filter_json)

    combined_html_path = os.path.join(out_dir, f"人民日报_{date_str}_海内外行业筛选.html")
    with open(combined_html_path, "w", encoding="utf-8") as f:
        f.write(build_combined_html(domestic_records, overseas_records, date_str))

    total = len(domestic_records) + len(overseas_records)
    print(f"Combined filtered records: {total}")
    print(f"Combined HTML: {combined_html_path}")


if __name__ == "__main__":
    main()
