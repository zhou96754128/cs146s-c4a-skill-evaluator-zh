# Zhouruoying_C4A_项目自评

**挑战**：C4A 技能提交自动评审（`ch-20260717031432-5jvqje`）
**提交身份**：2025105400318 ｜ **日期**：2026-10-06 ｜ **自评区间：84–93 / 100**

---

## 一、交付物清单（含体积与校验值）

| # | 文件 | 说明 | 体积 | sha256（前 16 位） |
| --- | --- | --- | --- | --- |
| 1 | `Zhouruoying_C4A_方案设计.md` | 问题定义、输入输出契约、评分口径、可复现性与已知局限 | 6590 B | `eb4011a0f3dfc560` |
| 2 | `Zhouruoying_C4A_skill-evaluator.skill` | 可执行技能包（SKILL.md + scripts/ + references/） | 见包内校验 | 见 §四 |
| 3 | `Zhouruoying_C4A_评审报告.md` | 真实样本评审报告（4 份在范围内 + 1 份范围外登记） | 14270 B | `03a43c51d99a2681` |
| 4 | `Zhouruoying_C4A_AI日志.md` | 逐轮留痕：采纳 / 修改 / 驳回及理由 | 4715 B | `6b8bd9d1329fe3f2` |
| 5 | `Zhouruoying_C4A_教学说明.md` | 面向使用者的上手指南 | 4737 B | `6aa99027e499bead` |
| 6 | `Zhouruoying_C4A_拿来说明.md` | 从 `wechat-doc-mapper` 拿了什么 / 改了什么 / 为什么（4 个拿来点、5 处改动、3 处有意不拿） | 5788 B | `e827a7a83f8b9131` |
| 7 | `Zhouruoying_C4A_demo运行记录.txt` | 真实执行记录（version / selfcheck / review 三段原文 + 退出码） | 5528 B | `91c796bf88a653e4` |
| 8 | `Zhouruoying_C4A_AAR.md` | 复盘（7 节） | 5666 B | `459806ae97840ead` |
| 9 | `Zhouruoying_C4A_评审详表.xlsx` | Excel 详表（挑战正文要求的输出格式）：总览 / 排名表 / 高频失分点 / 范围外登记 | 6708 B | `bf1f57d094439d4c` |

> CHALLENGE 声明的**六件必交物**（方案设计 / `skill-evaluator` 技能包 / 评审报告 / 教学说明 / AI日志 / 拿来说明）已**全部到位**；上表第 7、9 项与项目自评本身为补充材料。

## 二、可复现命令（评审可直接照抄）

```bash
cd Zhouruoying_C4A_skill-evaluator
python3 scripts/c4_evaluator.py version      # rc=0
python3 scripts/c4_evaluator.py selfcheck    # 19/19 PASS, VERDICT: GREEN, rc=0
python3 scripts/c4_evaluator.py review ../sample_corpus \
    --out 评审报告.md --dashboard logs/评审看板.json --history logs/评审历史.jsonl  # rc=0
```

- 环境：python3 3.12.13（3.8+ 均可），**零第三方依赖**（无 PyYAML 时自动降级到内置 YAML 子集读取器，并在 `version` 中如实打印）。
- 技能确定性：同一输入两次运行结果逐字节一致（自检用例 P18 即为此项断言）。
- 退出码约定：0 成功；1 用法/自检失败；2 输入目录无效；3 rubric 读取失败；4 rubric 与实现不同步；5 未发现提交。

## 三、按平台五维自评

| 维度 | 满分 | 自评 | 依据 |
| --- | --- | --- | --- |
| evaluatorQuality 评审质量 | 25 | 20–22 | rubric 口径与「必交物 + 4 判据」绑定成可执行检查项，16 条 rule 全部有实现、权重和为 1（自检 P19 断言）；每条扣分附命中原文；有 `capped_by` 说明等级被什么压住；不足：完整性只数件数，未校验单件内容量 |
| technicalExecution 技术执行 | 20 | 16–18 | 纯标准库实现、零依赖、跨 3.8+ 可跑；19 条用例（13 条负例）全绿；包结构/入口脚本/硬编码路径/越界条目均有防护，告警不吞；不足：入口脚本只做静态检查，未真跑 |
| artifactCompleteness 材料完整 | 15 | 14–15 | 六件必交物全部齐备（含补齐的 `拿来说明`），另附 demo 运行记录、Excel 详表与项目自评；命名符合 `姓名拼音_C4A_内容` 约定；报告与 demo 均可复现 |
| aiUsage AI 用量与判断 | 20 | 17–19 | AI 日志 5 轮，逐条记录采纳 5 / 修改 4 / 驳回 3 及理由，含失败痕迹（负例误判 → 修识别方式而非关检查）；不足：未保留完整对话存档，仅留结构化摘要 |
| reflectionQuality 反思深度 | 20 | 17–19 | AAR 7 节，含可复用的流程结论、四个具体改动点与三条下次要改的事；ΔR 归因区分了「比预期好/差」各自的原因 |

**合计自评 84–93**（较自筛前一版上调 2 分：补齐必交件 `拿来说明` 与挑战要求的 Excel 详表）。折扣仍主要来自两条已知局限（完整性只看件数、入口脚本未真跑），两条都已写进报告与 AAR 的改进项，不做掩饰。

## 四、包与盘一致性

技能包 `.skill` 由目录 `Zhouruoying_C4A_skill-evaluator/` 直接打包（排除 `__pycache__`）。提交前记录包文件 sha256，与盘上目录内容解包后逐文件比对；两者不一致时不得提交。校验记录写在仓库 `logs/` 下。

## 五、本次范围说明

评测样本包含 5 个技能包：作者本人 C4 / C4B 两个提交，以及课程材料中的三个示例包（无作者前缀者归入 `Unknown Author` 并标「（推断）」）。其中 `c2a-proposal-generator.skill` 挑战号不属 C4 家族，报告将其登记在「不在目标挑战范围内的提交」一节，只登记、不计入平均分——避免与其他挑战的提交混算。报告对每份提交都给出了凭证行号或片段，可直接复核。
