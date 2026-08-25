# minimax-tts-format（海螺语音文稿格式化）

把 Markdown / LaTeX / HTML / 代码 / 口语动作标注混合的文稿，转换为 MiniMax 海螺语音（speech-2.8 系列）可直接合成的朗读文本。

## 结构

```
minimax-tts-format/
├── SKILL.md                        # 主指令文件（给 AI 的执行指南）
├── VERSION
├── README.md
├── references/
│   ├── minimax-tts-spec.md         # 官方格式规范速查（停顿/语气词/发音替换/接口字段）
│   ├── conversion-rules.md         # 转换规则全集（决策树版）
│   └── examples.md                 # 8 个场景前后对照示例 + 常见错误对照
├── scripts/
│   └── convert_to_tts.py           # 零依赖 Python 转换器（Python 3.8+）
├── tests/
│   ├── test_input.md               # 综合测试（Markdown+LaTeX+代码+动作标注）
│   └── test_edge.md                # 边界测试（表格/HTML/emoji/任务列表）
└── dist/
    └── minimax-tts-format-lite.md  # 单文件轻量版（无脚本，纯规则）
```

## 脚本用法

```bash
# 文件输入
python3 convert_to_tts.py 文稿.md

# 管道输入
cat 文稿.md | python3 convert_to_tts.py

# 常用参数
python3 convert_to_tts.py 文稿.md --model speech-2.8-hd --pause-level light
python3 convert_to_tts.py 文稿.md --model speech-2.6-hd   # 语气词自动清除
python3 convert_to_tts.py 文稿.md --latex strip           # 公式不读，直接剥离
python3 convert_to_tts.py 文稿.md --code keep             # 保留并口语化代码
python3 convert_to_tts.py 文稿.md --json                  # 输出 JSON（含报告与警告）
python3 convert_to_tts.py 文稿.md -q                      # 只输出转换文本
```

## 核心能力

- **停顿**：`<#x#>`（0.01–99.99 秒，官方语法）；按段落/强调点/省略号智能插入；`（停顿 0.3 秒）` 自动转 `<#0.3#>`。
- **换气与语气词**：`(breath)` `(inhale)` `(sighs)` 等 19 个官方标签；`（笑）（叹气）（深呼吸）` 等中文动作标注自动映射；仅 speech-2.8 模型启用。
- **发音替换**：`(he2)` 拼音 / `(lɪv)` IPA / `(sung3)` 粤拼 原样保留。
- **公式口语化**：`\frac{a}{b}` → a 分之 b；`x^2` → x 的平方；希腊字母、运算符全覆盖。
- **格式剥离**：Markdown（标题/粗斜体/链接/列表/表格/引用/脚注）、HTML 标签、emoji、代码块。
- **校验**：停顿标记合法性、连续停顿合并、语气词白名单、残留语法检测、长度超限提醒。

## 验证

```bash
python3 scripts/convert_to_tts.py tests/test_input.md   # 综合用例
python3 scripts/convert_to_tts.py tests/test_edge.md    # 边界用例
```

## 依据

官方文档《同步语音合成 HTTP》：https://platform.minimaxi.com/docs/api-reference/speech-t2a-http

> 语气词标签仅 `speech-2.8-hd` / `speech-2.8-turbo` 支持；2.6 及以下模型请勿使用，脚本会自动清除。
