#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""run_tests.py — check_research.py / check_lesson.py 负样本自检壳（v8.13.0，纯标准库）。

用法：
  python3 scripts/tests/run_tests.py [--workspace DIR]

check_research 用 8 份故意违规摘要（覆盖失败项 1-5、7、8）＋2 份合格摘要
（常规；某类全丙但已出《人工取件清单》）；
check_lesson 用 7 份故意违规 md/docx（覆盖失败项 1-6）＋1 份合格样本。
docx 样本用工作区 00-模板与规范/教案docx生成脚本-v9.py 现场生成再拆改，不手搓 OOXML。
退出码：0=全部符合预期；1=有样本未被判失败或正样本被误判。
"""
import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile

BT = chr(96)
NL = chr(10)
HERE = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.path.dirname(os.path.dirname(HERE))
CHECK_RESEARCH = os.path.join(SKILL_DIR, 'scripts', 'check_research.py')
CHECK_LESSON = os.path.join(SKILL_DIR, 'scripts', 'check_lesson.py')
SKILL_MD = os.path.join(SKILL_DIR, 'SKILL.md')
FAILS = []

# 合格样本的正文：非空白字符数远高于 400，且含内容标记，用于通过「非空壳」的机械线。
BODY = (NL.join([
    '## 教学过程',
    '教师：请看课件第3页，先判断电压表应该并联还是串联接入电路。',
    '学生：并联在被测用电器两端，电流从正接线柱流入、负接线柱流出。',
    '电压表读数：先看量程，再看分度值，0～3 V 分度值 0.1 V，0～15 V 分度值 0.5 V。',
    '实验结论：只有一个用电器的电路中，用电器两端电压等于电源两端电压。',
    '板书：一、电压；二、电压表；三、使用规则。',
]) + NL) * 6

NAMES = {
    '教案': ['16.9测试节-教案-%d-21世纪教育网-2026-10-11.md' % i for i in (1, 2, 3)],
    '课件': ['16.9测试节-课件-%d-21世纪教育网-2026-10-11.md' % i for i in (1, 2, 3)],
    '练习': ['16.9测试节-练习-%d-2026-10-11.md' % i for i in (1, 2, 3)],
    '导学案': ['16.9测试节-学案-%d-2026-10-11.md' % i for i in (1, 2)],
    '板书参考': ['16.9测试节-板书-%d-2026-10-11.md' % i for i in (1, 2)],
}
SRC = {'教案': '官方', '课件': '精品', '练习': '官方', '导学案': '官方', '板书参考': '精品'}


def expect(tag, want, cmd):
    p = subprocess.run(cmd, capture_output=True, text=True)
    got = 0 if p.returncode == 0 else 1
    mark = 'OK ' if got == want else 'BAD'
    if got != want:
        FAILS.append(tag)
    print('[%s] %s  期望退出=%d 实际=%d' % (mark, tag, want, got))
    if got != want:
        print('--- stdout ---')
        print(p.stdout)
        print('--- stderr ---')
        print(p.stderr[-1500:])
    return p


def build_ws(root, empty=()):
    """写一个最小工作区；empty 里的类型写成空壳文件（正文为空）。返回 ws、章节、各类文件路径。"""
    ws = os.path.join(root, 'ws')
    ch = '第十六章-电压 电阻'
    base = os.path.join(ws, '08-网络资源')
    for d in ['优秀教案/' + ch + '/md文件', '优秀课件PPT/' + ch + '/md文件',
              '同步优学/九年级上册/' + ch + '/md文件', '板书设计参考/md文件']:
        os.makedirs(os.path.join(base, d), exist_ok=True)
    files = {'教案': [], '课件': [], '练习': [], '导学案': [], '板书参考': []}
    def put(typ, rel, body):
        p = os.path.join(base, rel)
        open(p, 'w', encoding='utf-8').write(body)
        files[typ].append(p)
    for i in (1, 2, 3):
        put('教案', '优秀教案/%s/md文件/16.9测试节-教案-%d-21世纪教育网-2026-10-11.md' % (ch, i),
            '' if '教案' in empty else BODY)
        put('课件', '优秀课件PPT/%s/md文件/16.9测试节-课件-%d-21世纪教育网-2026-10-11.md' % (ch, i),
            '' if '课件' in empty else BODY)
        put('练习', '同步优学/九年级上册/%s/md文件/16.9测试节-练习-%d-2026-10-11.md' % (ch, i),
            '' if '练习' in empty else BODY)
    for i in (1, 2):
        put('导学案', '优秀教案/%s/md文件/16.9测试节-学案-%d-2026-10-11.md' % (ch, i),
            '' if '导学案' in empty else BODY)
        put('板书参考', '板书设计参考/md文件/16.9测试节-板书-%d-2026-10-11.md' % i,
            '' if '板书参考' in empty else BODY)
    open(os.path.join(base, '备课缺口表.md'), 'w', encoding='utf-8').write(
        '# 备课缺口表' + NL + NL + '| 章节 | 节号+节名 | 教案 | 课件 | 练习 | 导学案 | 板书 | 视频 | 缺口摘要 | 最近更新 |' + NL
        + '|---|---|---|---|---|---|---|---|---|---|' + NL
        + '| 第十六章-电压 电阻 | 16.9测试节 | 3—5 / 3 | 3—5 / 3 | 3—5 / 3 | >=2 / 2 | >=2 / 2 | 可选 / 0 | 缺 板书 | 2026-10-11 |' + NL)
    return ws, ch, files


def dims(bad=None, nolink=None):
    lines = []
    for i, d in enumerate(['板书设计', '重点突破', '难点突破', '易错纠正', '过渡语', '讲授思路', '讲授顺序']):
        if d == bad:
            continue
        link = '' if d == nolink else '来源 https://example.com/%d 抓取日期 2026-10-11；' % i
        lines.append('- %s：%s做法：分组；采用。' % (d, link))
    return NL.join(lines)


def judge_rows(mode=None):
    """mode: None=全部乙；none 由调用方略去块；miss=少一条教案行；bing=导学案全部丙。"""
    rows = []
    for t, ns in NAMES.items():
        for n in ns:
            if mode == 'miss' and t == '教案' and n == NAMES['教案'][0]:
                continue
            g = '丙' if (mode == 'bing' and t == '导学案') else '乙'
            score = '12/18' if t == '教案' else ('11/16' if t == '课件' else ('9/14' if t in ('练习', '导学案') else '8/12'))
            rows.append('- %s | %s | %s | 人教版 | 过 | %s | %s | 借鉴点：%s——采用 | 不参考原因：无' % (n, t, SRC[t], score, g, t))
    return rows


def summary(drop_hash=False, low_jiao=False, bad=None, nolink=None, judge=None):
    s = ['# 16.9 测试节-调研摘要-20261011', '', '## 七维度', dims(bad, nolink), '', '## 份数统计',
         '教案=%s/3/3/3/官方/达标' % ('1' if low_jiao else '3'),
         '课件=3/3/3/3/精品/达标', '练习=3/3/3/3/官方/达标', '导学案=2/2/2/2/官方/达标',
         '板书参考=2/2/2/2/精品/达标', '视频=0/可选/0/0/不适用/不作硬要求', '']
    if judge != 'none':
        s += ['## 逐份判定'] + judge_rows(judge) + ['']
    if not drop_hash:
        s += ['## 哈希清单', 'abc123def456abcd 16.9测试节-教案-1.md', '']
    s += ['## 来源映射', 'https://example.com/0 -> 16.9测试节-教案-1.md', '',
          '## 失败站点', '- example.org | /x | 403 | 1 | 2026-10-11 | https://example.com/0', '']
    return NL.join(s)


def research_tests(root):
    print('===== check_research.py =====')
    ws, ch, files = build_ws(root)
    sec = '16.9测试节'
    sd = os.path.join(ws, '08-网络资源', '优秀教案', ch, 'md文件')
    good = os.path.join(sd, '16.9测试节-调研摘要-20261011.md')
    base = [sys.executable, CHECK_RESEARCH, '--workspace', ws, '--chapter', ch, '--section', sec]
    open(good, 'w', encoding='utf-8').write(summary())
    expect('正样本（应 PASS）', 0, base + ['--summary', good])
    for tag, text in [
        ('缺七维度', summary(bad='过渡语')),
        ('来源无链接', summary(nolink='讲授思路')),
        ('缺哈希清单', summary(drop_hash=True)),
        ('份数不足', summary(low_jiao=True)),
        ('缺逐份判定块', summary(judge='none')),
        ('逐份判定漏件', summary(judge='miss')),
        ('某类全丙且无《人工取件清单》', summary(judge='bing')),
    ]:
        p = os.path.join(sd, '16.9测试节-调研摘要-20261011-bad.md')
        open(p, 'w', encoding='utf-8').write(text)
        expect('负样本：' + tag, 1, base + ['--summary', p])
    lesson = os.path.join(sd, '16.9测试节-1课时-仅多媒体-详案.md')
    open(lesson, 'w', encoding='utf-8').write('九、参考资料' + NL + 'https://example.com/not-in-mapping' + NL)
    os.remove(good)
    open(good, 'w', encoding='utf-8').write(summary())
    expect('负样本：教案来源不可溯源', 1, base + ['--lesson', lesson])

    saved = {}
    for p in files['教案']:
        saved[p] = open(p, encoding='utf-8').read()
        open(p, 'w', encoding='utf-8').write('')
    expect('负样本：可用数超过正文达标数（空壳）', 1, base + ['--summary', good])
    for p, t in saved.items():
        open(p, 'w', encoding='utf-8').write(t)

    bing = os.path.join(sd, '16.9测试节-调研摘要-20261011-bing.md')
    open(bing, 'w', encoding='utf-8').write(summary(judge='bing'))
    manual = os.path.join(sd, '16.9测试节-人工取件清单-20261011.md')
    open(manual, 'w', encoding='utf-8').write('# 人工取件清单' + NL)
    expect('正样本：某类全丙但已出《人工取件清单》', 0, base + ['--summary', bing])
    os.remove(manual)


def base_md(boards=1, rows=4, note=True, boards_per_fence=1, last_rows=None):
    L = ['# 16.9 测试节', '', '三、教学目标', '- 学生能说出电流的方向。', '- 学生能由实物连接抽象出电路图并作出解释。', '',
         '四、教学重难点', '重点：电流方向。', '', '### 环节一 情境导入（约5分钟）', '内容。', '',
         '### 环节二 新授（约30分钟）', '内容。', '', '### 环节三 小结（约5分钟）', '内容。', '']
    if note:
        L += ['〔板书｜板1·1〕', '']
    L.append('## 板书完整设计')
    b = 0
    while b < boards:
        L.append(BT * 3 + 'board')
        L.append('# 16.9 测试节')
        for k in range(b, min(b + boards_per_fence, boards)):
            r_n = last_rows if (last_rows is not None and k == boards - 1) else rows
            L.append('## 板%d（主板）' % (k + 1))
            L.append('一、测试知识块')
            for r in range(r_n - 1):
                L.append('行%d：内容' % (r + 1))
        L.append(BT * 3)
        L.append('')
        b += boards_per_fence
    return NL.join(L)


def rewrite_docx(src, dst, doc_repl=None, styles_repl=None, drop_media=False):
    with zipfile.ZipFile(src) as zin:
        items = [(i, zin.read(i.filename)) for i in zin.infolist()]
    with zipfile.ZipFile(dst, 'w', zipfile.ZIP_DEFLATED) as zout:
        for info, data in items:
            if drop_media and info.filename.startswith('word/media/'):
                continue
            if info.filename == 'word/document.xml' and doc_repl:
                data = doc_repl(data.decode('utf-8')).encode('utf-8')
            if info.filename == 'word/styles.xml' and styles_repl:
                data = styles_repl(data.decode('utf-8')).encode('utf-8')
            zout.writestr(info, data)


def lesson_tests(root, ws):
    print('===== check_lesson.py =====')
    v9 = os.path.join(ws, '00-模板与规范', '教案docx生成脚本-v9.py')
    if not os.path.isfile(v9):
        print('[SKIP] 找不到 v9 脚本，跳过 check_lesson 测试：' + v9)
        return
    ch_dir = os.path.join(root, '04-教案', '测试章')
    mdd = os.path.join(ch_dir, 'md文件')
    os.makedirs(mdd, exist_ok=True)
    name = '16.9测试节-1课时-仅多媒体-详案'
    md = os.path.join(mdd, name + '.md')
    open(md, 'w', encoding='utf-8').write(base_md())
    env = dict(os.environ, JIAOAN_SKILL_DIR=SKILL_DIR)
    p = subprocess.run([sys.executable, v9, '--dir', mdd], capture_output=True, text=True, env=env)
    docx = os.path.join(ch_dir, name + '.docx')
    if not os.path.isfile(docx):
        print('[SKIP] v9 未生成 docx，跳过 check_lesson 测试')
        print(p.stdout[-500:], p.stderr[-500:])
        return

    def run(tag, want, m, d):
        expect(tag, want, [sys.executable, CHECK_LESSON, '--md', m, '--docx', d, '--skill', SKILL_MD])

    run('正样本（应 PASS）', 0, md, docx)

    m1 = os.path.join(mdd, name + '.md')
    open(m1, 'w', encoding='utf-8').write(base_md(boards=3))
    run('负样本：块数>2', 1, m1, docx)

    m2 = os.path.join(mdd, name + '.md')
    open(m2, 'w', encoding='utf-8').write(base_md(boards=1, rows=9))
    run('负样本：某块行数>8', 1, m2, docx)

    m2b = os.path.join(mdd, name + '.md')
    open(m2b, 'w', encoding='utf-8').write(base_md(boards=2, boards_per_fence=2, rows=8))
    run('正样本：一围栏两板（各8行）', 0, m2b, docx)

    m2c = os.path.join(mdd, name + '.md')
    open(m2c, 'w', encoding='utf-8').write(base_md(boards=2, boards_per_fence=2, rows=4, last_rows=9))
    run('负样本：一围栏两板其一>8行', 1, m2c, docx)

    m3 = os.path.join(mdd, name + '.md')
    open(m3, 'w', encoding='utf-8').write(base_md())
    d3 = os.path.join(ch_dir, name + '-n3.docx')
    rewrite_docx(docx, d3, drop_media=True)
    run('负样本：缺内嵌板书图', 1, m3, d3)

    bd = os.path.join(ch_dir, '板书图')
    os.makedirs(bd, exist_ok=True)
    png = os.path.join(bd, 'new.png')
    open(png, 'wb').write(b'x')
    future = os.path.getmtime(md) + 100
    os.utime(png, (future, future))
    run('负样本：板书图单独落盘', 1, m3, docx)
    os.remove(png)

    d5 = os.path.join(ch_dir, name + '-n5.docx')
    rewrite_docx(docx, d5, doc_repl=lambda s: s.replace('ProvenanceNote', 'XrovenanceNote'))
    run('负样本：版本块缺失', 1, m3, d5)

    d6 = os.path.join(ch_dir, name + '-n6.docx')
    rewrite_docx(docx, d6, styles_repl=lambda s: s.replace('w:val="C00000"', 'w:val="595959"'))
    run('负样本：板书旁批不红', 1, m3, d6)

    bad = os.path.join(mdd, '随便一个名字.md')
    open(bad, 'w', encoding='utf-8').write(base_md())
    run('负样本：文件名不合规', 1, bad, docx)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--workspace', default=os.environ.get('JIAOAN_WORKSPACE', '/root/dsh-workspace/工作文件'))
    a = ap.parse_args()
    root = tempfile.mkdtemp(prefix='jiaoan_tests_')
    try:
        research_tests(root)
        lesson_tests(root, a.workspace)
    finally:
        shutil.rmtree(root, ignore_errors=True)
    print('')
    if FAILS:
        print('结果：%d 个样本未达预期：%s' % (len(FAILS), '，'.join(FAILS)))
        return 1
    print('结果：全部样本判定符合预期')
    return 0


if __name__ == '__main__':
    sys.exit(main())
