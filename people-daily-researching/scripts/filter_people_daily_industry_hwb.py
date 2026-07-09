#!/usr/bin/env python3
"""
Filter People's Daily Overseas Edition extraction by industry keywords.
Produces:
  - 人民日报海外版_YYYYMMDD_行业筛选.html
  - 人民日报海外版_YYYYMMDD_行业筛选.json (when matches exist)
"""
import argparse
import json
import os
import re
from html import escape

DEFAULT_TERMS = {
      "美妆": [
        "美妆", "化妆品", "护肤", "彩妆", "香水", "口红", "面膜", "美容",
        "医美", "个护", "国货美妆", "化妆品监管", "欧莱雅", "联合利华",
        "资生堂", "上海家化", "雅诗兰黛", "Olay", "OLAY", "SK-II"
    ],
      "日化": [
        "日化", "洗护", "洗涤", "清洁", "家清", "个护", "洗发", "沐浴",
        "牙膏", "牙刷", "纸品", "卫生巾", "消毒", "清洁用品", " 护舒宝",
        "丹碧丝", "佳洁士", "欧乐B", "当妮", "汰渍", "碧浪", "舒肤佳",
        "飘柔", "潘婷", "海飞丝", "吉列", "博朗", "帮宝适", "原料", "纸尿裤", "婴幼", "剃须"
    ],
     "监管": [
       "原料", "法律", "化妆品监管", "抽检", "备案", "广告宣传", "质量安全", "召回", "虚假宣传", "消费投诉", "价格监管", "进口化妆品","规定","新规","药监局"
    ],
}


def load_learned_terms():
    """Load user-learned keywords from keywords.json next to this script."""
    learned_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "keywords.json")
    if not os.path.exists(learned_path):
        return {}
    try:
        with open(learned_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return {k: v for k, v in data.items() if isinstance(v, list)}
    except Exception:
        return {}


def merge_terms(default, learned):
    """Merge default and learned terms, preserving order and removing duplicates."""
    merged = {}
    for category, keywords in default.items():
        merged[category] = list(dict.fromkeys(keywords + learned.get(category, [])))
    for category, keywords in learned.items():
        if category not in merged:
            merged[category] = keywords
    return merged


def parse_response(response):
    response = response.strip()
    if not response or response in ("默认", "是", "确认", "yes", "Y"):
        return None
    return [t.strip() for t in re.split(r"[\s,;，、/\n]+", response) if t.strip()]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("json_file")
    parser.add_argument("--response", default="默认")
    parser.add_argument("--out", default="outputs")
    args = parser.parse_args()

    with open(args.json_file, "r", encoding="utf-8") as f:
        records = json.load(f)

    date_match = re.search(
        r"人民日报海外版_(\d{8})_报道摘要\.json", os.path.basename(args.json_file)
    )
    date_str = date_match.group(1) if date_match else "unknown"

    custom = parse_response(args.response)
    if custom is not None:
        terms = {"自定义": custom}
    else:
        terms = merge_terms(DEFAULT_TERMS, load_learned_terms())

    matched = []
    for r in records:
        text = f"{r.get('文章标题', '')} {r.get('摘要', '')}"
        for category, keywords in terms.items():
            hit = False
            for kw in keywords:
                if kw in text:
                    r2 = dict(r)
                    r2["匹配行业"] = category
                    r2["匹配关键词"] = kw
                    matched.append(r2)
                    hit = True
                    break
            if hit:
                break

    os.makedirs(args.out, exist_ok=True)

    if matched:
        json_path = os.path.join(args.out, f"人民日报海外版_{date_str}_行业筛选.json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(matched, f, ensure_ascii=False, indent=2)

    html_path = os.path.join(args.out, f"人民日报海外版_{date_str}_行业筛选.html")
    lines = [
        "<!DOCTYPE html>",
        '<html lang="zh-CN">',
        "<head>",
        '<meta charset="UTF-8">',
        f"<title>人民日报海外版 {date_str} 行业筛选</title>",
        "<style>"
        "body{font-family:SimSun,Microsoft YaHei,sans-serif;max-width:900px;margin:0 auto;padding:20px;}"
        "h1{text-align:center;}"
        ".article{margin:10px 0;padding:10px;border-left:3px solid #c00;}"
        ".summary{color:#333;}"
        ".meta{color:#666;font-size:0.9em;}"
        "</style>",
        "</head>",
        "<body>",
        f"<h1>人民日报海外版 {date_str} 行业筛选</h1>",
        f"<p>筛选条件：{escape(str(list(terms.keys())))}</p>",
    ]
    if matched:
        for r in matched:
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
    else:
        lines.append(f"<p>未筛选到相关消息。</p>")
        lines.append(f"<p>使用的筛选词：{escape(json.dumps(terms, ensure_ascii=False))}</p>")
    lines.extend(["</body>", "</html>"])

    with open(html_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    if matched:
        print(f"Filtered {len(matched)} records.")
        print(f"JSON: {json_path}")
    else:
        print("未筛选到相关消息")
    print(f"HTML: {html_path}")


if __name__ == "__main__":
    main()
