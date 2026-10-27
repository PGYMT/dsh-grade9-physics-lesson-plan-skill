#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""checks.py — 校验脚本共用的三级判定（v1.0）。

三级含义（写进 02 §6 与 04 §1 的同一套口径）：
  item     阻断项：判不过就不许交付，退出码变 1。
  warn     提示项：不阻断，每次都报，提醒看一眼。
  advisory 遗留项：不阻断，只在「这次新出现」时报一次；已知的旧问题不再刷屏。

advisory 的「已知」用本地缓存判定：缓存文件缺省在
~/.cache/dsh-jiaoan/advisory.json（可用环境变量 JIAOAN_ADVISORY_CACHE 覆盖），
键是「脚本名:检查名:被检查文件:要点」，值只用来记录出现过。
缓存丢失不会造成误判为失败——advisory 从不改退出码。
"""
import hashlib
import json
import os

CACHE_ENV = 'JIAOAN_ADVISORY_CACHE'
CACHE_DEFAULT = os.path.join(os.path.expanduser('~'), '.cache', 'dsh-jiaoan', 'advisory.json')


def _cache_path():
    return os.environ.get(CACHE_ENV) or CACHE_DEFAULT


def _load():
    p = _cache_path()
    try:
        with open(p, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _save(data):
    p = _cache_path()
    os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = p + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=1, sort_keys=True)
    os.replace(tmp, p)


def _key(script, name, target, detail=''):
    raw = '%s|%s|%s|%s' % (script, name, target, detail[:120])
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()[:24]


def advisory(script, name, target, detail='', quiet=False):
    """报一条遗留项：新出现才打印，已知的静默记一笔。返回是否属新出现。"""
    data = _load()
    k = _key(script, name, target, detail)
    fresh = k not in data
    data[k] = {'script': script, 'name': name, 'target': target, 'detail': detail[:200]}
    try:
        _save(data)
    except OSError:
        pass
    if fresh and not quiet:
        print('  [ADVISORY] %s%s' % (name, ('  ' + detail) if detail else ''))
    return fresh
