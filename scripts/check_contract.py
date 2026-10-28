#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""check_contract.py — 课时契约格式校验（L1，写正文前跑，纯标准库）。

用法：
  python3 scripts/check_contract.py 课时契约.json [--md 详案.md] [--strict]

10 项（每项带连续「第N项」，供自检回报引用；失败不影响其余项，一次报全）：
  1. 必填齐：身份/目标/流程/板书/材料/来源六组的必填键都在；
  2. 枚举合法：experiment_mode、dimension、kind、type、level 只能取词表里的值；
  3. 课时长度 20—60 分钟；
  4. segments 的 minutes 之和＝duration_min；
  5. segments 3—12 条；
  6. 板书上限：count 1—2、max_lines ≤8、max_chars ≤14；type 可缺省，写了须是六种版式之一；
  7. sources 字段格式：url 是 http(s)、fetched_date 是年月日、sha256_16 是 16 位小写十六进制；
  8. objectives 四个维度每维至少 1 条，单条 ≤80 字；
  9. sources 至少 3 条，且教案／课件／练习各至少 1 条；
  10. version_tag 与文件名一致（只在 --strict 时判，给 --md 或 --name 取文件名）。

契约字段（六组，完整定义见 schemas/lesson.schema.json、最小样例见 schemas/example.lesson.json）：
  身份  id 章-课时  chapter 章名  section 节号  title 节名  textbook 教材版本
        duration_min 分钟  experiment_mode 仅多媒体/教师演示实验/不涉及实验  version_tag 文件名版本段  draft 真假
  目标  objectives[{dimension 四维之一, text 单句}]
  流程  segments[{name 环节名, minutes 分钟, kind 导入/新授/实验/练习/小结/作业/讲评}]
  板书  boards{count 1—2, max_lines ≤8, max_chars ≤14, type 提纲/表格/图解/流程/对比/综合，可缺省；
        style_source 版式来源，填了就写非空字符串，可缺省}
  材料  student_sheets[] 学生用件名（不印发写 []）、deck_pages[] 课件页码范围
  来源  sources[{url, fetched_date, type, level, sha256_16}]

