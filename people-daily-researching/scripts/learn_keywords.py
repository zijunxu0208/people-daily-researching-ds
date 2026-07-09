#!/usr/bin/env python3
"""
Learn new industry keywords from a user-provided article URL.

Analyzes the page text, determines which default categories (美妆/日化/监管)
are relevant, extracts co-occurring candidate terms, and appends them to
scripts/keywords.json. The filter scripts automatically load keywords.json
on the next run.

Usage:
    python3 learn_keywords.py <URL> [--category 美妆|日化|监管] [--dry-run]
"""
import argparse
import json
import os
import re
import sys
import urllib.request
from html.parser import HTMLParser

DEFAULT_TERMS = {
    "美妆": [
        "美妆", "化妆品", "护肤", "彩妆", "香水", "口红", "面膜", "美容",
        "医美", "个护", "国货美妆", "化妆品监管", "欧莱雅", "联合利华",
        "资生堂", "上海家化", "雅诗兰黛", "Olay", "OLAY", "SK-II"
    ],
    "日化": [
        "日化", "洗护", "洗涤", "清洁", "家清", "个护", "洗发", "沐浴",
        "牙膏", "牙刷", "纸品", "卫生巾", "消毒", "清洁用品", "护舒宝",
        "丹碧丝", "佳洁士", "欧乐B", "当妮", "汰渍", "碧浪", "舒肤佳",
        "飘柔", "潘婷", "海飞丝", "吉列", "博朗", "帮宝适", "原料", "纸尿裤", "婴幼", "剃须"
    ],
    "监管": [
        "原料", "法律", "化妆品监管", "抽检", "备案", "广告宣传", "质量安全",
        "召回", "虚假宣传", "消费投诉", "价格监管", "进口化妆品", "规定", "新规", "药监局"
    ],
}

# Common function words, pronouns, verbs, adjectives, numbers, and measure words.
STOP_WORDS = {
    "的", "了", "在", "是", "我", "有", "和", "就", "不", "人", "都", "一",
    "一个", "上", "也", "很", "到", "说", "要", "去", "你", "会", "着", "没有",
    "看", "好", "自己", "这", "那", "这些", "那些", "等", "及", "与", "或", "但",
    "而", "因", "为", "之", "其", "该", "这个", "那个", "对于", "关于", "通过", "进行",
    "已经", "可以", "需要", "表示", "认为", "目前", "今天", "今年", "现在", "随着", "根据",
    "由于", "因此", "如果", "虽然", "但是", "因为", "所以", "并且", "以及", "或者", "还是",
    "要么", "不仅", "而且", "只要", "只有", "无论", "不管", "尽管", "即使", "即便", "除非",
    "假如", "假若", "譬如", "例如", "比如", "像是", "像", "如同", "作为", "成为", "变得",
    "显得", "出现", "发生", "产生", "形成", "构成", "组成", "包括", "包含", "涉及", "针对",
    "有关", "相关", "按照", "依照", "依据", "本着", "基于", "鉴于", "因而", "从而", "于是",
    "由此", "故而", "总之", "综上所述", "由此可见", "由此看来", "也就是说", "换句话说",
    "换言之", "即", "也就是", "就是说", "可谓", "所谓", "意味着", "表明", "说明", "显示",
    "反映", "表现", "体现", "代表", "象征", "标志", "而言", "来说", "说来", "看来", "看起来",
    "看上去", "听上去", "想来", "来讲", "我国", "我们", "他们", "它们", "她们",
    "大家", "一些", "一定", "一种", "一直", "一次", "一方面", "为了", "成为", "具有",
    "其中", "同时", "此外", "另外", "然后", "之前", "之后", "以来", "以后", "以内",
    "以外", "以上", "以下", "以为", "十分", "非常", "比较", "更加", "最为",
    "不能", "不会", "不得", "不可", "不宜", "应当", "应该", "应", "须", "必须", "可以",
    "可能", "也许", "大概", "大约", "左右", "上下", "前后", "期间", "时候", "时间", "地方",
    "地区", "区域", "范围", "领域", "方面", "部分", "环节", "过程", "阶段", "时期", "时代",
    "年度", "月份", "日期", "一天", "两天", "三天", "一次", "两次", "三次", "第一", "第二",
    "第三", "最后", "最初", "此前", "此后", "当前", "今后", "近日", "日前", "去年", "明年",
    "当月", "当日", "当年", "本报", "记者", "报道", "新华社", "人民日报", "新闻网",
    "讯", "据悉", "据了解", "负责人介绍", "负责人表示", "业内人士认为", "业内", "专家认为",
    "专家表示", "会议指出", "会议强调", "会议提出", "会议要求", "会议认为",
    "据统计", "数据显示", "据介绍", "了解到", "发现", "认为", "表示", "指出", "提到", "强调",
    "的", "地", "得", "着", "过", "把", "被", "让", "给", "向", "从", "到", "在", "对",
    "为", "以", "因", "于", "与", "和", "同", "跟", "比", "有关",
    "第", "名", "位", "种", "类", "项", "个", "条", "款", "章", "节",
    "元", "亿元", "万元", "千元", "百元", "万亿元",
    "每", "各", "诸", "凡", "凡此", "种种", "有的", "之一",
    "零", "一", "二", "三", "四", "五", "六", "七", "八", "九", "十", "百", "千", "万", "亿",
    "〇", "壹", "贰", "叁", "肆", "伍", "陆", "柒", "捌", "玖", "拾",
    "年", "月", "日", "时", "分", "秒", "季度", "年度", "月份", "上周", "本周", "下周",
    "一季度", "二季度", "三季度", "四季度", "上半年", "下半年",
    "第一季度", "第二季度", "第三季度", "第四季度",
    "消费者", "消费市场", "市场", "集团", "增长", "业绩", "品牌", "产品", "企业", "公司",
    "行业", "发展", "持续", "释放", "信号", "同时", "加速", "变化", "需求", "人群", "场景",
    "涌现", "重塑", "生产", "消费", "格局", "财报", "销售", "营收", "利润", "同比", "环比",
    "去年", "今年", "明年", "不少", "多家", "多个", "进一步", "不断", "逐步", "正在", "已经",
    "有望", "实现", "达到", "超过", "突破", "占比", "份额", "位居", "位列", "排名",
    "发布", "报告", "显示", "指出", "认为", "表示", "强调", "提到", "介绍", "了解", "据悉",
    "者", "性", "型", "款", "式",
}

