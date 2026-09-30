#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""extract_video_frames.py — 课件视频抽帧与封面（v1.0，2026-09-30）。

用法：
  python3 extract_video_frames.py <视频.mp4|素材目录|课件.enbx> [输出根目录]
输出：<输出根>/<视频名>-截图/<视频名>-01.png … 与 <视频名>-封面.png
帧数按时长自适应 clamp(ceil(时长/30), 3, 6)；封面优先取 .enbx 内 <Video> 的 Thumbnail。
"""
import glob, math, os, re, shutil, subprocess, sys, zipfile


def dur_of(path):
    try:
        r = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
                            '-of', 'default=nw=1:nk=1', path], capture_output=True, text=True, timeout=30)
        return float((r.stdout or '0').strip() or 0)
    except Exception:
        return 0.0


def n_frames(d):
    if d <= 0:
        return 3
    return max(3, min(6, int(math.ceil(d / 30.0))))


def do_video(path, outroot, cover=None):
    stem = os.path.splitext(os.path.basename(path))[0]
    outdir = os.path.join(outroot, stem + '-截图')
    os.makedirs(outdir, exist_ok=True)
    d = dur_of(path)
    n = n_frames(d)
    fps = (n / d) if d > 0 else 1.0
    subprocess.run(['ffmpeg', '-v', 'error', '-i', path, '-vf', 'fps=%.6f' % fps,
                    '-frames:v', str(n), os.path.join(outdir, stem + '-%02d.png'), '-y'], check=False)
    cv = os.path.join(outroot, stem + '-封面.png')
    if cover and os.path.exists(cover):
        shutil.copy2(cover, cv)
    else:
        subprocess.run(['ffmpeg', '-v', 'error', '-i', path, '-frames:v', '1', cv, '-y'], check=False)
    made = len(glob.glob(os.path.join(outdir, '*.png')))
    print('OK %s  时长=%.1fs 帧数=%d 截图=%d 封面=%s' % (stem, d, n, made, os.path.basename(cv)))
    return made


def covers_from_enbx(enbx):
    """返回 {视频资源文件名: 封面临时路径}。需要时把封面解到内存临时文件。"""
    out = {}
    tmp = os.path.join(os.path.dirname(os.path.abspath(enbx)), '.tmp_covers')
    try:
        z = zipfile.ZipFile(enbx)
    except Exception:
        return out
    for n in z.namelist():
        if not re.match(r'Slides/Slide_\d+\.xml$', n):
            continue
        s = z.read(n).decode('utf-8', 'ignore')
        for m in re.finditer(r'<Video>.*?</Video>', s, re.S):
            blk = m.group(0)
            sm = re.search(r'<Source>id://([0-9a-fA-F\-]+)</Source>', blk)
            tm = re.search(r'<Thumbnail>id://([0-9a-fA-F\-]+)</Thumbnail>', blk)
            if not (sm and tm):
                continue
            vid = [x for x in z.namelist() if x.startswith('Resources/' + sm.group(1) + '.')]
            cov = [x for x in z.namelist() if x.startswith('Resources/' + tm.group(1) + '.')]
            if not (vid and cov):
                continue
            os.makedirs(tmp, exist_ok=True)
            p = os.path.join(tmp, 'cover_' + tm.group(1) + os.path.splitext(cov[0])[1])
            if not os.path.exists(p):
                with open(p, 'wb') as f:
                    f.write(z.read(cov[0]))
            out[os.path.basename(vid[0])] = p
    return out


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    src = os.path.abspath(sys.argv[1])
    outroot = os.path.abspath(sys.argv[2]) if len(sys.argv) > 2 else os.path.dirname(src)
    videos, covers = [], {}
    if src.lower().endswith('.enbx') and os.path.isfile(src):
        z = zipfile.ZipFile(src)
        videos = [os.path.join(os.path.dirname(src), '.tmp_videos', os.path.basename(n))
                  for n in z.namelist() if n.startswith('Resources/') and n.lower().endswith('.mp4')]
        if not videos:
            print('该课件没有 mp4'); return 0
        tmpv = os.path.dirname(videos[0]); os.makedirs(tmpv, exist_ok=True)
        for n in z.namelist():
            if n.startswith('Resources/') and n.lower().endswith('.mp4'):
                with open(os.path.join(tmpv, os.path.basename(n)), 'wb') as f:
                    f.write(z.read(n))
        covers = covers_from_enbx(src)
    elif os.path.isdir(src):
        videos = sorted(glob.glob(os.path.join(src, '*.mp4')))
    else:
        videos = [src]
    total = 0
    for v in videos:
        total += do_video(v, outroot, covers.get(os.path.basename(v)))
    print('共 %d 段视频，%d 张截图' % (len(videos), total))
    return 0


if __name__ == '__main__':
    sys.exit(main())