#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""build_enbx_native_pages.py — 用希沃「原生文字/形状/图片」给 .enbx 副本加页。
- 新增内容以原生文字为主；图片按需插入（T8 对比用）。
- 页面母版（课堂练习横幅 + 优翼 logo + 底栏）从原件第 34 页克隆，保证风格一致。

用法:
  python3 build_enbx_native_pages.py --help
  python3 build_enbx_native_pages.py [--set test|t8|p1|t16] [--out <路径>]

内置 15.2 课件的一次性页组；--help 只打印用法，不构建、不写文件。通用加页按 references/06 §2 自己写。
"""
import os, sys, re, zipfile, hashlib

HERE = os.path.dirname(os.path.abspath(__file__))
WS = os.path.abspath(os.path.join(HERE, "..", ".."))
SLIDE_W, SLIDE_H = 960, 540

SRC = os.path.join(WS, "05-课件与文本", "第十五章-电流和电路", "原始课件", "15.2第2节  电流和电路.enbx")
STAGE = os.path.join(WS, "99-待处理", "收件箱", "图片测试素材")

TEAL, DARK, GRAY = "#FF249087", "#FF000000", "#FF666666"
HEI, NUM = "微软雅黑", "Times New Roman"
TEMPLATE_SLIDE = 33
TEMPLATE_INDICES = [0, 1, 2, 3, 4, 5, 26]
BANNER_OLD = "课堂练习"


def _pillow():
    try:
        from PIL import Image
        return Image
    except Exception:
        libs = os.path.join(HERE, "vendor", "_libs")
        if os.path.isdir(libs) and libs not in sys.path:
            sys.path.insert(0, libs)
        from PIL import Image
        return Image


def uid():
    return hashlib.md5(os.urandom(16)).hexdigest()


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def est_lines(text, width, size):
    """估算一行文字在给定宽度下会折成几行（按中文字宽≈字号）。"""
    cpl = max(1, int(width / (size * 1.02)))
    return max(1, (len(text) + cpl - 1) // cpl)


def text_height(lines, width, size):
    return max(round(size * 2.0), sum(est_lines(t, width, size) for t in lines) * round(size * 2.0))


def segments(text):
    segs, cur, cur_a = [], "", None
    for ch in text:
        a = ord(ch) < 128
        if cur_a is None:
            cur_a = a
        if a != cur_a:
            segs.append((cur, cur_a)); cur, cur_a = "", a
        cur += ch
    if cur:
        segs.append((cur, cur_a))
    return segs or [(text, False)]


def run_xml(text, size, family, color, bold, crlf=False):
    body = esc(text) + ("&#xD;\n" if crlf else "")
    return ("<TextRun><Text>%s</Text><FontSize>%s</FontSize><FontVariants>Normal</FontVariants>"
            "<FontStyle>Normal</FontStyle><FontWeight>%s</FontWeight>"
            "<FontFamily><Source>%s</Source></FontFamily>"
            "<Background><ColorBrush>#00FFFFFF</ColorBrush></Background>"
            "<Foreground><ColorBrush>%s</ColorBrush></Foreground><Opacity>1</Opacity></TextRun>"
            ) % (body, size, "Bold" if bold else "Normal", family, color)


def line_xml(text, size, color, bold, align, is_last, spacing):
    segs = segments(text)
    runs = [run_xml(t, size, NUM if a else HEI, color, bold, crlf=(not is_last and i == len(segs) - 1))
            for i, (t, a) in enumerate(segs)]
    runs.append(run_xml("", size, NUM, color, bold))
    visible = sum(1 for ch in text if ch not in "\r\n")
    return ("<TextLine><LineSpacing>%s</LineSpacing><FixedLineSpacing>NaN</FixedLineSpacing>"
            "<TextAlignment>%s</TextAlignment><TextRuns>%s</TextRuns>"
            "<DefaultRunProperty>%s</DefaultRunProperty><MarginLeft>0</MarginLeft><Indent>0</Indent>"
            "<TextMarkerStyle><FontSize>0</FontSize></TextMarkerStyle>"
            "<SpaceBefore>0</SpaceBefore><SpaceAfter>0</SpaceAfter>"
            "<Lines><LineProperty><StartOffset>0</StartOffset><Length>%d</Length></LineProperty></Lines>"
            "<Direction>LeftToRight</Direction><IndentLevel>0</IndentLevel>"
            "<TextMarker>None</TextMarker><IndentType>FirstLine</IndentType></TextLine>"
            ) % (spacing, align, "".join(runs[:-1]), runs[-1], visible)


def anim_xml(n):
    return ("<Animations><Animation><Type>FadeIn</Type><Id>%s</Id><Number>%d</Number>"
            "<Category>Appearance</Category><Trigger>Click</Trigger><TriggerSource></TriggerSource>"
            "<Duration>3000000</Duration><Delay>0</Delay><AccelerationRatio>0</AccelerationRatio>"
            "<DecelerationRatio>1</DecelerationRatio><RepeatBehavior>1</RepeatBehavior>"
            "<Start>0</Start><End>1</End></Animation></Animations>") % (uid(), n)


def text_xml(lines, x, y, w, h, size, color=DARK, bold=False, align="Left", anim=None):
    tl = "".join(line_xml(t, size, color, bold, align, i == len(lines) - 1, round(size * 0.21, 2))
                 for i, t in enumerate(lines))
    full = "&#xD;\n".join(esc(t) for t in lines)
    return ("<Text><RichText><SizeToContent>Manual</SizeToContent><ArrangingType>Horizontal</ArrangingType>"
            "<VerticalTextAlignment>Top</VerticalTextAlignment><TextLines>%s</TextLines>"
            "<Text>%s</Text></RichText><BorderThickness>0</BorderThickness><BorderType>None</BorderType>"
            "<Id>%s</Id><X>%s</X><Y>%s</Y><Width>%s</Width><Height>%s</Height>"
            "<Rotation>0</Rotation><IsLocked>False</IsLocked><CanClone>False</CanClone>%s"
            "<HasMask>False</HasMask><RotateOrigin>0.5,0.5</RotateOrigin>"
            "<SaveInfoMetadata><SupportsFallback>True</SupportsFallback><ImportanceLevel>Important</ImportanceLevel></SaveInfoMetadata>"
            "<ElementPptxOriginId><OriginPptxId>4</OriginPptxId><OriginPptxName>TextBox 1</OriginPptxName></ElementPptxOriginId>"
            "</Text>") % (tl, full, uid(), x, y, w, h, (anim_xml(anim) if anim else ""))


def picture_xml(res_id, name, size_bytes, pw, ph, x, y, w, h, anim=None):
    return ("<Picture><Source>id://%s</Source><PictureName>%s</PictureName><Alpha>1</Alpha>"
            "<DisplayRegion><Rectangle>0,0,%d,%d</Rectangle></DisplayRegion>"
            "<Style><StyleType>None</StyleType><PicturePresetStyle>None</PicturePresetStyle></Style>"
            "<MetaData><PictureSize>%d,%d</PictureSize><FileSize>%d</FileSize></MetaData>"
            "<Id>%s</Id><X>%s</X><Y>%s</Y><Width>%s</Width><Height>%s</Height>"
            "<Rotation>0</Rotation><IsLocked>False</IsLocked><CanClone>False</CanClone>%s"
            "<HasMask>False</HasMask><RotateOrigin>0.5,0.5</RotateOrigin>"
            "<SaveInfoMetadata><SupportsFallback>True</SupportsFallback><ImportanceLevel>Important</ImportanceLevel></SaveInfoMetadata>"
            "<ElementPptxOriginId><OriginPptxId>12</OriginPptxId><OriginPptxName>图片</OriginPptxName></ElementPptxOriginId>"
            "</Picture>") % (res_id, name, ph, pw, pw, ph, size_bytes, uid(), x, y, w, h, (anim_xml(anim) if anim else ""))


def slide_xml(sid, elements):
    return ('<?xml version="1.0" encoding="utf-8"?>\n<Slide><Id>%s</Id><Width>960</Width><Height>540</Height>'
            '<KeepIndependentSize>False</KeepIndependentSize>'
            '<Background><ColorBrush>#FFFFFFFF</ColorBrush></Background>'
            '<Elements>%s</Elements><Duration>5000000</Duration>'
            '<ThemeForSlide><ThemeId>-1</ThemeId></ThemeForSlide></Slide>'
            ) % (sid, "".join(elements))


RE_ID32 = re.compile(r"<Id>([0-9a-f]{32})</Id>")


def top_elements(raw):
    open_re = re.compile(r"<(Text|Shape|Picture|Video)(\s[^>]*)?>")
    res, i = [], 0
    while True:
        mo = open_re.search(raw, i)
        if not mo:
            break
        name, d, j = mo.group(1), 0, mo.start()
        while True:
            mo2 = re.compile(r"<" + name + r"(\s[^>]*)?>").search(raw, j)
            mc2 = re.compile(r"</" + name + r">").search(raw, j)
            if mo2 and (not mc2 or mo2.start() < mc2.start()):
                d += 1; j = mo2.end()
            elif mc2:
                d -= 1; j = mc2.end()
                if d == 0:
                    break
            else:
                break
        res.append(raw[mo.start():j]); i = j
    return res


def make_furniture(template_raw, banner_text):
    els = top_elements(template_raw)
    picked = [els[k] for k in TEMPLATE_INDICES]
    picked = [RE_ID32.sub(lambda m: "<Id>%s</Id>" % uid(), e) for e in picked]
    return [e.replace(BANNER_OLD, banner_text) for e in picked]


# ---------------- 内容 ----------------
TEST_PAGES = [
    {"banner": "当堂练习", "topic": "电流和电路 · 第2课时",
     "blocks": [("q", "1. 关于电流方向，下列说法正确的是（　　）"),
                ("o", "A. 正电荷定向移动的方向规定为电流的方向"),
                ("o", "B. 电流方向总是从电源负极经用电器流向正极"),
                ("o", "C. 金属导体中电流方向与自由电子定向移动方向相同"),
                ("o", "D. 只有正电荷定向移动才能形成电流")]},
    {"banner": "参考答案", "topic": "",
     "blocks": [("q", "1. 关于电流方向，下列说法正确的是（　　）"),
                ("ans", "正确答案：A"),
                ("note", ["解析：", "A 对：正电荷定向移动的方向规定为电流方向。",
                          "B 错：电源外部电流由正极经用电器流向负极。",
                          "C 错：金属中自由电子带负电，与电流方向相反。"])]},
]

T8_PAGES = [
    {"banner": "图片对比", "topic": "",
     "blocks": [("q", "1. 如图是一段电路，闭合开关后小灯泡发光。请在图中标出电流的方向。")],
     "absolute": [
         ("txt", ["A · 网络截图（原样贴入）"], 60, 214, 420, 40, 22, GRAY, False),
         ("img", os.path.join(STAGE, "t8_A_网络截图.png"), 60, 246, 330),
         ("txt", ["B · 原图适配（抠底＋缩放）"], 520, 214, 420, 40, 22, GRAY, False),
         ("img", os.path.join(STAGE, "t8_B_原图适配.png"), 520, 246, 270),
     ]},
]

P1_PAGES = [
    {"banner": "重点突破", "topic": "① 电路元件符号画法",
     "blocks": [("note", "口诀：长正短负 · 有点才连 · 不漏不造"),
                ("q", "电源：长线表示正极，短线表示负极。"),
                ("q", "灯泡：圆圈内画叉；电动机：圆圈内写 M。"),
                ("q", "定值电阻：长方形；导线交叉相连要画实心圆点。"),
                ("q", "导线交叉不相连：交叉处不画点，画成隔开的圆弧。")]},
    {"banner": "重点突破", "topic": "② 电路图四步画法",
     "blocks": [("note", "口诀：定连接 → 按电流顺序列元件 → 用标准符号 → 横平竖直、交叉加点"),
                ("q", "第1步 定连接：先判断串联还是并联。"),
                ("q", "第2步 按电流方向依次画出各元件。"),
                ("q", "第3步 用统一的标准符号，不漏不造。"),
                ("q", "第4步 导线横平竖直，交叉处加点。"),
                ("nq", "并联：先标分流点与汇合点，再连线。")]},
    {"banner": "重点突破", "topic": "③ 通路 / 断路 / 短路 / 短接",
     "blocks": [("note", "口诀：通路亮堂堂，断路全不响，短路危险大"),
                ("q", "通路：处处接通，有电流，用电器工作。"),
                ("q", "断路：某处断开，无电流，用电器不工作。"),
                ("q", "短路：导线直接接电源两极，电流过大，会烧坏电源。"),
                ("q", "短接：导线并接在用电器的两端，该用电器不工作。")]},
    {"banner": "当堂练习", "topic": "第1课时 · 电流与电路（点一下出答案）",
     "blocks": [("q", "1. 电荷的定向移动形成____。"),
                ("q", "2. 规定____电荷的定向移动方向为电流方向。"),
                ("q", "3. 电源外部，电流由____极流向____极。"),
                ("ans", "1. 电流"),
                ("ans", "2. 正电荷"),
                ("ans", "3. 正；负")]},
    {"banner": "当堂练习", "topic": "第2课时 · 电路图与电路状态（点一下出答案）",
     "blocks": [("q", "1. 电路图是用____表示电路连接情况的图。"),
                ("q", "2. 导线交叉相连处要画____。"),
                ("q", "3. 电路的三种状态：通路、____、____。"),
                ("ans", "1. 符号"),
                ("ans", "2. 实心圆点"),
                ("ans", "3. 断路；短路")]},
]

T16_PAGES = [
    {"banner": "当堂练习", "topic": "第1课时 · 电流与电路（点一下出答案）",
     "blocks": [("stem", "1. 关于电流的形成，下列说法正确的是（　）"),
                ("opt", "A. 电荷只要运动，就能形成电流"),
                ("opt", "B. 只有正电荷的定向移动才能形成电流"),
                ("opt", "C. 正、负电荷的定向移动都能形成电流"),
                ("opt", "D. 金属导体中自由电子定向移动的方向就是电流的方向"),
                ("ans", "正确答案：C")]},
    {"banner": "当堂练习", "topic": "第1课时 · 电流与电路（点一下出答案）",
     "blocks": [("stem", "2. 关于电流的方向，下列说法正确的是（　）"),
                ("opt", "A. 在电源外部，电流从电源正极经用电器流向负极"),
                ("opt", "B. 在电源内部，电流从正极流向负极"),
                ("opt", "C. 酸、碱、盐溶液中电流方向与负离子移动方向相同"),
                ("opt", "D. 电流的方向由自由电子的移动方向决定"),
                ("ans", "正确答案：A")]},
    {"banner": "当堂练习", "topic": "第1课时 · 电流与电路（点一下出答案）",
     "blocks": [("stem", "3. 要形成持续电流，必须满足的条件是（　）"),
                ("opt", "A. 电路中只要有电源"),
                ("opt", "B. 电路中只要有闭合的导线"),
                ("opt", "C. 电路中有电源，且电路是闭合回路"),
                ("opt", "D. 电路中只要有足够多的自由电荷"),
                ("ans", "正确答案：C")]},
    {"banner": "当堂练习", "topic": "第1课时 · 电流与电路（点一下出答案）",
     "blocks": [("stem", "4. 将下列物品接入电路的 a、b 两点，能使小灯泡发光的是（　）"),
                ("opt", "A. 塑料尺　B. 金属勺　C. 橡皮擦　D. 玻璃杯"),
                ("ans", "正确答案：B")]},
    {"banner": "当堂练习", "topic": "第1课时 · 电流与电路（点一下出答案）",
     "blocks": [("stem", "5. 一个完整的电路由____、____、____、____四部分组成。"),
                ("stem", "其中提供电能的是____，消耗电能的是____，"),
                ("stem", "控制电路通断的是____，输送电能的是____。"),
                ("ans", "电源、用电器、开关、导线；电源；用电器；开关；导线。")]},
    {"banner": "当堂练习", "topic": "第1课时 · 电流与电路（点一下出答案）",
     "blocks": [("stem", "6. 带正电的物体接触不带电的验电器的金属球，接触瞬间"),
                ("stem", "金属杆中的电流方向是____（选填“从物体到验电器”"),
                ("stem", "或“从验电器到物体”），金属箔将____。"),
                ("ans", "从物体到验电器；张开。")]},
]

# t16 = P1 的 5 页 + 第1课时 6 道当堂练习（内容来自 15.2 教案 docx，经 markitdown 提取、用户确认）
SETS = {"test": TEST_PAGES, "t8": T8_PAGES, "p1": P1_PAGES, "t16": P1_PAGES + T16_PAGES}
OUTS = {"test": "15.2第2节  电流和电路-原生大字测试.enbx",
        "t8": "15.2第2节  电流和电路-图片对比版.enbx",
        "p1": "15.2第2节  电流和电路-原生页版.enbx",
        "t16": "15.2第2节  电流和电路-原生页版-加第1课时练习.enbx"}


def render_page(sid, page, furniture):
    els = list(furniture)
    y = 60
    anim_n = 0
    if page.get("topic"):
        th = text_height([page["topic"]], 840, 24)
        els.append(text_xml([page["topic"]], 62, y, 840, th, 24, GRAY)); y += th + 8
    for kind, text in page.get("blocks", []):
        size, gap = {"q": (28, 8), "o": (28, 4), "ans": (28, 8), "note": (24, 6), "nq": (26, 6),
                      "stem": (28, 8), "opt": (22, 4)}.get(kind, (26, 6))
        color = TEAL if kind in ("ans", "ans2") else (GRAY if kind == "note" else DARK)
        lines = text if isinstance(text, list) else [text]
        h = text_height(lines, 840, size)
        anim = None
        if kind in ("ans", "ans2"):
            anim_n += 1; anim = anim_n
        els.append(text_xml(lines, 60, y, 840, h, size, color, bold=(kind == "ans"), anim=anim))
        y += h + gap
    resources = []
    for item in page.get("absolute", []):
        if item[0] == "txt":
            _, lines, x, yy, w, h, size, color, bold = item
            els.append(text_xml(lines, x, yy, w, h, size, color, bold))
        elif item[0] == "img":
            _, path, x, yy, w = item
            Image = _pillow()
            im = Image.open(path)
            pw, ph = im.size
            h = round(w * ph / pw)
            rid = uid()
            resources.append((rid, path))
            els.append(picture_xml(rid, os.path.basename(path), os.path.getsize(path), pw, ph, x, yy, w, h))
    return slide_xml(sid, els), y, resources


def build(src, out, pages):
    zin = zipfile.ZipFile(src)
    names = zin.namelist()
    n = len([x for x in names if re.match(r"Slides/Slide_\d+\.xml$", x)])
    board = zin.read("Board.xml").decode("utf-8-sig")
    items = re.findall(r"<Item>([^<]+)</Item>", board)
    if len(items) != n:
        raise SystemExit("Board 项数(%d) != Slide 数(%d)" % (len(items), n))
    out_entries = [(False, zin.read("Slides/Slide_%d.xml" % i)) for i in range(n)]
    out_items = list(items)
    new_res = []
    template_raw = zin.read("Slides/Slide_%d.xml" % TEMPLATE_SLIDE).decode("utf-8-sig")
    for page in pages:
        sid = uid()
        furn = make_furniture(template_raw, page["banner"])
        xml, used, res = render_page(sid, page, furn)
        if used > SLIDE_H:
            print("  ! 警告：页 [%s] 内容高 %dpx，超出 540" % (page["banner"], used))
        out_entries.append((True, xml.encode("utf-8"))); out_items.append(sid); new_res += res

    new_board = re.sub(r"<Slides>.*?</Slides>",
                       "<Slides>" + "".join("<Item>%s</Item>" % g for g in out_items) + "</Slides>",
                       board, flags=re.S)
    ref = zin.read("Reference.xml").decode("utf-8-sig")
    rels = "".join(
        "<Relationship><Id>%s</Id><Target>Resources\\%s.png</Target><Hash>%s</Hash></Relationship>"
        % (rid, rid, hashlib.md5(open(p, "rb").read()).hexdigest()) for rid, p in new_res)
    if rels:
        ref = ref.replace("</Relationships>", rels + "</Relationships>")
    zout = zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED)
    for nm in names:
        if nm in ("Board.xml", "Reference.xml") or re.match(r"Slides/Slide_\d+\.xml$", nm):
            continue
        zout.writestr(nm, zin.read(nm))
    for i, (is_new, data) in enumerate(out_entries):
        zout.writestr("Slides/Slide_%d.xml" % i, data)
    zout.writestr("Board.xml", new_board.encode("utf-8"))
    zout.writestr("Reference.xml", ref.encode("utf-8"))
    for rid, p in new_res:
        zout.writestr("Resources/%s.png" % rid, open(p, "rb").read())
    zout.close(); zin.close()
    return n, len(out_entries), len(new_res)


def verify(path):
    z = zipfile.ZipFile(path)
    names = z.namelist()
    n = len([x for x in names if re.match(r"Slides/Slide_\d+\.xml$", x)])
    items = re.findall(r"<Item>([^<]+)</Item>", z.read("Board.xml").decode("utf-8-sig"))
    ok = len(items) == n
    for i, g in enumerate(items):
        sid = re.search(r"<Id>([^<]+)</Id>", z.read("Slides/Slide_%d.xml" % i).decode("utf-8-sig"))
        if not sid or sid.group(1) != g:
            ok = False
    print("  自检：%s（%d 页，Board/Slide 一一对应）" % ("通过" if ok else "失败", n))
    return ok


USAGE = """用法：python3 build_enbx_native_pages.py [--set test|t8|p1|t16] [--out <路径>]

