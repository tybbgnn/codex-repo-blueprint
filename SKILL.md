---
name: codex-repo-blueprint
description: 给定 definitions 行、hash、canonical_path 或批量清单，该 skill 解析可执行 Rust MIR body，并从 Rust 源码、MIR control flow 与 basic block 事实自下而上生成可校验的 HTML blueprint，用于控制流拆解、分层文档和 white-box replication；不适用于只读源码问答或不需要交付蓝图的代码解释。
---

# Codex Repo Blueprint

从完整 MIR 事实与 Rust 源码出发，自下而上构建可核验的 0/1/1.5/2/3/4 层文档，并用冻结渲染器交付。

## 输入

用户可以给出以下任一身份：

- `definitions.json` 中的一行。
- `def_path_hash`。
- `identity.canonical_path`。
- 包含多个身份的批量清单。

每个目标必须有可执行 MIR body。async 构造入口要先解析到真正执行体。

运行环境需要：

- Python 3.9 或更新（脚本使用 `Path.is_relative_to`），`python3` 在 `PATH` 中。
- Node.js 18 或更新，`node` 在 `PATH` 中。
- S7/S8 需要 Playwright 及可用的 Chromium/Chrome；`PLAYWRIGHT_PATH` 必须指向 Playwright module，`BROWSER_PATH` 可选地指向浏览器可执行文件。
- `DEFINITIONS`：definitions 总表路径。
- `MIR_BODIES`：全量 MIR bodies 路径。
- `SOURCE_WORKSPACE`：Rust 源码工作区根。
- `OUTPUT_ROOT`：用户指定的输出根目录；必须在请求中提供；缺失则以 failed 结束并列出缺失参数。
- `INPUTS`：当前 body 的已声明输入与 Agent 账本。
- `OUTPUT`：当前 body 的隔离输出目录。

脚本还会设置 `TMPDIR`、`BLUEPRINT_SCRATCH_ROOT`、`PYTHONPATH`、`NODE_OPTIONS` 和 `PYTHONDONTWRITEBYTECODE`；这些是内部运行参数，Agent 不要伪造。

随 skill 携带：

- `resources/rules.json`：方法规则和机械检查定义。
- `scripts/`：确定性流水线、生成器和独立检查器。
- `references/`：按需读取的方法与合同。
- `assets/renderer/`：渲染 schema 与页面资产。
- `assets/frozen-renderers/`：经 SHA 锁定的静态文件。

## 运行原则

- 语义分析只读 Rust 源码、MIR、方法规则和本次 OUTPUT 产物。
- 不读归档、其他 body 的产物或旧基线来推理新 body。
- Agent 只写语义账本；机械事实、派生字段和最终 JSON 由脚本生成。
- 每句中文结论必须能指回 BB、原边、terminator 或源码行。
- BB 全覆盖，每个 BB 有且只有一个直属容器。
- 自下而上推理，不用节点数、调用数、BB 区间或历史答案决定边界。

## 九步流程

每一步都先 extract，再 validate，最后 build；账本开写前先读表中文件。

