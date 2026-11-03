#!/usr/bin/env bash
# 把官方编译好的 flypy.table.bin 反编译成「词<TAB>码」文本
set -euo pipefail

if [ $# -ne 2 ]; then
  echo "usage: $0 <flypy.table.bin> <out.yaml>" >&2
  exit 2
fi

bin=$1
out=$2

[ -f "$bin" ] || { echo "找不到 $bin" >&2; exit 2; }

find_decompiler() {
  command -v rime_table_decompiler 2>/dev/null && return 0
  local p
  if command -v nix >/dev/null 2>&1; then
    for p in $(nix build --no-link --print-out-paths nixpkgs#librime 2>/dev/null); do
      if [ -x "$p/bin/rime_table_decompiler" ]; then
        echo "$p/bin/rime_table_decompiler"
        return 0
      fi
    done
  fi
  return 1
}

DEC=$(find_decompiler) || {
  echo "找不到 rime_table_decompiler。" >&2
  echo "安装方式：nix profile install nixpkgs#librime  （或发行版的 librime 包）" >&2
  exit 2
}

"$DEC" "$bin" "$out"