内置 15.2 课件的一次性页组，只做只读参数校验；--help 只打印用法，不执行构建、不写任何文件。
通用加页请按 references/06 §2 自己写。"""


def main():
    if "--help" in sys.argv or "-h" in sys.argv:
        print(USAGE)
        return 0
    setname = "p1"
    if "--set" in sys.argv:
        i = sys.argv.index("--set")
        if i + 1 >= len(sys.argv):
            print("错误：--set 缺少取值\n\n" + USAGE)
            return 2
        setname = sys.argv[i + 1]
        if setname not in SETS:
            print("错误：未知页组 %r（可选：%s）\n\n%s" % (setname, "/".join(SETS), USAGE))
            return 2
    out = os.path.join(WS, "99-待处理", "收件箱", OUTS[setname])
    if "--out" in sys.argv:
        i = sys.argv.index("--out")
        if i + 1 >= len(sys.argv):
            print("错误：--out 缺少取值\n\n" + USAGE)
            return 2
        out = sys.argv[i + 1]
    pages = SETS[setname]
    print("源课件:", os.path.basename(SRC), "| 页组:", setname, "| 新增", len(pages), "页")
    n0, n1, nr = build(SRC, out, pages)
    print("OK ->", out)
    print("  原页数 %d -> 新页数 %d（新增 %d 页；新图片资源 %d 个）" % (n0, n1, n1 - n0, nr))
    for p in pages:
        print("   ", p["banner"], "|", p.get("topic") or "")
    verify(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
