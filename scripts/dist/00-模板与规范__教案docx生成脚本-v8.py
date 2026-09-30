#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把教案详案 Markdown 转成 Word .docx（纯标准库 OOXML，无需 python-docx）。

排版依据：教案生成技能 v8「Word 排版要求（docx 便于查阅）」
  - 一至三级标题 = Heading1/Heading2/Heading3，写 w:outlineLvl，导航窗格可折叠；
  - 一级标题 pageBreakBefore 独立起页，标题 keepNext 不与后文分离；
  - 正文中文宋体、西文 Times New Roman，小四(12pt)，1.5 倍行距，段后 7pt，
    两端对齐，首行缩进 2 字符；
  - 页边距上下 2.54cm、左右 3.17cm；
  - 教学旁批「〔类型｜内容〕」用 Note 样式（仿宋、五号、左缩进、浅底纹），
    学生预设「学生：」用 StudentReply 样式（楷体、灰色），与讲课正文可区分；
  - 兼容旧写法「（板书：……）」段落左缩进；表格带边框且首行表头；公式用 Unicode 文本。

用法：
  python3 教案docx生成脚本-v6.py                 # 默认转换第十五章 md文件/ 下全部*详案.md
  python3 教案docx生成脚本-v6.py <a.md> [b.md…]  # 转换指定 md
  python3 教案docx生成脚本-v6.py --verify        # 重读已生成 docx 自检
