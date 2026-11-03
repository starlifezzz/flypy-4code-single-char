#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""flypy4 —— 小鹤音形 4 码唯一单字裁决器

输入：由官方 flypy.table.bin 反编译得到的文本（tab 分隔：词<TAB>码）
输出：flypy.dict.yaml（重建后的主词库）+ flypy_sys.txt（剔除已裁决 4 码的符号表）

规则见 docs/rules.md。用法见 README。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import defaultdict

# 允许出现在 4 码上的「文字」：CJK 各扩展区 + 中文标点（用于一句话词条）
CJK_RE = re.compile(
    r'^[\u3000-\u303f\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff'
    r'\U00020000-\U0003ffff，。、·？！：；（）《》“”‘’—…]+$'
)

SRC_RANK = {'main': 0, 'flypy_top': 1, 'flypy_sys': 2, 'flypy_user': 3, 'flypy_full': 4}
WORD_RANK = 999  # 排序取最小者，故词用最大 rank = 永远输给单字


def log(msg: str) -> None:
    print(msg, file=sys.stderr)


def read_table(path: str) -> list[tuple[str, str]]:
    """读 Rime 的「词<TAB>码」文本，跳过注释与空行。"""
    rows = []
    with open(path, encoding='utf-8') as fh:
        for line in fh:
            line = line.rstrip('\n')
            if not line or line.startswith('#') or '\t' not in line:
                continue
            parts = line.split('\t')
            if len(parts) < 2:
                continue
            rows.append((parts[0], parts[1]))
    return rows


def find_first(base: str, names: list[str]) -> str | None:
    for n in names:
        p = os.path.join(base, n)
        if os.path.isfile(p):
            return p
    return None


def load_levels(path: str | None) -> dict[str, int]:
    """《通用规范汉字表》等级表（1/2/3）。缺省时全部视作同级。"""
    if not path:
        return {}
    with open(path, encoding='utf-8') as fh:
        data = json.load(fh)
    levels: dict[str, int] = {}
    for row in data:
        try:
            levels.setdefault(row['character'], int(row['level']))
        except (KeyError, TypeError, ValueError):
            continue
    return levels


