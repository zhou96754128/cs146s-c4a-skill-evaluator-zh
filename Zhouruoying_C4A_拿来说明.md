# Zhouruoying_C4A_拿来说明

**挑战**：C4A 技能提交自动评审（`ch-20260717031432-5jvqje`）

**拿来对象**：`_ref/wechat-doc-mapper/wechat-doc-mapper/`（`SKILL.md` 13156 字符 / sha256 `ff9d1ba659a5dfbf…`；`scripts/wechat_doc_mapper.py` 19870 B；`references/challenges.yaml` 6435 B）

**一句话结论**：借它的「交付包骨架 + 命名解析与作者兜底链 + 注册表驱动 + 缺口表格化」四件事，换掉它的内核（**归类 → 打分**），并把第三方依赖全部降为零。

---

## 一、拿了什么（4 处）

| # | 拿来的东西 | 在 wechat-doc-mapper 里的形态 | 在本技能里的落点 |
| --- | --- | --- | --- |
| 1 | 交付包结构约定 | `SKILL.md + scripts/ + references/`，配置集中在 `references/*.yaml` | 同构；本技能配置为 `references/c4_rubric.yaml`（16 条规则 + 权重） |
| 2 | 文件命名解析 | `<Author>_<ChallengeID>_<Part>.<ext>` 正则 | `scripts/c4_scan.py` 的姓名 / 挑战号解析，同一条正则语义 |
| 3 | 作者判定兜底链 | 父目录名 → 文档元数据 → 正文前几行 → `[Name]` 前缀，无法判定进人工队列 | 改为「文件名 → 上级子目录 → 包内 `SKILL.md` 元数据 → `Unknown Author`」，判定不了的一律在报告「采集告警」区登记，供人工复核 |
| 4 | 注册表 + 缺口表格化 | `references/challenges.yaml` 作为挑战注册表；输出 Markdown 表 + Excel gap 分析（top gaps 计数） | 挑战号**家族前缀过滤**（C4 → C4 / C4A / C4B / C4C / C4D）；看板 JSON 保留 `top_gaps` 计数与「缺失必交物」列 |

## 二、改了什么、为什么（5 处）

**1. 内核换掉：归类 → 打分。**
wechat-doc-mapper 回答的是「这份文件属于谁、属于哪个挑战」；C4A 要回答的是「这份提交值多少分、凭什么」。因此保留扫描 / 识别层，重写评分层：完整性 = 命中必交物件数 ÷ 5，质量 = `reusable` / `executable` / `verifiable` / `clear_io` 四条判据等权，综合分 = 0.4×完整性 + 0.6×质量。
*为什么*：挑战正文把评审拆成「必交物齐不齐」和「能不能复用、能不能跑」两类**可观察事实**；doc-mapper 的映射结果正好可以当输入，但不能当结论。

**2. 依赖降到零。**
wechat-doc-mapper 的 `SKILL.md` 声明 openpyxl / pypdf / python-pptx / pandas；本技能只用标准库，读 YAML 时优先 PyYAML，缺失则降级到内置 YAML 子集读取器，并在 `version` 输出里**如实打印**当前走的是哪条路径。
*为什么*：评审环境不可控，装包失败就等于技能不可用；「零依赖可跑」本身也是评审标准里「可复用性 15%」的直接得分项。

**3. 输出物替换：Excel → 看板 JSON + 历史 JSONL（另附 Excel 详表）。**
零依赖下无法直接生成 xlsx，所以本技能的**机器可读详表**是 `logs/评审看板.json`（含全部计数、排名、缺失项、高频失分点），逐次运行追加 `logs/评审历史.jsonl`，支持「同一批提交跨次对比」；表格化的 `top_gaps` 与 doc-mapper 的 gap 分析同思路。挑战正文要求的 Excel 详表另以 `Zhouruoying_C4A_评审详表.xlsx` 提供，**内容与看板 JSON 逐项对应**（差异只在显示精度，见该文件「总览」页说明）。
*为什么*：JSON 可被程序消费、可 diff、可入库；xlsx 只是给人看的皮。两者数字同源，避免「看板一个数、表里另一个数」。

**4. 每一分都要能回到原文。**
doc-mapper 只给「文件 → 挑战」的映射清单；本技能对每条 check_item 记录**规则编号**（rubric 16 条之一）与**命中片段**，报告里任一扣分点都能回原文核对，并附 `capped_by` 说明该等级是被哪一项压住的。
*为什么*：评审标准第一条是「评审准确性 30%」，拿不出凭证的分数等于没有分数。

**5. 退出码与范围隔离。**
doc-mapper 没有退出码语义；本技能约定六档退出码（0 成功 / 1 用法或自检失败 / 2 输入目录无效 / 3 rubric 读取失败 / 4 rubric 与实现不同步 / 5 未发现可评审提交），可直接接流水线门禁。另加挑战号家族过滤：范围外提交（如 C2A 的包）只登记、不计入平均分。
*为什么*：doc-mapper 是给人看的报告工具；C4A 要的是「自动评审」，必须能被别的程序判断成败。

## 三、没拿的部分（有意为之）

- **未复制任何一行代码**，只复用其结构约定与命名 / 兜底策略；可对照 `_ref/` 原文逐条核验。
- **未采用它的 LLM 可选增强路径**（starter 材料中提到的 Level 3 LLM 抽取）。本技能保持「同一输入、两次运行、逐字节一致」的确定性——自检用例 P18 即为此项断言。
- **未引入 openpyxl / pypdf 等依赖**，代价是放弃直接读 PDF / DOCX 元数据；因此作者兜底链止于「包内 `SKILL.md` 元数据 → `Unknown Author`」，不确定项**显式登记为告警而不是猜**。

## 四、核验入口（拿到就能自己验）

| 拿来点 | 怎么验 |
| --- | --- |
| 包结构约定 | `Zhouruoying_C4A_skill-evaluator/` 与 `_ref/…/wechat-doc-mapper/` 同构：一层目录 + `SKILL.md` + `scripts/` + `references/` |
| 命名解析与兜底链 | `python3 scripts/c4_evaluator.py selfcheck` → 19/19 PASS（含作者识别正负例） |
| 注册表 / 过滤 | `review ../sample_corpus` 的输出中，C2A 的包落在「范围外登记」一节而非排名表 |
| 缺口表格化 | `logs/评审看板.json` 的 `top_gaps` 字段；`Zhouruoying_C4A_评审详表.xlsx` 的「高频失分点」页 |
| 零依赖 | `python3 scripts/c4_evaluator.py version` 打印依赖探测结果与 Python 版本 |