# Characters that strongly suggest a candidate is not a useful industry keyword.
NOISY_PREFIXES = {"的", "了", "是", "在", "和", "与", "或", "及", "等", "第", "每", "各", "被", "把", "向", "从", "际"}
NOISY_SUFFIXES = {"的", "了", "是", "在", "和", "与", "或", "及", "等", "中", "上", "下", "前", "后", "发", "布", "出", "来", "去", "到", "过", "得", "地", "着", "被", "把", "向", "从", "比", "对", "为", "以", "因", "于", "同", "跟", "速", "报", "告", "加", "正", "部"}


class TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.texts = []
        self.skip_tags = {"script", "style", "nav", "footer", "header", "aside"}
        self.skip = False

    def handle_starttag(self, tag, attrs):
        if tag in self.skip_tags:
            self.skip = True
        if tag in ("br", "p", "div", "h1", "h2", "h3", "h4", "li"):
            self.texts.append(" ")

    def handle_endtag(self, tag):
        if tag in self.skip_tags:
            self.skip = False

    def handle_data(self, data):
        if not self.skip:
            self.texts.append(data)


def _set_utf8_stdout():
    """Reconfigure stdout/stderr to UTF-8 when possible (helpful on Windows)."""
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    try:
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass


def fetch_html(url):
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8", errors="replace")


def extract_text(html):
    parser = TextExtractor()
    parser.feed(html)
    return re.sub(r"\s+", " ", "".join(parser.texts)).strip()


def get_title(html):
    m = re.search(r"<title[^>]*>(.*?)</title>", html, re.S | re.I)
    if m:
        return re.sub(r"\s+", " ", m.group(1)).strip()
    return ""


def detect_categories(text):
    """Return categories whose default keywords appear in the text."""
    matched = []
    for category, keywords in DEFAULT_TERMS.items():
        for kw in keywords:
            if kw in text:
                matched.append(category)
                break
    return matched


def split_sentences(text):
    # Split on common Chinese sentence endings and newlines.
    return [s.strip() for s in re.split(r"[。！？\n]+", text) if s.strip()]


def _is_noisy(term):
    """Heuristically reject low-quality candidate terms."""
    # Reject terms with digits or ASCII letters.
    if re.search(r"[0-9a-zA-Z]", term):
        return True
    # Reject very short or very long terms.
    if len(term) < 4 or len(term) > 6:
        return True
    # Reject terms containing the possessive/relative particle "的" anywhere.
    if "的" in term:
        return True
    # Reject terms starting/ending with noisy function characters.
    if term[0] in NOISY_PREFIXES or term[-1] in NOISY_SUFFIXES:
        return True
    # Reject if most characters are common stop words.
    stop_count = sum(1 for ch in term if ch in STOP_WORDS)
    if stop_count / len(term) >= 0.5:
        return True
    # Reject single repeated character.
    if len(set(term)) == 1:
        return True
    return False


