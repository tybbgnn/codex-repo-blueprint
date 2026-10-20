# 划分粒度标准

## 目录

- [共享分类契约](#共享分类契约)
- [G1–G11](#g1g11)
- [BB组规则](#bb组规则)

标准决定划分依据，不规定数量、比例、规模或既有答案。

## 共享分类契约

例外种类、证据字段和消费者以 `assets/renderer/classification-registry.mjs` 为唯一注册表；`scripts/classify.py` 是 body、BB、操作和属性的唯一分类阶段。resolver、source_ranges 与检查器只读分类结果。

- body 分类只使用 `kind=direct|async-shell`；执行形态另存 `executionForm=sync|coroutine`。
- async-shell 以唯一直接 ownership child 的 inner 为主分析 body；不得增加案例专属 kind/mode。
- `pure_loop_handoff` 必须同时满足受限操作、Goto 到 loop entry、scope 成员和真实 MIR 循环。
- `instrumentation` 逐 BB 证明操作/调用纯度，冲突 BB 和混合操作默认保留为 business。
- S1 elements携带证明；S2自动派生instrumentation technicalBlocks并将已证明BB移到ROOT，禁止手抄证明副本。
- 纯tracing日志BB必须完整证明后移到ROOT；未获证明是证据缺口，不能伪装成业务组交付。tokio/core/?/async宏来源不能充当日志证明；混合BB按下文技术区间处理。
- 这种 null 可能来自 MIR 把前一 `format!` 尾部的 coroutine 投影字段 drop flag 复位与 `warn!` 开头放进同一入口 BB；冻结证明要求区域内 Assign 属于同一调用点且目的地无投影，因此 fail-closed。它是 MIR 块边界与冻结分类器共同造成的，不能靠 S0 pin 修复，也不得修改 classify。
- `source_less` 保留完整函数、BB refs 和非空原因；只有经注册表证明的纯循环交接 action 可省略详情片段。
- `loop.exitMode=terminalOnly` 只承载函数终止型循环的窄例外；`commonAfter` 与 `terminalOnly` 严格互斥。

## G1–G11

### G1 业务消息归属

- 判据：每次业务请求及其条件完成组成同一 invocation，消息对唯一归属一个 action；跨层只引用该成员。
- 正例：一次外部业务请求及其成功或失败结果处理 → 同一 action 的消息对。
- 反例：为 goal 和 action 各复制一份相同请求。

### G2 action 的独立事实与边界

- 判据：action 至少解释一项有证据的业务调用、业务判断、业务状态变化或业务结果；同一操作的参数准备和直接取结果可合并。
- 正例：虚构 `submit_order` 失败后连续保全订单、报告事件并返回拒绝结果，中间没有业务判断 → 合为一个失败处理 action；正常与恢复路径仍分开。
- action/BB组标题只描述其 BB 实际覆盖的操作；标题提到的操作必须在其 BB 范围内。只保全订单的组不能命名为“保全订单并报告事件”。
- 反例：把锁、future 构造单独成 action；把正常路径与恢复路径塞进同一 action。

### G3 goal 与 phase 边界

- 判据：goal 的成员共同履行一个可核验的业务完成合同：同一责任/对象、进入模式、状态承诺及后继用途。先逐 action 写合同，再合组。phase 在生命周期责任、输入承诺或处理模式交接处划分。
- 分界：独立接纳/提交/交付的状态承诺；正常尝试与改变输入承诺后的恢复重试；有独立输入保全、通知或终止义务的失败协议。
- 合组：兄弟 action 共享业务完成合同及进入模式时必须合为一个 goal；多个 actor 或 decision 本身不强制拆分。
- 反例：按 callee、decision 数、BB 大小或目标数量切分；把每个 Result 分支拆成 goal。
- 账本：`granularity.goalContracts[]` 覆盖每个 action 恰好一次；同 goal 成员的合同和进入模式一致。连续至少三个同合同/进入模式的单 action goals 判 fail。

### G4 业务 decision

- 判据：影响是否调用、选择输入、状态承诺、后续成员或业务出口的判断进入业务判断清单并绑定可见 alt/opt/loop。
- 反例：把 poll 的挂起分支当业务选择。

### G5 可跳过成员

所有读者可见文案（label、name、summary、condition、skip、result、purpose、object 等）只用业务语言，不得出现 bbN、mN.N、call:N 标识；这些标识只写在 evidenceRefs、bypassEvidenceRefs、entryEvidenceRefs、basis 等证据字段中。结构引用字段保持其身份引用，不作为展示文案。 S4 control.skip 必须与 S2 memberGuards.skip 一致，文案缺陷须回 S2 修正。

- 判据：成员仅在某业务条件下执行、否则只绕过该工作时，必须用 opt；真实 guard 和绕过路径须有证据。
- 正例：配置开启才准备、预算超限才压缩、配置 hook 才执行，均用 opt。
- 反例：把调用后的结果 alt 当作调用前 guard。

### G6 跨成员 readingScope

- 判据：业务循环和跨多个成员的连续条件范围必须形成 readingScope，记录入口、成员、绕过/汇合或回边/出口。
- 反例：范围跨越无关成员或把外部后继纳入循环。

### G7 目的投影覆盖

- 判据：每个有业务 invocation 的 goal 均须由包含其成员的 purposeProjection 覆盖；纯本地判断、状态变化或结果交付由阅读摘要表达。
- 反例：为了让每个 goal 都有投影而虚构外部调用。

### G8 sequence / alt / opt 的选择

- 判据：sequence 保持同一路径的操作先后；alt 表达完整互斥业务替代；单侧可选成员用 opt。
- 反例：为每个 Result/Option 处理单独包 opt；将互斥分支排成无条件 sequence。

### G9 按目的组投影

- 判据：S2 必须为每一个业务 invocation（来源：facts/call-bindings 中被 selection 选为业务调用的项，以及 memberGuards/controls 的 invocationRef）写一条 purposeGroups，不论 projection 是否已存在；每条固定 projectionRef（即 S5 将使用的 projection id）、object、purpose、condition（或 phase）、result、可解析 evidenceRefs。projectionRef 唯一；同一端点服务不同目的时分开写；不得用空数组。用 invocationRefs 或 bindingRefs 显式关联业务调用；已有证据中的真实 Call/调用 BB 也可用于覆盖核对。虚构 submit_order 正例：S2 尚无 projection，仍为扣款写 purpose-charge（订单款项、确认可落库、库存允许、付款确认、call:1/bb1），为通知写 purpose-notify（已创建订单、告知订阅方、订单已写入、通知已接收、call:2/bb3）。反例：等待 S5 再填、purposeGroups=[]，或因同一端点而合并不同目的。
- S5：每个 purposeProjection 的 id 必须等于某条 S2 granularity.purposeGroups.projectionRef；两者一一对应，双方均不得遗漏或重复。S5 validate 同时报告缺 group 的 projection id 和缺 projection 的 projectionRef。沿用 S3 自动锁定的 S2 目的边界；需要改变边界时回到 S2/S3 重新审阅。

### G10 阅读树覆盖

- 判据：除纯技术 BB 外，业务路径上每个 BB 必须归入 action。回到循环入口前的共同收尾必须形成 action。
- 正例：循环各分支汇合后共同完成本轮收尾，再进入下一轮。
- 反例：把业务收尾留在 ROOT 下无 action；仅凭 Drop/Return terminator 或笼统技术说明豁免整个块。
- 账本：`stage2/granularity.json.technicalBlocks[]` 逐块记录 `bbRef, category, reason, evidenceRefs`，并证明整个 BB 纯属技术机制。

### G11 phase 生命周期边界

- 判据：phase 在生命周期责任、输入承诺或处理模式的交接点划分，按执行顺序排列。跨 phase 循环必须有跨 phase 的 loop readingScope 和有证据的回边。
- 反例：仅按成功、错误等结果类别拆 phase；为保持 SCC 单一而吞并生命周期交接。

## BB组规则

> **BB → BB组（第 3 层）**：沿控制流把顺序执行的 BB 连成片段。一个 BB组是一段顺序路径，组内顺序按执行先后，不按 BB 编号排序。为每组算出 `entry_blocks`、`exit_blocks`、`exit_edge_ids`（离开本组且有 BB 目标的原边 ID）、`terminal_event_ids`（无 BB 目标的 typed 事件 ID）、`port_transfer`（入口到出口及终结事件的对应）。

## S2 源范围与清单填写

先逐项核对 goal/action 高亮集合，排除无关行；按不连续区间的 inclusive 并集计算行数，超过函数跨度的 25% 时，必须在该 S2 节点写具体 broadRangeReason，说明哪几行为什么必须高亮；不得用理由掩盖错范围；phase 豁免。虚构 submit_order 正例：函数 10–49 共40行，失败处理高亮 30–32、34–38、40–43 共12行（30%），理由逐段说明保全订单、报告失败、返回拒绝结果的必要性。反例：把 30–43 包围区间内无关的33/39行也高亮，再写“失败处理很复杂”。

成员在业务条件下才执行时，逐成员登记 guard、take/skip 值域、执行证据与绕过路径；跨成员条件或业务循环必须登记 range 的入口、成员、汇合/回边和证据，并绑定后续 readingScope。空清单不能冒充没有 guard/range；确实不存在时须给出覆盖源码与路径的审查依据。虚构 submit_order 正例：仅库存允许时执行扣款和落库，登记两个成员的 take/skip、拒绝路径及同一 opt range 的入口/汇合；逐订单行循环另登记入口、成员、回边/出口。反例：源码有库存分支和逐行循环，却因已有图框而把 memberGuards/ranges 都留空。

完整虚构填写例见 [ledger-templates](ledger-templates.md#s2-审查字段完整填写例)。


## 混合 BB 的明确代价

渲染器按整 BB 展示。业务与 tracing 混合的 BB 整块留在业务 group，日志操作以 S1 elements 的 technicalIntervals 证明投影到 S2 granularity.technicalIntervals（statementIndices 与 terminator），S5/S7 检查投影相等。页面仍显示该 BB 的日志细节，不能声称实现了语句级隐藏。仅有 core 宏、? 或 async 脱糖的混合 BB 保持业务，不记日志技术区间。


非日志技术 BB 也只写分类、源码理由与依据（必要时operationReasons/terminatorReason）。哈希、操作kind/下标清单和terminator形状由elements.mirWitness推导，禁止手抄factSha256/operationKinds/operationProofs/terminatorProof；冻结检查仍用原始MIR逐项验证。S1还提供结构化drop/cleanup/unwind/stateDispatch候选属性；候选不自动改变业务归属。

调用/闭包的 shown/folded 只按 [信息保持规则](s2-authoring.md#信息保持规则唯一选择定义) 从 MIR 推导；信息改变和技术 BB 证明是两个独立维度。
