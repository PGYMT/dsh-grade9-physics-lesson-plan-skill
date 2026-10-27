#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""check_lesson.py — 教案成品·板书规格外部校验（v8.18.1，纯标准库）。

用法：
  python3 scripts/check_lesson.py --docx 详案.docx --md 详案.md [--skill SKILL.md]

失败项（影响退出码；每项在输出里带连续「第N项」，供自检回报引用）：
  1. board 块数 1—2（## 板N 与 board 围栏数双测）；
  2. 每块实际书写行 ≤8（块＝「## 板N」；围栏内没有板N 时整个围栏算一块）；
  3. docx 内嵌 board-*.png 数＝md board 块数，且至少 1 张；
  4. 本次未向 04-教案/<章节>/板书图/ 新增板书图；
  5. docx 末尾生成信息块存在，版本串＝SKILL.md frontmatter（读不到 SKILL 时跳过）；
  6. 〔板书｜…〕 段落为红色样式，docx 用数不少于 md 真实旁批数；多出只提示；
  7. 文件名符合现行命名规则。
  8. 各环节用时之和＝课时分钟（读「课时：…N分钟」；读不到按默认 40 分钟并提示）；
  9. md 未晚于同名 docx（md 改了忘了重生成；-旧版 归档不查）。
     --warn-only 时第 5、8、9 项降为提示，不影响退出码（复检历史旧稿用）。
提示项（不影响退出码）：每行字数 ≤14、科学思维 ≥2 类、科学探究 ≥2 类、目标单句 ≤40 字、同一操作口径唯一（互斥说法同现）、两版该同部分一致（--pair）。
视觉层：把内嵌板书图导出并打印路径，供模型 read_image 复核；--export-dir（或 JIAOAN_EXPORT_DIR）指定导出目录，缺省临时目录，指定目录不可写时自动退回临时目录。
契约层：--contract 课程契约.json 时，末尾再跑 check_consistency.py 的 5 项（L2 一致层），结果并入本脚本退出码；不传时输出与旧版逐字节一致。
退出码：0=全绿；1=有失败项。
"""
import argparse
import os
import re
import subprocess
import sys
import tempfile
import zipfile

BT = chr(96)
FENCE = BT * 3
BOARD_RE = re.compile(r'^[ ]*' + re.escape(FENCE) + r'board[ ]*$')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import checks  # noqa: E402  三级判定：item 阻断 / warn 提示 / advisory 遗留

HEAD_RE = re.compile(r'^##\s*板([0-9]+)', re.M)
WEN_RE = re.compile(r'[0-9]+\.[0-9]+.+-((第[0-9]+课时)|(1课时))-[^\-]+-详案(-旧版)?\.(md|docx)$')
PRAC_RE = re.compile(r'[0-9]+\.[0-9]+.+-练习课-详案(-旧版)?\.(md|docx)$')
VER_RE = re.compile(r'^version:\s*([0-9][^\s]*)\s*$', re.M)
TIME_RE = re.compile(r'^###\s*.*环节.*?约?\s*([0-9]+)\s*分钟', re.M)
PUNCT = set('，。、；：！？（）【】「」《》〈〉“”‘’·—…→←↔=+*/|_[]{}<>~!@#$%^&*()"\',.:;?')

RESULTS = []
WARN_ONLY = [False]
ITEM_NO = 0


def item(name, ok, detail='', soft=False):
    global ITEM_NO
    ITEM_NO += 1
    if soft and not ok and WARN_ONLY[0]:
        print('  [WARN] 第%d项 %s%s（--warn-only）' % (ITEM_NO, name, ('  ' + detail) if detail else ''))
        return
    RESULTS.append((name, ok, detail))
    print('  [%s] 第%d项 %s%s' % ('PASS' if ok else 'FAIL', ITEM_NO, name, ('  ' + detail) if detail else ''))


def warn(name, detail=''):
    print('  [WARN] %s%s' % (name, ('  ' + detail) if detail else ''))


def skip(name, detail=''):
    global ITEM_NO
    ITEM_NO += 1
    print('  [SKIP] 第%d项 %s%s' % (ITEM_NO, name, ('  ' + detail) if detail else ''))


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


def board_units(block):
    units = []
    cur = None
    for ln in block:
        s = ln.strip()
        if HEAD_RE.match(s):
            cur = []
            units.append(cur)
            continue
        if not s or s.startswith('#'):
            continue
        if cur is None:
            cur = []
            units.append(cur)
        cur.append(s)
    return [u for u in units if u]


def board_rows(block):
    return [r for u in board_units(block) for r in u]


def actual_chars(s):
    return sum(1 for ch in s if not ch.isspace() and ch not in PUNCT)


def board_notes(md):
    n = 0
    for ln in md.splitlines():
        s = ln.strip()
        if not s or s.startswith('>'):
            continue
        for body in re.findall(r'〔板书｜([^〕]*)〕', s):
            if re.match(r'^板[0-9N]+·x', body.strip()):
                continue
            n += 1
    return n


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


def common_blocks(t):
    boards = ['\n'.join(b).strip() for b in parse_boards(t)]
    heads = [ln.strip() for ln in t.splitlines() if re.match(r'^###\s*.*环节', ln)]
    return boards, heads


def compare_common(a, b):
    out = []
    ba, ha = common_blocks(a)
    bb, hb = common_blocks(b)
    if ba != bb:
        out.append('板书块不一致（%d／%d 块）' % (len(ba), len(bb)))
    if ha != hb:
        only = sorted(set(ha) ^ set(hb))
        out.append('环节标题或用时不一致 %d 处：%s' % (len(only), '｜'.join(only[:2])))
    return out


EPILOG = """字段词表（--contract 指向的课程契约 json；完整规则见 schemas/lesson.schema.json）
  id / section / title / chapter / textbook   身份；version_tag 决定成品文件名后缀
  duration_min                               课时分钟数，20—60
  objectives[].dimension / text              四维目标：物理观念／科学思维／科学探究／科学态度与责任
  segments[].name / minutes / kind           课堂环节；各 minutes 之和＝duration_min
  boards.count / max_lines / max_chars       板书块数（≤2）、每块行数（≤8）、每行字数（≤14）
  student_sheets[] / deck_pages[]            材料：导学案文件名、课件页码
  sources[].url / fetched_date / type / level / sha256_16
                                             来源；甲、乙级来源必须写进 md「九、参考资料」

