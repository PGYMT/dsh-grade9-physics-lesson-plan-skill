#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""教案 docx 目检：docx → PDF → 逐页 PNG（v1.0）

交付前用它把 Word 成品变成图，用眼睛看四样东西：
① 板书图有没有被压扁或出界；② 旁批红字有没有跑段；③ 表格有没有串行；④ 分页有没有把小结切开。

用法：
  python3 scripts/render_docx_check.py 某详案.docx
  python3 scripts/render_docx_check.py /path/a.docx /path/b.docx --dpi 120
  python3 scripts/render_docx_check.py 某详案.docx --out-dir /tmp/preview --keep-pdf

依赖：LibreOffice（soffice）与 poppler-utils（pdftoppm）。缺哪个会直接说明装什么。
输出：默认把图放在 docx 同目录的 preview-<文件名>/ 下，文件名 <文件名>-第1页.png 起。退出码：0 出图成功；2 环境缺工具；1 转换失败。
"""
import argparse
import os
import shutil
import subprocess
import sys
import tempfile

CHECKLIST = ('看四样：① 板书图有没有被压扁或出界；② 旁批红字有没有跑段；'
             '③ 表格有没有串行；④ 分页有没有把小结切开。')
INSTALL_HINT = ('缺 LibreOffice。装法（Ubuntu/Debian，一条）：'
                'sudo apt-get install -y --no-install-recommends libreoffice-writer')


def which(name):
    return shutil.which(name)


def find_soffice():
    for name in ('soffice', 'libreoffice'):
        p = which(name)
        if p:
            return p
    for p in ('/usr/bin/soffice', '/usr/lib/libreoffice/program/soffice',
              '/opt/libreoffice/program/soffice'):
        if os.path.isfile(p) and os.access(p, os.X_OK):
            return p
    return None


def docx_to_pdf(docx, outdir, soffice):
    """LibreOffice 转 PDF：--convert-to pdf，输出到 outdir。"""
    cmd = [soffice, '--headless', '--norestore', '--convert-to', 'pdf',
           '--outdir', outdir, docx]
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    pdf = os.path.join(outdir, os.path.splitext(os.path.basename(docx))[0] + '.pdf')
    if p.returncode != 0 or not os.path.isfile(pdf):
        tail = (p.stderr or p.stdout or '').strip().splitlines()[-3:]
        return None, '转换失败：' + (' / '.join(tail) if tail else '没生成 PDF')
    return pdf, ''


def pdf_to_pngs(pdf, outdir, stem, dpi):
    """pdftoppm -png -r DPI：输出 <stem>-第N页.png。"""
    prefix = os.path.join(outdir, stem)
    p = subprocess.run(['pdftoppm', '-png', '-r', str(dpi), pdf, prefix],
                       capture_output=True, text=True, timeout=300)
    if p.returncode != 0:
        return [], '出图失败：' + (p.stderr or '').strip()
    got = sorted(x for x in os.listdir(outdir)
                 if x.startswith(os.path.basename(stem)) and x.endswith('.png'))
    pages = []
    for i, name in enumerate(got, 1):
        new = '%s-第%d页.png' % (stem, i)
        os.replace(os.path.join(outdir, name), os.path.join(outdir, new))
        pages.append(os.path.join(outdir, new))
    return pages, ''


def pdf_pages(pdf):
    p = which('pdfinfo')
    if not p:
        return 0
    r = subprocess.run([p, pdf], capture_output=True, text=True)
    for ln in r.stdout.splitlines():
        if ln.startswith('Pages:'):
            try:
                return int(ln.split(':', 1)[1].strip())
            except ValueError:
                return 0
    return 0


def main():
    ap = argparse.ArgumentParser(
        description='教案 docx 目检：docx → PDF → 逐页 PNG。',
        epilog=('四样检查：板书图被压/出界、旁批跑段、表格串行、分页切开小结。\n'
                '例：python3 scripts/render_docx_check.py 15.2电流和电路-第1课时-仅多媒体-详案.docx'))
    ap.add_argument('docx', nargs='+', help='要出图的 docx，可以给多份')
    ap.add_argument('--out-dir', help='图放哪；默认 docx 同目录 preview-<文件名>/')
    ap.add_argument('--dpi', type=int, default=110, help='出图清晰度，默认 110（够看版式）')
    ap.add_argument('--keep-pdf', action='store_true', help='保留中间 PDF')
    a = ap.parse_args()

    soffice = find_soffice()
    pdftoppm = which('pdftoppm')
    missing = []
    if not soffice:
        missing.append('LibreOffice（soffice）')
    if not pdftoppm:
        missing.append('poppler-utils（pdftoppm）')
    if missing:
        print('[缺工具] ' + '、'.join(missing))
        print(INSTALL_HINT)
        return 2

    bad = 0
    for docx in a.docx:
        if not os.path.isfile(docx):
            print('[FAIL] %s 不存在' % docx)
            bad += 1
            continue
        stem = os.path.splitext(os.path.basename(docx))[0]
        outdir = a.out_dir or os.path.join(os.path.dirname(os.path.abspath(docx)), 'preview-' + stem)
        os.makedirs(outdir, exist_ok=True)
        tmp = tempfile.mkdtemp(prefix='docxcheck-')
        try:
            pdf, err = docx_to_pdf(os.path.abspath(docx), tmp, soffice)
            if not pdf:
                print('[FAIL] %s  %s' % (os.path.basename(docx), err))
                bad += 1
                continue
            pages, err = pdf_to_pngs(pdf, outdir, stem, a.dpi)
            if not pages:
                print('[FAIL] %s  %s' % (os.path.basename(docx), err))
                bad += 1
                continue
            n = pdf_pages(pdf) or len(pages)
            print('[OK] %s  %d 页 → %s' % (os.path.basename(docx), n, outdir))
            for pth in pages:
                print('     ' + pth)
            if a.keep_pdf:
                dst = os.path.join(outdir, stem + '.pdf')
                shutil.copyfile(pdf, dst)
                print('     ' + dst)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    print(CHECKLIST)
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