"""
from __future__ import annotations

import os
import re
import sys
import zipfile
from xml.sax.saxutils import escape

DEFAULT_MD_DIR = "/root/dsh-workspace/工作文件/04-教案/第十五章-电流和电路/md文件"

# ---------------------------------------------------------------- 样式表
STYLES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:docDefaults>
    <w:rPrDefault><w:rPr>
      <w:rFonts w:ascii="Times New Roman" w:eastAsia="\u5b8b\u4f53" w:hAnsi="Times New Roman" w:cs="Times New Roman"/>
      <w:sz w:val="24"/><w:szCs w:val="24"/>
    </w:rPr></w:rPrDefault>
    <w:pPrDefault><w:pPr>
      <w:spacing w:after="140" w:line="360" w:lineRule="auto"/>
      <w:jc w:val="both"/>
    </w:pPr></w:pPrDefault>
  </w:docDefaults>

  <w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/><w:qFormat/>
    <w:pPr>
      <w:spacing w:after="140" w:line="360" w:lineRule="auto"/>
      <w:jc w:val="both"/>
      <w:ind w:firstLineChars="200" w:firstLine="480"/>
    </w:pPr>
    <w:rPr><w:rFonts w:ascii="Times New Roman" w:eastAsia="\u5b8b\u4f53" w:hAnsi="Times New Roman"/><w:sz w:val="24"/><w:szCs w:val="24"/></w:rPr>
  </w:style>

  <w:style w:type="paragraph" w:styleId="Title"><w:name w:val="Title"/><w:basedOn w:val="Normal"/><w:next w:val="Normal"/><w:qFormat/>
    <w:pPr>
      <w:spacing w:before="240" w:after="240" w:line="360" w:lineRule="auto"/>
      <w:jc w:val="center"/><w:ind w:firstLineChars="0" w:firstLine="0"/>
    </w:pPr>
    <w:rPr><w:rFonts w:ascii="Times New Roman" w:eastAsia="\u9ed1\u4f53" w:hAnsi="Times New Roman"/><w:b/><w:sz w:val="40"/><w:szCs w:val="40"/></w:rPr>
  </w:style>

  <w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/><w:basedOn w:val="Normal"/><w:next w:val="Normal"/><w:qFormat/>
    <w:pPr>
      <w:keepNext/><w:pageBreakBefore/><w:outlineLvl w:val="0"/>
      <w:spacing w:before="240" w:after="160" w:line="360" w:lineRule="auto"/>
      <w:jc w:val="left"/><w:ind w:firstLineChars="0" w:firstLine="0"/>
    </w:pPr>
    <w:rPr><w:rFonts w:ascii="Times New Roman" w:eastAsia="\u9ed1\u4f53" w:hAnsi="Times New Roman"/><w:b/><w:sz w:val="36"/><w:szCs w:val="36"/></w:rPr>
  </w:style>

  <w:style w:type="paragraph" w:styleId="Heading2"><w:name w:val="heading 2"/><w:basedOn w:val="Normal"/><w:next w:val="Normal"/><w:qFormat/>
    <w:pPr>
      <w:keepNext/><w:outlineLvl w:val="1"/>
      <w:spacing w:before="200" w:after="120" w:line="360" w:lineRule="auto"/>
      <w:jc w:val="left"/><w:ind w:firstLineChars="0" w:firstLine="0"/>
    </w:pPr>
    <w:rPr><w:rFonts w:ascii="Times New Roman" w:eastAsia="\u9ed1\u4f53" w:hAnsi="Times New Roman"/><w:b/><w:sz w:val="28"/><w:szCs w:val="28"/></w:rPr>
  </w:style>

  <w:style w:type="paragraph" w:styleId="Heading3"><w:name w:val="heading 3"/><w:basedOn w:val="Normal"/><w:next w:val="Normal"/><w:qFormat/>
    <w:pPr>
      <w:keepNext/><w:outlineLvl w:val="2"/>
      <w:spacing w:before="160" w:after="100" w:line="360" w:lineRule="auto"/>
      <w:jc w:val="left"/><w:ind w:firstLineChars="0" w:firstLine="0"/>
    </w:pPr>
    <w:rPr><w:rFonts w:ascii="Times New Roman" w:eastAsia="\u9ed1\u4f53" w:hAnsi="Times New Roman"/><w:b/><w:sz w:val="26"/><w:szCs w:val="26"/></w:rPr>
  </w:style>

  <w:style w:type="paragraph" w:styleId="Quote"><w:name w:val="Quote"/><w:basedOn w:val="Normal"/><w:qFormat/>
    <w:pPr>
      <w:spacing w:after="80" w:line="320" w:lineRule="auto"/>
      <w:jc w:val="left"/><w:ind w:left="240" w:firstLineChars="0" w:firstLine="0"/>
    </w:pPr>
    <w:rPr><w:rFonts w:ascii="Times New Roman" w:eastAsia="\u5b8b\u4f53" w:hAnsi="Times New Roman"/><w:sz w:val="21"/><w:color w:val="595959"/></w:rPr>
  </w:style>

  <w:style w:type="paragraph" w:styleId="Code"><w:name w:val="Code"/><w:basedOn w:val="Normal"/><w:qFormat/>
    <w:pPr>
      <w:spacing w:after="0" w:line="240" w:lineRule="auto"/>
      <w:jc w:val="left"/><w:ind w:left="200" w:firstLineChars="0" w:firstLine="0"/>
    </w:pPr>
    <w:rPr><w:rFonts w:ascii="Consolas" w:eastAsia="\u5b8b\u4f53" w:hAnsi="Consolas"/><w:sz w:val="21"/></w:rPr>
  </w:style>

  <w:style w:type="paragraph" w:styleId="ListPlain"><w:name w:val="ListPlain"/><w:basedOn w:val="Normal"/><w:qFormat/>
    <w:pPr>
      <w:spacing w:after="80" w:line="360" w:lineRule="auto"/>
      <w:jc w:val="left"/><w:ind w:left="420" w:firstLineChars="0" w:firstLine="0"/>
    </w:pPr>
    <w:rPr><w:rFonts w:ascii="Times New Roman" w:eastAsia="\u5b8b\u4f53" w:hAnsi="Times New Roman"/><w:sz w:val="24"/></w:rPr>
  </w:style>

  <w:style w:type="paragraph" w:styleId="Note"><w:name w:val="Note"/><w:basedOn w:val="Normal"/><w:qFormat/>
    <w:pPr>
      <w:shd w:val="clear" w:color="auto" w:fill="F2F2F2"/>
      <w:spacing w:after="60" w:line="340" w:lineRule="auto"/>
      <w:jc w:val="left"/><w:ind w:left="420" w:firstLineChars="0" w:firstLine="0"/>
    </w:pPr>
    <w:rPr><w:rFonts w:ascii="FangSong" w:eastAsia="仿宋" w:hAnsi="FangSong"/><w:color w:val="595959"/><w:sz w:val="21"/><w:szCs w:val="21"/></w:rPr>
  </w:style>

  <w:style w:type="paragraph" w:styleId="StudentReply"><w:name w:val="StudentReply"/><w:basedOn w:val="Normal"/><w:qFormat/>
    <w:pPr>
      <w:spacing w:after="80" w:line="360" w:lineRule="auto"/>
      <w:jc w:val="left"/><w:ind w:left="420" w:firstLineChars="0" w:firstLine="0"/>
    </w:pPr>
    <w:rPr><w:rFonts w:ascii="KaiTi" w:eastAsia="楷体" w:hAnsi="KaiTi"/><w:color w:val="595959"/><w:sz w:val="24"/></w:rPr>
  </w:style>

  <w:style w:type="paragraph" w:styleId="BoardMark"><w:name w:val="BoardMark"/><w:basedOn w:val="Normal"/><w:qFormat/>
    <w:pPr>
      <w:spacing w:after="80" w:line="360" w:lineRule="auto"/>
      <w:jc w:val="left"/><w:ind w:left="420" w:firstLineChars="0" w:firstLine="0"/>
    </w:pPr>
    <w:rPr><w:rFonts w:ascii="Times New Roman" w:eastAsia="\u5b8b\u4f53" w:hAnsi="Times New Roman"/><w:sz w:val="24"/></w:rPr>
  </w:style>
</w:styles>"""

