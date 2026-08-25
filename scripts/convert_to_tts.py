#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
convert_to_tts.py — 海螺语音（MiniMax TTS）文稿转换器

把 Markdown / LaTeX / HTML / 代码 / 口语动作标注混合的文稿，
转换为 MiniMax speech-2.8 系列可直接合成的朗读文本。

零第三方依赖，Python 3.8+ 即可运行。

用法:
    python3 convert_to_tts.py 输入.md
    cat 输入.md | python3 convert_to_tts.py
    python3 convert_to_tts.py 输入.md --model speech-2.8-hd --pause-level light --json

选项:
    -o, --output FILE     转换结果写入文件（默认 stdout）
    --model MODEL         speech-2.8-hd / speech-2.8-turbo / speech-2.6-hd ...（默认 speech-2.8-hd）
    --pause-level LEVEL   none | light | medium | strong（默认 light）
    --code MODE           strip(默认, 剥离代码块) | keep(保留并口语化)
    --latex MODE          auto(默认, 自动识别并口语化) | convert(强制口语化) | strip(剥离)
    --json                输出 JSON（含转换文本与报告）
    -q, --quiet           只输出转换文本
"""

import argparse
import json
import re
import sys

# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------

INTERJECTIONS = {
    "laughs": "笑声", "chuckle": "轻笑", "coughs": "咳嗽",
    "clear-throat": "清嗓子", "groans": "呻吟", "breath": "正常换气",
    "pant": "喘气", "inhale": "吸气", "exhale": "呼气", "gasps": "倒吸气",
    "sniffs": "吸鼻子", "sighs": "叹气", "snorts": "喷鼻息",
    "burps": "打嗝", "lip-smacking": "咂嘴", "humming": "哼唱",
    "hissing": "嘶嘶声", "emm": "嗯", "sneezes": "喷嚏",
}
INTERJECTION_RE = re.compile(r"\((laughs|chuckle|coughs|clear-throat|groans|breath|pant|inhale|exhale|gasps|sniffs|sighs|snorts|burps|lip-smacking|humming|hissing|emm|sneezes)\)")

PAUSE_RE = re.compile(r"<#(\d+(?:\.\d{1,2})?)#>")

GREEK = {
    "alpha": "阿尔法", "beta": "贝塔", "gamma": "伽马", "delta": "德尔塔",
    "Delta": "德尔塔", "theta": "西塔", "lambda": "兰姆达", "mu": "缪",
    "sigma": "西格玛", "Sigma": "西格玛", "omega": "欧米伽", "Omega": "欧米伽",
    "epsilon": "艾普西隆", "phi": "斐", "pi": "派", "rho": "柔",
    "tau": "套", "eta": "伊塔", "zeta": "泽塔", "kappa": "卡帕",
    "Gamma": "伽马", "Theta": "西塔", "Lambda": "兰姆达", "Psi": "普赛",
    "psi": "普赛", "Xi": "克赛", "xi": "克赛", "nu": "纽", "omicron": "欧米克隆",
}

LATEX_COMMANDS = {
    "times": "乘", "cdot": "乘", "ast": "乘", "div": "除以",
    "pm": "正负", "mp": "负正", "approx": "约等于", "neq": "不等于",
    "ne": "不等于", "leq": "小于等于", "le": "小于等于", "geq": "大于等于",
    "ge": "大于等于", "ll": "远小于", "gg": "远大于", "equiv": "恒等于",
    "sim": "约等于", "propto": "正比于", "infty": "无穷", "partial": "偏导",
    "nabla": "梯度", "in": "属于", "notin": "不属于", "subset": "包含于",
    "supset": "包含", "cup": "并", "cap": "交", "forall": "任意",
    "exists": "存在", "rightarrow": "趋向", "Rightarrow": "推出",
    "to": "趋向", "mapsto": "映射到", "longrightarrow": "趋向",
    "leftarrow": "反向", "uparrow": "向上", "downarrow": "向下",
    "cdotp": "乘", "cdots": "省略", "ldots": "省略", "dots": "省略",
    "angle": "角", "degree": "度", "circ": "度", "prime": "撇",
    "lim": "极限",
    "vert": "", "Vert": "", "mid": "", "quad": " ", "qquad": "  ",
    " ": " ", ",": " ", ";": " ", "!": "",
}

KEEP_LATIN = {"sin", "cos", "tan", "cot", "sec", "csc", "log", "ln", "lg", "exp", "max", "min", "inf", "sup", "det", "arg"}

CN_DIGITS = "零一二三四五六七八九"
CN_UNITS = ["", "十", "百", "千", "万"]


def num_to_cn(s):
    """阿拉伯数字转中文口语，支持整数与一位以上小数。'50'→五十 '99.9'→九十九点九"""
    s = s.strip()
    if "." in s:
        int_part, dec_part = s.split(".", 1)
        dec_cn = "".join(CN_DIGITS[int(d)] for d in dec_part if d.isdigit())
        return (int_cn(int(int_part)) if int_part else "零") + "点" + dec_cn
    return int_cn(int(s)) if s.isdigit() else s


def int_cn(n):
    if n == 0:
        return "零"
    if n >= 100000:
        return str(n)  # 超万级直接保留数字，交给 TTS
    s = str(n)
    length = len(s)
    out = ""
    zero_pending = False
    for i, ch in enumerate(s):
        d = int(ch)
        if d == 0:
            if out and not out.endswith("零"):
                if any(int(c) > 0 for c in s[i + 1:]):
                    out += "零"
            continue
        out += CN_DIGITS[d] + CN_UNITS[length - 1 - i]
    return out

EMOJI_TO_ACTION = {
    "😄": "chuckle", "😊": "chuckle", "😁": "chuckle", "🥳": "chuckle", "😆": "chuckle",
    "😂": "laughs", "🤣": "laughs", "😢": "sighs", "😭": "sighs", "😞": "sighs",
    "😔": "sighs", "😣": "sighs", "😲": "gasps", "😮": "gasps", "😱": "gasps",
    "😮💨": "exhale", "🥱": "sighs", "😩": "exhale", "😏": "chuckle", "🤔": "emm",
}
EMOJI_RE = re.compile(
    "["
    "\U0001F000-\U0001F02F"   # 麻将
    "\U0001F300-\U0001F5FF"   # 符号与象形
    "\U0001F600-\U0001F64F"   # 表情
    "\U0001F680-\U0001F6FF"   # 交通
    "\U0001F700-\U0001F77F"   # 字母
    "\U0001F780-\U0001F7FF"   # 几何
    "\U0001F800-\U0001F8FF"   # 补充箭头
    "\U0001F900-\U0001F9FF"   # 补充表情
    "\U0001FA00-\U0001FA6F"   # 象形扩展
    "\U0001FA70-\U0001FAFF"   # 象形扩展 B
    "\u2600-\u27BF"           # 杂项符号与箭头
    "\u2B00-\u2BFF"           # 补充箭头
    "\uFE0F\u200D"            # 变体选择符 / 零宽连接
    "]+"
)

ACTION_TO_TAG = {
    "笑": "laughs", "轻笑": "chuckle", "微笑": "chuckle",
    "叹气": "sighs", "唉": "sighs", "叹息": "sighs",
    "换气": "breath", "深呼吸": "breath", "呼": "breath",
    "吸气": "inhale", "吸一口气": "inhale",
    "呼气": "exhale", "吐气": "exhale",
    "喘气": "pant", "喘息": "pant",
    "倒吸气": "gasps", "倒抽一口气": "gasps",
    "咳嗽": "coughs", "咳": "coughs",
    "清嗓子": "clear-throat",
    "吸鼻子": "sniffs",
    "哼": "snorts", "嗤笑": "snorts", "喷鼻息": "snorts",
    "打嗝": "burps", "咂嘴": "lip-smacking",
    "哼唱": "humming", "哼歌": "humming",
    "嘶声": "hissing", "嘶嘶": "hissing",
    "嗯": "emm", "唔": "emm",
    "喷嚏": "sneezes", "阿嚏": "sneezes",
    "呻吟": "groans",
}

EMPHASIS_WORDS = "但是|然而|不过|可是|重点是|关键在于|结论是|请注意|记住|别忘了|重要|关键|注意|所以|因此|也就是说"

# ---------------------------------------------------------------------------
# 工具
# ---------------------------------------------------------------------------


def find_matching_brace(s, start):
    """s[start] == '{'，返回配对 '}' 的索引；找不到返回 -1。"""
    depth = 0
    for i in range(start, len(s)):
        if s[i] == "{":
            depth += 1
        elif s[i] == "}":
            depth -= 1
            if depth == 0:
                return i
    return -1


def strip_markdown_inline(text):
    """剥离行内 Markdown：粗体/斜体/删除线/行内代码/链接。"""
    # 行内代码（保护 _ * 不被当作强调处理）
    text = re.sub(r"`([^`]+)`", r"\1", text)
    # 图片 ![alt](url)
    text = re.sub(r"!\[([^\]]*)\]\([^)]*\)", r"图片：\1", text)
    # 链接 [text](url "title")
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)
    # 粗体/斜体/删除线（先粗后细）
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    text = re.sub(r"__([^_]+)__", r"\1", text)
    text = re.sub(r"~~([^~]+)~~", r"\1", text)
    text = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"\1", text)
    text = re.sub(r"(?<!_)_([^_]+)_(?!_)", r"\1", text)
    # 脚注引用
    text = re.sub(r"\[\^[^\]]+\]", "", text)
    return text


def convert_table(lines):
    """把 markdown 表格转成逐行朗读文本。lines 为表格行（含分隔行）。"""
    rows = []
    for ln in lines:
        cells = [c.strip() for c in ln.strip().strip("|").split("|")]
        if all(re.fullmatch(r":?-{2,}:?", c) for c in cells):
            continue  # 分隔行
        rows.append(cells)
    if not rows:
        return ""
    out = []
    header = rows[0]
    out.append("表格内容：" + "，".join(header) + "。")
    for r in rows[1:]:
        cells = (r + [""] * len(header))[: len(header)]
        out.append("，".join(cells) + "。")
    return "\n".join(out)


# ---------------------------------------------------------------------------
# LaTeX 口语化
# ---------------------------------------------------------------------------


def latex_to_speech(expr):
    """把一段 LaTeX 公式转成中文口语。"""
    expr = expr.strip()

    # 1. 去掉 \left \right 等修饰
    expr = re.sub(r"\\left|\\right|\\displaystyle|\\textstyle|\\limits", "", expr)
    expr = re.sub(r"\\text\{([^}]*)\}", r"\1", expr)
    expr = re.sub(r"\\mathrm\{([^}]*)\}", r"\1", expr)
    expr = re.sub(r"\\mathit\{([^}]*)\}", r"\1", expr)
    expr = re.sub(r"\\mathbf\{([^}]*)\}", r"\1", expr)

    # 2. 递归处理 \frac / \dfrac
    while True:
        m = re.search(r"\\(?:frac|dfrac)", expr)
        if not m:
            break
        idx = m.end()
        while idx < len(expr) and expr[idx] == " ":
            idx += 1
        if idx >= len(expr) or expr[idx] != "{":
            break
        num_end = find_matching_brace(expr, idx)
        if num_end < 0:
            break
        den_start = num_end + 1
        while den_start < len(expr) and expr[den_start] == " ":
            den_start += 1
        if den_start >= len(expr) or expr[den_start] != "{":
            break
        den_end = find_matching_brace(expr, den_start)
        if den_end < 0:
            break
        num = latex_to_speech(expr[idx + 1:num_end])
        den = latex_to_speech(expr[den_start + 1:den_end])
        frac = f"{num}<#0.2#>分之{den}" if len(den) > 4 else f"{num}分之{den}"
        expr = expr[: m.start()] + frac + expr[den_end + 1:]

    # 3. \sqrt[n]{x} 与 \sqrt{x}
    while True:
        m = re.search(r"\\sqrt", expr)
        if not m:
            break
        idx = m.end()
        n = None
        if idx < len(expr) and expr[idx] == "[":
            end = expr.find("]", idx)
            if end > 0:
                n = expr[idx + 1:end]
                idx = end + 1
        while idx < len(expr) and expr[idx] == " ":
            idx += 1
        if idx >= len(expr) or expr[idx] != "{":
            break
        end = find_matching_brace(expr, idx)
        if end < 0:
            break
        inner = latex_to_speech(expr[idx + 1:end])
        rep = f"{inner}开{n}次方" if n else f"根号{inner}"
        expr = expr[: m.start()] + rep + expr[end + 1:]

    # 4. 运算符上下限（\int_{a}^{b} \sum_{i=1}^n \lim_{x\to0} 等）
    def make_limits(lo, hi, word):
        if word == "积分":
            if lo and hi:
                return f"从{lo}到{hi}的积分"
            if lo:
                return f"下限{lo}的积分"
            if hi:
                return f"上限{hi}的积分"
        elif word == "求和":
            if lo and hi:
                return f"对{lo}到{hi}求和"
            if lo:
                return f"对{lo}求和"
        elif word == "连乘":
            if lo and hi:
                return f"从{lo}到{hi}的连乘"
            if lo:
                return f"从{lo}开始的连乘"
        elif word == "极限":
            if lo:
                return f"当{lo}时的极限"
        return word

    for cmd, word in (("int", "积分"), ("oint", "环路积分"),
                      ("sum", "求和"), ("prod", "连乘"), ("lim", "极限")):
        # \int_{a}^{b} / \int_a^b / \sum_{i=1}^n / \lim_{x\to0} 等上下限组合
        def repl_limits(m, _word=word):
            lo = m.group(1) or m.group(3) or ""
            hi = m.group(2) or m.group(4) or ""
            lo = latex_to_speech(lo) if lo else ""
            hi = latex_to_speech(hi) if hi else ""
            return make_limits(lo, hi, _word)
        expr = re.sub(
            r"\\" + cmd + r"(?:_\{([^{}]*)\}|\^\{([^{}]*)\}|_(\S)|\^(\S))*",
            repl_limits, expr)

    # 5. 上标 / 下标（循环迭代处理上下标链：a_i^2 → a 下标 i 的平方）
    def sup_sub(match):
        base, kind, arg = match.group(1), match.group(2), match.group(3)
        if kind == "^":
            if arg in ("2", "3"):
                return f"{base}的{'平方' if arg == '2' else '立方'}"
            return f"{base}的{arg}次方"
        else:
            return f"{base}下标{arg}"

    for _ in range(5):
        n1 = re.sub(r"([A-Za-z0-9)\]}]+)([\^_])\{([^{}]*)\}", sup_sub, expr)
        n2 = re.sub(r"([A-Za-z0-9)\]}]+)([\^_])([A-Za-z0-9])", sup_sub, n1)
        if n2 == expr:
            break
        expr = n2

    # 6. 希腊字母
    for name, zh in GREEK.items():
        expr = re.sub(r"\\" + name + r"(?![a-zA-Z])", zh, expr)

    # 7. 其他命令
    for cmd, zh in LATEX_COMMANDS.items():
        expr = re.sub(r"\\" + cmd + r"(?![a-zA-Z])", zh, expr)

    # 8. 函数名保留
    for fn in KEEP_LATIN:
        expr = re.sub(r"\\" + fn + r"(?![a-zA-Z])", fn, expr)

    # 9. 残留反斜杠命令：去掉命令词保留参数
    expr = re.sub(r"\\[a-zA-Z]+\{([^{}]*)\}", r"\1", expr)
    expr = re.sub(r"\\[a-zA-Z]+", "", expr)
    expr = expr.replace("{", "").replace("}", "")

    # 9. 运算符口语化（避免重复处理）
    expr = expr.replace("\\", "")
    expr = re.sub(r"\s*=\s*", "等于", expr)
    expr = re.sub(r"\s*\+\s*", "加", expr)
    expr = re.sub(r"\s*-\s*", "减", expr)
    expr = re.sub(r"\s*\*\s*", "乘", expr)
    expr = re.sub(r"\s*/\s*", "除以", expr)
    expr = re.sub(r"\s*±\s*", "正负", expr)
    expr = re.sub(r"\s*×\s*", "乘", expr)
    expr = re.sub(r"\s*÷\s*", "除以", expr)
    expr = re.sub(r"\s*≈\s*", "约等于", expr)
    expr = re.sub(r"\s*≠\s*", "不等于", expr)
    expr = re.sub(r"\s*≤\s*", "小于等于", expr)
    expr = re.sub(r"\s*≥\s*", "大于等于", expr)
    expr = re.sub(r"\s*<\s*", "小于", expr)
    expr = re.sub(r"\s*>\s*", "大于", expr)
    expr = re.sub(r"\s*\.\s*", "点", expr)
    expr = re.sub(r"\s*,\s*", "，", expr)

    # 10. 清理多余空格与孤立标点
    expr = re.sub(r"\s+", " ", expr).strip()
    expr = re.sub(r"^[,，.。]+|[,，.。]+$", "", expr)
    return expr


# ---------------------------------------------------------------------------
# 主转换管道
# ---------------------------------------------------------------------------


class Converter:
    def __init__(self, model="speech-2.8-hd", pause_level="light",
                 code_mode="strip", latex_mode="auto"):
        self.model = model
        self.supports_interjections = model in ("speech-2.8-hd", "speech-2.8-turbo")
        self.pause_level = pause_level
        self.code_mode = code_mode
        self.latex_mode = latex_mode
        self.stats = {
            "code_blocks": 0, "code_lines": 0, "latex_inline": 0,
            "latex_block": 0, "latex_stripped": 0, "html_tags": 0,
            "images": 0, "footnotes": 0, "pauses_added": 0,
            "interjections_added": 0, "interjections_removed": 0,
            "emoji_removed": 0, "tables": 0, "lists": 0,
        }

    # -- 阶段 1：代码块 ---------------------------------------------------
    def process_code_blocks(self, text):
        lines = text.split("\n")
        out, i, in_block, fence = [], 0, False, None
        block_count = 0
        block_lines = []
        while i < len(lines):
            ln = lines[i]
            m = re.match(r"^\s*(```|~~~)(.*)$", ln)
            if m and not in_block:
                in_block, fence = True, m.group(1)
                block_count += 1
                block_lines = []
                i += 1
                continue
            if m and in_block and m.group(1) == fence:
                in_block = False
                self.stats["code_lines"] += len(block_lines)
                if self.code_mode == "keep":
                    out.append(self.code_to_speech(block_lines))
                else:
                    out.append("（代码略）")
                i += 1
                continue
            if in_block:
                block_lines.append(ln)
                i += 1
                continue
            # 缩进代码块：连续 >=2 行 4 空格缩进才判定为代码
            if re.match(r"^ {4}\S", ln):
                j = i
                code_lines = []
                while j < len(lines) and (lines[j].strip() == "" or re.match(r"^ {4}\S", lines[j])):
                    if lines[j].strip():
                        code_lines.append(lines[j][4:])
                    j += 1
                if len(code_lines) >= 2:
                    block_count += 1
                    self.stats["code_lines"] += len(code_lines)
                    if self.code_mode == "keep":
                        out.append(self.code_to_speech(code_lines))
                    else:
                        out.append("（代码略）")
                    i = j
                    continue
            out.append(ln)
            i += 1
        if in_block:
            block_count += 1
            self.stats["code_lines"] += len(block_lines)
            if self.code_mode == "keep":
                out.append(self.code_to_speech(block_lines))
            else:
                out.append("（代码略）")
        self.stats["code_blocks"] = block_count
        return "\n".join(out)

    @staticmethod
    def code_to_speech(code_lines):
        spoken = []
        for ln in code_lines:
            s = ln.rstrip()
            s = re.sub(r"#.*$", "", s)  # 行注释
            s = s.replace("_", "下划线").replace("->", "指向").replace("==", "等于")
            s = s.replace("(", " 左括号 ").replace(")", " 右括号 ")
            s = s.replace("[", " 左中括号 ").replace("]", " 右中括号 ")
            s = s.replace("{", " 左花括号 ").replace("}", " 右花括号 ")
            s = re.sub(r"\s+", " ", s).strip()
            if s:
                spoken.append(s)
        return "，".join(spoken) if spoken else "（空代码）"

    # -- 阶段 2：LaTeX ----------------------------------------------------
    def process_latex(self, text):
        if self.latex_mode == "strip":
            text = re.sub(r"\$\$[^$]*\$\$", "", text, flags=re.S)
            text = re.sub(r"\$[^$]*\$", "", text)
            text = re.sub(r"\\\([^)]*\\\)", "", text)
            self.stats["latex_stripped"] += 1
            return text

        def repl_block(m):
            self.stats["latex_block"] += 1
            return "\n" + latex_to_speech(m.group(1)) + "\n"

        def repl_inline(m):
            self.stats["latex_inline"] += 1
            return latex_to_speech(m.group(1))

        text = re.sub(r"\$\$(.+?)\$\$", repl_block, text, flags=re.S)
        text = re.sub(r"\\\((.+?)\\\)", repl_inline, text, flags=re.S)
        text = re.sub(r"\$(.+?)\$", repl_inline, text)
        return text

    # -- 阶段 3：HTML -----------------------------------------------------
    def process_html(self, text):
        # 实体
        entities = {
            "&nbsp;": " ", "&amp;": "和", "&lt;": "小于", "&gt;": "大于",
            "&quot;": '"', "&#39;": "'", "&mdash;": "——", "&ndash;": "–",
            "&hellip;": "……", "&times;": "乘", "&divide;": "除以",
            "&deg;": "度", "&copy;": "",
        }
        for k, v in entities.items():
            text = text.replace(k, v)
        # 换行类标签
        text = re.sub(r"<br\s*/?>|</p>|</div>|</li>|</h\d>|<hr\s*/?>", "\n", text, flags=re.I)
        # 图片
        def repl_img(m):
            self.stats["images"] += 1
            try:
                alt = (m.group(1) or m.group(2) or "").strip()
            except IndexError:
                alt = ""
            return f"图片：{alt}" if alt else ""
        text = re.sub(r"<img[^>]*alt=[\"']?([^\"'>\s]*)[\"']?[^>]*>", repl_img, text, flags=re.I)
        text = re.sub(r"<img[^>]*>", repl_img, text, flags=re.I)
        # 链接
        text = re.sub(r"<a[^>]*href=[\"']([^\"']*)[\"'][^>]*>(.*?)</a>", r"\2", text, flags=re.I | re.S)
        # 其余标签（保护 <#x#>）
        n = len(re.findall(r"<(?!\#)[^>]+>", text))
        self.stats["html_tags"] += n
        text = re.sub(r"<(?!\#)[^>]+>", "", text)
        return text

    # -- 阶段 4：Markdown ------------------------------------------------
    def process_markdown(self, text):
        lines = text.split("\n")
        out, i = [], 0
        buf = None  # ('ul'|'ol'|'task', [items])
        ordered_counter = 0

        def flush():
            nonlocal buf, ordered_counter
            if buf:
                kind, items = buf
                if items:
                    if len(items) > 1:
                        self.stats["pauses_added"] += len(items) - 1
                    out.append("<#0.2#>".join(items))
                buf = None
            ordered_counter = 0

        while i < len(lines):
            ln = lines[i].rstrip()

            # 分隔线
            if re.match(r"^\s*(---+|\*\*\*+|___+)\s*$", ln) and not buf:
                flush()
                if out and out[-1].strip():
                    out.append("<#0.5#>")
                i += 1
                continue

            # 表格：连续 2 行以上含 |
            if "|" in ln and re.match(r"^\s*\|", ln):
                flush()
                tbl = [ln]
                j = i + 1
                while j < len(lines) and "|" in lines[j] and re.match(r"^\s*\|", lines[j]):
                    tbl.append(lines[j].rstrip())
                    j += 1
                self.stats["tables"] += 1
                out.append(convert_table(tbl))
                i = j
                continue

            # 标题
            m = re.match(r"^(#{1,6})\s+(.*)$", ln)
            if m:
                flush()
                level, content = len(m.group(1)), strip_markdown_inline(m.group(2))
                if content.strip():
                    if level == 1 and out and out[-1].strip():
                        out.append("<#0.5#>")
                    out.append(content)
                i += 1
                continue

            # 引用
            m = re.match(r"^\s*>\s?(.*)$", ln)
            if m:
                flush()
                out.append(m.group(1))
                i += 1
                continue

            # 任务列表项
            m = re.match(r"^\s*[-*+]\s+\[( |x|X)\]\s+(.*)$", ln)
            if m:
                if not buf or buf[0] != "task":
                    flush()
                    buf = ("task", [])
                tag = "已完成" if m.group(1) in "xX" else "待办"
                buf[1].append(f"{tag}，{strip_markdown_inline(m.group(2))}")
                self.stats["lists"] += 1
                i += 1
                continue

            # 无序列表项
            m = re.match(r"^\s*[-*+]\s+(.*)$", ln)
            if m:
                if not buf or buf[0] != "ul":
                    flush()
                    buf = ("ul", [])
                buf[1].append(strip_markdown_inline(m.group(1)))
                self.stats["lists"] += 1
                i += 1
                continue

            # 有序列表项
            m = re.match(r"^\s*(\d+)[.)]\s+(.*)$", ln)
            if m:
                num = int(m.group(1))
                if not buf or buf[0] != "ol":
                    flush()
                    buf = ("ol", [])
                    ordered_counter = num
                else:
                    ordered_counter += 1
                cn = "第一，第二，第三，第四，第五，第六，第七，第八，第九，第十".split("，")
                prefix = cn[ordered_counter - 1] if ordered_counter <= 10 else f"第{ordered_counter}项，"
                buf[1].append(f"{prefix}{strip_markdown_inline(m.group(2))}")
                self.stats["lists"] += 1
                i += 1
                continue

            # 普通行
            if buf:
                if ln.strip() == "":
                    flush()
                    out.append("")
                    i += 1
                    continue
                # 列表内的续行：并入最后一项
                buf[1][-1] += strip_markdown_inline(ln)
                i += 1
                continue
            out.append(strip_markdown_inline(ln))
            i += 1

        flush()
        # 脚注定义行
        text = "\n".join(out)
        text = re.sub(r"^\s*\[\^[^\]]+\]:.*$", "", text, flags=re.M)
        return text

    # -- 阶段 5：特殊符号 -------------------------------------------------
    def process_symbols(self, text):
        # 百分比 / 千分比
        text = re.sub(r"(\d+(?:\.\d+)?)\s*%", lambda m: "百分之" + num_to_cn(m.group(1)), text)
        text = re.sub(r"(\d+(?:\.\d+)?)\s*‰", lambda m: "千分之" + num_to_cn(m.group(1)), text)
        # 常用符号
        text = text.replace("±", "正负").replace("×", "乘").replace("÷", "除以")
        text = text.replace("≈", "约等于").replace("≠", "不等于")
        text = text.replace("≤", "小于等于").replace("≥", "大于等于")
        text = text.replace("℃", "摄氏度").replace("℉", "华氏度")
        text = text.replace("→", "指向").replace("←", "退回")
        text = text.replace("↑", "向上").replace("↓", "向下")
        text = text.replace("&", "和")
        # 重复标点
        text = re.sub(r"！+", "！", text)
        text = re.sub(r"？+", "？", text)
        text = re.sub(r"。+", "。", text)
        # 连续空格
        text = re.sub(r"[ \t]{2,}", " ", text)
        # emoji
        def repl_emoji(m):
            ch = m.group(0)
            self.stats["emoji_removed"] += 1
            if self.supports_interjections and ch in EMOJI_TO_ACTION:
                return "(" + EMOJI_TO_ACTION[ch] + ")"
            return ""
        text = EMOJI_RE.sub(repl_emoji, text)
        return text

    # -- 阶段 6：停顿策略 -------------------------------------------------
    def add_pauses(self, text):
        level = self.pause_level
        if level == "none":
            return text
        pauses = 0

        # 省略号与破折号（所有档位）
        text, n1 = re.subn(r"……+", "<#0.4#>", text)
        pauses += n1
        text, n2 = re.subn(r"\.{3,}", "<#0.4#>", text)
        pauses += n2
        text, n3 = re.subn(r"——+", "<#0.3#>", text)
        pauses += n3

        if level == "light":
            # 强调词前（句号/问号/叹号之后，中间允许语气词标签）
            def light_emph(m):
                nonlocal pauses
                pauses += 1
                return m.group(1) + "<#0.5#>" + m.group(2)
            text = re.sub(
                r"(?<=[。！？；])((?:\([a-z-]+\)\s*)*)(" + EMPHASIS_WORDS + r")",
                light_emph, text)
        elif level == "medium":
            # 句间停顿
            def med(m):
                nonlocal pauses
                pauses += 1
                return m.group(0) + "<#0.3#>"
            text = re.sub(r"[。！？](?=\S)", med, text)
            def light_emph(m):
                nonlocal pauses
                pauses += 1
                return m.group(1) + "<#0.5#>" + m.group(2)
            text = re.sub(
                r"(?<=[。！？；])((?:\([a-z-]+\)\s*)*)(" + EMPHASIS_WORDS + r")",
                light_emph, text)
        elif level == "strong":
            def strong_sent(m):
                nonlocal pauses
                pauses += 1
                return m.group(0) + "<#0.3#>"
            def strong_comma(m):
                nonlocal pauses
                pauses += 1
                return m.group(0) + "<#0.2#>"
            text = re.sub(r"[。！？](?=\S)", strong_sent, text)
            text = re.sub(r"[，、](?=\S)", strong_comma, text)
            def light_emph(m):
                nonlocal pauses
                pauses += 1
                return m.group(1) + "<#0.5#>" + m.group(2)
            text = re.sub(
                r"(?<=[。！？；])((?:\([a-z-]+\)\s*)*)(" + EMPHASIS_WORDS + r")",
                light_emph, text)

        self.stats["pauses_added"] += pauses
        return text

    # -- 阶段 7：语气词 ---------------------------------------------------
    def process_interjections(self, text):
        # 1. 中文动作标注 / 官方标签 → 统一处理
        def repl_action(m):
            inner = m.group(1).strip()
            # 官方标签原样保留（半角括号内是白名单词）
            if inner in INTERJECTIONS:
                if self.supports_interjections:
                    self.stats["interjections_added"] += 1
                    return f"({inner})"
                self.stats["interjections_removed"] += 1
                return ""
            # 发音标注原样保留括号：拼音带声调 1-6 / 粤拼 1-6 / IPA
            if re.fullmatch(r"[a-zA-Z]+[1-6]", inner):
                return f"({inner})"
            if re.search(r"[ɪʊəɜæɒŋʃʒθðŋɡʰ]", inner):
                return f"({inner})"
            # 脚本生成的占位内容保留括号（（代码略）（空代码）等）
            if inner.startswith(("代码", "图片", "公式")):
                return f"（{inner}）"
            mm = re.match(r"^([^0-9]+?)\s*(\d+(?:\.\d+)?)?\s*秒?$", inner)
            if mm:
                word, sec = mm.group(1), mm.group(2)
                if word in ("停顿", "暂停", "停"):
                    self.stats["pauses_added"] += 1
                    if sec:
                        v = min(99.99, max(0.01, float(sec)))
                        return f"<#{v:g}#>"
                    return "<#0.5#>"
                if word in ACTION_TO_TAG:
                    if self.supports_interjections:
                        self.stats["interjections_added"] += 1
                        return f"({ACTION_TO_TAG[word]})"
                    self.stats["interjections_removed"] += 1
                    return ""
            # 无法识别：剥离括号保留内容
            return inner

        text = re.sub(r"[（(\[]([^）)\]]{1,12})[）)\]]", repl_action, text)

        # 2. 非 2.8 模型：清除残留的官方标签
        if not self.supports_interjections:
            def drop(m):
                self.stats["interjections_removed"] += 1
                return ""
            text = INTERJECTION_RE.sub(drop, text)
        else:
            # 删除白名单外的疑似英文标签
            text = re.sub(r"\((?:applause|clap|whisper|singing|yawning|whistle)\)", "", text)
        return text

    # -- 阶段 8：校验与收尾 ----------------------------------------------
    def finalize(self, text):
        warnings = []

        # 折叠空行
        text = re.sub(r"\n{3,}", "\n\n", text)
        # 清理每行首尾空格
        text = "\n".join(l.strip() for l in text.split("\n"))
        text = re.sub(r"\n{2,}", "\n", text)

        # 停顿标记合法化
        def fix_pause(m):
            v = float(m.group(1))
            v = min(99.99, max(0.01, v))
            s = f"{v:.2f}".rstrip("0").rstrip(".")
            return f"<#{s}#>"
        text = PAUSE_RE.sub(fix_pause, text)
        # 宽松处理非法停顿（超过两位小数 / 非数字内容）
        def fix_bad_pause(m):
            raw = m.group(1).strip()
            try:
                v = float(raw)
            except ValueError:
                return m.group(0)  # 保留，由后续警告提示
            v = min(99.99, max(0.01, v))
            s = f"{v:.2f}".rstrip("0").rstrip(".")
            return f"<#{s}#>"
        text = re.sub(r"<#([^#>]+)#>", fix_bad_pause, text)

        # 非法连续停顿：合并为单个
        text = re.sub(r"(<#[^>]+#>)\s*(<#[^>]+#>)", r"\1", text)
        # 仅删除全文最开头 / 最结尾的停顿（段首段尾的显式停顿保留）
        text = re.sub(r"^(<#[^>]+#>\s*)+", "", text)
        text = re.sub(r"(\s*<#[^>]+#>)+$", "", text)

        # 中英文混排空格（"熵entropy" → "熵 entropy"）
        text = re.sub(r"([\u4e00-\u9fff])([A-Za-z0-9])", r"\1 \2", text)
        text = re.sub(r"([A-Za-z0-9])([\u4e00-\u9fff])", r"\1 \2", text)

        # 残留检查
        for pat, desc in [
            (r"\*\*", "残留粗体标记 **"),
            (r"(?<!\\)\$", "残留美元符 $"),
            (r"\\[a-zA-Z]+", "残留 LaTeX 命令"),
            (r"\[[^\]]*\]\([^)]*\)", "残留链接"),
            (r"<(?!#)[a-zA-Z/][^>]*>", "残留 HTML 标签"),
        ]:
            if re.search(pat, text):
                warnings.append(f"检测到{desc}，请人工检查")

        # 停顿位置合法性（停顿后必须是可发音内容）
        for m in PAUSE_RE.finditer(text):
            post = text[m.end():].lstrip()
            if not post:
                warnings.append("发现停顿标记位于文本末尾，请复核")
                continue
            if not re.search(r"[\u4e00-\u9fffA-Za-z0-9%]", post[0]):
                warnings.append("停顿标记后跟非发音内容，请复核")

        # 语气词位置（句内残留全角括号动作词）
        for m in re.finditer(r"[（(](笑|叹气|吸气|呼气|喘气|停顿)[）)]", text):
            warnings.append(f"发现未转换的动作标注 {m.group(0)}，请复核")

        # 长度
        n = len(text)
        if n >= 10000:
            warnings.append(f"文本 {n} 字符超过 10000 上限，请按段落分段（每段 <10000）")
        elif n > 3000:
            warnings.append(f"文本 {n} 字符，超过 3000 建议使用流式输出")

        return text, warnings

    # -- 主入口 ----------------------------------------------------------
    def convert(self, text):
        text = text.lstrip("\ufeff")
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        text = self.process_code_blocks(text)
        text = self.process_latex(text)
        text = self.process_html(text)
        text = self.process_markdown(text)
        text = self.process_symbols(text)
        text = self.add_pauses(text)
        text = self.process_interjections(text)
        text, warnings = self.finalize(text)
        return text, warnings

    def report(self, src_len):
        s = self.stats
        lines = [
            f"转换报告（model={self.model}, pause={self.pause_level}）",
            f"  原字符数: {src_len} → 转换后: {s.get('_out_len', '?')}",
            f"  代码块: {s['code_blocks']} 个（{s['code_lines']} 行）",
            f"  LaTeX: 行内 {s['latex_inline']} 处 / 块级 {s['latex_block']} 处 / 剥离 {s['latex_stripped']} 处",
            f"  HTML 标签: {s['html_tags']} 个 / 图片 {s['images']} 个",
            f"  表格: {s['tables']} 个 / 列表: {s['lists']} 项",
            f"  停顿标记: 共 {s['pauses_added']} 处",
            f"  语气词: 添加 {s['interjections_added']} 个 / 移除 {s['interjections_removed']} 个",
            f"  emoji: 移除 {s['emoji_removed']} 个",
        ]
        return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description="海螺语音（MiniMax TTS）文稿转换器")
    ap.add_argument("input", nargs="?", help="输入文件；缺省读 stdin")
    ap.add_argument("-o", "--output", help="转换结果输出文件（默认 stdout）")
    ap.add_argument("--model", default="speech-2.8-hd",
                    help="speech-2.8-hd / speech-2.8-turbo / speech-2.6-hd ...（默认 speech-2.8-hd）")
    ap.add_argument("--pause-level", default="light", choices=["none", "light", "medium", "strong"])
    ap.add_argument("--code", default="strip", choices=["strip", "keep"], help="代码块处理方式")
    ap.add_argument("--latex", default="auto", choices=["auto", "convert", "strip"])
    ap.add_argument("--json", action="store_true", help="输出 JSON（含报告）")
    ap.add_argument("-q", "--quiet", action="store_true", help="只输出转换文本")
    args = ap.parse_args()

    if args.input:
        with open(args.input, encoding="utf-8") as f:
            src = f.read()
    else:
        src = sys.stdin.read()

    c = Converter(model=args.model, pause_level=args.pause_level,
                  code_mode=args.code, latex_mode=args.latex)
    out, warnings = c.convert(src)
    c.stats["_out_len"] = len(out)

    if args.json:
        payload = {
            "model": args.model,
            "pause_level": args.pause_level,
            "text": out,
            "stats": c.stats,
            "warnings": warnings,
        }
        sys.stdout.write(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
        return

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(out)
    if not args.quiet:
        sys.stdout.write(out + "\n")
        sys.stderr.write("\n" + c.report(len(src)) + "\n")
        for w in warnings:
            sys.stderr.write("  ⚠ " + w + "\n")
    else:
        sys.stdout.write(out + "\n")


if __name__ == "__main__":
    main()