最小示例（存成 15.2电流和电路-第1课时-仅多媒体-详案.lesson.json 即可跑）
  {"id":"15.2-第1课时","section":"15.2","title":"电流和电路","chapter":"第十五章 电流和电路",
   "textbook":"人教版（2024）九年级物理全一册","duration_min":40,"experiment_mode":"仅多媒体",
   "version_tag":"第1课时-仅多媒体-详案","draft":false,
   "objectives":[{"dimension":"物理观念","text":"知道电流由电荷的定向移动形成"}],
   "segments":[{"name":"情境导入","minutes":5,"kind":"导入"},
               {"name":"新授","minutes":20,"kind":"新授"},
               {"name":"当堂练习","minutes":10,"kind":"练习"},
               {"name":"小结","minutes":5,"kind":"小结"}],
   "boards":{"count":1,"max_lines":8,"max_chars":14},
   "student_sheets":[],"deck_pages":[],
   "sources":[{"url":"https://example.com/a","fetched_date":"2026-10-27","type":"教案",
               "level":"甲","sha256_16":"0123456789abcdef"}]}
  上面只放 1 条来源，正式契约要 ≥3 条且教案／课件／练习各 1；先跑 check_contract.py 看全部 10 项。
"""


def main():
    ap = argparse.ArgumentParser(
        description='教案成品·板书规格校验（L3 内容层）',
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--docx', required=True, help='教案成品 docx 路径')
    ap.add_argument('--md', required=True, help='对应详案 md 路径（与 docx 同名同内容）')
    ap.add_argument('--skill', default='', help='SKILL.md 路径（取版本串）；缺省自动找技能根')
    ap.add_argument('--export-dir', default=os.environ.get('JIAOAN_EXPORT_DIR', ''),
                    help='导出内嵌板书图的目录；缺省临时目录')
    ap.add_argument('--pair', default='', help='另一版详案 md：比对板书块与环节标题行')
    ap.add_argument('--warn-only', action='store_true', help='第 5、8、9 项降为提示（复检历史旧稿用）')
    ap.add_argument('--contract', default='',
                    help='可选的课程契约 json；传了就在末尾加跑 5 项一致校验（L2）')
    a = ap.parse_args()
    WARN_ONLY[0] = a.warn_only
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

    print('== 块数 ==')
    item('board 块数 1—2', 1 <= len(blocks) <= 2 and 1 <= heads <= 2,
         '围栏 %d，##板N %d' % (len(blocks), heads))

    print('== 每块行数 ==')
    units = [u for b in blocks for u in board_units(b)]
    worst = max([len(u) for u in units], default=0)
    item('每块实际书写行 <=8', worst <= 8, '最多 %d 行／共 %d 块' % (worst, len(units)))

    print('== 内嵌板书图 / 未单独落盘 ==')
    names, doc, styles, media = docx_parts(docx_path)
    board_media = [n for n in media
                   if os.path.basename(n).lower().startswith('board-')
                   and n.lower().endswith('.png')]
    ok_a = len(board_media) == len(blocks) and len(board_media) >= 1
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
    item('docx 内嵌 board-*.png 数＝md board 块数', ok_a,
         'board-*.png %d 张／md board %d 块（word/media 共 %d 个）'
         % (len(board_media), len(blocks), len(media)))
    item('未单独落盘板书图', not bad_b, '／'.join(bad_b) if bad_b else '')

    print('== 生成信息块 / 版本 ==')
    skill = resolve_skill(a.skill)
    if not skill:
        skip('生成信息块版本', '读不到 SKILL.md')
    else:
        ver = ''
        m = VER_RE.search(read(skill))
        ver = m.group(1) if m else ''
        has_block = 'ProvenanceNote' in doc
        stale = bool(ver) and ver != '版本未知' and ver not in doc
        item('生成信息块存在', has_block, 'SKILL v%s' % (ver or '?'), soft=True)
        if has_block and stale:
            checks.advisory('check_lesson', '生成信息块版本是旧版',
                            md_path, 'docx 里的版本串不含 v%s，属旧版生成的成品' % ver)

    print('== 板书旁批 ==')
    note_n = board_notes(md)
    if not blocks:
        skip('板书旁批红色', '该 md 无 board 块')
    else:
        red, note = boardmark_red(styles)
        used = len(re.findall(r'w:pStyle w:val="BoardMark"', doc))
        if used > note_n:
            warn('docx 板书旁批多于 md', 'docx %d 次／md 真实旁批 %d 处' % (used, note_n))
        item('板书旁批红色（至少一处）', red and used >= 1,
             note + ('，docx 用 %d 次（md 真实旁批 %d 处）' % (used, note_n)))
        if red and used >= 1 and used < note_n:
            checks.advisory('check_lesson', '板书旁批少于 md 标注',
                            md_path, 'docx %d 次／md %d 处' % (used, note_n))

    print('== 文件名 ==')
    base_md = os.path.basename(md_path)
    base_docx = os.path.basename(docx_path)
    def name_ok(n):
        return bool(WEN_RE.match(n) or PRAC_RE.match(n))
    stem_ok = os.path.splitext(base_md)[0] == os.path.splitext(base_docx)[0]
    item('文件名符合规则', name_ok(base_md) and name_ok(base_docx) and stem_ok,
         '%s / %s' % (base_md, base_docx))

    print('== 各环节用时 ==')
    tm = re.search(r'课时[：:][^\n]*?(\d+)\s*分钟', md)
    if tm:
        lesson_min = int(tm.group(1))
    else:
        lesson_min = 40
        warn('课时分钟声明', '未读到「课时：…N分钟」，按默认 40 分钟')
    mins = [int(x) for x in TIME_RE.findall(md)]
    item('各环节用时求和', bool(mins) and sum(mins) == lesson_min,
         '合计 %d 分钟／课时 %d 分钟' % (sum(mins), lesson_min), soft=True)

    print('== md/docx 时间戳 ==')
    if '-旧版' in base_md or '-旧版' in base_docx:
        skip('md 未晚于 docx', '旧版归档不查')
    else:
        md_newer = os.path.getmtime(md_path) > os.path.getmtime(docx_path)
        item('md 未晚于 docx', not md_newer,
             'md 已改、docx 未重生成，请重跑生成脚本' if md_newer else '', soft=True)

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
    PAIRS = [('停两次', '停一次'), ('最右端', '最左端'), ('滑片向右移', '滑片向左移')]
    clashes = ['%s／%s' % (x, y) for x, y in PAIRS if x in md and y in md]
    warn('同一操作口径唯一', ('同现：' + '；'.join(clashes)) if clashes else '通过')
    if a.pair:
        if not os.path.isfile(a.pair):
            warn('两版该同部分一致', '配对文件不存在：' + a.pair)
        else:
            diffs = compare_common(md, read(a.pair))
            warn('两版该同部分一致', '一致' if not diffs else '；'.join(diffs))

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

    if a.contract:
        print('== 契约交叉校验（L2 · --contract）==')
        cc = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'check_consistency.py')
        if not os.path.isfile(a.contract):
            item('契约文件存在', False, '读不到 ' + a.contract)
        elif not os.path.isfile(cc):
            skip('契约与 md 一致（L2）', '找不到相邻的 check_consistency.py')
        else:
            p = subprocess.run([sys.executable, cc, '--contract', a.contract, '--md', md_path],
                               capture_output=True, text=True)
            for ln in (p.stdout or '').splitlines():
                print('  ' + ln)
            if p.returncode != 0 and (p.stderr or '').strip():
                print('  ' + p.stderr.strip().splitlines()[-1])
            item('契约与 md 一致（L2）', p.returncode == 0,
                 '契约 %s' % os.path.basename(a.contract))

    bad = [n for n, ok, _ in RESULTS if not ok]
    print('')
    print('结果：%d 项，失败 %d 项' % (len(RESULTS), len(bad)))
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