退出码：0＝10 项全过；1＝有失败项。
"""
import argparse
import json
import os
import re
import sys

REQUIRED = ['id', 'chapter', 'section', 'title', 'textbook', 'duration_min',
            'experiment_mode', 'version_tag', 'draft', 'objectives', 'segments',
            'boards', 'student_sheets', 'deck_pages', 'sources']
MODES = ['仅多媒体', '教师演示实验', '不涉及实验']
DIMS = ['物理观念', '科学思维', '科学探究', '科学态度与责任']
KINDS = ['导入', '新授', '实验', '练习', '小结', '作业', '讲评']
TYPES = ['教案', '课件', '练习', '导学案', '板书', '视频', '文献', '其他']
BOARD_TYPES = ['提纲', '表格', '图解', '流程', '对比', '综合']
LEVELS = ['甲', '乙', '丙']
ID_RE = re.compile(r'^[0-9]+\.[0-9]+-(第[0-9]+课时|1课时|练习课)$')
SEC_RE = re.compile(r'^[0-9]+\.[0-9]+$')
URL_RE = re.compile(r'^https?://\S+$')
DATE_RE = re.compile(r'^[0-9]{4}-?[0-9]{2}-?[0-9]{2}$')
SHA_RE = re.compile(r'^[0-9a-f]{16}$')

RESULTS = []
NO = [0]


def item(name, ok, detail=''):
    NO[0] += 1
    RESULTS.append((name, ok))
    print('  [%s] 第%d项 %s%s' % ('PASS' if ok else 'FAIL', NO[0], name,
                                 ('  ' + detail) if detail else ''))


def brief(v, limit=60):
    s = v if isinstance(v, str) else json.dumps(v, ensure_ascii=False)
    return s if len(s) <= limit else s[:limit] + '…'


def as_list(d, key):
    v = d.get(key)
    return v if isinstance(v, list) else []


def as_dict(d, key):
    v = d.get(key)
    return v if isinstance(v, dict) else {}


def check(d, name=None, strict=False):
    # 1 必填齐
    missing = [k for k in REQUIRED if k not in d]
    item('必填齐', not missing,
         '缺：' + '、'.join(missing) if missing else '15 个必填键都在')

    # 2 枚举合法
    bad = []
    if d.get('experiment_mode') not in MODES:
        bad.append('experiment_mode=%s' % brief(d.get('experiment_mode')))
    for i, o in enumerate(as_list(d, 'objectives')):
        if not isinstance(o, dict) or o.get('dimension') not in DIMS:
            bad.append('objectives[%d].dimension=%s' % (i, brief((o or {}).get('dimension'))))
    for i, s in enumerate(as_list(d, 'segments')):
        if not isinstance(s, dict) or s.get('kind') not in KINDS:
            bad.append('segments[%d].kind=%s' % (i, brief((s or {}).get('kind'))))
    for i, s in enumerate(as_list(d, 'sources')):
        if not isinstance(s, dict) or s.get('type') not in TYPES:
            bad.append('sources[%d].type=%s' % (i, brief((s or {}).get('type'))))
        if not isinstance(s, dict) or s.get('level') not in LEVELS:
            bad.append('sources[%d].level=%s' % (i, brief((s or {}).get('level'))))
    item('枚举合法', not bad,
         '；'.join(bad[:6]) + ('…' if len(bad) > 6 else '') if bad else
         'experiment_mode/dimension/kind/type/level 均在词表内')

    # 3 课时长度
    dur = d.get('duration_min')
    ok3 = isinstance(dur, int) and not isinstance(dur, bool) and 20 <= dur <= 60
    item('课时 20—60 分钟', ok3, '当前 %s' % brief(dur))

    # 4 用时求和
    segs = [s for s in as_list(d, 'segments') if isinstance(s, dict)]
    mins = [s.get('minutes') for s in segs]
    ok4 = (all(isinstance(m, int) and not isinstance(m, bool) for m in mins)
           and isinstance(dur, int) and sum(mins) == dur)
    item('用时求和＝课时', ok4,
         'segments 合计 %s，duration_min %s' % (sum(mins) if all(
             isinstance(m, int) and not isinstance(m, bool) for m in mins) else '有非整数分钟', dur))

    # 5 segments 条数
    n = len(segs)
    item('segments 3—12 条', 3 <= n <= 12, '当前 %d 条' % n)

    # 6 板书上限
    b = as_dict(d, 'boards')
    cnt, ml, mc = b.get('count'), b.get('max_lines'), b.get('max_chars')
    btype = b.get('type')
    ssrc = b.get('style_source')
    ok6 = (isinstance(cnt, int) and 1 <= cnt <= 2 and
           isinstance(ml, int) and 1 <= ml <= 8 and
           isinstance(mc, int) and 1 <= mc <= 14 and
           (btype is None or btype in BOARD_TYPES) and
           (ssrc is None or (isinstance(ssrc, str) and bool(ssrc.strip()))))
    item('板书上限', ok6,
         'count=%s max_lines=%s max_chars=%s type=%s style_source=%s（上限 2／8／14；type 与 style_source 可缺省，填了不能是空串）'
         % (brief(cnt), brief(ml), brief(mc), brief(btype), brief(ssrc)))

    # 7 sources 字段格式
    bad7 = []
    for i, s in enumerate(as_list(d, 'sources')):
        if not isinstance(s, dict):
            bad7.append('sources[%d] 不是对象' % i)
            continue
        if not URL_RE.match(str(s.get('url', ''))):
            bad7.append('sources[%d].url=%s' % (i, brief(s.get('url'))))
        if not DATE_RE.match(str(s.get('fetched_date', ''))):
            bad7.append('sources[%d].fetched_date=%s' % (i, brief(s.get('fetched_date'))))
        if not SHA_RE.match(str(s.get('sha256_16', ''))):
            bad7.append('sources[%d].sha256_16=%s' % (i, brief(s.get('sha256_16'))))
    item('sources 字段格式', not bad7,
         '；'.join(bad7[:6]) + ('…' if len(bad7) > 6 else '') if bad7 else
         'url／fetched_date／sha256_16 格式均合规')

    # 8 objectives 四维与字数
    objs = [o for o in as_list(d, 'objectives') if isinstance(o, dict)]
    dims = [o.get('dimension') for o in objs]
    missing_dims = [x for x in DIMS if x not in dims]
    long_ones = ['objectives[%d]=%d 字' % (i, len(str(o.get('text', '')).replace(' ', '')))
                 for i, o in enumerate(objs)
                 if len(str(o.get('text', '')).replace(' ', '')) > 80]
    empty = [i for i, o in enumerate(objs) if not str(o.get('text', '')).strip()]
    ok8 = not missing_dims and not long_ones and not empty
    detail8 = []
    if missing_dims:
        detail8.append('缺维度：' + '、'.join(missing_dims))
    if long_ones:
        detail8.append('超 80 字：' + '、'.join(long_ones[:4]))
    if empty:
        detail8.append('空 text：objectives[%d]' % empty[0])
    item('objectives 四维与字数', ok8, '；'.join(detail8) if detail8 else
         '四维齐全，单条均 ≤80 字')

    # 9 sources 覆盖
    srcs = [s for s in as_list(d, 'sources') if isinstance(s, dict)]
    have = set(s.get('type') for s in srcs)
    lack = [t for t in ('教案', '课件', '练习') if t not in have]
    ok9 = len(srcs) >= 3 and not lack
    item('sources ≥3 且教案/课件/练习各 1', ok9,
         '当前 %d 条，类型 %s；缺 %s' % (len(srcs), '、'.join(sorted(x for x in have if x)),
                                        '、'.join(lack) if lack else '无'))

    # 10 version_tag 与文件名一致（--strict 才判）
    if not strict:
        NO[0] += 1
        RESULTS.append(('version_tag 与文件名一致', True))
        print('  [SKIP] 第%d项 version_tag 与文件名一致（未给 --strict）' % NO[0])
    else:
        tag = str(d.get('version_tag', ''))
        sec = str(d.get('section', ''))
        title = str(d.get('title', ''))
        want = sec + title + '-' + tag
        if name:
            base = os.path.basename(name)
            base = re.sub(r'\.(md|docx)$', '', base)
            ok10 = base == want
            detail10 = '文件名 %s，契约拼出 %s' % (base, want)
        else:
            ok10, detail10 = False, '给了 --strict 却没给 --md/--name，无法比对文件名'
        item('version_tag 与文件名一致', ok10, detail10)


def main():
    ap = argparse.ArgumentParser(
        description='课时契约格式校验（L1）：10 项，写正文前跑。',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''字段词表：
  必填 15 键：id chapter section title textbook duration_min experiment_mode
             version_tag draft objectives segments boards student_sheets deck_pages sources
  experiment_mode：仅多媒体 / 教师演示实验 / 不涉及实验（练习课等）
  objectives.dimension：物理观念 / 科学思维 / 科学探究 / 科学态度与责任
  segments.kind：导入 / 新授 / 练习 / 小结 / 作业 / 讲评
  sources.type：教案 / 课件 / 练习 / 导学案 / 板书 / 视频 / 文献 / 其他
  sources.level：甲 / 乙 / 丙

最小示例（也见 schemas/example.lesson.json）：
  {
    "id": "15.2-第1课时", "chapter": "第十五章 电流和电路",
    "section": "15.2", "title": "电流和电路",
    "textbook": "人教版（2024）九年级物理全一册",
    "duration_min": 40, "experiment_mode": "仅多媒体",
    "version_tag": "第1课时-仅多媒体-详案", "draft": false,
    "objectives": [{"dimension": "物理观念", "text": "知道电流方向的规定"}],
    "segments": [{"name": "情境导入", "minutes": 5, "kind": "导入"}],
    "boards": {"count": 1, "max_lines": 8, "max_chars": 14},
    "student_sheets": [], "deck_pages": ["第1—17页"],
    "sources": [{"url": "https://example.com/a", "fetched_date": "2026-10-20",
                 "type": "教案", "level": "甲", "sha256_16": "0123456789abcdef"}]
  }
  （示例只列最小形状；objectives≥4、segments≥3、sources≥3 才过 10 项。）
''')
    ap.add_argument('contract', help='课时契约 JSON 路径')
    ap.add_argument('--md', help='对应详案 md/docx 路径，--strict 时用来比对文件名')
    ap.add_argument('--name', help='只给文件名同样可，--strict 时用')
    ap.add_argument('--strict', action='store_true', help='启用第 10 项（文件名比对）')
    ns = ap.parse_args()

    try:
        with open(ns.contract, encoding='utf-8') as f:
            d = json.load(f)
    except Exception as e:
        print('  [FAIL] 契约读不了：%s（%s）' % (ns.contract, e))
        print('\n结果：10 项，失败 1 项')
        return 1
    if not isinstance(d, dict):
        print('  [FAIL] 契约顶层必须是对象，当前是 %s' % type(d).__name__)
        print('\n结果：10 项，失败 1 项')
        return 1

    print('== %s ==' % os.path.basename(ns.contract))
    check(d, name=ns.md or ns.name, strict=ns.strict)
    failed = [n for n, ok in RESULTS if not ok]
    print('\n结果：%d 项，失败 %d 项' % (len(RESULTS), len(failed)))
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
