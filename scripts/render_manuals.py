#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 references/data/*.yaml 渲染成 05、07 里的标记块（v1.0）。

用法：
    python3 scripts/render_manuals.py --write    # 用 yaml 重写两个 md 的标记块
    python3 scripts/render_manuals.py --check    # 只比对，不一致退出 1（check_structure 调这个）
    python3 scripts/render_manuals.py --print 05 # 打印渲染结果，不落盘

标记块格式：
    <!-- BEGIN:SITES 由 scripts/render_manuals.py 生成，勿手改 -->
    ...
    <!-- END:SITES -->
块外的手写散文不受影响；yaml 改了必须重跑 --write，否则 --check 报不一致。
"""
import argparse
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import simple_yaml  # noqa: E402

DATA = os.path.join(SKILL_DIR, 'references', 'data')
TARGETS = {
    '05': os.path.join(SKILL_DIR, 'references', '05-教学资源网站.md'),
    '07': os.path.join(SKILL_DIR, 'references', '07-网络资源参考价值评价维度.md'),
}
MARK = '由 scripts/render_manuals.py 生成，勿手改'
BEGIN = '<!-- BEGIN:%s ' + MARK + ' -->'
END = '<!-- END:%s -->'


def row(cells):
    return '| ' + ' | '.join('' if c is None else str(c) for c in cells) + ' |'


def table(head, rows):
    out = [row(head), row(['---'] * len(head))]
    out.extend(row(r) for r in rows)
    return '\n'.join(out)


def render_quick(s):
    return table(['要什么', '首选', '可达性', '抓不到换谁'],
                 [[q[0], q[1], q[2], q[3]] for q in s['quick']])


def render_login(s):
    return table(['站点', '账号', '免费能下什么（2026-10-17 实核）', '操作路径', '落位'],
                 s['channels']['login'])


def render_direct(s):
    return table(['站点', '内容', '可达性'],
                 s['channels']['direct'])


def render_sites(s):
    rows = []
    for x in s['sites']:
        rows.append([x['id'], x['name'], x['kind'], x['access'], x['fee'], x['fallback']])
    return table(['编号', '站点', '资源类型', '可达性', '费用', '抓不到换谁'], rows)


def render_05(sources):
    parts = [
        '### 0.1 速查：要什么先去哪（按资源类型）',
        '',
        render_quick(sources),
        '',
        '### 0.2 登录后免费下载的 10 个站',
        '',
        render_login(sources),
        '',
        '### 0.3 免登录就能下的 4 个站',
        '',
        render_direct(sources),
        '',
        '### 0.4 站点总表（30 条，按编号查可达性与替代源）',
        '',
        render_sites(sources),
    ]
    return '\n'.join(parts)


def render_gate(r):
    return table(['编号', '门槛', '怎么查', '不通过的样子'],
                 [[g['no'], g['name'], g['how'], g['fail']] for g in r['gate']])


def render_kinds(r):
    out = []
    for k in r['kinds']:
        b = k['bands']
        yi = '%d–%d' % (b['yi_min'], b['yi_max']) if b.get('yi_max') else '≥%d' % b['yi_min']
        out.append('#### %s（满分 %d）' % (k['name'], k['full']))
        out.append('')
        out.append(table(['维度', '0 分', '1 分', '2 分'],
                         [['%d %s' % (d['no'], d['name']), d['s0'], d['s1'], d['s2']] for d in k['dims']]))
        out.append('')
        if k.get('entry'):
            out.append('**准入补充**：' + k['entry'])
            out.append('')
        out.append('**分线**：甲 ≥%d（%s）｜乙 %s｜丙 ≤%d' % (b['jia'], b.get('jia_note') or '', yi, b['bing_max']))
        out.append('')
    return '\n'.join(out).rstrip()


def rendered(src_key):
    if src_key == '05':
        return {'SITES': render_05(simple_yaml.load(os.path.join(DATA, 'sources.yaml')))}
    return {
        'GATE': render_gate(simple_yaml.load(os.path.join(DATA, 'rubric.yaml'))),
        'KINDS': render_kinds(simple_yaml.load(os.path.join(DATA, 'rubric.yaml'))),
    }


def block_re(name):
    return re.compile(re.escape(BEGIN % name) + r'(.*?)' + re.escape(END % name), re.S)


def apply(text, key, blocks):
    """把 key 对应的所有标记块内容替换成渲染结果。"""
    for name, content in blocks.items():
        pat = block_re(name)
        found = pat.findall(text)
        if len(found) != 1:
            raise SystemExit('%s 里 %s 标记块应恰好 1 个，实有 %d 个' % (key, name, len(found)))
        text = pat.sub(lambda m: (BEGIN % name) + '\n' + content + '\n' + (END % name), text)
    return text


def main():
    ap = argparse.ArgumentParser(description='由 references/data/*.yaml 渲染 05、07 的标记块')
    ap.add_argument('--write', action='store_true', help='写回 md（默认只检查）')
    ap.add_argument('--check', action='store_true', help='只比对，不一致退出 1')
    ap.add_argument('--print', dest='show', choices=['05', '07'], help='打印渲染结果，不落盘')
    a = ap.parse_args()
    keys = [a.show] if a.show else ['05', '07']
    bad = []
    for key in keys:
        blocks = rendered(key)
        if a.show:
            for name, content in blocks.items():
                print('===== %s %s =====' % (key, name))
                print(content)
            return 0
        p = TARGETS[key]
        with open(p, encoding='utf-8') as f:
            old = f.read()
        new = apply(old, key, blocks)
        if new == old:
            print('[OK] %s 标记块与 yaml 一致' % key)
        elif a.write:
            with open(p, 'w', encoding='utf-8') as f:
                f.write(new)
            print('[FIX] %s 已按 yaml 重写标记块' % key)
        else:
            bad.append(key)
            print('[FAIL] %s 标记块与 yaml 不一致，跑 --write' % key)
    if bad:
        print('结果：%d 个文件待重渲染' % len(bad))
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
