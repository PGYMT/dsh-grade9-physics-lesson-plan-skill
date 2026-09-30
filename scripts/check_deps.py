#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""check_deps.py — 教案技能依赖自检与自举（v1.0，2026-09-30）。

用法：
  python3 check_deps.py                  # 只检测：打印就绪/缺失与安装建议
  python3 check_deps.py --install        # 缺的工作区脚本，从 skill/scripts/dist/ 补齐
  python3 check_deps.py --sync-dist      # 反向：把工作区脚本同步到 skill/scripts/dist/
  python3 check_deps.py --workspace DIR  # 指定工作区（默认 /root/dsh-workspace/工作文件）
退出码：0＝必需项全就绪；1＝有必需项缺失。无网络时只报缺，不尝试联网。
"""
import argparse, glob, os, shutil, subprocess, sys

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_WS = '/root/dsh-workspace/工作文件'
DIST = os.path.join(SKILL_DIR, 'scripts', 'dist')

# 工作区脚本清单：相对路径 -> 用途
WS_SCRIPTS = {
    '00-模板与规范/教案docx生成脚本-v8.py': 'docx 基础生成与样式（v9 的底层依赖）',
    '00-模板与规范/教案docx生成脚本-v9.py': 'md→docx：板书图/旁批/待查/生成信息块',
    '06-工具与提示词/教程/build_board_png.py': 'board 围栏渲染板书 PNG',
    '06-工具与提示词/教程/extract_enbx.py': '解包 .enbx：文本/动画/素材/视频信息',
    '06-工具与提示词/教程/extract_video_frames.py': '课件视频抽帧与封面',
    '06-工具与提示词/教程/build_enbx_native_pages.py': '给 .enbx 副本加原生页',
    '06-工具与提示词/教程/enbx_verify2.ps1': 'Windows 侧打开/跳页/截图',
    '06-工具与提示词/教程/enbx_shot_ocr.py': '截图 OCR 机器层比对',
    '06-工具与提示词/教程/expected_pages.json': '课件验证预期清单',
}

def ok(m, extra=''): print('  [OK] ' + m + (('  ' + extra) if extra else ''))
def bad(m, fix=''): print('  [缺] ' + m + (('  -> ' + fix) if fix else ''))
def cmd_ok(cmd):
    try:
        return subprocess.run(cmd, capture_output=True).returncode == 0
    except Exception:
        return False

def pillow_state():
    try:
        from PIL import Image  # noqa: F401
        return True, '系统 Pillow 可用'
    except Exception:
        pass
    tag = 'cp%d%d' % sys.version_info[:2]
    pats = [os.path.join(DEFAULT_WS, '06-工具与提示词/教程/vendor', 'pillow-*-%s-*.whl' % tag),
            os.path.join(SKILL_DIR, 'scripts', 'vendor', 'pillow-*-%s-*.whl' % tag)]
    for p in pats:
        for f in glob.glob(p):
            return True, 'vendor wheel 可用：' + os.path.basename(f)
    return False, 'pip download pillow --only-binary=:all: --python-version %d.%d' % sys.version_info[:2]

def check(ws):
    missing = []
    print('== Python 与库 ==')
    print('  Python %s' % sys.version.split()[0])
    pil, note = pillow_state()
    (ok if pil else bad)('Pillow（板书渲染）', note)
    if not pil: missing.append('Pillow')
    print('== 外部命令（可选） ==')
    for c, why in [('ffmpeg', '视频抽帧'), ('ffprobe', '读取视频时长/分辨率'), ('tesseract', '截图 OCR')]:
        (ok if shutil.which(c) else bad)('%s（%s）' % (c, why))
    print('== 字体 ==')
    fonts = ['/mnt/c/Windows/Fonts/simkai.ttf', '/mnt/c/Windows/Fonts/simhei.ttf',
             '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc']
    (ok if any(os.path.exists(f) for f in fonts) else bad)('中文字体（simkai/simhei 或 Noto）')
    print('== 工作区脚本 ==')
    ws_missing = []
    for rel, why in WS_SCRIPTS.items():
        p = os.path.join(ws, rel)
        if os.path.exists(p):
            ok(rel)
        else:
            bad('%s（%s）' % (rel, why), 'python3 %s --install' % os.path.abspath(__file__))
            ws_missing.append(rel)
    print('== 仅 Windows（课件核对用） ==')
    for c in ['/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe']:
        (ok if os.path.exists(c) else bad)('PowerShell')
    print('== 交叉依赖 ==')
    for p in ['/root/.dsh/skills/auto-organize-work-files/scripts/organize.py',
              '/root/.dsh/skills/auto-organize-work-files/scripts/skill_link.py',
              '/root/.dsh/skills/auto-organize-work-files/scripts/sync_checklist.py',
              os.path.join(SKILL_DIR, 'SKILL.md')]:
        (ok if os.path.exists(p) else bad)(p)
    return missing + ws_missing

def install(ws):
    n = 0
    for rel in WS_SCRIPTS:
        src = os.path.join(DIST, rel.replace('/', '__'))
        dst = os.path.join(ws, rel)
        if os.path.exists(dst) or not os.path.exists(src):
            continue
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(src, dst); n += 1; print('  补齐 ' + rel)
    print('已补齐 %d 个' % n)

def sync_dist(ws):
    os.makedirs(DIST, exist_ok=True)
    n = 0
    for rel in WS_SCRIPTS:
        src = os.path.join(ws, rel)
        if not os.path.exists(src):
            continue
        shutil.copy2(src, os.path.join(DIST, rel.replace('/', '__'))); n += 1
    print('已同步 %d 个到 %s' % (n, DIST))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--workspace', default=DEFAULT_WS)
    ap.add_argument('--install', action='store_true')
    ap.add_argument('--sync-dist', action='store_true')
    a = ap.parse_args()
    if a.sync_dist:
        sync_dist(a.workspace); return 0
    miss = check(a.workspace)
    if a.install:
        install(a.workspace)
    print('')
    print('结果：必需项缺失 %d 项' % len(miss))
    return 1 if miss else 0

if __name__ == '__main__':
    sys.exit(main())