def extract_candidate_terms(sentence):
    """Extract plausible Chinese terms from one sentence."""
    # Split sentence into chunks by non-Chinese delimiters.
    chunks = re.split(r"[^\u4e00-\u9fa5]", sentence)
    candidates = set()
    for chunk in chunks:
        if len(chunk) < 3:
            continue
        # Extract sliding windows of length 3..min(6, len(chunk)).
        for length in range(3, min(6, len(chunk)) + 1):
            for i in range(len(chunk) - length + 1):
                term = chunk[i:i + length]
                if not _is_noisy(term):
                    candidates.add(term)
    return candidates


def _remove_substrings(terms):
    """Drop terms that are substrings of a higher-priority term."""
    kept = []
    for term in terms:
        if any(term != other and term in other for other in kept):
            continue
        kept.append(term)
    return kept


def rank_candidates(sentences, seed_words, top_n=10):
    """Rank candidate terms by how often they co-occur with seed words."""
    freq = {}
    for sentence in sentences:
        if not any(seed in sentence for seed in seed_words):
            continue
        terms = extract_candidate_terms(sentence)
        for term in terms:
            freq[term] = freq.get(term, 0) + 1
    # Keep only terms that appear at least twice; sort by frequency then length.
    ranked = [term for term, count in freq.items() if count >= 2]
    ranked.sort(key=lambda t: (-freq[t], -len(t), t))
    ranked = _remove_substrings(ranked)
    return ranked[:top_n]


def load_keywords(path):
    if not os.path.exists(path):
        return {"美妆": [], "日化": [], "监管": []}
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    for category in DEFAULT_TERMS:
        if category not in data:
            data[category] = []
    return data


def save_keywords(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def learn_from_url(url, forced_category=None, dry_run=False, top_n=10):
    html = fetch_html(url)
    title = get_title(html)
    text = extract_text(html)
    full_text = f"{title} {text}"

    categories = [forced_category] if forced_category else detect_categories(full_text)
    if not categories:
        return {
            "title": title,
            "url": url,
            "categories": [],
            "learned": {},
            "message": "未检测到美妆/日化/监管相关主题。可使用 --category 强制指定类别。",
        }

    sentences = split_sentences(full_text)
    learned_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "keywords.json")
    learned = load_keywords(learned_path)

    result = {}
    for category in categories:
        seed_words = DEFAULT_TERMS[category]
        candidates = rank_candidates(sentences, seed_words, top_n=top_n)
        # Exclude terms already present in defaults or previously learned.
        existing = set(seed_words + learned.get(category, []))
        new_terms = [t for t in candidates if t not in existing]
        if new_terms:
            result[category] = new_terms
            if not dry_run:
                learned[category] = sorted(set(learned.get(category, [])) | set(new_terms))

    if result and not dry_run:
        save_keywords(learned_path, learned)

    return {
        "title": title,
        "url": url,
        "categories": categories,
        "learned": result,
        "keywords_file": learned_path,
    }


def main():
    _set_utf8_stdout()
    parser = argparse.ArgumentParser()
    parser.add_argument("url", help="Article URL to learn keywords from")
    parser.add_argument("--category", choices=list(DEFAULT_TERMS.keys()), help="Force a category")
    parser.add_argument("--dry-run", action="store_true", help="Preview keywords without saving")
    parser.add_argument("--top-n", type=int, default=10, help="Maximum new keywords per category")
    args = parser.parse_args()

    try:
        info = learn_from_url(args.url, args.category, args.dry_run, top_n=args.top_n)
    except Exception as e:
        print(f"学习失败：{e}", file=sys.stderr)
        sys.exit(1)

    print(f"页面标题：{info['title']}")
    print(f"来源URL：{info['url']}")

    if not info.get("categories"):
        print(info.get("message", ""))
        sys.exit(0)

    print(f"检测到类别：{'、'.join(info['categories'])}")
    if info.get("learned"):
        mode = "（预览，未保存）" if args.dry_run else ""
        print(f"本次学习到的新关键词{mode}：")
        for category, terms in info["learned"].items():
            print(f"  [{category}] {', '.join(terms)}")
        if not args.dry_run:
            print(f"已保存至：{info['keywords_file']}")
            print("下次运行筛选脚本时将自动加载这些关键词。")
    else:
        print("未提炼出新的高质量关键词（候选词可能已存在或频率不足）。")


if __name__ == "__main__":
    main()
