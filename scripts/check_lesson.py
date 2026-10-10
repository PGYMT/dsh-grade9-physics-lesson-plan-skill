#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""check_lesson.py — 教案成品·板书规格外部校验（v8.10.0，纯标准库）。

用法：
  python3 scripts/check_lesson.py --docx 详案.docx --md 详案.md [--skill SKILL.md]

失败项 6 项（影响退出码）：
  1. board 块数 ≤2（## 板N 与 board 围栏数双测）；
  2. 每块实际书写行 ≤8（不含 #/## 标题与空行）；
  3. docx 有内嵌板书图，且本次未向 04-教案/<章节>/板书图/ 新增文件；
  4. docx 末尾生成信息块存在，版本串＝SKILL.md frontmatter（读不到 SKILL 时跳过）；
  5. 〔板书｜…〕 段落为红色样式（该 md 没有 board 块时跳过）；
  6. 文件名符合现行命名规则。
提示项 5 项（不影响退出码）：每行字数 ≤14、科学思维 ≥2 类、科学探究 ≥2 类、目标单句 ≤40 字、各环节用时求和＝40。
视觉层：把内嵌板书图导出并打印路径，供模型 read_image 复核；--export-dir（或 JIAOAN_EXPORT_DIR）指定导出目录，缺省临时目录，指定目录不可写时自动退回临时目录。
退出码：0=全绿；1=有失败项。
"""
import argparse
import os
import re
import sys
import tempfile
import zipfile

BT = chr(96)
FENCE = BT * 3
BOARD_RE = re.compile(r'^[ ]*' + re.escape(FENCE) + r'board[ ]*$')
HEAD_RE = re.compile(r'^##\s*板([0-9]+)', re.M)
WEN_RE = re.compile(r'[0-9]+\.[0-9]+.+-((第[0-9]+课时)|(1课时))-[^\-]+-详案(-旧版)?\.(md|docx)$')
PRAC_RE = re.compile(r'[0-9]+\.[0-9]+.+-练习课-详案(-旧版)?\.(md|docx)$')
VER_RE = re.compile(r'^version:\s*([0-9][^\s]*)\s*$', re.M)
TIME_RE = re.compile(r'^###\s*.*环节.*?约?\s*([0-9]+)\s*分钟', re.M)
PUNCT = set('，。、；：！？（）【】「」《》〈〉“”‘’·—…→←↔=+*/|_[]{}<>~!@#$%^&*()"\',.:;?')

RESULTS = []


def item(name, ok, detail=''):
    RESULTS.append((name, ok, detail))
    print('  [%s] %s%s' % ('PASS' if ok else 'FAIL', name, ('  ' + detail) if detail else ''))


def warn(name, detail=''):
    print('  [WARN] %s%s' % (name, ('  ' + detail) if detail else ''))


def skip(name, detail=''):
    print('  [SKIP] %s%s' % (name, ('  ' + detail) if detail else ''))


def read(path):
    with open(path, encoding='utf-8') as f:
        return f.read()


def parse_boards(md):
    blocks = []
    cur = None
    for ln in md.splitlines():
        if BOARD_RE.match(ln):
            cur = []
            blocks.append(cur)
        elif cur is not None and ln.strip().startswith(FENCE):
            cur = None
        elif cur is not None:
            cur.append(ln)
    return blocks


def board_rows(block):
    rows = []
    for ln in block:
        s = ln.strip()
        if not s or s.startswith('#'):
            continue
        rows.append(s)
    return rows


def actual_chars(s):
    return sum(1 for ch in s if not ch.isspace() and ch not in PUNCT)


def find_chapter_dir(md_path):
    parts = os.path.abspath(md_path).split(os.sep)
    for i, seg in enumerate(parts):
        if seg == '04-教案' and i + 1 < len(parts):
            return os.sep.join(parts[:i + 2])
    return None


def resolve_skill(arg):
    cands = []
    if arg:
        cands.append(arg)
    env = os.environ.get('JIAOAN_SKILL_DIR')
    if env:
        cands.append(env)
    cands.append(os.path.expanduser('~/.dsh/skills/generate-9th-grade-physics-lesson-plan'))
    cands.append('/root/skill-repos/g9-physics')
    for d in cands:
        p = d if os.path.basename(d) == 'SKILL.md' else os.path.join(d, 'SKILL.md')
        if os.path.isfile(p):
            return p
    return None


def docx_parts(path):
    with zipfile.ZipFile(path) as z:
        names = z.namelist()
        doc = read_zip(z, 'word/document.xml')
        styles = read_zip(z, 'word/styles.xml')
        media = [n for n in names if n.startswith('word/media/')]
        return names, doc, styles, media


def read_zip(z, name):
    try:
        return z.read(name).decode('utf-8', 'replace')
    except KeyError:
        return ''


def boardmark_red(styles):
    m = re.search(r'w:styleId="BoardMark"(.{0,4000}?)</w:style>', styles, re.S)
    if not m:
        return False, '无 BoardMark 样式'
    c = re.search(r'w:color w:val="([0-9A-Fa-f]{6})"', m.group(1))
    if not c:
        return False, 'BoardMark 无颜色'
    return c.group(1).upper() in ('C00000', 'FF0000'), 'BoardMark 颜色 ' + c.group(1)


def main():
    ap = argparse.ArgumentParser(description='教案成品·板书规格校验')
    ap.add_argument('--docx', required=True)
    ap.add_argument('--md', required=True)
    ap.add_argument('--skill', default='')
    ap.add_argument('--export-dir', default=os.environ.get('JIAOAN_EXPORT_DIR', ''))
    a = ap.parse_args()
    md_path = a.md
    docx_path = a.docx
    if not os.path.isfile(md_path):
        print('  [FAIL] md 不存在  ' + md_path)
        return 1
    if not os.path.isfile(docx_path):
        print('  [FAIL] docx 不存在  ' + docx_path)
        return 1
    md = read(md_path)
    blocks = parse_boards(md)
    heads = sum(len(HEAD_RE.findall('\n'.join(b))) for b in blocks)

    print('== 1. 块数 <=2 ==')
    item('board 块数 <=2', len(blocks) <= 2 and heads <= 2,
         '围栏 %d，##板N %d' % (len(blocks), heads))

    print('== 2. 每块行数 <=8 ==')
    rows = [board_rows(b) for b in blocks]
    worst = max([len(r) for r in rows], default=0)
    item('每块实际书写行 <=8', worst <= 8, '最多 %d 行' % worst)

    print('== 3. docx 内嵌板书图 + 未单独落盘 ==')
    names, doc, styles, media = docx_parts(docx_path)
    ok_a = len(media) > 0
    chapter = find_chapter_dir(md_path)
    bad_b = []
    if chapter:
        bd = os.path.join(chapter, '板书图')
        if os.path.isdir(bd):
            ref = os.path.getmtime(md_path)
            for dp, dn, fn in os.walk(bd):
                for f in fn:
                    p = os.path.join(dp, f)
                    if os.path.getmtime(p) > ref:
                        bad_b.append(os.path.relpath(p, chapter))
    item('docx 有内嵌板书图', ok_a, 'word/media 共 %d 个' % len(media))
    item('未单独落盘板书图', not bad_b, '／'.join(bad_b) if bad_b else '')

    print('== 4. 生成信息块 + 版本 ==')
    skill = resolve_skill(a.skill)
    if not skill:
        skip('生成信息块版本', '读不到 SKILL.md')
    else:
        ver = ''
        m = VER_RE.search(read(skill))
        ver = m.group(1) if m else ''
        ok4 = 'ProvenanceNote' in doc
        if ver and ver != '版本未知' and ver not in doc:
            ok4 = False
        item('生成信息块版本', ok4, 'SKILL v%s' % (ver or '?'))

    print('== 5. 板书旁批红色 ==')
    note_n = len(re.findall(r'〔板书｜', md))
    if not blocks:
        skip('板书旁批红色', '该 md 无 board 块')
    else:
        red, note = boardmark_red(styles)
        used = len(re.findall(r'w:pStyle w:val="BoardMark"', doc))
        item('板书旁批红色', red and used >= 1, note + ('，docx 用 %d 次（md 旁批 %d 处）' % (used, note_n)))

    print('== 6. 文件名 ==')
    base_md = os.path.basename(md_path)
    base_docx = os.path.basename(docx_path)
    def name_ok(n):
        return bool(WEN_RE.match(n) or PRAC_RE.match(n))
    stem_ok = os.path.splitext(base_md)[0] == os.path.splitext(base_docx)[0]
    item('文件名符合规则', name_ok(base_md) and name_ok(base_docx) and stem_ok,
         '%s / %s' % (base_md, base_docx))

    print('== 提示项（不影响退出码）==')
    over = []
    for b in blocks:
        for r in board_rows(b):
            if actual_chars(r) > 14:
                over.append(r)
    warn('每行字数 <=14', '超标 %d 行' % len(over) if over else '通过')
    think = [k for k in ['模型建构', '科学推理', '科学论证', '质疑创新'] if k in md]
    acts = [k for k in ['抽象', '比较', '归纳', '推理', '类比', '质疑', '修正'] if k in md]
    warn('科学思维 >=2 类', '要素 %d 个／动作 %d 个' % (len(think), len(acts)))
    inq = [k for k in ['提出问题', '获取证据', '作出解释', '交流评估'] if k in md]
    warn('科学探究 >=2 类', '命中 %d 个：%s' % (len(inq), '／'.join(inq)))
    seg = md
    i = md.find('三、教学目标')
    j = md.find('四、教学重难点')
    if i >= 0 and j > i:
        seg = md[i:j]
    long = [s for s in re.split(r'[；;。]', seg) if len(s.strip()) > 40]
    warn('目标单句 <=40 字', '超长 %d 句' % len(long) if long else '通过')
    mins = [int(x) for x in TIME_RE.findall(md)]
    warn('各环节用时求和', '合计 %d 分钟' % sum(mins) if mins else '未识别到环节标题行')

    print('== 视觉层：导出内嵌板书图 ==')
    if media:
        d = a.export_dir or tempfile.mkdtemp(prefix='lesson_board_')
        try:
            os.makedirs(d, exist_ok=True)
            with zipfile.ZipFile(docx_path) as z:
                for n in media:
                    out = os.path.join(d, os.path.basename(n))
                    with open(out, 'wb') as fh:
                        fh.write(z.read(n))
            print('  已导出 %d 张到 %s' % (len(media), d))
        except OSError as ex:
            d2 = tempfile.mkdtemp(prefix='lesson_board_')
            with zipfile.ZipFile(docx_path) as z:
                for n in media:
                    with open(os.path.join(d2, os.path.basename(n)), 'wb') as fh:
                        fh.write(z.read(n))
            print('  已导出 %d 张到 %s（指定目录不可写：%s）' % (len(media), d2, ex))
    else:
        print('  无内嵌图可导出')

    bad = [n for n, ok, _ in RESULTS if not ok]
    print('')
    print('结果：%d 项，失败 %d 项' % (len(RESULTS), len(bad)))
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
