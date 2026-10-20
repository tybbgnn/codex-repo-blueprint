# S2 作者判定步骤（生成文件）

唯一来源：stage-io.json 的 reading_group_policy；开始编写任何新账本前逐项执行。

1. 从 facts/edges.json 找出 action 内的控制流，沿执行顺序划分 BB 片段；每个 BB 恰好一个 owner。
2. 读取facts/elements.json及facts/instrumentation-candidates.json的完整证明，由脚本派生instrumentation technicalBlocks、ROOT归属和组间CFG桥接；禁止手抄记录，空action立即停止。
3. 纯tracing日志BB不能留在业务组；未获完整证明属于证据缺口，先核验pin及证明器，不能靠宏来源伪造技术归属。
4. S3 review如实记录证明缺口；已证明BB须移到ROOT，混合BB仅日志操作进技术区间；tokio/core/?/async不算日志。
5. 忽略 unwind 边和进入 cleanup BB 的边；cleanup BB 不得放入 action 下的业务组。
6. 每组只保留一个入口，且每个成员的组内入度、出度都不超过 1；遇到分支或合并立即切组。
7. 沿唯一入口生成执行顺序；只允许最后一个成员回到入口，basic_block_order 只由脚本生成。
8. 组 ID 最后一段写 C{执行顺序第一个BB号}；name 描述本组自己的操作，规范化后不得包含父 action 名的完整文本。
9. evidence 必须是本组真实 BB；方案 A 不要求 adds 或 granularity.boundaryDecisions。
10. 先逐项核对 goal/action 高亮集合，排除无关行；按不连续区间的 inclusive 并集计算行数，超过函数跨度的 25% 时，必须在该 S2 节点写具体 broadRangeReason，说明哪几行为什么必须高亮；不得用理由掩盖错范围；phase 豁免。虚构 submit_order 正例：函数 10–49 共40行，失败处理高亮 30–32、34–38、40–43 共12行（30%），理由逐段说明保全订单、报告失败、返回拒绝结果的必要性。反例：把 30–43 包围区间内无关的33/39行也高亮，再写“失败处理很复杂”。
11. S2 必须为每一个业务 invocation（来源：facts/call-bindings 中被 selection 选为业务调用的项，以及 memberGuards/controls 的 invocationRef）写一条 purposeGroups，不论 projection 是否已存在；每条固定 projectionRef（即 S5 将使用的 projection id）、object、purpose、condition（或 phase）、result、可解析 evidenceRefs。projectionRef 唯一；同一端点服务不同目的时分开写；不得用空数组。用 invocationRefs 或 bindingRefs 显式关联业务调用；已有证据中的真实 Call/调用 BB 也可用于覆盖核对。虚构 submit_order 正例：S2 尚无 projection，仍为扣款写 purpose-charge（订单款项、确认可落库、库存允许、付款确认、call:1/bb1），为通知写 purpose-notify（已创建订单、告知订阅方、订单已写入、通知已接收、call:2/bb3）。反例：等待 S5 再填、purposeGroups=[]，或因同一端点而合并不同目的。
12. 成员在业务条件下才执行时，逐成员登记 guard、take/skip 值域、执行证据与绕过路径；跨成员条件或业务循环必须登记 range 的入口、成员、汇合/回边和证据，并绑定后续 readingScope。空清单不能冒充没有 guard/range；确实不存在时须给出覆盖源码与路径的审查依据。虚构 submit_order 正例：仅库存允许时执行扣款和落库，登记两个成员的 take/skip、拒绝路径及同一 opt range 的入口/汇合；逐订单行循环另登记入口、成员、回边/出口。反例：源码有库存分支和逐行循环，却因已有图框而把 memberGuards/ranges 都留空。
13. 同一失败处理中连续的“保全状态 → 报告事件 → 返回结果”等 action，若中间没有业务判断，合并为一个 action；正常与恢复路径仍分开。action/BB组标题只能描述其 BB 实际覆盖的操作，标题提到的操作必须在其 BB 范围内。虚构 submit_order 正例：bb20 保全、bb21 报告、bb22 返回且无业务判断，归入一个失败处理 action；bb20 的组只称“保全待提交订单”。反例：把三步拆成三个 action，或 bb20 的组标题称“保全订单并报告事件”但报告实际在 bb21。
14. 所有读者可见文案（label、name、summary、condition、skip、result、purpose、object 等）只用业务语言，不得出现 bbN、mN.N、call:N 标识；这些标识只写在 evidenceRefs、bypassEvidenceRefs、entryEvidenceRefs、basis 等证据字段中。结构引用字段保持其身份引用，不作为展示文案。
15. ownerActionRef、technicalBlocks中的instrumentation、basic_block_order、group_order_basis与S4 sourceInventory均由事实/层级/证明推导，不手写重复。非instrumentation只写分类、原因和源码依据，原始MIR见elements，完整证据形状由脚本生成后交冻结检查。
16. 混合业务+tracing BB保持业务组，日志操作仅记technicalIntervals；core/tokio/?/async宏不按日志归技术。S2/S5/S7统一模型检查通过后才继续。
17. loop ranges.memberActionRefs 不手写：从 S4 的入口/出口决定及 S1 MIR 推导真实循环动作的最小连续阅读区间；环内额外动作必须有不能回入口且只能到 commonAfter/已认证终点的完整证明。
18. 调用与闭包的去向只按下文信息保持规则从MIR推导；technical须独立证明。
19. 节点名称、条件、结果与边标签中，来自源码的函数、类型、字段、变量、枚举值、模块以及 session、sampling、history、hook、token 等术语大致保留英文原文并放入反引号；连接语用中文。这是写作规则，不增加机器检查。

