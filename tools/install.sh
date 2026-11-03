#!/usr/bin/env bash
# 一键安装：备份 → 反编译官方 bin → 裁决 → 写回 → 摘掉 full 补全 → 关 emoji
set -euo pipefail

here=$(cd "$(dirname "$0")/.." && pwd)

RIME=${RIME_DIR:-$HOME/.local/share/fcitx5/rime}
BIN=""
LEVELS=""
EMOJI=off
DRY=0

while [ $# -gt 0 ]; do
  case "$1" in
    --rime)     RIME=${2:?}; shift 2 ;;
    --bin)      BIN=${2:?}; shift 2 ;;
    --levels)   LEVELS=${2:?}; shift 2 ;;
    --emoji)    EMOJI=${2:?}; shift 2 ;;
    --dry-run)  DRY=1; shift ;;
    -h|--help)
      sed -n '2,6p' "$0" | sed 's/^# \{0,1\}//'
      echo "用法: $0 [--rime DIR] [--bin 官方bin] [--levels 等级表.json] [--emoji on|off] [--dry-run]"
      exit 0 ;;
    *) echo "未知参数: $1" >&2; exit 2 ;;
  esac
done

[ -d "$RIME" ] || { echo "找不到 Rime 用户目录: $RIME" >&2; exit 2; }
BIN=${BIN:-$RIME/build/flypy.table.bin}
[ -f "$BIN" ] || {
  echo "找不到 $BIN" >&2
  echo "官方包里的 bin 通常在 rime/build/flypy.table.bin，用 --bin 指定。" >&2
  exit 2
}
[ -f "$RIME/flypy_sys.txt" ] || { echo "$RIME 下没有 flypy_sys.txt，这不是一个 flypy 用户目录" >&2; exit 2; }

tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT

echo "==> 反编译 $BIN"
"$here/tools/decompile.sh" "$BIN" "$tmp/flypy.yaml"

echo "==> 裁决"
if [ -n "$LEVELS" ]; then
  python3 "$here/flypy4.py" --decompiled "$tmp/flypy.yaml" --rime "$RIME" \
    --out "$tmp/out" --levels "$LEVELS"
else
  python3 "$here/flypy4.py" --decompiled "$tmp/flypy.yaml" --rime "$RIME" --out "$tmp/out"
fi

if [ "$DRY" = 1 ]; then
  echo "==> dry-run：产物在 $tmp/out（临时目录，随脚本退出删除）"
  cp -a "$tmp/out" ./out-dry-run
  echo "    已复制到 ./out-dry-run"
  exit 0
fi

BACKUP="$HOME/rime-backup-$(date +%Y%m%d-%H%M%S)"
echo "==> 备份 $RIME → $BACKUP"
cp -a "$RIME" "$BACKUP"

echo "==> 写入词库"
cp "$tmp/out/flypy.dict.yaml" "$RIME/flypy.dict.yaml"
cp "$tmp/out/flypy_sys.txt" "$RIME/flypy_sys.txt"

echo "==> 摘掉 schema 里的 custom_phraseQMZ"
python3 "$here/tools/patch-schema.py" "$RIME/flypy.schema.yaml"

echo "==> 停用全码字补全表"
shopt -s nullglob
for f in "$RIME"/flypy_full*.txt; do
  case "$f" in
    *.disabled) ;;
    *) mv "$f" "$f.disabled"; echo "    $(basename "$f") → $(basename "$f").disabled" ;;
  esac
done
shopt -u nullglob

echo "==> emoji 联想：$EMOJI"
python3 - "$RIME/flypy.custom.yaml" "$EMOJI" <<'PY'
import re, sys
path, mode = sys.argv[1], sys.argv[2]
try:
    text = open(path, encoding='utf-8').read()
except FileNotFoundError:
    print('    没有 flypy.custom.yaml —— 参考 examples/flypy.custom.yaml 手动添加')
    sys.exit(0)
if 'emoji_suggestion' not in text:
    print('    custom.yaml 里没有 emoji_suggestion —— 无需处理')
    sys.exit(0)
want = '0' if mode == 'off' else '1'
new = re.sub(r'(name:\s*emoji_suggestion\s*\n\s*reset:\s*)[01]', r'\g<1>' + want, text)
if new != text:
    open(path, 'w', encoding='utf-8').write(new)
    print(f'    reset: {want}')
else:
    print('    已是目标值')
PY

cat <<EOF

完成。备份：$BACKUP

下一步：托盘右键 → 部署（脚本不会替你部署），然后试：

  qrrw → 全      bnmm → 骉      aifu → 挨      yivv → 已

回滚：

  cp -a $BACKUP/. $RIME/

注意：只还原 bin 而不删 flypy.dict.yaml 是没用的，下次部署会再覆盖回去。
EOF