CONTENT_TYPES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
  <Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
  <Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>
  <Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>
</Types>"""

RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>
  <Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>
</Relationships>"""

DOC_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
</Relationships>"""


def _core(title: str) -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties"'
        ' xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/"'
        ' xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
        f"<dc:title>{escape(title)}</dc:title><dc:creator>AI Assistant</dc:creator>"
        "<cp:lastModifiedBy>AI Assistant</cp:lastModifiedBy></cp:coreProperties>"
    )


APP = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties" xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">
  <Application>jiaoxue-docx-v8</Application>
</Properties>"""


# ---------------------------------------------------------------- 行内解析
def runs_xml(text: str) -> str:
    """把 [标题](链接)、**粗体** 与 `等宽` 转成 run，其余转普通 run。"""
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", lambda m: m.group(1) + "（" + m.group(2) + "）", text)
    text = text.replace("`", "")
    out = []
    for part in re.split(r"(\*\*.+?\*\*)", text):
        if not part:
            continue
        if part.startswith("**") and part.endswith("**") and len(part) > 4:
            out.append(
                '<w:r><w:rPr><w:b/></w:rPr><w:t xml:space="preserve">'
                + escape(part[2:-2])
                + "</w:t></w:r>"
            )
        else:
            out.append('<w:r><w:t xml:space="preserve">' + escape(part) + "</w:t></w:r>")
    return "".join(out) or '<w:r><w:t xml:space="preserve"> </w:t></w:r>'


def para(text: str = "", style: str | None = None) -> str:
    ppr = "<w:pPr>"
    if style:
        ppr += f'<w:pStyle w:val="{style}"/>'
    ppr += "</w:pPr>"
    if not text:
        return f"<w:p>{ppr}</w:p>"
    return f"<w:p>{ppr}{runs_xml(text)}</w:p>"


def table_xml(rows: list[list[str]]) -> str:
    ncols = max(len(r) for r in rows)
    widths = [int(9600 / ncols)] * ncols
    widths[-1] += 9600 - sum(widths)
    out = [
        "<w:tbl><w:tblPr><w:tblW w:w=\"9600\" w:type=\"dxa\"/><w:tblLayout w:type=\"fixed\"/>",
        "<w:tblBorders>"
        '<w:top w:val="single" w:sz="4" w:space="0" w:color="808080"/>'
        '<w:left w:val="single" w:sz="4" w:space="0" w:color="808080"/>'
        '<w:bottom w:val="single" w:sz="4" w:space="0" w:color="808080"/>'
        '<w:right w:val="single" w:sz="4" w:space="0" w:color="808080"/>'
        '<w:insideH w:val="single" w:sz="4" w:space="0" w:color="808080"/>'
        '<w:insideV w:val="single" w:sz="4" w:space="0" w:color="808080"/>'
        "</w:tblBorders></w:tblPr><w:tblGrid>",
    ]
    out.append("".join(f'<w:gridCol w:w="{w}"/>' for w in widths))
    out.append("</w:tblGrid>")
    for i, row in enumerate(rows):
        out.append("<w:tr>")
        for j in range(ncols):
            cell = row[j] if j < len(row) else ""
            shade = '<w:shd w:val="clear" w:color="auto" w:fill="DCE6F1"/>' if i == 0 else ""
            body = (
                "<w:p><w:pPr><w:pStyle w:val=\"TableText\"/>"
                + ("<w:rPr><w:b/></w:rPr>" if i == 0 else "")
                + "</w:pPr>"
                + runs_xml(cell)
                + "</w:p>"
            )
            out.append(
                f'<w:tc><w:tcPr><w:tcW w:w="{widths[j]}" w:type="dxa"/>{shade}'
                '<w:vAlign w:val="center"/></w:tcPr>' + body + "</w:tc>"
            )
        out.append("</w:tr>")
    out.append("</w:tbl>")
    return "".join(out)