## 证据字段要求

- **node.evidence**：非空 bbN 数组，均属于本组且存在 S1 facts；通过 facts 的 source_info/span 逐项核对固定源码，不能借用其他组的 BB。
- **node.id**：最后一段必须是 C{执行顺序第一个BB号}；执行顺序由脚本从组入口和原边顺序派生。
- **node.name**：规范化后不得包含父 action 名的完整文本，必须描述本组自己的操作。
- **granularity.technicalBlocks**：仅写非instrumentation的BB分类、理由、evidenceRefs及必要逐操作理由；factSha256、operationKinds/Proofs、terminatorProof由elements.mirWitness推导。instrumentation整条由证明自动生成。
- **未获证明的日志宏展开**：记录具体证明缺口；纯日志不得作为业务组交付，不以宏来源代替证明。
- **证据缺口**：源码 span 缺失时列出真实路径端点/边及事实，标记无法证明的判断；不得捏造行号或用历史产物替代。
- **node.broadRangeReason**：先逐项核对 goal/action 高亮集合，排除无关行；按不连续区间的 inclusive 并集计算行数，超过函数跨度的 25% 时，必须在该 S2 节点写具体 broadRangeReason，说明哪几行为什么必须高亮；不得用理由掩盖错范围；phase 豁免。虚构 submit_order 正例：函数 10–49 共40行，失败处理高亮 30–32、34–38、40–43 共12行（30%），理由逐段说明保全订单、报告失败、返回拒绝结果的必要性。反例：把 30–43 包围区间内无关的33/39行也高亮，再写“失败处理很复杂”。
- **granularity.purposeGroups**：S2 必须为每一个业务 invocation（来源：facts/call-bindings 中被 selection 选为业务调用的项，以及 memberGuards/controls 的 invocationRef）写一条 purposeGroups，不论 projection 是否已存在；每条固定 projectionRef（即 S5 将使用的 projection id）、object、purpose、condition（或 phase）、result、可解析 evidenceRefs。projectionRef 唯一；同一端点服务不同目的时分开写；不得用空数组。用 invocationRefs 或 bindingRefs 显式关联业务调用；已有证据中的真实 Call/调用 BB 也可用于覆盖核对。虚构 submit_order 正例：S2 尚无 projection，仍为扣款写 purpose-charge（订单款项、确认可落库、库存允许、付款确认、call:1/bb1），为通知写 purpose-notify（已创建订单、告知订阅方、订单已写入、通知已接收、call:2/bb3）。反例：等待 S5 再填、purposeGroups=[]，或因同一端点而合并不同目的。
- **granularity.memberGuards / granularity.ranges**：成员在业务条件下才执行时，逐成员登记 guard、take/skip 值域、执行证据与绕过路径；跨成员条件或业务循环必须登记 range 的入口、成员、汇合/回边和证据，并绑定后续 readingScope。空清单不能冒充没有 guard/range；确实不存在时须给出覆盖源码与路径的审查依据。虚构 submit_order 正例：仅库存允许时执行扣款和落库，登记两个成员的 take/skip、拒绝路径及同一 opt range 的入口/汇合；逐订单行循环另登记入口、成员、回边/出口。反例：源码有库存分支和逐行循环，却因已有图框而把 memberGuards/ranges 都留空。
- **G2 action / BB组标题**：同一失败处理中连续的“保全状态 → 报告事件 → 返回结果”等 action，若中间没有业务判断，合并为一个 action；正常与恢复路径仍分开。action/BB组标题只能描述其 BB 实际覆盖的操作，标题提到的操作必须在其 BB 范围内。虚构 submit_order 正例：bb20 保全、bb21 报告、bb22 返回且无业务判断，归入一个失败处理 action；bb20 的组只称“保全待提交订单”。反例：把三步拆成三个 action，或 bb20 的组标题称“保全订单并报告事件”但报告实际在 bb21。
- **读者可见文案 / P7**：所有读者可见文案（label、name、summary、condition、skip、result、purpose、object 等）只用业务语言，不得出现 bbN、mN.N、call:N 标识；这些标识只写在 evidenceRefs、bypassEvidenceRefs、entryEvidenceRefs、basis 等证据字段中。结构引用字段保持其身份引用，不作为展示文案。
- **selection.items**：每个Call/body稳定id恰好一个去向；理由与信息效果从MIR推导，归属来自层级，shown与消息互证。

