# 股票分析应用

这个项目会把本地招商证券自选股列表转换成一份可推送到飞书的分析结果，处理链路如下：

1. 提取自选股
2. 拉取历史行情
3. 计算技术指标
4. 调用 Codex / OpenAI 做个股分析
5. 按推荐优先级排序
6. 通过飞书机器人推送结果

## 当前实现

第一版已经打通完整流水线，并把“自选股提取”设计成可替换适配器：

- `csv`：从本地 `data/watchlist.csv` 读取
- `json`：从本地 `data/watchlist.json` 读取
- `manual`：从环境变量 `MANUAL_SYMBOLS` 读取
- `clipboard`：读取你刚从招商证券复制到系统剪贴板里的列表
- `csc_app`：自动连接本地招商证券客户端并抓取自选股
- `csc_files`：从招商证券安装目录或数据目录中的本地自选股文件读取

行情数据源同样可切换：

- `eastmoney`：直接拉取 A 股日线
- `csv`：从本地 `data/history/<symbol>.csv` 读取

这意味着你现在可以先手工导出或维护一份自选股文件，先把分析和推送跑起来。后续如果你希望直接从本地“招商证券”桌面 App 自动提取，我可以继续帮你补一个 Windows UI 自动化适配器。

## 安装

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -e .
```

## 配置

1. 复制 `.env.example` 为 `.env`
2. 填好：

- `OPENAI_API_KEY`
- `FEISHU_SEND_MODE`
- `FEISHU_APP_ID`
- `FEISHU_APP_SECRET`
- `FEISHU_RECEIVE_ID`
- `WATCHLIST_SOURCE`
- `WATCHLIST_FILE`
- `MARKET_DATA_SOURCE`

如果你暂时还没配好 OpenAI 或飞书，也可以先把：

- `ENABLE_LLM=false`
- `SEND_FEISHU=false`

这样应用会仅根据技术指标完成排序，并把结果写到本地报告文件。

如果你想自动抓取招商证券客户端里的自选股，建议这样配置：

- `WATCHLIST_SOURCE=csc_app`
- `BROKER_WINDOW_TITLE=招商证券`
- `WATCHLIST_TAB_TEXT=自选`

默认会先尝试 UI 自动抓取，再回退为模拟复制。

如果你更希望走本地文件方式，建议这样配置：

- `WATCHLIST_SOURCE=csc_files`
- `BROKER_DATA_DIR=C:\你的\招商证券\安装目录或用户数据目录`

程序会递归扫描常见的 `*.blk`、`*.ebk`、`*.txt`、`*.csv`、`*.ini`、`*.dat` 文件，并优先选择能解析出最多股票代码的那一份。

## 自选股文件格式

`data/watchlist.csv`

```csv
symbol,name
600519,贵州茅台
000001,平安银行
```

或 `data/watchlist.json`

```json
[
  {"symbol": "600519", "name": "贵州茅台"},
  {"symbol": "000001", "name": "平安银行"}
]
```

如果 `WATCHLIST_SOURCE=clipboard`，可以先在招商证券里复制自选股列表，然后直接运行命令。程序会自动从剪贴板里提取六位股票代码，并尽量保留同一行里的股票名称。

## 本地历史行情格式

如果 `MARKET_DATA_SOURCE=csv`，请准备：

`data/history/600519.csv`

```csv
date,open,close,high,low,volume
2026-03-10,1450.1,1461.0,1468.0,1443.2,321456
2026-03-11,1461.0,1458.6,1465.0,1450.0,298765
```

## 运行

```bash
python -m stock_analysis
```

运行后会在 `output/latest_report.md` 生成一份最新分析报告。

如果使用飞书应用给指定用户发消息，推荐使用：

```env
FEISHU_SEND_MODE=app
FEISHU_RECEIVE_ID_TYPE=open_id
FEISHU_RECEIVE_ID=<目标用户的 open_id>
SEND_FEISHU=true
```

如果你只有手机号，也可以这样配：

```env
FEISHU_SEND_MODE=app
FEISHU_RECEIVE_ID_TYPE=mobile
FEISHU_RECEIVE_ID=13922200297
SEND_FEISHU=true
```

程序会先通过飞书通讯录接口把手机号解析成用户标识，再发送消息。

如果你想把结果发到飞书群，直接这样配置：

```env
FEISHU_SEND_MODE=app
FEISHU_RECEIVE_ID_TYPE=chat_id
FEISHU_RECEIVE_ID=<目标群的 chat_id>
SEND_FEISHU=true
```

当前发送逻辑对 `chat_id` 和单个用户共用一套接口，所以切到群聊不需要改代码，只需要替换接收对象。

如果开启 `ENABLE_LLM=true`，当前版本会按 100 分制股票评分模型输出：

- 综合评分
- 分项得分
- 评级
- 一句话结论
- 核心优点
- 核心风险
- 后续跟踪指标
- 明确操作建议

## 无 API Key 的 Codex 工作流

如果你不使用 OpenAI API Key，而是希望直接在 Codex 里完成模型分析，可以这样跑：

1. 先生成分析素材：

```bash
python -m stock_analysis.prepare
```

它会输出：

- `output/codex_analysis_input.json`
- `output/codex_analysis_prompt.md`

2. 在 Codex 中读取这份 JSON，让 Codex 按你的 100 分模板生成正式报告
3. 把正式报告保存为 `output/codex_scored_report.md`
4. 如需把报告摘要发飞书，再运行：

```bash
python -m stock_analysis.send_report
```

## UI 排查

如果招商证券版本和默认控件定位不一致，可以先打开客户端，再运行：

```bash
python -m stock_analysis.inspect_ui
```

它会打印匹配窗口下的控件树，方便继续微调窗口标题或自选页关键字。

## 排序逻辑

最终优先级分数由三部分组成：

- 趋势强度
- 动量与超买超卖状态
- LLM 给出的投资关注分数

你可以在 `src/stock_analysis/ranking.py` 里继续调整权重。

## 下一步建议

如果你想把“招商证券”桌面 App 里的自选股自动提取出来，下一步最适合做的是二选一：

1. 做一个 Windows UI 自动化适配器，直接从应用窗口抓取自选股
2. 做一个半自动桥接器，从招商证券里复制列表后自动读取剪贴板

我已经把项目结构拆好了，后面继续加这块不会影响现有分析链路。
