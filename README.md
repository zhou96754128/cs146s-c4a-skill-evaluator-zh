# Zhouruoying_C4A 技能提交自动评审 — c4-skill-evaluator

C4A 挑战（`ch-20260717031432-5jvqje`）交付仓库。

## 这是什么

`c4-skill-evaluator` 是一个**零依赖、确定性**的评审技能：给它一个装着若干技能类提交（含 `.skill` / `.zip`）的目录，它输出一份**每一分都能回到原文**的评审报告——必交物命中情况、四条质量判据（可复用 / 可执行 / 可验证 / 输入输出明确）的命中项与凭证、综合分、等级（L1–L4）、封顶原因，以及需要人工确认的复核队列。

它适合三种用法：**批改他人提交**、**提交前自查**、**流水线门禁**（拿退出码卡关）。

## 快速开始

```bash
# 1. 环境确认（需要 Python 3.8+，不需要任何第三方库）
cd Zhouruoying_C4A_skill-evaluator
python3 scripts/c4_evaluator.py version
# → c4-skill-evaluator 1.0.0 (challenge C4A / ch-20260717031432-5jvqje)
#    并打印当前 rubric 路径与 YAML 解析引擎（pyyaml 或内置 mini）

# 2. 技能自检：19 条用例（6 正 / 13 负）必须全绿
python3 scripts/c4_evaluator.py selfcheck
# → 19/19 PASS，VERDICT: GREEN，退出码 0

# 3. 采集（只看收上来什么，不评分）
python3 scripts/c4_evaluator.py scan ../sample_corpus

# 4. 正式评审
python3 scripts/c4_evaluator.py review ../sample_corpus \
    --out 评审报告.md --dashboard logs/评审看板.json --history logs/评审历史.jsonl
```

安装方式：把 `Zhouruoying_C4A_skill-evaluator/` 整个目录放进你的技能目录即可；或直接用打包好的 `Zhouruoying_C4A_skill-evaluator.skill`（ZIP 格式，包内为 `SKILL.md + scripts/ + references/`）。

## 评分口径（可改）

| 项 | 规则 |
| --- | --- |
| 综合分 | `0.4 × 完整性 + 0.6 × 质量` |
| 完整性 | 必交物五件（技能说明 / 可执行内容 / Demo / 教学说明 / AI 日志）命中数 ÷ 5 |
| 质量 | 四条判据各自命中检查项数：≥2 判 ✅(1.0)、1 判 ⚠️(0.5)、0 判 ❌(0.0)，再取均值 |
| 等级 | L1 ≥0.20 ／ L2 ≥0.45 ／ L3 ≥0.70 ／ L4 ≥0.85 |
| 封顶 | 缺必交物 → 材料维度低分；无 AI 日志 → 反思维度上限 5；AI 日志无迭代痕迹 → AI 用量上限 5；有负例/异常说明缺失 → 可验证性扣 1 项 |

口径写在 `Zhouruoying_C4A_skill-evaluator/references/c4_rubric.yaml`。改完**必须重跑 `selfcheck`**：rubric 与实现不同步时命令返回退出码 4 且不出报告，防止拿旧结论。

## 退出码（可直接做门禁）

`0` 成功 ｜ `1` 用法错误或自检失败 ｜ `2` 输入目录无效 ｜ `3` rubric 读取失败 ｜ `4` rubric 与实现不同步 ｜ `5` 未发现可评审的提交

## 仓库内容

| 路径 | 说明 |
| --- | --- |
| `Zhouruoying_C4A_skill-evaluator/` | 技能本体（SKILL.md、scripts/、references/） |
| `Zhouruoying_C4A_skill-evaluator.skill` | 技能包（ZIP），与上目录同源，`logs/包与盘一致性校验.txt` 记录逐文件 sha256 比对 |
| `Zhouruoying_C4A_方案设计.md` | 问题定义、输入输出契约、评分口径、可复现性、已知局限 |
| `Zhouruoying_C4A_评审报告.md` | 对真实样本语料（作者侧目录 `_corpus/wechat_c4`，与仓库 `sample_corpus/` 为同一批 5 个样本）的评审结果：4 份在范围内 + 1 份范围外只登记，平均综合分 0.60 |
| `Zhouruoying_C4A_demo运行记录.txt` | version / selfcheck / review 三段真实执行原文与退出码 |
| `Zhouruoying_C4A_教学说明.md` | 上手指南（四步跑通、报告解读、常见问题） |
| `Zhouruoying_C4A_AI日志.md` | 与 AI 协作逐轮留痕：采纳 5 / 修改 4 / 驳回 3 |
| `Zhouruoying_C4A_AAR.md` | 复盘 7 节，含 ΔR 归因 |
| `Zhouruoying_C4A_项目自评.md` | 交付物清单、可复现命令、五维自评区间 |
| `sample_corpus/` | 复现用样本（作者本人 C4 / C4B 提交 + 课程材料示例包） |
| `logs/` | 评审看板 JSON、评审历史 JSONL、仓库内复跑记录、包与盘一致性校验记录 |

## 可复现性说明

- 技能只用 Python 标准库；无网络、无 API Key、无环境变量依赖。
- **确定性**：同一目录两次评审结果逐字节一致（自检 P18 断言的正是这一点）。
- **仓库内复跑已留证**：`logs/评审复跑记录.md` 记录了在仓库内用 `../sample_corpus` 复跑的命令、退出码与完整输出，平均分、等级分布、排名与交付报告逐项一致。
- **路径与泛化**：技能本体**无本地路径依赖**——安装即用，不写死任何目录，可换任意语料目录。报告中出现的 `/Users/...` 抬头是当次运行的**运行痕迹**（扫描目录原文），不是依赖。
- 样本包内 `c2a-proposal-generator.skill` 的挑战号不属于 C4 家族，报告会把它登记在「不在目标挑战范围内的提交」一节，只登记、不参与排名与均分。

## 已知局限

1. 完整性只统计必交物件数，五件齐但内容空壳仍可拿满完整性分（由质量维度 0.6 权重制衡，但偏乐观）。
2. 作者归属依赖 `姓名拼音_挑战号_内容描述` 命名约定；不符约定的会进人工复核队列，不做自动猜测。
3. 入口脚本只做静态检查（存在、体积、可读），未在沙箱中真实执行。

以上三条已列入下一版改进项，与 `Zhouruoying_C4A_评审报告.md`、`Zhouruoying_C4A_AAR.md` 中的记载一致。
