# 阶段指南

## 目录

- [通用调用](#通用调用)
- [S0–S8](#s0s8)
- [失败处理](#失败处理)

## 通用调用

```bash
python3 -B scripts/blueprint.py S{n} extract --inputs INPUTS --out OUTPUT
python3 -B scripts/blueprint.py S{n} validate --inputs INPUTS --out OUTPUT
python3 -B scripts/blueprint.py S{n} build --inputs INPUTS --out OUTPUT
```

Agent 只修改 `INPUTS/ledgers/` 下本阶段的语义账本。脚本、facts、work 产物和渲染器不是账本。

## S0–S8

### S0 解析与提取

- 输入二选一：prepared 模式直接提供 `raw-body.json`、`input-pins.json`、`rules.json`、`renderer-lock.json`、`source/`；request 模式提供含 `identity`、`definitions`、`mir_bodies`、`source_workspace`、`renderer_version` 的 `request.json`。
- request 模式按 `renderer_version` 从 frozen-renderers 清单唯一选择锁，不按 body 选择；并暂存 definitions 引用及从 definitions 通用抽取的 `facts/definitions-index.json`，因此 S0 文件集合覆盖 prepared 模式。
- request 模式先运行冻结算法的 `resolve_bodies.py`，再把唯一 resolved item 交给冻结算法的 `extract_body.py`；解析主 body 后，同样解析并抽取事件宏 `Fn::call` 引用且 definitions 唯一的闭包，按原始 MIR 字节写入 `pins/event-macro/` 并登记 `input-pins.json.event_macro_closures`。MIR 缺失项跳过并记入 S0 checkpoint 的 `missing_event_macro_closures`；prepared 模式保持复制路径。
- 输出：work 内的 raw/source/pins/rules、`stage0/input-sha256.json`、`raw-body.slice-sha256.txt`；request 模式另有 `stage0/resolved-row.json`。
- Agent 账本：无。
- 门禁：request 字段和路径有效；commit 由 extractor 对本地 workspace 元数据校验；raw owner 与 definition row 一致；MIR slice、附属 raw pin 和 owner 均一致。

### S1 事实提取

- 输入：`work/raw-body.json`。
- 输出：`facts/elements.json`（BB/Call/body/SwitchInt统一事实）、`facts/blocks.json`、`edges.json`、`call-bindings.json`、`terminal-events.json`、`async-states.json`、`summary.json`、`instrumentation-candidates.json`。最后一项是 `prove_instrumentation` 的只读结果，可能为 `null`。
- Agent 账本：无。
- 门禁：BB 与原边全覆盖，无悬空后继，调用 binding 可回到 Call terminator。

### S2 自下而上建层

- 输入：`facts/*`、`source/*`、`rules.json`。
- 输出：`stage2/hierarchy.json`、`selection.json`、`granularity.json`、`blocks-ledger.tsv`、`reading-summaries.json`。
- Agent 写：`ledgers/stage2.json`、`ledgers/summaries.json`。
- 核心字段：root、phase_order、nodes、selection、`granularity.goalContracts[]`、`technicalBlocks[]`、`memberGuards[]`。
- elements中的证明驱动instrumentation technicalBlocks、ROOT归属和空group移除；作者只写selection决定，禁止重复抄写instrumentation和basic_block_order。空action立即停止；纯日志不能留业务组。
- 门禁：BB 全覆盖且唯一归属；层与父子关系合法；中文字段有证据。

### S3 五维验收

- 输入：S2 hierarchy、facts/blocks、源码。
- 输出：`stage3/review.json`、`stage3/review.md`、`stage3/lock.json`。
- Agent 写：`ledgers/stage3.json`、`ledgers/review-narrative.md`。
- narrative 要求：review.md 直接复制作者手写的 ledgers/review-narrative.md；必须在 narrative 中列出 purposeGroups 一节，逐条展示 S2 的 projectionRef、object、purpose、condition（或 phase）、result 与 evidenceRefs，供 agent 在 S3 自动锁定前核对。
- 核心字段：`dimensions.accurate_work`、`flow_readable`、`useful_expansion`、`semantic_completeness`、`bidirectional_evidence`，以及 partial/wrong 原因。
- 门禁：五维全过；validate + build 全过即自动锁定并继续 S4。 S3通过后锁定S2/S3账本、hierarchy和review哈希；S8首先复核，变化后必须重做S3。

### S4 语义关系与控件

- 所有读者可见文案（label、name、summary、condition、skip、result、purpose、object 等）只用业务语言，不得出现 bbN、mN.N、call:N 标识；这些标识只写在 evidenceRefs、bypassEvidenceRefs、entryEvidenceRefs、basis 等证据字段中。结构引用字段保持其身份引用，不作为展示文案。
- controls、readingScopes（含 branches、commonAfter、arrivals）的文案在 S4 validate 提前检查；control.skip 与 memberGuards.skip 一致，须在 S2 源头修正。

- 输入：S2 hierarchy/granularity/reading summaries、facts/edges、facts/call-bindings。
- 输出：`stage4/edges.json`、`stage4/presentation.json`。
- Agent 写：`ledgers/edges.json`、`ledgers/stage4.json`；可选 execution label review。
- 核心字段：controls、readingScopes、decisions、branchRoles、returnContracts、executionNodes/Edges、memberGuards。
- 门禁：语义边 kind 只使用九种词表；members/transitions 引用真实原边；保存前按 member guard、action 身份和摘要规范化重复控件。
- loop 成员由 MIR 真实循环动作在阅读顺序中的最小连续区间派生；额外成员为环内出口，须证明不能回入口且所有路径只到 commonAfter 或已认证终点，否则失败并拆成精确范围。loop-exit 只指向 commonAfter 或已认证终点，进入环内出口动作使用普通 branch。

### S5 外部交互

- 输入：`facts/call-bindings.json`、definitions/MIR 身份信息、`ledgers/endpoint-ledger.json`。
- 输出：`stage5/resolved-endpoints.json`、`stage5/external.json`。
- Agent 写：`ledgers/stage5.json` 和只含 `canonical_path` selector 的 `ledgers/endpoint-ledger.json`；端点 kind 由事实派生：已 pin 的可用 MIR 为 body；无 MIR 的 Fn/AssocFn 为 declaration；其他情况拒绝并要求 S0 补 pin。作者 kind 仅作兼容提示。
- 核心字段：actors、messages、business_members、purposeProjections、segments、clauses；去向只在S2 selection.items。
- 内层体：check_model消费facts/elements.json和S2去向表，shown必须绑定真实endpoint与成对消息，技术去向必须有构造/消费BB证明；取消包装与业务callee不重复计数。
- 目的边界：每个 purposeProjection 的 id 必须等于某条 S2 granularity.purposeGroups.projectionRef；两者一一对应，双方均不得遗漏或重复。S5 validate 同时报告缺 group 的 projection id 和缺 projection 的 projectionRef。沿用 S3 自动锁定的 S2 目的边界；需要改变边界时回到 S2/S3 重新审阅。
- 门禁：endpoint-ledger 禁止 hash 字段和值，selector 必须唯一解析；`body` 端点必须由冻结 resolver 唯一解析到非空 MIR，`sourceNodeRef` 与 `bodyRef` 均回填完整 body key；`declaration` 端点只从 definitions 唯一解析，回填 kind/declarationRef/sourceNodeRef/implementationStatus，其中两个 Ref 均为完整声明 hash，删除 bodyRef，并按 ownership 校验 crate→module→declaration 祖先。主 body 必须是 `body`；作者身份与解析结果不一致则失败；`bindingRef` 存在；request/return 成对；pair 的 invocation、binding 和端点身份一致。

### S6 三路生成

- 输入：S2/S4/S5、facts、raw、pins、definitions index、source、inventory anchors。
- 输出：`renderer-input.json`、`reading-summaries.json`、`basic-block-details.json`、stage6 lineage/determinism。
- Agent 账本：无；缺语义时回 S2/S4/S5 补账本。
- 门禁：两次生成字节一致；引用可解析；转换器不生成中文文案。

### S7 验收

- 输入：三份 JSON、S2、raw/pins/definitions/source、renderer lock、agent 审阅证据。
- 输出：principles、independent-source、duplicates、contract、browser、agent-review、acceptance 报告。
- Agent 写：`ledgers/stage7-review.json`，唯一声明的 agent 审阅输入位置。
- 门禁：所有机械检查与 agent 决定通过；warning 单列，直接进入 S8。

### S8 交付

- 输入：三份 JSON、renderer lock、S7 acceptance。
- 输出：候选/交付站点、报告和 candidate 指针。
- Agent 账本：无。
- 门禁：S7 全过；发布的渲染器字节与锁定 SHA 一致；发布输入与已检查候选一致。

## 失败处理

先读 `OUTPUT/work/stageN/failure.json` 和原始证据，按 [run-recovery.md](run-recovery.md) 分类和恢复。账本错修账本；环境缺失记未运行并继续；有证据的机制 bug 在本次运行目录修正并登记偏离，再接受所有原始输出检查。无法在保持规则的前提下解决时以 failed 结束，写明原因与证据。

S7 受阻仍保存原 acceptance.json，生成 blocked-report.json/md；报告逐条给出 class、resolver、数量、最多 5 个原报告示例、rule-index key、action，environment 另给确切 rerun_command；另列 agent 审阅项数量与 warnings。
S8 拒绝发布，在预览目录新增 `未验收预览.md` 指向阻塞报告；candidate.json 标记 preview=true，failure.json 的 class=blocked，并以 1 退出。已有站点文件保持原字节。预览不是交付物。

无论哪类，给用户的内容都是：**预览路径 + blocked-report.md + 每项由谁决定**。
S3 validate + build 全过即锁定并继续；S7 通过即进入 S8；无法解决则以 failed 结束。

### S2 已证明 instrumentation 的自动归档

elements证明自动派生唯一granularity.technicalBlocks；已证BB直接归ROOT，空group移除并按CFG桥接组间顺序，空action停止。没有derived-technical-blocks副本；手抄instrumentation无效。

I/O文件与schema只在stage-io.json声明；contracts/S0–S8、canonical-schema与pipeline_reports输出闭包由它生成。S2/S5/S7均运行check_model；summary、resolved-endpoints等标为receipt，不能替代门禁。


非日志技术 BB 也只写分类、源码理由与依据（必要时operationReasons/terminatorReason）。哈希、操作kind/下标清单和terminator形状由elements.mirWitness推导，禁止手抄factSha256/operationKinds/operationProofs/terminatorProof；冻结检查仍用原始MIR逐项验证。S1还提供结构化drop/cleanup/unwind/stateDispatch候选属性；候选不自动改变业务归属。

### Erased future identity

For a local MIR call returning a trait-erased future, S1 reads the exact SHA-pinned constructor MIR slice, proves the returned coroutine identity through moves, Box::pin and unsizing, and proves the caller value flow to Future::poll. The resulting body element and call links are checked again by check_model. Handwritten lifecycle or boxed-future identity claims are not accepted as evidence. This proves value identity, not purity of constructor work.


## v22 按需 MIR 与运行恢复

S0 请求/准备两种模式都由 skill 自行生成 information pins；只为当前折叠判断按需打开项目被调函数，结论成立或遇循环即停止，无固定层数。S1 补齐闭包与 erased future 证明所需 pin；S2/S5/S7 独立核验精确切片与完整性。trait 方法先按具体接收者和 definitions 中 impl 实体解析；dyn/std/第三方声明照常折叠并列入报告。definitions 存在但容器无 body（含 body_available=true）单列范围缺失与补抽命令。容器有 body 却无 pin 为硬错误。

失败分类、环境项继续、运行目录内机制修正与偏离登记，以 [run-recovery](run-recovery.md) 为唯一操作定义。S3 自动锁定，S7 由 agent 有证据地完成审阅。

shown 的 trait 调用在 S1 元素中附 `resolvedCallee`（原 MIR callee 身份保留），实际 impl 定义与祖先一并纳入 definitions-index。S2/S5/S7 从原始 trait 调用重新解析校验该字段，S5 消息与 endpoint 约束使用核验后的 impl 身份；作者不手填此派生字段。
