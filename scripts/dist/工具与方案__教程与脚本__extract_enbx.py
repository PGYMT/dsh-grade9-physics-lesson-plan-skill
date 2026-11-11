#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""extract_enbx.py — 解包希沃白板 .enbx 课件（v1.0，2026-09-27）。

输出（默认写到 <enbx目录>/<课件名>-解包/）：
  - <名>-课件文本.md   逐页文字
  - <名>-动画脚本.md   逐页动画顺序（类型/触发/顺序/时长/所属元素）
  - <名>-素材清单.md   图片/视频清单与所在页
  - <名>-素材/         导出的图片与视频

用法：python3 extract_enbx.py <课件.enbx> [输出目录]
"""
import sys, os, zipfile, re, json, subprocess
import xml.etree.ElementTree as ET

def tag(e):
    return e.tag.split('}')[-1]

def slide_key(n):
    m = re.search(r'Slide_(\d+)\.xml$', n)
    return int(m.group(1)) if m else 10**9

def first_child(el, name):
    for c in el:
        if tag(c) == name:
            return c
    return None

def page_texts(root):
    out = []
    for rt in root.iter():
        if tag(rt) != 'RichText':
            continue
        t = first_child(rt, 'Text')
        if t is not None and t.text and t.text.strip():
            v = t.text.strip()
        else:
            runs = [x.text.strip() for x in rt.iter()
                    if tag(x) == 'Text' and x.text and x.text.strip()]
            v = ' '.join(runs).strip()
        if v and v not in out:
            out.append(v)
    return out

def owner_label(el):
    for p in el.iter():
        if tag(p) == 'PictureName' and p.text:
            return '图片:' + p.text.strip()
    for p in el.iter():
        if tag(p) == 'MediaName' and p.text:
            return '视频:' + p.text.strip()
    ts = page_texts(el)
    if ts:
        v = ' / '.join(ts).replace('\n', ' ').replace('\r', ' ')
        return '文字:' + v[:40]
    return '元素'

def animations_of(el):
    a = first_child(el, 'Animations')
    if a is None:
        return []
    out = []
    for an in a:
        if tag(an) != 'Animation':
            continue
        out.append({tag(x): (x.text or '').strip() for x in an})
    order = []
    oe = first_child(el, 'AnimationOrders')
    if oe is not None:
        order = [(x.text or '').strip() for x in oe if tag(x) == 'Item']
    def key(a):
        i = a.get('Id', '')
        if i in order:
            return order.index(i)
        try:
            return 10000 + int(a.get('Number', '0'))
        except ValueError:
            return 99999
    return sorted(out, key=key)

def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    path = os.path.abspath(sys.argv[1])
    if not path.lower().endswith('.enbx') or not os.path.isfile(path):
        print('错误：请提供 .enbx 文件路径')
        return 2
    base = os.path.splitext(os.path.basename(path))[0]
    outdir = os.path.abspath(sys.argv[2]) if len(sys.argv) > 2 \
        else os.path.join(os.path.dirname(path), base + '-解包')
    matdir = os.path.join(outdir, base + '-素材')
    os.makedirs(matdir, exist_ok=True)
    z = zipfile.ZipFile(path)
    slides = sorted([n for n in z.namelist()
                     if re.match(r'Slides/Slide_\d+\.xml$', n)], key=slide_key)
    text_md = ['# ' + base + '（课件文本）', '']
    anim_md = ['# ' + base + '（动画脚本）', '',
               '> 说明：按页列出动画出现顺序；“触发”Click=点击、Before=与上一动画同时、After=上一动画之后。', '']
    res_use = {}
    anim_total = 0
    for i, sn in enumerate(slides, 1):
        root = ET.fromstring(z.read(sn).decode('utf-8-sig', 'ignore'))
        text_md.append('## 第 %d 页' % i)
        for v in page_texts(root):
            text_md.append('- ' + v)
        text_md.append('')
        for s in root.iter():
            if tag(s) == 'Source' and s.text and s.text.startswith('id://'):
                res_use.setdefault(s.text[5:], set()).add(i)
        anims = []
        for el in root.iter():
            if first_child(el, 'Animations') is None:
                continue
            for an in animations_of(el):
                an['_owner'] = owner_label(el)
                anims.append(an)
        if anims:
            anim_total += len(anims)
            anim_md.append('## 第 %d 页' % i)
            for k, an in enumerate(anims, 1):
                anim_md.append('%d. [%s] %s（触发:%s，时长:%s）—— %s' % (
                    k, an.get('Category', ''), an.get('Type', ''), an.get('Trigger', ''),
                    an.get('Duration', ''), an.get('_owner', '')))
            anim_md.append('')
    resources = [(n, z.getinfo(n).file_size) for n in z.namelist() if n.startswith('Resources/')]
    res_md = ['# ' + base + '（素材清单）', '', '| 文件 | 类型 | 大小(字节) | 所在页 |', '|---|---|---|---|']
    n_img = n_vid = 0
    for n, size in sorted(resources, key=lambda x: x[1]):
        fn = os.path.basename(n)
        rid = os.path.splitext(fn)[0]
        ext = os.path.splitext(fn)[1].lower()
        kind = '图片' if ext in ('.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp') \
            else ('视频' if ext in ('.mp4', '.avi', '.mov', '.wmv', '.webm') else '其他')
        if kind == '图片':
            n_img += 1
        if kind == '视频':
            n_vid += 1
        pages = sorted(res_use.get(rid, []))
        page_s = '、'.join(str(p) for p in pages) if pages else '-'
        res_md.append('| %s | %s | %d | %s |' % (fn, kind, size, page_s))
        with open(os.path.join(matdir, fn), 'wb') as f:
            f.write(z.read(n))
    vid_rows = []
    for n, size in sorted(resources, key=lambda x: x[1]):
        fn = os.path.basename(n)
        if os.path.splitext(fn)[1].lower() not in ('.mp4', '.avi', '.mov', '.wmv', '.webm'):
            continue
        p = os.path.join(matdir, fn)
        dur, res = '-', '-'
        try:
            r = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
                                '-show_entries', 'stream=width,height', '-of', 'json', p],
                               capture_output=True, text=True, timeout=30)
            jj = json.loads(r.stdout or '{}')
            dur = '%.1fs' % float(jj.get('format', {}).get('duration', 0) or 0)
            st = (jj.get('streams') or [{}])[0]
            if st.get('width'):
                res = '%sx%s' % (st.get('width'), st.get('height'))
        except Exception:
            pass
        vid_rows.append('| %s | %s | %s | %s-截图/ |' % (fn, dur, res, os.path.splitext(fn)[0]))
    if vid_rows:
        res_md += ['', '## 视频信息（抽帧用；脚本：extract_video_frames.py）', '',
                   '| 文件 | 时长 | 分辨率 | 截图目录 |', '|---|---|---|---|'] + vid_rows
    open(os.path.join(outdir, base + '-课件文本.md'), 'w', encoding='utf-8').write('\n'.join(text_md))
    open(os.path.join(outdir, base + '-动画脚本.md'), 'w', encoding='utf-8').write('\n'.join(anim_md))
    open(os.path.join(outdir, base + '-素材清单.md'), 'w', encoding='utf-8').write('\n'.join(res_md))
    print('OK', outdir)
    print('  页数=%d 动画节点=%d 图片=%d 视频=%d' % (len(slides), anim_total, n_img, n_vid))
    return 0

if __name__ == '__main__':
    sys.exit(main())