TABLE_TEXT_STYLE = """  <w:style w:type="paragraph" w:styleId="TableText"><w:name w:val="TableText"/><w:basedOn w:val="Normal"/><w:qFormat/>
    <w:pPr>
      <w:spacing w:after="20" w:before="20" w:line="280" w:lineRule="auto"/>
      <w:jc w:val="left"/><w:ind w:firstLineChars="0" w:firstLine="0"/>
    </w:pPr>
    <w:rPr><w:rFonts w:ascii="Times New Roman" w:eastAsia="\u5b8b\u4f53" w:hAnsi="Times New Roman"/><w:sz w:val="21"/></w:rPr>
  </w:style>
</w:styles>"""


def is_sep_row(cells: list[str]) -> bool:
    return all(re.fullmatch(r":?-{2,}:?", c.replace(" ", "")) for c in cells if c != "") and any(
        c.strip() for c in cells
    )


def convert(md_text: str) -> tuple[str, dict]:
    body: list[str] = []
    stats = {"h1": 0, "h2": 0, "h3": 0, "tables": 0, "code_lines": 0, "paras": 0,
             "notes": 0, "student": 0}
    in_code = False
    first_h1 = True
    lines = md_text.splitlines()
    i = 0
    while i < len(lines):
        raw = lines[i].rstrip()
        stripped = raw.strip()

        if stripped.startswith("```"):
            in_code = not in_code
            i += 1
            continue

        if in_code:
            body.append(para(raw, "Code"))
            stats["code_lines"] += 1
            i += 1
            continue

        if stripped.startswith("|"):
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                if not is_sep_row(cells):
                    rows.append(cells)
                i += 1
            if rows:
                body.append(table_xml(rows))
                stats["tables"] += 1
            continue

        if not stripped or re.fullmatch(r"-{3,}", stripped):
            i += 1
            continue

        if stripped.startswith("#### "):
            body.append(para(stripped[5:], "Heading3"))
            stats["h3"] += 1
        elif stripped.startswith("### "):
            body.append(para(stripped[4:], "Heading2"))
            stats["h2"] += 1
        elif stripped.startswith("## "):
            body.append(para(stripped[3:], "Heading1"))
            stats["h1"] += 1
        elif stripped.startswith("# "):
            # 文档标题：首个标题用 Title 样式（不进导航缩进），后续按一级标题处理
            style = "Title" if first_h1 else "Heading1"
            body.append(para(stripped[2:], style))
            first_h1 = False
        elif stripped.startswith("> "):
            body.append(para(stripped[2:], "Quote"))
        elif re.match(r"^\d+[.、]\s+", stripped):
            body.append(para(stripped, "ListPlain"))
        elif stripped.startswith(("- ", "* ")):
            body.append(para("- " + stripped[2:], "ListPlain"))
        elif stripped.startswith("〔"):
            body.append(para(stripped, "Note"))
            stats["notes"] += 1
        elif stripped.startswith("学生："):
            body.append(para(stripped, "StudentReply"))
            stats["student"] += 1
        elif stripped.startswith(("（板书：", "（板书时机：", "**（板书：", "**（板书时机：")):
            body.append(para(stripped, "BoardMark"))
        else:
            # 行尾的（板书：……）单独成段并左缩进，保持它在教师语言流程中的位置
            m = re.match(r"^(.*?)(（板书：[^（）]*）)$", stripped)
            if m and m.group(1).strip():
                body.append(para(m.group(1).strip()))
                body.append(para(m.group(2), "BoardMark"))
            else:
                body.append(para(stripped))
            stats["paras"] += 1
        i += 1

    xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        "<w:body>"
        + "".join(body)
        + '<w:sectPr><w:pgSz w:w="11906" w:h="16838"/>'
        '<w:pgMar w:top="1440" w:right="1797" w:bottom="1440" w:left="1797" '
        'w:header="851" w:footer="992" w:gutter="0"/></w:sectPr>'
        "</w:body></w:document>"
    )
    return xml, stats


