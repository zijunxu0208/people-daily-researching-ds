#!/usr/bin/env python3
from __future__ import annotations

import argparse
import html
import json
import re
from pathlib import Path


DEFAULT_TERMS = [
    "旅游", "文旅", "景区", "景点", "酒店", "民宿", "旅行", "游客", "出行", "航旅", "航空", "机场", "高铁", "铁路", "邮轮", "度假", "假日", "入境游", "出境游", "乡村旅游",
    "美妆", "化妆品", "护肤", "彩妆", "香水", "口红", "面膜", "美容", "医美", "个护", "国货美妆", "化妆品监管",
    "日化", "洗护", "洗涤", "清洁", "家清", "洗发", "沐浴", "牙膏", "牙刷", "纸品", "卫生巾", "消毒", "清洁用品",
]


def split_screening_terms(response: str) -> list[str]:
    terms = [t.strip() for t in re.split(r"[\s,，;；/、\n]+", response or "") if t.strip()]
    weak_yes = {"是", "需要", "要", "好", "可以", "yes", "y", "ok", "默认"}
    if not terms or all(t.lower() in weak_yes for t in terms):
        return DEFAULT_TERMS
    return terms


def filter_records(records: list[dict], terms: list[str]) -> list[dict]:
    matched = []
    for record in records:
        haystack = " ".join(str(record.get(k, "")) for k in ("title", "summary", "body", "page"))
        if any(term and term in haystack for term in terms):
            matched.append(record)
    return matched


def build_html(date_label: str, terms: list[str], records: list[dict]) -> str:
    if records:
        row_parts = []
        for record in records:
            pdf = str(record.get("pdf", ""))
            pdf_cell = f'<a href="{html.escape(pdf)}" target="_blank" rel="noopener">PDF</a>' if pdf else "无PDF"
            row_parts.append(
                "      <tr>"
                f"<td>{html.escape(str(record.get('page', '')))}</td>"
                f"<td><a href=\"{html.escape(str(record.get('url', '')))}\" target=\"_blank\" rel=\"noopener\">{html.escape(str(record.get('title', '')))}</a></td>"
                f"<td>{html.escape(str(record.get('summary', '')))}</td>"
                f"<td>{pdf_cell}</td>"
                "</tr>"
            )
        rows = "\n".join(row_parts)
    else:
        rows = '      <tr><td colspan="4">未筛选到相关消息</td></tr>'

    return f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>人民日报 {html.escape(date_label)} 行业筛选</title>
<style>
  body {{ margin: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; color: #1f2328; background: #f6f8fa; }}
  .wrap {{ max-width: 1240px; margin: 0 auto; padding: 28px 20px 44px; }}
  h1 {{ font-size: 24px; margin: 0 0 8px; }}
  .meta {{ color: #59636e; margin: 0 0 18px; font-size: 14px; line-height: 1.6; }}
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
  <h1>人民日报 {html.escape(date_label)} 行业筛选</h1>
  <p class="meta">筛选词：{html.escape('、'.join(terms))}<br>筛选结果：{len(records)} 条。</p>
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


def main() -> int:
    parser = argparse.ArgumentParser(description="Filter extracted People's Daily records by industry terms.")
    parser.add_argument("json_path")
    parser.add_argument("--response", default="默认")
    parser.add_argument("--out", default="outputs")
    args = parser.parse_args()

    data = json.loads(Path(args.json_path).read_text(encoding="utf-8"))
    yyyymmdd = str(data["date"])
    date_label = f"{yyyymmdd[:4]}年{yyyymmdd[4:6]}月{yyyymmdd[6:]}日"
    terms = split_screening_terms(args.response)
    matched = filter_records(data.get("records", []), terms)

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    html_path = out_dir / f"人民日报_{yyyymmdd}_行业筛选.html"
    json_path = out_dir / f"人民日报_{yyyymmdd}_行业筛选.json"

    html_path.write_text(build_html(date_label, terms, matched), encoding="utf-8")
    json_path.write_text(
        json.dumps(
            {"date": yyyymmdd, "terms": terms, "records": matched, "count": len(matched)},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print(f"筛选日期: {yyyymmdd}")
    print(f"筛选词数: {len(terms)}")
    print(f"命中记录: {len(matched)}")
    if not matched:
        print("未筛选到相关消息")
    print(f"HTML: {html_path}")
    print(f"JSON: {json_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
