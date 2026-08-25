# MiniMax 海螺语音 TTS 格式规范速查

> 来源：MiniMax 开放平台官方文档《同步语音合成 HTTP》（platform.minimaxi.com/docs/api-reference/speech-t2a-http，含备用域名 platform.minimax.io 英文版）。信息以官方文档最新版为准；本文件用于快速查阅。

## 接口

- 同步 HTTP：`POST https://api.minimaxi.com/v1/t2a_v2`（备用 `https://api-bj.minimaxi.com/v1/t2a_v2`）
- WebSocket：`wss://api.minimax.io/ws/v1/t2a_v2`
- 异步：`POST /v1/t2a_async_v2`（长文本，TXT 文件输入支持停顿标记）
- 认证：`Authorization: Bearer <API_KEY>`

## 请求字段（T2aV2Req）

| 字段 | 说明 |
| --- | --- |
| `model` | `speech-2.8-hd`、`speech-2.8-turbo`、`speech-2.6-hd/turbo`、`speech-02-hd/turbo`、`speech-01-hd/turbo` |
| `text` | 要合成的文本，**< 10000 字符**；> 3000 字符推荐流式 |
| `stream` | 是否流式，默认 false |
| `voice_setting` | `voice_id`、`speed`（语速，1 为基准）、`vol`、`pitch`、`emotion`（情绪） |
| `pronunciation_dict` | 词典级发音替换（全局，见下） |
| `language_boost` | 小语种/方言增强，如 `Chinese`、`Chinese,Yue`、`Japanese`；默认 null，可 `auto` |
| `audio_setting` | `sample_rate`、`bitrate`、`format`（mp3/pcm/flac）、`channel` |
| `subtitle_enable` / `subtitle_type` | 字幕；粒度 `sentence` / `word` / `word_streaming` |
| `output_format` | `url` 或 `hex`（默认 hex，非流式有效） |

## text 字段支持的标记（核心）

### 1. 段落切换

> 段落切换用换行符标记

多段文本用 `\n` 分隔即可，不要用停顿标记模拟分段。

### 2. 停顿控制 `<#x#>`

> 在文本中增加 `<#x#>` 标记，x 为停顿时长（单位：秒），范围 [0.01, 99.99]，最多保留两位小数。文本间隔时间需设置在两个可以语音发音的文本之间，不可连续使用多个停顿标记。

- 合法：`朋友们<#0.3#>今天聊个重要的话题`
- 非法：`<#0.3#><#0.5#>今天`（连续标记）、`今天<#0.3#>`（结尾无后续文本）

### 3. 行内发音替换（半角括号包裹）

> 将普通话拼音（带声调数字 1–5）或 IPA 音标或粤语拼音（带声调数字 1–6）用英文小括号包裹，可临时覆盖有问题的单词或者多音汉字的发音。

- 普通话：`"This is (he2)平, not (huo4)面."`
- IPA：`"The word live is pronounced (lɪv) as a verb and (laɪv) as an adjective."`
- 粤语：`"去街市買啲(sung3)。"`
- 注意：必须是**半角括号**，不要用全角。

### 4. 语气词标签（仅 speech-2.8-hd / speech-2.8-turbo）

完整白名单 19 个：

| 标签 | 含义 | 标签 | 含义 |
| --- | --- | --- | --- |
| `(laughs)` | 笑声 | `(chuckle)` | 轻笑 |
| `(coughs)` | 咳嗽 | `(clear-throat)` | 清嗓子 |
| `(groans)` | 呻吟 | `(breath)` | 正常换气 |
| `(pant)` | 喘气 | `(inhale)` | 吸气 |
| `(exhale)` | 呼气 | `(gasps)` | 倒吸气 |
| `(sniffs)` | 吸鼻子 | `(sighs)` | 叹气 |
| `(snorts)` | 喷鼻息 | `(burps)` | 打嗝 |
| `(lip-smacking)` | 咂嘴 | `(humming)` | 哼唱 |
| `(hissing)` | 嘶嘶声 | `(emm)` | 嗯 |
| `(sneezes)` | 喷嚏 | | |

官方示例：`今天是不是很开心呀(laughs)，当然了！`

### 5. 发音词典 pronunciation_dict

词典级替换，格式 `原文/替换`，其中替换可用括号拼音标注：

```json
{
  "pronunciation_dict": {
    "tone": [
      "处理/(chu3)(li3)",
      "危险/dangerous"
    ]
  }
}
```

适用于固定专有名词、多音字，比行内标注更适合 WebSocket/异步接口。

## 官方推荐的节奏参数

- `voice_setting.speed`：语速，1 为正常；1.1–1.3 常用于口播。
- 实测经验：speed 1.3 时**不加停顿标记效果最好**，自然语速已给足节奏；只有刻意强调时才补 `<#0.3#>`。

## 已知陷阱

1. 停顿标记与 `<词>` 形式冲突：不要用尖括号包裹普通词（会被当成格式或产生异常停顿）。
2. 流式场景中 `<#0.5#>` 可能被拆成多个 chunk（如 `<#0.` 与 `5#>` 分到两次），前端需要容忍不完整标记或延迟展示。
3. `(applause)` 等不在白名单的标签不保证生效，不要用。
4. 全角括号做发音标注无效，必须半角。
5. 异步接口直接传 text 时停顿标记行为未明确文档化；需要精确停顿请走 TXT 文件输入。

## 模型能力对照（摘要）

| 能力 | 2.8-hd/turbo | 2.6 | 02 | 01 |
| --- | --- | --- | --- | --- |
| 停顿 `<#x#>` | ✅ | ✅ | ✅ | ✅ |
| 行内发音替换 | ✅ | ✅ | ✅ | ✅ |
| 语气词标签 | ✅ | ❌ | ❌ | ❌ |
| 字幕 | ✅ | ✅ | ✅ | ✅ |
| language_boost 全语种 | ✅ | 部分 | 不含波斯/菲/泰米尔 | 同左 |