| 步骤 | Agent 写入 | 写前必读 | 门禁 |
|---|---|---|---|
| S0 解析与提取 | 无 | [stage-guide](references/stage-guide.md) S0、[layers-and-contracts](references/layers-and-contracts.md) | request 经 resolve→extract；commit、owner、pins、SHA 一致 |
| S1 事实提取 | 无 | [stage-guide](references/stage-guide.md) S1 | BB/原边全覆盖，无悬空目标 |
| S2 自下而上建层 | `stage2.json`、`summaries.json` | [ENGLISH-TERMS](references/ENGLISH-TERMS.md) + [stage-guide S2](references/stage-guide.md#s2-自下而上建层) + [granularity](references/granularity.md) + [s2-authoring](references/s2-authoring.md) + [ledger-templates](references/ledger-templates.md) + [source-ranges](references/source-ranges.md) | 归属唯一，层与父子关系合法，证据可解析 |
| S3 五维验收 | `stage3.json`、`review-narrative.md` | [acceptance](references/acceptance.md) + [display-validation](references/display-validation.md) | validate + build 全过自动锁定，接着 S4 |
| S4 语义关系与控件 | `edges.json`、`stage4.json` | [ledger-templates 控件决策表](references/ledger-templates.md#s4-控件决策表) + [display-principles](references/display-principles.md) | kind 词表合法，members 指向真实原边，loop 成员为事实派生的最小连续区间，环内出口逐路径证明 |
| S5 外部交互 | `stage5.json`、`endpoint-ledger.json` | [ledger-templates](references/ledger-templates.md) + [display-validation](references/display-validation.md) S5 + [stage-guide](references/stage-guide.md) S5 | endpoint 唯一解析，主 body 可执行，消息成对；check_model双向核对S2去向与真实endpoint/消息 |
| S6 三路生成 | 无；缺语义则回前阶段 | [ENGLISH-TERMS](references/ENGLISH-TERMS.md) + [ledger-templates](references/ledger-templates.md) + [source-ranges](references/source-ranges.md) + [display-validation](references/display-validation.md) S6 | 两次生成字节一致，引用闭合 |
| S7 验收 | `ledgers/stage7-review.json` 审阅结论 | [acceptance](references/acceptance.md) + [display-validation](references/display-validation.md) S7 + [rule-index](references/rule-index.md) | 机器检查与 agent 决定全过，接着 S8 |
| S8 交付 | 无 | [stage-guide](references/stage-guide.md) S8 | S7 全过，发布字节与锁定 SHA 一致 |

### 建议的逐步调用

表中的 `extract|validate|build` 表示三次独立命令，不是 shell 管道。例如 S2：

```bash
python3 -B scripts/blueprint.py S2 extract --inputs INPUTS --out OUTPUT
python3 -B scripts/blueprint.py S2 validate --inputs INPUTS --out OUTPUT
python3 -B scripts/blueprint.py S2 build --inputs INPUTS --out OUTPUT
```

开始下一阶段前，确认当前 build 返回的 `output_closure.passed` 为 true。S7 环境项未运行时也必须写出验收报告，补跑前不进入 S8 发布。

## 可复制的进度检查单

- [ ] S0：无 Agent 账本→validate 通过→build 通过→`output_closure.passed=true`
- [ ] S1：无 Agent 账本→validate 通过→build 通过→`output_closure.passed=true`
- [ ] S2：`stage2.json` + `summaries.json`→validate 通过→build 通过→`output_closure.passed=true`
- [ ] S3：`stage3.json` + `review-narrative.md`→validate 通过→build 通过→`output_closure.passed=true`→继续下一阶段
- [ ] S4：`edges.json` + `stage4.json`→validate 通过→build 通过→`output_closure.passed=true`
- [ ] S5：`stage5.json` + `endpoint-ledger.json`→validate 通过→build 通过→`output_closure.passed=true`
- [ ] S6：无 Agent 账本→validate 通过→build 通过→`output_closure.passed=true`
- [ ] S7：`ledgers/stage7-review.json` 审阅结论→validate 通过→build 通过→`output_closure.passed=true`→继续下一阶段
- [ ] S8：无 Agent 账本→validate 通过→build 通过→`output_closure.passed=true`

## 失败处理

读 `work/stageN/failure.json` 和受阻时的 `work/stage7/blocked-report.md`，按 [failure-classes](references/failure-classes.json) 分类；细节见 [stage-guide §失败处理](references/stage-guide.md#失败处理)。

失败先按 [运行恢复](references/run-recovery.md) 分类：账本错改账本并重验；环境缺失记“未运行＋原因＋补跑命令”，继续其他检查并生成验收报告；有证据的 skill 机制 bug 只在本次 OUTPUT/run-fixes 修正和登记偏离，再跑全部原检查。保留全部原则、阈值和白名单。无法保持规则解决时以 failed 结束，记录原因与证据。

S3 validate + build 通过即自动锁定基线并继续 S4。S7 每项审阅必须由 agent 有证据地决定 pass/fail；仅写法提示记 warning。机器检查全部通过直接进入 S8 交付；失败或未运行最终记 failed，记录原因和证据后结束。

S2/S6 写账本或修订展示文案前：节点名称、条件、结果与边标签中，来自源码的函数、类型、字段、变量、枚举值、模块以及 session、sampling、history、hook、token 等术语大致保留英文原文并放入反引号；连接语用中文。这是写作规则，不增加机器检查。

S7 唯一审阅输入位置是 `INPUTS/ledgers/stage7-review.json`，复制至 `work/stage7/agent-review.json` 后只读。格式及关闭证据见 [ledger-templates](references/ledger-templates.md#s7-agent-审阅)。

## 账本边界

- S2：`stage2.json` 写 ROOT、phase、goal、action、BB组、selection 和 granularity；BB 叶与 `basic_block_order` 由脚本派生。`summaries.json` 只写有证据的阅读摘要。
- S3：`stage3.json` 逐节点写 `accurate_work`、`flow_readable`、`useful_expansion`、`semantic_completeness`、`bidirectional_evidence`；`review-narrative.md` 说明 partial/wrong 与返工边界。
- S4：`edges.json` 只写有原边证据的语义关系；`stage4.json` 写 controls、readingScopes、decisions 和 execution 投影。
- S5：`stage5.json` 写外部交互、目的投影、segments 和 clauses；`bindingRef` 必须指向真实 Call。`endpoint-ledger.json` 只写 `canonical_path` selector 与 endpoint kind；实际实体由调用处 MIR 身份和可调用种类约束。

## 参考文件路由

按阶段必读的 agent 参考：[ENGLISH-TERMS](references/ENGLISH-TERMS.md)、[acceptance](references/acceptance.md)、[display-principles](references/display-principles.md)、[display-validation](references/display-validation.md)、[granularity](references/granularity.md)、[layers-and-contracts](references/layers-and-contracts.md)、[ledger-templates](references/ledger-templates.md)、[source-ranges](references/source-ranges.md)、[stage-guide](references/stage-guide.md)。

主合同：[ledger-schema.json](references/ledger-schema.json) 与 [stage-io.json](references/stage-io.json) 的字段/路径为准；[input-manifest.json](references/input-manifest.json)、[canonical-schema.json](references/canonical-schema.json)、[output-index.schema.json](references/output-index.schema.json)、[package-runtime.json](references/package-runtime.json)、[layer-contract.json](references/layer-contract.json) 由脚本消费或校验。

生成/检查索引：[s2-authoring.md](references/s2-authoring.md) 是 `generate_stage2_contracts.py` 生成的 S2 步骤；[rule-index.md](references/rule-index.md) 供报错 key 反查。[layer-contract.md](references/layer-contract.md) 与阶段合同 [S0](references/contracts/S0.json)、[S1](references/contracts/S1.json)、[S2](references/contracts/S2.json)、[S3](references/contracts/S3.json)、[S4](references/contracts/S4.json)、[S5](references/contracts/S5.json)、[S6](references/contracts/S6.json)、[S7](references/contracts/S7.json)、[S8](references/contracts/S8.json) 由脚本读取，字段以此为准，Agent 一般无需通读。

## 禁止事项

形状、引用闭合、覆盖、控件唯一性、回归、schema 和浏览器约束由各阶段 validate、独立检查器与 [rule-index](references/rule-index.md) 所列规则拦截；不在这里抄写检查器清单。

- 不为某个 body 写分支、常量、ID、预期答案或特判，因为新 body 必须从本次证据重建语义。
- 不用旧产物、历史基线、数量或比例代替推理，因为它们不证明当前边界。
- 不在转换器、脚本或渲染器写死中文文案，因为语义必须留在可审查账本。
- loop 成员从 MIR 真实循环动作推导最小连续阅读区间；额外动作必须证明不能回入口且只到 commonAfter/认证终点。进入这些环内出口用 branch，loop-exit 只指向范围外的 commonAfter/认证终点；见 [stage-guide](references/stage-guide.md)。
- 不复制跨层业务消息或同一 invocation，因为三个层必须引用同一业务成员。
- 不用空控件、同义改名或删真实路径“消除”重复，因为重复审计要修的是语义归属。
- 不把未解析 evidence、未关闭 review 或 `execution.inconclusive` 当作通过，因为缺证据不等于反证成立。

## 完成条件

只有在以下条件全部成立时，才能宣称交付完成：

- 从 S0 到 S8 的必需 build 成功。
- BB、原边、调用、语义边和外部交互引用闭合。
- 三份渲染 JSON 在同一输入下两次生成逐字节一致。
- 原则、源证据、重复、schema、回归和浏览器检查全部关闭失败与 review。
- S3 基线自动锁定；S7 agent 审阅已用当前证据关闭。
- 发布的冻结资产字节与 renderer lock 声明的 SHA 一致。


### 统一元素去向与本地函数

调用、闭包/coroutine 的去向与 MIR 理由只按 [信息保持规则](references/s2-authoring.md#信息保持规则唯一选择定义) 推导；技术证明、BB归属和消息覆盖由统一模型检查，不另写本地函数折叠清单。
