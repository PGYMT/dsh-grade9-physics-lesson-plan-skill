#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把教案 md 里的 board 围栏渲染成板书 PNG（黑板风，纯 Pillow）。

用法：
  python3 build_board_png.py <md文件> [输出目录]
  from build_board_png import render_boards; render_boards(md, out_dir) -> [{path,width,height}]

依赖 Pillow：优先系统 Pillow；没有就把同目录 vendor/ 下的 pillow-*.whl 解压到 vendor/_libs 再用。
布局：左板｜课件屏（2 倍板宽）｜右板（1:2:1）；行首每两级空格右移 24 px；板头只画「左板／右板」。
字体：优先 /mnt/c/Windows/Fonts/simkai.ttf（正文）与 simhei.ttf（标题）；找不到退回 DejaVu。
"""
from __future__ import annotations
import os, re, sys, glob, zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
FENCE = chr(96) * 3

BG = (31, 45, 38)
CHALK = (240, 240, 230)
RED = (255, 125, 115)
YELLOW = (255, 214, 102)


def _vendor_dirs():
    """Pillow wheel 候选目录：先本脚本旁 vendor/，再旧的 06-工具与提示词/教程/vendor。"""
    cands = [os.path.join(HERE, "vendor")]
    legacy = os.environ.get("JIAOAN_VENDOR_DIR") or \
        "/root/dsh-workspace/工作文件/06-工具与提示词/教程/vendor"
    if legacy not in cands:
        cands.append(legacy)
    return cands


def _pillow():
    try:
        from PIL import Image, ImageDraw, ImageFont
        return Image, ImageDraw, ImageFont
    except Exception:
        pass
    tag = "cp%d%d" % sys.version_info[:2]
    for vendor in _vendor_dirs():
        libs = os.path.join(vendor, "_libs")
        if os.path.isdir(libs):
            if libs not in sys.path:
                sys.path.insert(0, libs)
            try:
                from PIL import Image, ImageDraw, ImageFont
                return Image, ImageDraw, ImageFont
            except Exception:
                continue
        whls = sorted(glob.glob(os.path.join(vendor, "pillow-*.whl")))
        pick = [w for w in whls if tag in os.path.basename(w)] or \
               [w for w in whls if "py3-none-any" in os.path.basename(w)]
        if not pick:
            continue
        os.makedirs(libs, exist_ok=True)
        with zipfile.ZipFile(pick[0]) as z:
            z.extractall(libs)
        if libs not in sys.path:
            sys.path.insert(0, libs)
        from PIL import Image, ImageDraw, ImageFont
        return Image, ImageDraw, ImageFont
    raise RuntimeError(
        "Pillow 不可用：系统未装 Pillow，vendor/ 里也没有匹配当前解释器（%s）的 wheel。"
        "请运行 pip install pillow，或把 pillow-*-%s-*.whl 放进本脚本旁的 vendor/。" % (tag, tag))


KAI = ["/mnt/c/Windows/Fonts/simkai.ttf",
       "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
       "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]
HEI = ["/mnt/c/Windows/Fonts/simhei.ttf",
       "/mnt/c/Windows/Fonts/msyh.ttc",
       "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
       "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]


def _font(ImageFont, paths, size):
    for p in paths:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                continue
    return ImageFont.load_default()


FENCE_RE = re.compile("^[ ]*" + FENCE + "board[ ]*$")
TOKEN = re.compile("[{]红[|]([^}]*)[}]|[{]圈[|]([^}]*)[}]|[{]下[|]([^}]*)[}]|[{]括号[|]([^}]*)[}]|(_{3,})")


def split_blocks(md):
    blocks = []
    cur = None
    for ln in md.splitlines():
        if cur is None:
            if FENCE_RE.match(ln):
                cur = []
            continue
        if ln.strip().startswith(FENCE):
            blocks.append(cur)
            cur = None
        else:
            cur.append(ln)
    if cur is not None:
        blocks.append(cur)
    return blocks


def parse_block(block):
    title = []
    panels = []
    cur = None
    for ln in block:
        s = ln.rstrip()
        if not s.strip():
            continue
        if s.startswith("## "):
            cur = {"head": s[3:].strip(), "lines": []}
            panels.append(cur)
        elif s.startswith("# "):
            title.append(s[2:].strip())
        else:
            if cur is None:
                cur = {"head": "", "lines": []}
                panels.append(cur)
            cur["lines"].append(s)
    return {"title": "   ".join(title), "panels": panels}


def segs(line):
    out = []
    pos = 0
    for m in TOKEN.finditer(line):
        if m.start() > pos:
            out.append(("t", line[pos:m.start()]))
        if m.group(1) is not None:
            out.append(("red", m.group(1)))
        elif m.group(2) is not None:
            out.append(("cir", m.group(2)))
        elif m.group(3) is not None:
            out.append(("und", m.group(3)))
        elif m.group(4) is not None:
            out.append(("t", m.group(4)))
        else:
            out.append(("blank", ""))
        pos = m.end()
    if pos < len(line):
        out.append(("t", line[pos:]))
    return out


def _line_width(d, line, font):
    w = 0.0
    for typ, txt in segs(line):
        if typ == "blank":
            w += 101
        else:
            w += d.textlength(txt, font=font)
    return w


def _draw_line(d, x, y, line, font):
    fs = getattr(font, "size", 25)
    for typ, txt in segs(line):
        if typ == "blank":
            d.line((x, y + fs + 4, x + 95, y + fs + 4), fill=YELLOW, width=3)
            x += 101
            continue
        w = d.textlength(txt, font=font)
        color = RED if typ == "red" else CHALK
        d.text((x, y), txt, font=font, fill=color)
        if typ == "und":
            d.line((x, y + fs + 4, x + w, y + fs + 4), fill=YELLOW, width=3)
        elif typ == "cir":
            d.ellipse((x - 7, y - 5, x + w + 7, y + fs + 7), outline=RED, width=3)
        x += w
    return x


def line_indent(line):
    """行首空格 ÷ 2：两级空格算一级缩进，渲染时右移 24 px。"""
    return (len(line) - len(line.lstrip(" "))) // 2


def head_label(head):
    """板标题给老师看的名字：板1→左板、板2→右板；括号里的（主板）（副板）不画。"""
    s = re.sub(r"[（(][^）)]*[）)]", "", head).strip()
    if s in ("板1", "板 1"):
        return "左板"
    if s in ("板2", "板 2"):
        return "右板"
    return s


def _dashed_rect(d, x0, y0, x1, y1, color, dash=10, space=8, width=2):
    """虚线空框：只有一块板时，右槽留位给人看。"""
    x0, y0, x1, y1 = int(x0), int(y0), int(x1), int(y1)
    x = x0
    while x < x1:
        d.line((x, y0, min(x + dash, x1), y0), fill=color, width=width)
        d.line((x, y1, min(x + dash, x1), y1), fill=color, width=width)
        x += dash + space
    y = y0
    while y < y1:
        d.line((x0, y, x0, min(y + dash, y1)), fill=color, width=width)
        d.line((x1, y, x1, min(y + dash, y1)), fill=color, width=width)
        y += dash + space


def render_block(Image, ImageDraw, ImageFont, blk, out_path):
    title = blk["title"]
    panels = blk["panels"]
    ft = _font(ImageFont, HEI, 30)
    fh = _font(ImageFont, HEI, 26)
    fh18 = _font(ImageFont, HEI, 18)
    fb = _font(ImageFont, KAI, 25)
    body_lh = 44
    head_h = 52
    pad = 26
    gap = 24
    margin = 28
    metric = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    IND = 24                      # 每级缩进右移的像素
    SCREEN_FILL = (231, 234, 236)
    SCREEN_LINE = (176, 182, 188)
    SCREEN_TEXT = (128, 134, 140)
    DASH = (198, 202, 196)

    def _panel_w(p):
        w = 0
        for ln in p["lines"]:
            w = max(w, _line_width(metric, ln.strip(), fb) + line_indent(ln) * IND)
        return w

    pw = 340
    for p in panels:
        pw = max(pw, int(_panel_w(p) + pad * 2))
    title_w = metric.textlength(title, font=ft) if title else 0
    left_x = margin
    screen_x0 = margin + pw + gap
    right_x = screen_x0 + 2 * pw + gap
    W = int(max(right_x + pw + margin, title_w + margin * 2 + 40, 900))
    rows = (len(panels) + 1) // 2
    ph = max([head_h + len(p["lines"]) * body_lh + pad for p in panels] or [200])
    top = margin + (58 if title else 0)
    H = int(top + rows * ph + (rows - 1) * gap + margin)
    img = Image.new("RGB", (W, H), (255, 255, 255))
    d = ImageDraw.Draw(img)
    if title:
        d.rounded_rectangle((margin, margin, W - margin, margin + 50), radius=8, fill=BG)
        d.text((margin + 24, margin + 9), title, font=ft, fill=(255, 255, 245))
    # 中间是课件屏：2 倍板宽，浅灰，不写字
    d.rounded_rectangle((screen_x0, top, right_x - gap, top + ph), radius=10,
                        fill=SCREEN_FILL, outline=SCREEN_LINE, width=2)
    label = "课件屏（不写字）"
    lw = metric.textlength(label, font=fh)
    d.text((screen_x0 + (2 * pw - lw) / 2, top + ph / 2 - 18), label, font=fh, fill=SCREEN_TEXT)
    for i, p in enumerate(panels):
        r = i // 2
        x = right_x if i % 2 else left_x
        y = top + r * (ph + gap)
        d.rounded_rectangle((x, y, x + pw, y + ph), radius=8, fill=BG, outline=(150, 150, 140), width=2)
        d.text((x + 22, y + 14), head_label(p["head"]), font=fh18, fill=(176, 184, 176))
        d.line((x + 20, y + head_h - 4, x + pw - 20, y + head_h - 4), fill=(115, 125, 115), width=1)
        yy = y + head_h + 6
        for ln in p["lines"]:
            _draw_line(d, x + 22 + line_indent(ln) * IND, yy, ln.strip(), fb)
            yy += body_lh
    if len(panels) == 1:
        _dashed_rect(d, right_x, top, right_x + pw, top + ph, DASH)
    img.save(out_path)
    return {"path": out_path, "width": img.size[0], "height": img.size[1]}


def render_boards(md_path, out_dir=None):
    Image, ImageDraw, ImageFont = _pillow()
    md = open(md_path, encoding="utf-8").read()
    blocks = split_blocks(md)
    if not blocks:
        return []
    if out_dir is None:
        out_dir = os.path.join(os.path.dirname(os.path.abspath(md_path)), "板书图")
    os.makedirs(out_dir, exist_ok=True)
    stem = os.path.splitext(os.path.basename(md_path))[0]
    out = []
    for i, b in enumerate(blocks):
        blk = parse_block(b)
        if not blk["panels"]:
            continue
        name = stem + "-板书.png" if len(blocks) == 1 else stem + "-板书" + str(i + 1) + ".png"
        out.append(render_block(Image, ImageDraw, ImageFont, blk, os.path.join(out_dir, name)))
    return out


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法：python3 build_board_png.py <md文件> [输出目录]")
        raise SystemExit(1)
    if not os.path.isfile(sys.argv[1]):
        print("错误：找不到 md 文件：%s\n用法：python3 build_board_png.py <md文件> [输出目录]" % sys.argv[1])
        raise SystemExit(1)
    outdir = sys.argv[2] if len(sys.argv) > 2 else None
    for r in render_boards(sys.argv[1], outdir):
        print("OK", r["path"], r["width"], "x", r["height"])
