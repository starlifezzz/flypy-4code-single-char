#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从 flypy.schema.yaml 里摘掉 custom_phraseQMZ（「全码字补全表」的挂载点）。

幂等：跑第二次什么也不改。改之前留一份 .bak。
"""
from __future__ import annotations

import argparse
import os
import re
import shutil

BLOCK_KEYS = ('custom_phraseQMZ', 'custom_phraseQMZhi')
TRANSLATOR_RE = re.compile(r'^\s*-\s*table_translator@custom_phraseQMZ(hi)?\s*$')


def strip_block(lines: list[str], key: str) -> tuple[list[str], bool]:
    """删掉 `key:` 这个顶层块（直到下一个顶层键）。"""
    out: list[str] = []
    i = 0
    removed = False
    while i < len(lines):
        if lines[i].startswith(key + ':'):
            removed = True
            i += 1
            while i < len(lines) and (lines[i].startswith((' ', '\t')) or lines[i].strip() == ''):
                i += 1
            continue
        out.append(lines[i])
        i += 1
    return out, removed


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('schema', help='flypy.schema.yaml 路径')
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()

    with open(args.schema, encoding='utf-8') as fh:
        original = fh.read()

    lines = original.split('\n')
    changed = []

    kept = [ln for ln in lines if not TRANSLATOR_RE.match(ln)]
    if len(kept) != len(lines):
        changed.append(f'移除 {len(lines) - len(kept)} 行 table_translator@custom_phraseQMZ')
        lines = kept

    for key in BLOCK_KEYS:
        lines, removed = strip_block(lines, key)
        if removed:
            changed.append(f'移除 {key}: 块')

    new = '\n'.join(lines)
    while '\n\n\n' in new:
        new = new.replace('\n\n\n', '\n\n')

    if not changed:
        print('无需修改：schema 里没有 custom_phraseQMZ')
        return 0

    for item in changed:
        print('· ' + item)

    if args.dry_run:
        print('（dry-run，未写入）')
        return 0

    shutil.copy2(args.schema, args.schema + '.bak')
    with open(args.schema, 'w', encoding='utf-8') as fh:
        fh.write(new)
    print(f'已写入 {args.schema}（备份 {os.path.basename(args.schema)}.bak）')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
