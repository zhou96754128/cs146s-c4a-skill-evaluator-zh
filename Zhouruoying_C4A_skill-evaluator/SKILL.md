---
name: c4-skill-evaluator
description: 对 C4 家族（C4/C4A/C4B/C4C/C4D）的技能类提交做确定性自动评审：按冻结的 rubric 输出带证据的评分、等级、封顶原因与人工复核队列，可用于批改、自查、流水线门禁。
version: 1.0.0
---

# c4-skill-evaluator

C4 技能提交自动评审。给一个装着若干提交物的目录，输出**可复现、带证据**的评审报告：
每份提交拿到完整性分、质量分、综合分、等级（L1–L4），以及「哪一条规则命中/未命中、凭证是原文哪一段」。

## 一、安装 / 环境要求

- **Python 3.8+**（实测 3.12）。
- **零第三方依赖**：只用标准库。`references/c4_rubric.yaml` 优先用 PyYAML 解析；环境里没有 PyYAML 时自动降级为内置解析器，`version` 命令会如实打印当前引擎（`pyyaml` 或 `mini`），不会静默降级。
- 无需安装、无需联网、无需 API Key。把整个技能目录拷到任意位置即可运行。

## 二、快速开始

```bash
# 0. 看版本与当前 rubric 位置
python3 scripts/c4_evaluator.py version

# 1. 自查：19 条用例（正例 6 / 负例 13），全绿才说明环境与实现一致
python3 scripts/c4_evaluator.py selfcheck

# 2. 只采集，不评分（先看目录里都有什么）
python3 scripts/c4_evaluator.py scan <提交目录>

# 3. 正式评审：出 Markdown 报告
python3 scripts/c4_evaluator.py review <提交目录> --out 评审报告.md

# 4. 附带机器可读输出（流水线用）
python3 scripts/c4_evaluator.py review <提交目录> --out 评审报告.md --dashboard 看板.json --history 历史.jsonl

# 5. 换一份 rubric（默认用 references/c4_rubric.yaml）
python3 scripts/c4_evaluator.py review <提交目录> --out r.md --rubric 别的rubric.yaml
```

## 三、输入 / 输出格式

**输入**：一个目录（可含子目录）。识别两类文件：
- **技能包**：`.skill` / `.zip`。顶层只允许 `SKILL.md` + `scripts/` + `references/`；条目越界（如 `../evil.txt`）、非 zip 原名 `.skill`、超体积上限都会被拒绝并写入告警，不静默跳过。
- **文本物**：`.md` / `.txt` 等，直接读取计数。
识别不出作者时标 `Unknown Author`，识别不出挑战号时标 `unknown` 并进人工复核队列。

**输出**：
- `Markdown 评审报告`：总览（提交份数 / 平均分 / 等级分布 / 技能包数 / 总量）、逐份详情（每条规则命中与否 + 原文凭证）、**范围外登记表**（挑战号不在过滤范围内的提交只登记、不排名）、人工复核队列。
- `--dashboard` JSON：指标卡 + 各提交得分与等级，便于拼看板。
- `--history` JSONL：每次扫描追加一行，可看趋势。
- 退出码即结论：`0` 正常；`1` 用法错误或自检失败；`2` 目录无效；`3` rubric 读不了；`4` rubric 与实现不同步；`5` 目录里没有可评审提交。

## 四、评分口径（rubric v1.1）

**必交物五件**（各占完整性 1/5）：技能说明文档、可执行内容、Demo（截图 / 录屏 / 运行记录）、教学说明、AI 生成日志。

**质量四判据**（各 0.25）：可复用 / 可执行 / 可验证 / 输入输出明确。每条判据带 3–4 个检查项；命中 ≥2 判 ✅(1.0)、命中 1 判 ⚠️(0.5)、0 判 ❌(0.0)。

`综合分 = 0.4 × 完整性 + 0.6 × 质量`，等级阈值 **L1 ≥0.20 / L2 ≥0.45 / L3 ≥0.70 / L4 ≥0.85**。

**封顶与扣减**（防止「件数齐就给高分」）：缺必交物 → 判级封顶 L1；有技能说明但无 AI 日志 → 反思类维度封顶；AI 日志无迭代痕迹 → AI 用量维度封顶；有自检但全程无负例/异常用例 → 扣 1 个「可验证」命中项。封顶原因会写在报告里（`capped_by`），不隐藏。

## 五、边界与异常输入

- 空目录 → 退出码 5，报告写明「没有可评审提交」，不产生假分数。
- 损坏包 / 伪包 → 记为 `not_a_zip` 并继续处理其余提交，不中断整批。
- 混入其他挑战（如 C2A / C2G）的提交 → 移入第七节「范围外登记」，**不计入平均分与排名**，避免口径污染。
- 规则带语境豁免：文档在**描述**检测规则（出现「规则 / 词表 / 示例」等语境词）时，不判为「文档自身违规」。
- 全程确定性：同输入多次运行结果逐字节一致。

## 六、自定义

改 `references/c4_rubric.yaml` 即可调整：`selector.challenge_filter`（前缀家族语义，填 `C4` 时 C4/C4A/C4B/C4C/C4D 都在范围内）、`required_deliverables`（必交物与识别模式）、`quality_criteria`（判据与权重）、`red_flags`（封顶规则）、`level_thresholds`（等级线）。改完先跑 `selfcheck`：若 rubric 与实现不同步会返回退出码 4。

## 七、自检

```bash
python3 scripts/c4_evaluator.py selfcheck
```
覆盖：齐全样本、缺件、无 AI 日志、一次性 AI、硬编码绝对路径、无负例、无代码、IO 含糊、包结构越界、伪包、越界条目、空目录等。**全绿（VERDICT: GREEN，退出码 0）才算可用**。

自检夹具写到 `$C4A_SELFCHECK_DIR`；未设置时用**系统临时目录**下的 `c4a_selfcheck/`（每次运行重建），不会写进技能包目录，跑完不留痕。