def main() -> int:
    ap = argparse.ArgumentParser(
        description='小鹤音形 4 码唯一单字裁决器',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='示例：\n'
               '  python3 flypy4.py --decompiled flypy.yaml --rime ~/.local/share/fcitx5/rime --out ./out',
    )
    ap.add_argument('--decompiled', required=True,
                    help='rime_table_decompiler 反编译出的文本（词<TAB>码）')
    ap.add_argument('--rime', required=True, help='Rime 用户目录（含 flypy_sys.txt 等）')
    ap.add_argument('--out', required=True, help='输出目录')
    ap.add_argument('--levels', default=None,
                    help='《通用规范汉字表》等级 JSON（可选；省略则退化为「有无更短码 + 原顺序」）')
    ap.add_argument('--apostrophe', choices=['handle', 'keep'], default='handle',
                    help="如何处理 x x x' 这类「3 字母 + 隔音符」的码：handle=一并裁决（默认）；"
                         'keep=原样不动（它们本来就不会自动上屏）')
    ap.add_argument('--full', choices=['auto', 'yes', 'no'], default='auto',
                    help='是否吃进官方的「全码字补全表」flypy_full*.txt（auto=存在就用）')
    args = ap.parse_args()

    os.makedirs(args.out, exist_ok=True)

    levels = load_levels(args.levels)
    if not levels:
        log('警告：未提供 --levels，生僻字与常用字将无法区分（退化为「有无更短码 + 原顺序」）')

    # ---------- 载入四个来源 ----------
    src: dict[str, list[list]] = defaultdict(list)  # code -> [[text, source, order]]
    order = 0

    main_entries: list[tuple[str, str]] = []
    for text, code in read_table(args.decompiled):
        main_entries.append((text, code))
        src[code].append([text, 'main', order])
        order += 1

    if not main_entries:
        log(f'错误：{args.decompiled} 里没有任何「词<TAB>码」行')
        return 2

    sys_path = find_first(args.rime, ['flypy_sys.txt'])
    if not sys_path:
        log(f'错误：{args.rime} 下找不到 flypy_sys.txt')
        return 2

    extra_files = [('flypy_sys', sys_path)]
    top = find_first(args.rime, ['flypy_top.txt'])
    if top:
        extra_files.append(('flypy_top', top))
    user = find_first(args.rime, ['flypy_user.txt'])
    if user:
        extra_files.append(('flypy_user', user))

    full_name = None
    if args.full != 'no':
        full_name = find_first(args.rime, [
            'flypy_full.txt', 'flypy_full.txt.disabled',
            'flypy_full全码字.txt', 'flypy_full全码字.txt.disabled',
        ])
        if full_name:
            extra_files.append(('flypy_full', full_name))

    rows_by_src: dict[str, list[tuple[str, str]]] = {}
    for tag, path in extra_files:
        rows = read_table(path)
        rows_by_src[tag] = rows
        for text, code in rows:
            src[code].append([text, tag, order])
            order += 1

    if args.full == 'auto' and not full_name:
        log('提示：未找到 flypy_full 补全表，按「未启用补全」处理')

    # 同一码下的重复文本去重（保留先出现的来源）
    for code in list(src):
        seen, kept = set(), []
        for entry in src[code]:
            if entry[0] in seen:
                continue
            seen.add(entry[0])
            kept.append(entry)
        src[code] = kept

    # 每个字/词出现过的所有码（用于判断「有没有更短的码」）
    codes_of: dict[str, set[str]] = defaultdict(set)
    for code, entries in src.items():
        for text, _src, _o in entries:
            codes_of[text].add(code)

    def short_len(text: str, code: str) -> int:
        return min((len(c) for c in codes_of[text] if c != code), default=99)

    # ---------- 逐 4 码裁决 ----------
    four = {c: v for c, v in src.items() if len(c) == 4}
    handled: dict[str, list] = {}
    skipped_nosep: list[str] = []      # 含非汉字（符号/emoji/外文）
    skipped_nochar: list[str] = []     # 全是词，没有单字
    skipped_apos: list[str] = []       # xxx' 且 --apostrophe keep

    for code, entries in four.items():
        if len(entries) < 2:
            continue
        if args.apostrophe == 'keep' and "'" in code:
            skipped_apos.append(code)
            continue
        if not all(CJK_RE.match(text) for text, _s, _o in entries):
            skipped_nosep.append(code)
            continue
        if not any(len(text) == 1 for text, _s, _o in entries):
            skipped_nochar.append(code)
            continue
        handled[code] = entries

    def score(entry: list, code: str) -> tuple:
        text, source, order_ = entry
        if len(text) > 1:                       # 词：无条件让位于单字
            return (WORD_RANK, WORD_RANK, SRC_RANK.get(source, 9), order_)
        return (levels.get(text, 99),           # ① 通用规范汉字表等级（1 最常用，3 最生僻）
                short_len(text, code),          # ② 有更短的码 → 说明它不该占着 4 码
                SRC_RANK.get(source, 9),        # ③ 来源优先级
                order_)                         # ④ 原文件顺序

    winner: dict[str, list] = {}
    losers: list[tuple[str, str, str]] = []
    for code, entries in handled.items():
        best = min(entries, key=lambda e: score(e, code))
        winner[code] = best
        for entry in entries:
            if entry[0] != best[0]:
                losers.append((entry[0], code, entry[1]))

    # ---------- 组装新主词库 ----------
    out_rows: list[tuple[str, str]] = []
    handled_codes = set(handled)
    for text, code in main_entries:
        if code in handled_codes and winner[code][0] != text:
            continue                            # 输家：离开 4 码（下面降级）
        out_rows.append((text, code))

    have = set(out_rows)
    added_winner = 0
    for code, best in winner.items():           # 赢家若来自 sys/top/user，补进主词库
        if (best[0], code) not in have:
            out_rows.append((best[0], code))
            have.add((best[0], code))
            added_winner += 1

    # 只由「补全表」提供的「单候选四码」：补全表一停用，这些码就空了，
    # 所以把它们搬进主词库（它们本来就该原样不动）
    rescued = 0
    for code, entries in four.items():
        if len(entries) != 1 or code in handled:
            continue
        text, source, _o = entries[0]
        if source != 'flypy_full' or (text, code) in have:
            continue
        out_rows.append((text, code))
        have.add((text, code))
        rescued += 1

    demoted = 0
    for text, code, _src in losers:
        short = code[:3]
        if (text, short) in have:
            continue
        out_rows.append((text, short))
        have.add((text, short))
        demoted += 1

    # ---------- 写 flypy.dict.yaml ----------
    version = ''
    schema_path = os.path.join(args.rime, 'flypy.schema.yaml')
    if os.path.isfile(schema_path):
        with open(schema_path, encoding='utf-8') as fh:
            m = re.search(r'^\s*version:\s*"?([^"\n]+)"?\s*$', fh.read(), re.M)
            if m:
                version = m.group(1).strip()

    header = ['# Rime dictionary', '# encoding: utf-8', '---',
              'name: flypy']
    if version:
        header.append(f'version: "{version}"')
    header += ['sort: original', '...', '']

    with open(os.path.join(args.out, 'flypy.dict.yaml'), 'w', encoding='utf-8') as fh:
        fh.write('\n'.join(header + [f'{t}\t{c}' for t, c in out_rows]) + '\n')

    # ---------- 写 flypy_sys.txt ----------
    sys_rows = rows_by_src['flypy_sys']
    sys_keep = [(t, c) for t, c in sys_rows
                if not (len(c) == 4 and c in handled_codes)]
    with open(os.path.join(args.out, 'flypy_sys.txt'), 'w', encoding='utf-8') as fh:
        fh.write('\n'.join(f'{t}\t{c}' for t, c in sys_keep) + '\n')

    # ---------- 给 verify 用的 4 码清单 ----------
    all_codes = sorted({c for c in src if len(c) == 4 and re.fullmatch(r"[a-z']+", c)})
    with open(os.path.join(args.out, 'codes4.txt'), 'w', encoding='utf-8') as fh:
        fh.write('\n'.join(all_codes) + '\n')

    # ---------- 报告 ----------
    total4 = len(four)
    log('')
    log(f'4 码总数            {total4}')
    log(f'  单条（本来就唯一） {total4 - len(handled) - len(skipped_nosep) - len(skipped_nochar) - len(skipped_apos)}')
    log(f'  裁决为唯一单字     {len(handled)}')
    log(f'  跳过·无单字        {len(skipped_nochar)}')
    log(f'  跳过·符号/emoji    {len(skipped_nosep)}')
    if skipped_apos:
        log(f"  跳过·xxx'          {len(skipped_apos)}")
    log(f'输家               {len(losers)}（降级到 3 码 {demoted} 条）')
    log(f'赢家来自外部表     {added_winner} 条（已补进主词库）')
    log(f'补全表独占的四码   {rescued} 条（已搬进主词库，避免停用补全表后变成空码）')
    log(f'dict 条目          {len(out_rows)}')
    log(f'sys 条目           {len(sys_rows)} → {len(sys_keep)}')
    log(f'输出目录           {os.path.abspath(args.out)}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