def make_docx(md_path: str, out_path: str) -> dict:
    md_text = open(md_path, encoding="utf-8").read()
    doc_xml, stats = convert(md_text)
    title = md_text.splitlines()[0].lstrip("# ").strip()
    styles = STYLES.replace("</w:styles>", TABLE_TEXT_STYLE)
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", CONTENT_TYPES)
        zf.writestr("_rels/.rels", RELS)
        zf.writestr("word/document.xml", doc_xml)
        zf.writestr("word/styles.xml", styles)
        zf.writestr("word/_rels/document.xml.rels", DOC_RELS)
        zf.writestr("docProps/core.xml", _core(title))
        zf.writestr("docProps/app.xml", APP)
    stats["bytes"] = os.path.getsize(out_path)
    return stats


def default_targets() -> list[str]:
    if not os.path.isdir(DEFAULT_MD_DIR):
        return []
    return sorted(
        os.path.join(DEFAULT_MD_DIR, n)
        for n in os.listdir(DEFAULT_MD_DIR)
        if n.endswith("详案.md")
    )


def out_for(md_path: str) -> str:
    md_path = os.path.abspath(md_path)
    stem = os.path.splitext(os.path.basename(md_path))[0]
    parent = os.path.dirname(md_path)
    if os.path.basename(parent) == "md文件":
        return os.path.join(os.path.dirname(parent), stem + ".docx")
    return os.path.join(parent, stem + ".docx")


def verify(paths: list[str]) -> int:
    ok = True
    need = ["一、教材分析", "二、学情分析", "三、教学目标", "四、教学重难点",
            "五、教学准备", "六、教学过程", "七、板书完整设计", "八、教学反思预设", "九、参考资料"]
    for out in paths:
        try:
            with zipfile.ZipFile(out) as zf:
                names = set(zf.namelist())
                doc = zf.read("word/document.xml").decode("utf-8")
                styles = zf.read("word/styles.xml").decode("utf-8")
        except Exception as exc:  # noqa: BLE001
            print(f"[FAIL] {out}: {exc}")
            ok = False
            continue
        text = re.sub(r"<[^>]+>", "", doc)
        h1 = doc.count('w:val="Heading1"')
        h2 = doc.count('w:val="Heading2"')
        h3 = doc.count('w:val="Heading3"')
        miss = [s for s in need if s not in text]
        problems = []
        if miss:
            problems.append("缺章节:" + ",".join(miss))
        if 'w:outlineLvl w:val="0"' not in styles or 'w:outlineLvl w:val="2"' not in styles:
            problems.append("缺outlineLvl")
        if 'w:styleId="Note"' not in styles or 'w:styleId="StudentReply"' not in styles:
            problems.append("缺旁批样式")
        if "pageBreakBefore" not in styles:
            problems.append("缺pageBreakBefore")
        if "v4" in text:
            problems.append("残留v4")
        if not names >= {"word/document.xml", "word/styles.xml", "[Content_Types].xml"}:
            problems.append("缺部件")
        status = "OK " if not problems else "FAIL"
        if problems:
            ok = False
        print(
            f"[{status}] {os.path.basename(out)}: H1={h1} H2={h2} H3={h3} "
            f"表格={doc.count('<w:tbl>')} 板书行={doc.count('BoardMark')} "
            f"旁批={doc.count('w:val=\"Note\"')} 学生预设={doc.count('w:val=\"StudentReply\"')} "
            f"字符={len(text)} 大小={os.path.getsize(out)}B"
            + ("  << " + "; ".join(problems) if problems else "")
        )
    return 0 if ok else 1


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if "--verify" in sys.argv:
        targets = args or [out_for(p) for p in default_targets()]
        return verify(targets)
    mds = args or default_targets()
    if not mds:
        print("没有找到待转换的 md 文件")
        return 1
    for md in mds:
        out = out_for(md)
        stats = make_docx(md, out)
        print(
            f"[写出] {os.path.basename(out)}  H1={stats['h1']} H2={stats['h2']} "
            f"H3={stats['h3']} 表格={stats['tables']} 板书行={stats['code_lines']} "
            f"旁批={stats['notes']} 学生预设={stats['student']} "
            f"{stats['bytes']}B"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