## 信息保持规则（唯一选择定义）

S1 在 `facts/elements.json` 的 `proofs.informationEffect` 记录 MIR 判定；S2 `canonical_selection` 投影为唯一去向，S2/S5/S7 `check_model` 从原始 MIR 和 SHA 固定的 `input-pins.json.information_mir_slices` 重算校验。作者逐项确认 selection，不得用整类 foldRules 掩盖信息改变。理由与 sourceRefs 由判定生成；ownerActionRef 从层级推导。

仅当信息保持才 folded：输出只重塑、移动、借用、转换、格式化输入信息（含 `?` 与全量一对一变体映射），或属于不影响业务数据的日志/指标、async plumbing、锁、drop 基础设施。其余仅按四种效果 shown：**DECIDES**（结果决定非机制分支）、**WRITES**（写项目状态，含锁 guard）、**DROPS**（返回 None/常量/子集或筛除数据）、**COMPUTES**（计算新值）。项目 callee 对这四种效果按需递归分析，结论成立或遇到循环即停，不设层数上限，缓存包含当前递归上下文。未知库操作显式留在 proof 的 partial/unclassified 中。trait 先解析具体 impl；dyn/std/第三方按声明折叠并报告。容器有 body 却无 pin 必须报缺失；定义存在而容器无 body 单列抽取范围缺口、源码行与补抽命令，最终不得称为干净通过。S0 两种输入模式均由 skill 自行生成 pin，S1 补执行体，S2/S5/S7 重算核验。

机械顺序与固定库表以 `scripts/check_model.py` 的 `InformationRule`、`InformationBody` 和 `lib_kind` 为准：先查调用现场 &mut 状态写入，再查项目调用结果是否经透明操作/库操作流入非 await、?、drop flag、第三方宏分支；否则分析 callee 的状态写、项目来源分支、返回 None/常量、算术及递归调用/内部闭包。库操作按 infrastructure、格式/透明、predicate、DROPS、COMPUTES、其余透明表匹配。predicate 或 DROPS/COMPUTES 结果只喂分支时记作分支条件，不另建框；提供被判断值的项目调用 shown。第三方宏定义的闭包属于基础设施。不得按函数名例外或按 body 分支。

库表包含 tracing/metrics、poll/into_future/Pin/join/or_cancel、锁/drop；透明映射包含 clone/deref/from/into/as_*/fmt/iter/map/collect/extend/push/insert/sort/new/default/unwrap；筛减表包含 filter/find/retain/dedup/take/get/first/last/min/max/ok/and_then/trim；计算表包含 len/count/sum/checked_*/parse/from_str/now。完整正则表只维护在上述函数，不在文档复制第二份。

technical 是独立的 BB/语句区间证明去向：已证日志仍 technical 并归 ROOT，混合 BB 日志仅标技术区间；信息保持不等于有权把 BB 移到技术层。shown 外部调用每次恰好一对 request/return；主参与方内的库操作使用渲染器原生的一条 kind=self、pair=null 消息。shown 闭包由真实消费调用绑定 endpoint；若其库适配调用 folded，业务成员以 `bodyElementRef` 关联消息并明确表示闭包执行，不将适配调用重分类、也不重复计数。没有 definitions 条目的库操作作为主参与方内部自调用消息展示，业务成员的 `internalOperation` 明确核验原始调用和主 body；不伪造外部 declaration。每一项 shown 都有可见交互依据。
