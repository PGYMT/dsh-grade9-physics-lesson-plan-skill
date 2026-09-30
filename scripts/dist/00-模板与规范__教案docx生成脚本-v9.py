#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""教案 docx 生成脚本 v9（在 v8 基础上增强，不修改 v8 本体）。

v9 职责：
  1. ```board 围栏 -> 板书 PNG（渲染在临时目录，嵌入后删除，不单独落盘）；
  2. 〔板书｜…〕旁批与教学旁批同格式，仅颜色改红（BoardMark 由 Note 克隆）；
  3. 按段首类型改派：〔待查｜〕〔来源｜〕〔素材｜〕〔设备｜〕〔课件插页｜〕-> CheckNote；
     〔过渡｜〕-> TransitionNote；头部依据块（首个 Heading1 之前的引用段）-> CheckNote；
  4. 正文末尾（分节符前）写生成信息块：技能版本／生成脚本／生成日期 + 最近修改版本／日期；
  5. 生成后自检：图片三件套 + 版本块 + v8 结构自检。

版本号读 SKILL.md frontmatter（JIAOAN_SKILL_DIR / 运行入口软链 / 权威源 依次尝试），读不到写「版本未知」。

用法：
  python3 教案docx生成脚本-v9.py                 # 默认第十五章 md文件/ 下全部 *详案.md
  python3 教案docx生成脚本-v9.py --dir <md目录>    # 指定目录下全部 *详案.md
  python3 教案docx生成脚本-v9.py <a.md> [b.md…]
  python3 教案docx生成脚本-v9.py --verify
"""
from __future__ import annotations
import os, re, sys, zipfile, shutil, importlib.util, tempfile, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
V8 = os.path.join(HERE, '教案docx生成脚本-v8.py')
TUTORIAL = os.path.abspath(os.path.join(HERE, '..', '06-工具与提示词', '教程'))
FENCE = chr(96) * 3
NL = chr(10)
BOARD_FENCE_RE = re.compile('^[ ]*' + FENCE + 'board[ ]*$')
EMU_PER_PX = 9525
CONTENT_EMU = 5200000
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


def _xml(s):
    return s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def _load_v8():
    spec = importlib.util.spec_from_file_location('jiaoxue_v8', V8)
    mod = importlib.util.module_from_spec(spec)
    sys.modules['jiaoxue_v8'] = mod
    spec.loader.exec_module(mod)
    return mod


def _load_board():
    if TUTORIAL not in sys.path:
        sys.path.insert(0, TUTORIAL)
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
    v8 = _load_v8()
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
    stats = v8.make_docx(tmp_md, out_path)
    if blocks:
        _patch_docx(out_path, imgs, ver, datetime.date.today().isoformat())
        shutil.rmtree(tmpdir, ignore_errors=True)
        shutil.rmtree(os.path.dirname(tmp_md), ignore_errors=True)
    _verify_output(out_path, ver, bool(blocks))
    if v8.verify([out_path]) != 0:
        raise SystemExit('v8 结构自检失败：' + os.path.basename(out_path))
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


def _parse_argv(argv):
    positional, d = [], None
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == '--dir':
            if i + 1 >= len(argv):
                raise SystemExit('错误：--dir 缺少取值')
            d = argv[i + 1]; i += 2; continue
        if a.startswith('--'):
            i += 1; continue
        positional.append(a); i += 1
    return positional, d


def main():
    v8 = _load_v8()
    ver = skill_version()
    argv = sys.argv[1:]
    args, d = _parse_argv(argv)
    if '--verify' in argv:
        targets = args or [v8.out_for(p) for p in (scan_dir(d) if d else v8.default_targets())]
        return v8.verify(targets)
    mds = args or (scan_dir(d) if d else v8.default_targets())
    if not mds:
        print('没有找到待转换的 md 文件')
        return 1
    for md in mds:
        out = v8.out_for(md)
        stats = make_docx_v9(md, out, ver)
        print('[写出]', os.path.basename(out), stats, '技能版本', ver)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())