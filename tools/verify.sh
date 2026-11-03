#!/usr/bin/env bash
# 编译并运行 verify.c：对一批编码逐键回放，统计四码没直接上屏的数量
set -euo pipefail

rime=""
codes=""
shared=""

while [ $# -gt 0 ]; do
  case "$1" in
    --rime)   rime=${2:?}; shift 2 ;;
    --codes)  codes=${2:?}; shift 2 ;;
    --shared) shared=${2:?}; shift 2 ;;
    *) echo "未知参数: $1" >&2; exit 2 ;;
  esac
done

[ -n "$rime" ]  || { echo "缺少 --rime <Rime 用户目录>" >&2; exit 2; }
[ -f "$codes" ] || { echo "找不到编码清单 $codes" >&2; exit 2; }
[ -d "$rime" ]  || { echo "找不到目录 $rime" >&2; exit 2; }
shared=${shared:-$rime}

here=$(cd "$(dirname "$0")" && pwd)
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT

cc=${CC:-gcc}
if ! command -v "$cc" >/dev/null 2>&1; then
  if command -v nix >/dev/null 2>&1; then
    compile() { nix shell nixpkgs#gcc --command gcc "$@"; }
  else
    echo "找不到 C 编译器（设 CC=... 或安装 gcc）" >&2
    exit 2
  fi
else
  compile() { "$cc" "$@"; }
fi
flags=()

if command -v pkg-config >/dev/null 2>&1 && pkg-config --exists rime 2>/dev/null; then
  read -r -a flags <<<"$(pkg-config --cflags --libs rime)"
else
  lib=${LIBRIME:-}
  if [ -z "$lib" ] && command -v nix >/dev/null 2>&1; then
    lib=$(nix build --no-link --print-out-paths nixpkgs#librime 2>/dev/null | head -1 || true)
  fi
  if [ -z "$lib" ] || [ ! -d "$lib/include" ]; then
    echo "找不到 librime 头文件。设 LIBRIME=/nix/store/...-librime-x.y.z 或装 librime 的 -dev 包。" >&2
    exit 2
  fi
  flags=(-I"$lib/include" -L"$lib/lib" -lrime -Wl,-rpath,"$lib/lib")
fi

compile -O2 -o "$tmp/verify" "$here/verify.c" "${flags[@]}"
"$tmp/verify" "$shared" "$rime" < "$codes"
