#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""教案详案 Markdown 转 Word .docx：本技能唯一出口（纯标准库 OOXML，不依赖 python-docx）。

由工作区的「教案docx生成脚本-v8.py」(排版底座) 与「教案docx生成脚本-v9.py」(增强层) 合并而来；
板书图渲染由同目录 build_board_png.py 提供（Pillow）。合并后行为与合并前逐字节一致。

排版：一至三级标题写 outlineLvl，导航窗格可折叠；一级标题 pageBreakBefore 独立起页，
keepNext 不与后文分离；正文中文宋体、西文 Times New Roman，小四(12pt)，1.5 倍行距，
段后 7pt，两端对齐，首行缩进 2 字符；页边距上下 2.54cm、左右 3.17cm。教学旁批
「〔类型｜内容〕」用 Note 样式（仿宋、五号、左缩进、浅底纹）；学生预设「学生：」用
StudentReply 样式（楷体、灰色）。

增强层做五件事：
  1. 把 ```board 围栏渲染成板书 PNG 并居中嵌入（PNG 在临时目录生成，嵌入后即删，不落盘）；
  2. 旁批分色：〔板书｜〕红字、〔待查｜〕〔来源｜〕〔素材｜〕〔设备｜〕〔课件插页｜〕灰小字、
     〔过渡｜〕浅灰小字；首个一级标题之前的「依据」引用段转灰小字；
  3. 在分节符前写两行生成信息：本教案由教案技能 vX 生成（生成脚本／生成日期）、最近一次修改；
  4. 生成后自检图片三件套、版本块与 v8 结构（九个固定章节、outlineLvl、旁批样式、pageBreakBefore）；
  5. 生成后可选调用本技能 scripts/check_lesson.py 复核板书规格（失败只提示，不中断）。
   传 --contract 时一并跑契约↔正文一致校验（同样只提示）。

用法（与合并前的 v9 完全一致的旧接口）：
  python3 build_docx.py <a.md> [b.md…]          # 只处理显式给出的 md
  python3 build_docx.py --dir <md目录>           # 目录下全部 *详案.md
  python3 build_docx.py --all                    # 默认第十五章 md文件/ 下全部 *详案.md
  python3 build_docx.py --verify --dir <md目录>  # 只校验已生成的 docx
  python3 build_docx.py --dry-run <a.md…>        # 只列 md→docx，不写文件
用法（新增的干净接口，输出可离开教案目录）：
  python3 build_docx.py --md <a.md> --out <x.docx>       # 单份指定输出文件
  python3 build_docx.py --dir <md目录> --out-dir <目录>  # 批量输出到指定目录

安全约定：不带任何目标时只打印用法并退出 2；未知选项报错退出 2；--all 必须显式写。
依赖：Pillow（板书渲染）；系统没装时用本目录 vendor/pillow-*.whl，其次回退旧工作区 vendor。
版本号读 SKILL.md frontmatter：JIAOAN_SKILL_DIR／本技能根目录／运行入口软链／权威源 依次尝试。
"""
from __future__ import annotations
import argparse, datetime, os, re, shutil, subprocess, sys, tempfile, zipfile

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


HERE = os.path.dirname(os.path.abspath(__file__))
FENCE = chr(96) * 3
NL = chr(10)
BOARD_FENCE_RE = re.compile('^[ ]*' + FENCE + 'board[ ]*$')
EMU_PER_PX = 9525
CONTENT_EMU = 5200000
# 生成信息块里写的就是这个名字。改它会改变 docx 内容，与现存成品不再逐字节一致，
# 故合并后仍沿用旧名；要改等门3 重生成时统一改（方案批三）。
SCRIPT_NAME = '教案docx生成脚本-v9'
CHECK_TYPES = ['〔待查｜', '〔来源｜', '〔素材｜', '〔设备｜', '〔课件插页｜']
TYPE_STYLE = {'〔板书｜': 'BoardMark', '〔过渡｜': 'TransitionNote'}
for _t in CHECK_TYPES:
    TYPE_STYLE[_t] = 'CheckNote'


def skill_version():
    cands = []
    env = os.environ.get('JIAOAN_SKILL_DIR')
    if env:
        cands.append(env)
    cands.append(os.path.dirname(HERE))
    cands.append(os.path.expanduser('~/.dsh/skills/generate-9th-grade-physics-lesson-plan'))
    cands.append('/root/skill-repos/g9-physics')
    for d in cands:
        p = os.path.join(d, 'SKILL.md')
        if not os.path.isfile(p):
            continue
        try:
            m = re.search(r'^version:\s*([0-9][^\s]*)\s*$', open(p, encoding='utf-8').read(), re.M)
        except OSError:
            continue
        if m:
            return 'v' + m.group(1)
    return '版本未知'


def _skill_dir():
    cands = []
    env = os.environ.get('JIAOAN_SKILL_DIR')
    if env:
        cands.append(env)
    cands.append(os.path.dirname(HERE))
    cands.append(os.path.expanduser('~/.dsh/skills/generate-9th-grade-physics-lesson-plan'))
    cands.append('/root/skill-repos/g9-physics')
    for d in cands:
        if os.path.isfile(os.path.join(d, 'SKILL.md')):
            return d
    return ''


def _run_lesson_check(out_path, md_path, contract=''):
    skill = _skill_dir()
    p = os.path.join(skill, 'scripts', 'check_lesson.py') if skill else ''
    if not p or not os.path.isfile(p):
        print('  [提示] 未找到 check_lesson.py（路径：%s），跳过板书规格校验' % (p or '未定位技能目录'))
        return
    cmd = [sys.executable, p, '--docx', out_path, '--md', md_path]
    if contract:
        cmd += ['--contract', contract]
    if skill:
        cmd += ['--skill', skill]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True)
    except OSError as ex:
        print('  [提示] 调用 check_lesson.py 失败：%s' % ex)
        return
    print(r.stdout.rstrip())
    if r.returncode != 0:
        print('  [提示] check_lesson.py 有失败项（见上），不中断 docx 生成')


def _xml(s):
    return s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def _load_board():
    if HERE not in sys.path:
        sys.path.insert(0, HERE)
    import build_board_png
    return build_board_png


def _extract_blocks(md):
    lines = md.splitlines()
    out = []
    i = 0
    while i < len(lines):
        if BOARD_FENCE_RE.match(lines[i]):
            k = i + 1
            while k < len(lines) and not lines[k].strip().startswith(FENCE):
                k += 1
            out.append((i, min(k, len(lines) - 1)))
            i = k + 1
        else:
            i += 1
    return out


def _image_para(rid, docpid, cx, cy, name):
    s = '<w:p><w:pPr><w:jc w:val="center"/><w:spacing w:before="60" w:after="60"/></w:pPr>'
    s += '<w:r><w:drawing>'
    s += '<wp:inline distT="0" distB="0" distL="0" distR="0"'
    s += ' xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing">'
    s += '<wp:extent cx="' + str(cx) + '" cy="' + str(cy) + '"/>'
    s += '<wp:effectExtent l="0" t="0" r="0" b="0"/>'
    s += '<wp:docPr id="' + str(docpid) + '" name="' + name + '"/><wp:cNvGraphicFramePr/>'
    s += '<a:graphic xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">'
    s += '<a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture">'
    s += '<pic:pic xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture">'
    s += '<pic:nvPicPr><pic:cNvPr id="' + str(docpid) + '" name="' + name + '"/><pic:cNvPicPr/></pic:nvPicPr>'
    s += '<pic:blipFill><a:blip r:embed="' + rid + '"/><a:stretch><a:fillRect/></a:stretch></pic:blipFill>'
    s += '<pic:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="' + str(cx) + '" cy="' + str(cy) + '"/></a:xfrm>'
    s += '<a:prstGeom prst="rect"><a:avLst/></a:prstGeom></pic:spPr>'
    s += '</pic:pic></a:graphicData></a:graphic></wp:inline></w:drawing></w:r></w:p>'
    return s


def _clone_style(block, sid, color, sz=None, shd='KEEP'):
    b = block.replace('<w:style w:type="paragraph" w:styleId="Note">',
                      '<w:style w:type="paragraph" w:styleId="' + sid + '">', 1)
    b = b.replace('<w:name w:val="Note"/>', '<w:name w:val="' + sid + '"/>', 1)
    b = b.replace('<w:color w:val="595959"/>', '<w:color w:val="' + color + '"/>', 1)
    if sz is not None:
        b = b.replace('<w:sz w:val="21"/><w:szCs w:val="21"/>',
                      '<w:sz w:val="%d"/><w:szCs w:val="%d"/>' % (sz, sz), 1)
    if shd == 'KEEP':
        pass
    elif shd is None:
        b = re.sub(r'<w:shd\\b[^>]*/>', '', b, count=1)
    else:
        b = b.replace('w:fill="F2F2F2"', 'w:fill="' + shd + '"', 1)
    return b


def _reassign_styles(doc):
    def repl(m):
        blk = m.group(0)
        if 'w:val="Note"' not in blk:
            return blk
        tm = re.search(r'<w:t[^>]*>(.*?)</w:t>', blk, flags=re.S)
        if not tm:
            return blk
        for pref, style in TYPE_STYLE.items():
            if tm.group(1).startswith(pref):
                return blk.replace('w:val="Note"', 'w:val="%s"' % style, 1)
        return blk
    return re.sub(r'<w:p>.*?</w:p>', repl, doc, flags=re.S)


def _preamble_to_checknote(doc):
    m = re.search(r'<w:p><w:pPr><w:pStyle w:val="Heading1"/></w:pPr>', doc)
    if not m:
        return doc
    head, tail = doc[:m.start()], doc[m.start():]
    return head.replace('w:val="Quote"', 'w:val="CheckNote"') + tail


def _existing_provenance(path):
    try:
        with zipfile.ZipFile(path) as z:
            doc = z.read('word/document.xml').decode('utf-8')
    except Exception:
        return None
    m = re.search(r'本教案由 教案技能 (v[\w.\-]+) 生成（生成脚本：([^）]*)）｜生成日期 ([\d\-]+)', doc)
    if not m:
        return None
    return {'skill': m.group(1), 'script': m.group(2), 'date': m.group(3)}


def _provenance_lines(out_path, ver, today):
    old = _existing_provenance(out_path) if os.path.exists(out_path) else None
    gen = old or {'skill': ver, 'script': SCRIPT_NAME, 'date': today}
    return [
        '本教案由 教案技能 %s 生成（生成脚本：%s）｜生成日期 %s' % (gen['skill'], gen['script'], gen['date']),
        '最近一次修改：教案技能 %s｜修改日期 %s' % (ver, today),
    ]


def _insert_provenance(doc, lines):
    i = doc.rfind('<w:sectPr>')
    if i < 0:
        return doc
    para = ''
    for ln in lines:
        para += ('<w:p><w:pPr><w:pStyle w:val="ProvenanceNote"/></w:pPr><w:r>'
                 '<w:t xml:space="preserve">' + _xml(ln) + '</w:t></w:r></w:p>')
    return doc[:i] + para + doc[i:]


def make_docx_v9(md_path, out_path, ver):
    board = _load_board()
    md = open(md_path, encoding='utf-8').read()
    lines = md.splitlines()
    blocks = _extract_blocks(md)
    imgs = []
    tmpdir = None
    if blocks:
        tmpdir = tempfile.mkdtemp(prefix='board_')
        pngdir = os.path.join(tmpdir, 'png')
        tmp_boards = os.path.join(tmpdir, 'boards.md')
        with open(tmp_boards, 'w', encoding='utf-8') as f:
            for s, e in blocks:
                f.write(NL.join(lines[s:e + 1]))
                f.write(NL + NL)
        imgs = board.render_boards(tmp_boards, pngdir)
        for idx, info in enumerate(imgs):
            newpath = os.path.join(pngdir, 'board-%d.png' % (idx + 1))
            if os.path.abspath(info['path']) != os.path.abspath(newpath):
                os.replace(info['path'], newpath)
            info['path'] = newpath
        new_lines = list(lines)
        for k in range(len(blocks) - 1, -1, -1):
            s, e = blocks[k]
            new_lines[s:e + 1] = ['@@BOARDIMG' + str(k + 1) + '@@']
        md_dir = tempfile.mkdtemp(prefix='md_')
        tmp_md = os.path.join(md_dir, os.path.basename(md_path))
        with open(tmp_md, 'w', encoding='utf-8') as f:
            f.write(NL.join(new_lines) + NL)
    else:
        tmp_md = md_path
    stats = make_docx(tmp_md, out_path)
    if blocks:
        _patch_docx(out_path, imgs, ver, datetime.date.today().isoformat())
        shutil.rmtree(tmpdir, ignore_errors=True)
        shutil.rmtree(os.path.dirname(tmp_md), ignore_errors=True)
    _verify_output(out_path, ver, bool(blocks))
    if verify([out_path]) != 0:
        raise SystemExit('结构自检失败：' + os.path.basename(out_path))
    return stats


def _patch_docx(out_path, imgs, ver, today):
    with zipfile.ZipFile(out_path) as z:
        parts = {n: z.read(n) for n in z.namelist()}
    doc = parts['word/document.xml'].decode('utf-8')
    styles = parts['word/styles.xml'].decode('utf-8')
    rels = parts['word/_rels/document.xml.rels'].decode('utf-8')
    ctypes = parts['[Content_Types].xml'].decode('utf-8')

    root_old = '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
    root_new = '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
    doc = doc.replace(root_old, root_new, 1)
    doc = _reassign_styles(doc)
    doc = _preamble_to_checknote(doc)

    for i, info in enumerate(imgs):
        rid = 'rIdIM' + str(i + 1)
        name = 'board-%d.png' % (i + 1)
        px_w, px_h = info['width'], info['height']
        scale = min(1.0, CONTENT_EMU / float(px_w * EMU_PER_PX))
        cx = int(px_w * EMU_PER_PX * scale)
        cy = int(px_h * EMU_PER_PX * scale)
        img_xml = _image_para(rid, 900 + i, cx, cy, name)
        marker = '<w:p><w:pPr></w:pPr><w:r><w:t xml:space="preserve">@@BOARDIMG' + str(i + 1) + '@@</w:t></w:r></w:p>'
        if marker in doc:
            doc = doc.replace(marker, img_xml)
        else:
            doc = doc.replace('@@BOARDIMG' + str(i + 1) + '@@', img_xml)
        with open(info['path'], 'rb') as f:
            parts['word/media/' + name] = f.read()
        rels = rels.replace('</Relationships>',
            '<Relationship Id="' + rid + '" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="media/' + name + '"/></Relationships>')

    doc = _insert_provenance(doc, _provenance_lines(out_path, ver, today))

    nm = re.search(r'(<w:style w:type="paragraph" w:styleId="Note">.*?</w:style>)', styles, re.S)
    if nm:
        note = nm.group(1)
        styles = re.sub(r'<w:style w:type="paragraph" w:styleId="BoardMark">.*?</w:style>', '', styles, count=1, flags=re.S)
        add = (_clone_style(note, 'BoardMark', 'C00000')
               + _clone_style(note, 'CheckNote', '7F7F7F', sz=18, shd='F7F7F7')
               + _clone_style(note, 'TransitionNote', 'BFBFBF', sz=18, shd='FBFBFB')
               + _clone_style(note, 'ProvenanceNote', '808080', sz=18, shd=None))
        i = styles.rfind('</w:styles>')
        styles = styles[:i] + add + styles[i:]

    if 'Extension="png"' not in ctypes:
        ctypes = ctypes.replace('</Types>', '<Default Extension="png" ContentType="image/png"/></Types>')

    parts['word/document.xml'] = doc.encode('utf-8')
    parts['word/styles.xml'] = styles.encode('utf-8')
    parts['word/_rels/document.xml.rels'] = rels.encode('utf-8')
    parts['[Content_Types].xml'] = ctypes.encode('utf-8')
    with zipfile.ZipFile(out_path, 'w', zipfile.ZIP_DEFLATED) as z:
        for n, data in parts.items():
            z.writestr(n, data)


def _verify_output(out_path, ver, expect_media):
    with zipfile.ZipFile(out_path) as z:
        names = set(z.namelist())
        doc = z.read('word/document.xml').decode('utf-8')
        rels = z.read('word/_rels/document.xml.rels').decode('utf-8')
        styles_x = z.read('word/styles.xml').decode('utf-8')
    probs = []
    media = sorted(n for n in names if n.startswith('word/media/'))
    if expect_media and not media:
        probs.append('缺 word/media 板书图')
    for m in re.finditer(r'<Relationship Id="(rIdIM\d+)"[^>]*Target="media/([^"]+)"', rels):
        if ('r:embed="%s"' % m.group(1)) not in doc:
            probs.append('缺 r:embed:' + m.group(1))
    if 'w:styleId="BoardMark"' not in styles_x:
        probs.append('缺 BoardMark 样式')
    if 'ProvenanceNote' not in doc or (ver != '版本未知' and ver not in doc):
        probs.append('缺生成信息块或版本不符')
    if probs:
        raise SystemExit('自检失败 %s：%s' % (os.path.basename(out_path), '; '.join(probs)))


def scan_dir(d):
    if not os.path.isdir(d):
        raise SystemExit('目录不存在：' + d)
    return sorted(os.path.join(d, n) for n in os.listdir(d) if n.endswith('详案.md'))


def _build_parser():
    p = argparse.ArgumentParser(
        prog=os.path.basename(__file__),
        description='把教案 Markdown 转成 docx，并嵌入板书图、写版本块、做结构自检。',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            '示例：\n'
            '  python3 build_docx.py 某详案.md\n'
            '  python3 build_docx.py --dir 某章/md文件\n'
            '  python3 build_docx.py --all\n'
            '  python3 build_docx.py --dry-run 某详案.md\n'
            '  python3 build_docx.py --verify --dir 某章/md文件\n'
            '  python3 build_docx.py --md 某详案.md --out /tmp/x.docx\n'
            '  python3 build_docx.py --dir 某章/md文件 --out-dir /tmp/docx\n'
        ))
    p.add_argument('md', nargs='*', metavar='MD', help='要转换的 .md 文件；可给多个')
    g = p.add_mutually_exclusive_group()
    g.add_argument('--dir', metavar='DIR', help='转换目录下全部 *详案.md')
    g.add_argument('--all', action='store_true', help='显式转换默认第十五章 md文件/ 下全部 *详案.md')
    p.add_argument('--md', dest='md_opt', action='append', metavar='MD', default=[],
                   help='与位置参数等价，便于脚本调用；可重复')
    p.add_argument('--out', metavar='DOCX', help='单份时指定输出文件（可离开教案目录）')
    p.add_argument('--out-dir', metavar='DIR', help='指定输出目录，文件名沿用默认规则')
    p.add_argument('--verify', action='store_true', help='只校验 docx，不写文件')
    p.add_argument('--dry-run', action='store_true', help='只列出 md→docx，不写文件')
    p.add_argument('--contract', metavar='JSON',
                   help='可选课程契约 json；转给 check_lesson.py 顺带跑一致校验')
    return p


def _collect_mds(ns):
    if ns.all:
        return default_targets()
    if ns.dir:
        return scan_dir(ns.dir)
    return list(ns.md)


def _validate_mds(mds, parser):
    if not mds:
        parser.error('没有找到待转换的 md 文件')
    for md in mds:
        if not md.endswith('.md'):
            parser.error('只接受 .md 文件：' + md)
        if not os.path.isfile(md):
            parser.error('文件不存在：' + md)


def _out_path(md, ns):
    """单份 md 的输出路径：--out 优先，其次 --out-dir，否则按教案目录规则。"""
    if ns.out:
        return ns.out
    if ns.out_dir:
        return os.path.join(ns.out_dir, os.path.basename(out_for(md)))
    return out_for(md)


def main():
    parser = _build_parser()
    ns = parser.parse_args()
    ns.md = list(ns.md) + list(ns.md_opt or [])
    if ns.md and ns.all:
        parser.error('不能同时给 md 文件和 --all')
    if ns.md and ns.dir:
        parser.error('不能同时给 md 文件和 --dir')
    if ns.verify and ns.dry_run:
        parser.error('--verify 与 --dry-run 不能同时使用')
    if not ns.md and not ns.dir and not ns.all:
        parser.print_usage(sys.stderr)
        print('错误：必须显式指定 md 文件、--dir 或 --all；本脚本不再默认扫描整章。', file=sys.stderr)
        return 2
    ver = skill_version()
    mds = _collect_mds(ns)
    _validate_mds(mds, parser)
    if ns.out and ns.out_dir:
        parser.error('--out 与 --out-dir 不能同时使用')
    if ns.out and len(mds) != 1:
        parser.error('--out 只能配单份 md；多份请用 --out-dir')
    if ns.out_dir and not ns.verify:
        os.makedirs(ns.out_dir, exist_ok=True)
    if ns.out and not ns.verify:
        parent = os.path.dirname(os.path.abspath(ns.out))
        if parent:
            os.makedirs(parent, exist_ok=True)
    if ns.all:
        print('[范围] 默认章节目录，共 %d 份' % len(mds))
    if ns.verify:
        return verify([_out_path(md, ns) for md in mds])
    if ns.dry_run:
        print('[dry-run] 将处理 %d 份：' % len(mds))
        for md in mds:
            print('  %s -> %s' % (md, _out_path(md, ns)))
        return 0
    for md in mds:
        out = _out_path(md, ns)
        stats = make_docx_v9(md, out, ver)
        print('[写出]', os.path.basename(out), stats, '技能版本', ver)
        _run_lesson_check(out, md, ns.contract)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())