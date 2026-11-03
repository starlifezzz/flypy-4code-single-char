# 机制：为什么是重建词库，而不是改 bin

## 1. `build/*.bin` 是编译缓存，不是数据源

Rime 的目录结构里有两类东西：

```
~/.local/share/fcitx5/rime/
├── flypy.schema.yaml        # 方案：引擎、翻译器、自动上屏规则
├── flypy_sys.txt            # 符号表 / 二重简码（文本）
├── flypy_full.txt           # 「全码字」补全表（文本，官方默认叫 flypy_full全码字.txt）
├── flypy.dict.yaml          # 主词库（文本）—— 官方不给你这个
└── build/
    └── flypy.table.bin      # 主词库的编译产物 —— 官方只给你这个
```

`flypy.table.bin` 是 `flypy.dict.yaml` 经过 `rime_deployer` 编译后的二进制索引（`*.prism.bin` 是码表索引，`*.reverse.bin` 是反查索引，同一批产物）。

**部署器的工作方式：**

1. 用户目录里存在 `flypy.dict.yaml` → 编译它，写进 `build/flypy.table.bin`
2. 用户目录里不存在 → 保留现有 bin，只打一条 `E ... flypy.dict.yaml does not exist`，退出码仍是 0

所以「和官方 bin 共存」是做不到的：**只要 yaml 在，bin 每次部署都会被覆盖**。这也是为什么本项目的做法必须包含「反编译官方 bin 作为初始数据」这一步。

## 2. 实测时间戳

```
flypy.dict.yaml        18:16:23   ← 裁决后的词库落进用户目录
build/flypy.table.bin  18:16:47   ← 24 秒后，部署器重新编译
```

bin 的 md5 也随之变化（`fe6192a8…` → `1ddf03b5…`），条目数 157,452 → 159,660。

反编译两份 bin 可以逐条对照：

```
# 官方 bin
表面    bnmm
骉      bnm'

# 裁决后
表面    bnm
骉      bnmm
```

## 3. 自动上屏的唯一条件

librime 1.17.0 `src/rime/gear/speller.cc:162-168`：

```cpp
if (seg.menu->Prepare(2) == 1) {          // 准备两条，实际只有一条
  // ... commit 这一条
}
```

也就是说：**菜单必须只剩 1 条候选**，才会自动上屏。

`schema.yaml` 里的 `auto_select_pattern: ^;.$|^\w{4}$` 只决定「哪些输入允许自动上屏」，它**不能**绕过唯一性检查。所以想靠调正则、调 `initial_quality`、调权重来「让某一条赢」，只能改变顺序，不能把 2 条变成 1 条 —— 除非真的删掉一条。

这也是本项目唯一可行的路线：**让四码位置上只剩一条数据**。

## 4. 为什么输家是「降级到三码」而不是删除

- 删了就真打不出了：实测 2,425 条离开四码的条目里，0 条彻底消失（每个字都还有别的码），但**那个四码会变成空码**
- 降级后击键数不变：三码首选 = 空格，次选 = `;`（schema 里 `semicolon → 2`），仍然是四下
- 不动三码原有顺序，只往末尾追加

实测：挪走的 2,425 条里 1,206 条（76% 的词）排在三码前两位。

另有一条隐藏坑：**只由补全表提供的「单候选四码」**（14 个，如 `vyav → 屯`）在停用补全表后会变成空码。`flypy4.py` 会把它们搬进主词库，避免这个缺口。

## 5. 官方词库更新后怎么办

`flypy.table.bin` 换成新版 → 重跑一次 `tools/install.sh`（或 `flypy4.py`）。**不要**直接拷贝新 bin 进去指望生效：只要 `flypy.dict.yaml` 还在，新 bin 会被无视。

这也是本项目最大的长期成本，写在 README 的「已知局限」里。
