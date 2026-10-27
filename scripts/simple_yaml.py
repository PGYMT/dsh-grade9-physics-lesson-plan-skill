#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""simple_yaml.py — 技能用的极简 YAML 读写（纯标准库，v1）。

只覆盖 references/data/*.yaml 用到的子集：
  - 块状映射与 "- " 列表，可互相嵌套
  - 标量：整数、true/false/null、双引号字符串（支持 \" \\ \n）、裸字符串
  - 行内列表：[a, b, c]（元素按标量解析）
  - 行内空映射 {} 与空列表 []
不支持：锚点、多行块（| / >）、标签、合并键。遇到不支持写法直接抛 YAMLError，
不做猜测——数据文件由本技能自己写，写坏了应当报错而不是静默读错。

对外接口：
  loads(text) -> dict | list
  load(path)  -> dict | list
  dumps(obj)  -> str      # 往返稳定：同一对象两次 dumps 逐字节相同
  dump(obj, path)
"""
import json
import os

class YAMLError(ValueError):
    """语法超出本模块支持的子集。"""


def _strip_comment(line):
    out = []
    q = False
    i = 0
    while i < len(line):
        c = line[i]
        if c == '\\' and q and i + 1 < len(line):
            out.append(c); out.append(line[i + 1]); i += 2; continue
        if c == '"':
            q = not q
        if c == '#' and not q and (not out or out[-1] in ' \t'):
            break
        out.append(c)
        i += 1
    return ''.join(out).rstrip()


def _scalar(s):
    s = s.strip()
    if s == '':
        return None
    if s == 'null' or s == '~':
        return None
    if s == 'true':
        return True
    if s == 'false':
        return False
    if s.startswith('"'):
        if not s.endswith('"') or len(s) < 2:
            raise YAMLError('双引号未闭合：' + s)
        return json.loads(s)
    if s.startswith('[') and s.endswith(']'):
        inner = s[1:-1].strip()
        if not inner:
            return []
        return [_scalar(p) for p in _split_flow(inner)]
    if s == '{}':
        return {}
    if s.isdigit() or (s.startswith('-') and s[1:].isdigit()):
        return int(s)
    return s


def _split_flow(s):
    parts, buf, q = [], [], False
    i = 0
    while i < len(s):
        c = s[i]
        if c == '\\' and q and i + 1 < len(s):
            buf.append(c); buf.append(s[i + 1]); i += 2; continue
        if c == '"':
            q = not q
        if c == ',' and not q:
            parts.append(''.join(buf)); buf = []; i += 1; continue
        buf.append(c); i += 1
    if buf:
        parts.append(''.join(buf))
    return parts


def _split_key(s):
    q = False
    for i, c in enumerate(s):
        if c == '\\' and q:
            continue
        if c == '"':
            q = not q
        if c == ':' and not q and (i + 1 == len(s) or s[i + 1] in ' \t'):
            return s[:i].strip(), s[i + 1:].strip()
    return None, None


def loads(text):
    lines = []
    for raw in text.splitlines():
        if not raw.strip():
            continue
        if raw.lstrip().startswith('#'):
            continue
        body = _strip_comment(raw)
        if not body.strip():
            continue
        indent = len(body) - len(body.lstrip(' '))
        if '\t' in body[:indent + 1]:
            raise YAMLError('缩进里不能有制表符')
        lines.append((indent, body.strip()))
    idx = [0]

    def parse_block(indent):
        if idx[0] >= len(lines):
            return None
        cur_indent, cur = lines[idx[0]]
        if cur.startswith('- '):
            return parse_list(cur_indent)
        if cur == '-':
            return parse_list(cur_indent)
        return parse_map(cur_indent)

    def parse_map(indent):
        out = {}
        while idx[0] < len(lines):
            ind, cur = lines[idx[0]]
            if ind < indent:
                break
            if ind > indent:
                raise YAMLError('缩进异常：' + cur)
            if cur.startswith('- '):
                break
            key, rest = _split_key(cur)
            if key is None:
                raise YAMLError('缺少键值冒号：' + cur)
            key = _scalar(key) if key.startswith('"') else key
            idx[0] += 1
            if rest == '':
                if idx[0] < len(lines) and lines[idx[0]][0] > indent:
                    out[key] = parse_block(lines[idx[0]][0])
                else:
                    out[key] = None
            else:
                out[key] = _scalar(rest)
        return out

    def parse_list(indent):
        out = []
        while idx[0] < len(lines):
            ind, cur = lines[idx[0]]
            if ind < indent:
                break
            if ind > indent:
                raise YAMLError('缩进异常：' + cur)
            if not (cur.startswith('- ') or cur == '-'):
                break
            item = cur[1:].strip()
            idx[0] += 1
            if item == '':
                out.append(parse_block(lines[idx[0]][0]) if idx[0] < len(lines) and lines[idx[0]][0] > indent else None)
                continue
            k, rest = _split_key(item)
            if k is None:
                out.append(_scalar(item))
                continue
            # "- key: value" 起头的映射项
            node = {}
            key = _scalar(k) if k.startswith('"') else k
            if rest == '':
                if idx[0] < len(lines) and lines[idx[0]][0] > indent:
                    node[key] = parse_block(lines[idx[0]][0])
                else:
                    node[key] = None
            else:
                node[key] = _scalar(rest)
            while idx[0] < len(lines):
                ind2, cur2 = lines[idx[0]]
                if ind2 <= indent:
                    break
                if cur2.startswith('- ') and ind2 <= indent:
                    break
                if ind2 < indent + 2:
                    raise YAMLError('列表项内缩进异常：' + cur2)
                sub = parse_map(ind2) if not cur2.startswith('- ') else parse_list(ind2)
                if isinstance(sub, dict):
                    node.update(sub)
                else:
                    node.setdefault('_list', []).extend(sub)
                break
            out.append(node)
        return out

    if not lines:
        return None
    result = parse_block(lines[0][0])
    if idx[0] != len(lines):
        raise YAMLError('还有未解析的行：' + lines[idx[0]][1])
    return result


def load(path):
    with open(path, 'r', encoding='utf-8') as f:
        return loads(f.read())


def _q(s):
    if isinstance(s, bool):
        return 'true' if s else 'false'
    if isinstance(s, int):
        return str(s)
    if s is None:
        return 'null'
    s = str(s)
    if s and all(ch not in s for ch in '"\\\n') and not s.startswith(' ') and not s.endswith(' '):
        if s not in ('null', 'true', 'false') and not (s.isdigit() or (s.startswith('-') and s[1:].isdigit())):
            if not s.startswith('[') and '#' not in s:
                return s
    return json.dumps(s, ensure_ascii=False)


def _emit(obj, indent, out):
    pad = ' ' * indent
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(v, (dict, list)) and v:
                out.append('%s%s:' % (pad, _q(k)))
                _emit(v, indent + 2, out)
            elif isinstance(v, list) and not v:
                out.append('%s%s: []' % (pad, _q(k)))
            elif isinstance(v, dict) and not v:
                out.append('%s%s: {}' % (pad, _q(k)))
            else:
                out.append('%s%s: %s' % (pad, _q(k), _scalar_text(v)))
    elif isinstance(obj, list):
        for v in obj:
            if isinstance(v, dict) and v:
                first = True
                for k, vv in v.items():
                    prefix = '%s- ' % pad if first else '%s  ' % pad
                    first = False
                    if isinstance(vv, (dict, list)) and vv:
                        out.append('%s%s:' % (prefix, _q(k)))
                        _emit(vv, indent + 4, out)
                    else:
                        out.append('%s%s: %s' % (prefix, _q(k), _scalar_text(vv)))
            elif isinstance(v, list):
                out.append('%s-' % pad)
                _emit(v, indent + 2, out)
            else:
                out.append('%s- %s' % (pad, _scalar_text(v)))
    else:
        out.append('%s%s' % (pad, _scalar_text(obj)))


def _scalar_text(v):
    if isinstance(v, list) and v:
        return '[' + ', '.join(_scalar_text(x) for x in v) + ']'
    return _q(v)


def dumps(obj, header=''):
    out = []
    if header:
        for line in header.splitlines():
            out.append('# ' + line if line and not line.startswith('#') else line)
    _emit(obj, 0, out)
    return '\n'.join(out) + '\n'


def dump(obj, path, header=''):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(dumps(obj, header))
