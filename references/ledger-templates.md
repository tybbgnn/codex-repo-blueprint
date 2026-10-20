# 语义账本最小模板

## 目录

- [使用边界](#使用边界)
- [S2 字段怎么写](#s2-字段怎么写)
- [最小账本模板](#最小账本模板)
- [命名示例](#命名示例)
- [S4 控件决策表](#s4-控件决策表)

## 使用边界

下面只使用虚构的 Rust async 函数 `submit_order`：校验库存→扣款→写订单→通知。假定 S1 已产生 `bb0` 至 `bb3`、`m0.0` 至 `m2.0`、`call:1` 和 `call:2`。替换模板中的引用时，必须以本次 facts 和源码为准。

“最小”表示使用当前 `ledger-schema.json`、`contracts/*.json` 和阶段消费者已核对过的字段形状，不表示空数组能替代语义推理。真实 body 有决策、技术 BB、外部调用或循环时，必须增加相应记录。

## S2 字段怎么写

所有读者可见文案（label、name、summary、condition、skip、result、purpose、object 等）只用业务语言，不得出现 bbN、mN.N、call:N 标识；这些标识只写在 evidenceRefs、bypassEvidenceRefs、entryEvidenceRefs、basis 等证据字段中。结构引用字段保持其身份引用，不作为展示文案。

虚构 `submit_order`：正例 `skip="库存不足时不扣款，直接返回拒绝结果"`，绕过边写入 `bypassEvidenceRefs`；反例 `skip="经 m3.1 跳过扣款"`。S4 control.skip 与 S2 memberGuards.skip 保持一致，先在 S2 写好业务文案。

面向非技术读者的合格语义单元，不看下层也能回答“做什么、为什么、得到什么”。源码术语放在反引号内；可见文案不出现 `bbN`、`_N` 或 MIR 术语。

| 字段 | 写法 | 虚构示例 |
|---|---|---|
| `name` | 用动词+业务对象说清本层责任，不抄父节点 | “扣取本次订单款项” |
| `condition` | 说什么业务前提下执行，不把 poll/cleanup 写成业务条件 | “库存校验通过后” |
| `result` | 说本层完成后可观测的业务结果 | “产生可持久化的付款确认” |
| `purpose` | 说本层对父 goal 的价值，不重复操作步骤 | “确保只记录已成功收款的订单” |
| `boundary` | 说本层包含与不包含什么，以及向下一层的交接 | “到收到扣款结果为止；不包含订单落库” |
| `selection_basis` | 说明为何是独立业务单元，并指向源码/路径依据 | “该调用产生独立付款承诺，结果决定是否允许写订单” |

### folded 选择项

```json
{"id":"call:5","disposition":"folded","reason":"将支付响应的错误码转换为展示错误。","semanticRole":"adapter","sourceRefs":["call:5"]}
```

ownerActionRef由层级BB归属推出；去向、理由按 [信息保持规则](s2-authoring.md#信息保持规则唯一选择定义) 推导。shown与S5消息双向覆盖；technical须有证明。

## 最小账本模板

### `ledgers/stage2.json`

```json
{
  "schema_version": 1,
  "root": "ROOT",
  "phase_order": ["P01"],
  "nodes": [
    {"id":"ROOT","kind":"root","name":"提交订单并交付处理结果","condition":"收到订单请求","result":"订单被记录并发出通知","evidence":["bb0","bb1","bb2","bb3"],"members":["P01"]},
    {"id":"P01","kind":"phase","name":"完成订单提交","condition":"订单进入提交流程","result":"交付已记录的订单","evidence":["bb0","bb1","bb2","bb3"],"members":["sem:P01:complete-order"]},
    {"id":"sem:P01:complete-order","kind":"goal","name":"把可用库存转化为已通知的订单","condition":"收到待提交的商品与付款信息","result":"完成扣款、订单落库与通知","purpose":"以一致顺序完成订单承诺","boundary":"从库存校验开始，到通知已提交为止","selection_basis":"四个动作共同完成同一订单提交合同","evidence":["bb0","bb1","bb2","bb3"],"members":["P01/A01.0","P01/A02.1","P01/A03.2","P01/A04.3"]},
    {"id":"P01/A01.0","kind":"action","name":"确认商品仍有可用库存","condition":"订单尚未扣款","result":"得到允许扣款的库存结论","selection_basis":"该判断决定是否允许进入付款","evidence":["bb0"],"members":["P01/A01.0/C0"]},
    {"id":"P01/A01.0/C0","kind":"bb_group","name":"读取并核对商品可售数量","evidence":["bb0"],"members":["bb0"]},
    {"id":"P01/A02.1","kind":"action","name":"扣取本次订单款项","condition":"库存校验通过","result":"获得付款确认","selection_basis":"该外部调用产生独立的付款承诺","evidence":["bb1","call:1"],"members":["P01/A02.1/C1"]},
    {"id":"P01/A02.1/C1","kind":"bb_group","name":"提交扣款请求并接收确认","evidence":["bb1"],"members":["bb1"]},
    {"id":"P01/A03.2","kind":"action","name":"持久化已付款订单","condition":"扣款成功","result":"生成可查询的订单记录","selection_basis":"写入订单是与扣款分开的状态承诺","evidence":["bb2"],"members":["P01/A03.2/C2"]},
    {"id":"P01/A03.2/C2","kind":"bb_group","name":"写入付款标识与订单明细","evidence":["bb2"],"members":["bb2"]},
    {"id":"P01/A04.3","kind":"action","name":"发送订单已创建通知","condition":"订单已持久化","result":"订阅方收到订单标识","selection_basis":"通知是订单记录之后的独立外部协作","evidence":["bb3","call:2"],"members":["P01/A04.3/C3"]},
    {"id":"P01/A04.3/C3","kind":"bb_group","name":"向订阅方投递订单标识","evidence":["bb3"],"members":["bb3"]}
  ],
  "selection": {
    "items": [
      {"id":"call:1","disposition":"shown"},
      {"id":"call:2","disposition":"shown"}
    ]
  },
  "granularity": {
    "businessFacts": [
      {"id":"fact-stock","kind":"decision","claim":"库存结论决定是否允许扣款","actionRef":"P01/A01.0","evidenceRefs":["bb0"]},
      {"id":"fact-payment","kind":"call","claim":"付款结果是写订单的前提","actionRef":"P01/A02.1","evidenceRefs":["call:1","bb1"]},
      {"id":"fact-order","kind":"state_change","claim":"已付款订单被持久化","actionRef":"P01/A03.2","evidenceRefs":["bb2"]},
      {"id":"fact-notice","kind":"call","claim":"订阅方获得新订单标识","actionRef":"P01/A04.3","evidenceRefs":["call:2","bb3"]}
    ],
    "boundaries": [
      {"ref":"P01","purpose":"完成订单提交","completion":"订单已持久化并通知","entry":"接收待提交订单","exit":"交还订单标识","evidenceRefs":["bb0","bb3"]},
      {"ref":"sem:P01:complete-order","purpose":"交付已付款订单","completion":"扣款、落库与通知已完成","entry":"库存校验","exit":"通知已投递","evidenceRefs":["bb0","bb1","bb2","bb3"]}
    ],
    "decisions": [],
    "memberGuards": [],
    "ranges": [],
    "purposeGroups": [
      {"projectionRef":"purpose-charge","object":"订单款项","purpose":"确认订单可以落库","condition":"库存允许","phase":"P01","result":"取得付款确认","evidenceRefs":["call:1","bb1"]},
      {"projectionRef":"purpose-notify","object":"已创建订单","purpose":"告知订阅方有新订单","condition":"订单已写入","phase":"P01","result":"通知已接收","evidenceRefs":["call:2","bb3"]}
    ],
    "technicalBlocks": [],
    "goalContracts": [
      {"goalRef":"sem:P01:complete-order","contractRef":"contract:complete-order","targetRef":"input:order","receiverRef":null,"entryMode":"initial-submit","completion":"订单已持久化并通知","cohesionReason":"四个动作共同履行同一订单提交承诺","evidenceRefs":["bb0","bb1","bb2","bb3"],"memberContracts":[
        {"actionRef":"P01/A01.0","contractRef":"contract:complete-order","entryMode":"initial-submit","evidenceRefs":["bb0"]},
        {"actionRef":"P01/A02.1","contractRef":"contract:complete-order","entryMode":"initial-submit","evidenceRefs":["bb1"]},
        {"actionRef":"P01/A03.2","contractRef":"contract:complete-order","entryMode":"initial-submit","evidenceRefs":["bb2"]},
        {"actionRef":"P01/A04.3","contractRef":"contract:complete-order","entryMode":"initial-submit","evidenceRefs":["bb3"]}
      ]}
    ]
  }
}
```

### `ledgers/summaries.json`

```json
{"units":{"P01":{"kind":"phase","text":"完成库存确认、扣款、订单落库与通知。"},"sem:P01:complete-order":{"kind":"goal","text":"把可用库存转化为已付款、可查询且已通知的订单。"},"P01/A02.1":{"kind":"action","text":"库存允许时请求扣款，并把付款确认交给落库步骤。"}}}
```

### `ledgers/stage3.json`

```json
{
  "passed": true,
  "reviewer": "Agent source/MIR decision",
  "scope": "Fictional submit_order reading tree",
  "findings_resolved": [],
  "unresolved": [],
  "nodes": [
    {
      "nodeRef": "sem:P01:complete-order",
      "evidence": ["bb0","bb1","bb2","bb3"],
      "exitEvidenceRefs": ["m2.0"],
      "dimensions": {
        "accurate_work": {"passed":true,"basis":"名称与成员都覆盖订单提交承诺。"},
        "flow_readable": {"passed":true,"basis":"读者能按库存、扣款、落库、通知的顺序阅读。"},
        "useful_expansion": {"passed":true,"basis":"展开后增加每个独立承诺的条件与结果。"},
        "semantic_completeness": {"passed":true,"basis":"关键动作在到达 BB 层前已说清。"},
        "bidirectional_evidence": {"passed":true,"basis":"每个上层结论有下层证据，下层业务工作也都被概括。"}
      }
    }
  ]
}
```

`passed` 表示 agent 五维自审通过；S3 build 自动锁定当前基线。

### `ledgers/review-narrative.md`

`stage3/review.md` 直接复制本手写文件。必须列出 **purposeGroups** 一节，逐条抄列 S2 的 projectionRef、object、purpose、condition（或 phase）、result 与 evidenceRefs，说明边界，供 agent 锁定前核对。虚构 `submit_order` 示例：

| projectionRef | object | purpose | condition / phase | result | evidenceRefs |
|---|---|---|---|---|---|
| purpose-charge | 订单款项 | 确认订单可以落库 | 库存允许 / P01 | 取得付款确认 | call:1, bb1 |
| purpose-notify | 已创建订单 | 告知订阅方有新订单 | 订单已写入 / P01 | 通知已接收 | call:2, bb3 |

反例：只写“五维通过”，没有可供审阅的目的边界列表。

### `ledgers/edges.json`

```json
{"edges":[{"id":"order-flow-payment-to-write","kind":"goal_flow","source":"P01/A02.1","target":"P01/A03.2","label":"付款确认后写入订单","condition":"扣款成功","result":"进入订单持久化","depth":2,"view":"reading","members":["m1.0"],"clauses":[{"edgeRef":"m1.0","source_bb":"bb1","target_bb":"bb2","condition":"付款确认可用","result":"转交订单写入"}]}],"transitions":[]}
```

### `ledgers/stage4.json`

```json
{
  "controls": [
    {"id":"control-charge","kind":"sequence","messages":["request-charge","return-charge"],"invocationRef":"invocation-charge"},
    {"id":"control-notify","kind":"sequence","messages":["request-notify","return-notify"],"invocationRef":"invocation-notify"}
  ],
  "ownerControls": {"P01/A01.0":[],"P01/A02.1":["control-charge"],"P01/A03.2":[],"P01/A04.3":["control-notify"]},
  "controlEvidence": {"control-charge":["call:1"],"control-notify":["call:2"]},
  "readingScopes": [],
  "decisions": [],
  "executionNodes": [
    {"id":"exec-entry","kind":"entry","label":"接收订单提交请求","sourceEvidenceRefs":["bb0"],"evidenceRefs":["ev-entry"]},
    {"id":"exec-stock","kind":"action","actionRef":"P01/A01.0","label":"确认商品库存","sourceEvidenceRefs":["bb0"],"evidenceRefs":["ev-stock"]},
    {"id":"exec-charge","kind":"action","actionRef":"P01/A02.1","label":"扣取订单款项","sourceEvidenceRefs":["bb1"],"evidenceRefs":["ev-charge"]},
    {"id":"exec-write","kind":"action","actionRef":"P01/A03.2","label":"写入已付款订单","sourceEvidenceRefs":["bb2"],"evidenceRefs":["ev-write"]},
    {"id":"exec-notify","kind":"action","actionRef":"P01/A04.3","label":"发送订单通知","sourceEvidenceRefs":["bb3"],"evidenceRefs":["ev-notify"]},
    {"id":"exec-return","kind":"terminal","outcome":"return","label":"交还订单标识","sourceEvidenceRefs":["bb3"],"evidenceRefs":["ev-return"]}
  ],
  "executionEdges": [
    {"id":"exec-edge-0","source":"exec-entry","target":"exec-stock","kind":"flow","guards":[],"sourceEvidenceRefs":["bb0"],"evidenceRefs":["ev-edge-0"]},
    {"id":"exec-edge-1","source":"exec-stock","target":"exec-charge","kind":"flow","guards":[],"sourceEvidenceRefs":["m0.0"],"evidenceRefs":["ev-edge-1"]},
    {"id":"exec-edge-2","source":"exec-charge","target":"exec-write","kind":"flow","guards":[],"sourceEvidenceRefs":["m1.0"],"evidenceRefs":["ev-edge-2"]},
    {"id":"exec-edge-3","source":"exec-write","target":"exec-notify","kind":"flow","guards":[],"sourceEvidenceRefs":["m2.0"],"evidenceRefs":["ev-edge-3"]},
    {"id":"exec-edge-4","source":"exec-notify","target":"exec-return","kind":"flow","guards":[],"sourceEvidenceRefs":["bb3"],"evidenceRefs":["ev-edge-4"]}
  ],
  "branchRoles": [],
  "returnContracts": [
    {"messageRef":"return-charge","meaning":"normal-return"},
    {"messageRef":"return-notify","meaning":"normal-return"}
  ]
}
```

### `ledgers/stage5.json`

每个 purposeProjection 的 id 必须等于某条 S2 granularity.purposeGroups.projectionRef；两者一一对应，双方均不得遗漏或重复。S5 validate 同时报告缺 group 的 projection id 和缺 projection 的 projectionRef。沿用 S3 自动锁定的 S2 目的边界；需要改变边界时回到 S2/S3 重新审阅。

```json
{
  "rootActorRef": "actor-main",
  "actors": [
    {"actorId":"actor-main","kind":"body","label":"submit_order","color":"#42758c"},
    {"actorId":"actor-payments-crate","kind":"crate","label":"payments","color":"#42758c","children":[{"actorId":"actor-payments-module","kind":"module","label":"gateway","color":"#42758c","children":[{"actorId":"actor-charge","kind":"body","label":"charge","color":"#42758c"}]}]},
    {"actorId":"actor-notifications-crate","kind":"crate","label":"notifications","color":"#42758c","children":[{"actorId":"actor-notifications-module","kind":"module","label":"orders","color":"#42758c","children":[{"actorId":"actor-notify","kind":"body","label":"send_created","color":"#42758c"}]}]}
  ],
  "messages": [
    {"messageId":"request-charge","bindingRef":"call:1","pair":"pair-charge","kind":"request","invocationRef":"invocation-charge","fromActorId":"actor-main","toActorId":"actor-charge","label":"提交订单金额","stage":"business-request"},
    {"messageId":"return-charge","bindingRef":"call:1","pair":"pair-charge","kind":"return","invocationRef":"invocation-charge","fromActorId":"actor-charge","toActorId":"actor-main","label":"交还付款确认","stage":"business-completion"},
    {"messageId":"request-notify","bindingRef":"call:2","pair":"pair-notify","kind":"request","invocationRef":"invocation-notify","fromActorId":"actor-main","toActorId":"actor-notify","label":"提交订单标识","stage":"business-request"},
    {"messageId":"return-notify","bindingRef":"call:2","pair":"pair-notify","kind":"return","invocationRef":"invocation-notify","fromActorId":"actor-notify","toActorId":"actor-main","label":"确认通知已接收","stage":"business-completion"}
  ],
  "business_members": [
    {"id":"member-charge","invocationRef":"invocation-charge","bindingRef":"call:1","purposeRef":"purpose-charge","targetActorRef":"actor-charge","stageRole":"business-request-and-completion","basis":"真实 Call 同时支撑扣款请求与返回","ownerActionRef":"P01/A02.1","condition":"库存允许","result":"获得付款确认","evidenceRefs":["call:1","bb1"]},
    {"id":"member-notify","invocationRef":"invocation-notify","bindingRef":"call:2","purposeRef":"purpose-notify","targetActorRef":"actor-notify","stageRole":"business-request-and-completion","basis":"真实 Call 向订阅方交付订单标识","ownerActionRef":"P01/A04.3","condition":"订单已写入","result":"通知已接收","evidenceRefs":["call:2","bb3"]}
  ],
  "purposeProjections": [
    {"id":"purpose-charge","goalRef":"sem:P01:complete-order","invocationRefs":["invocation-charge"],"relatedGoalRefs":[],"defaultVisible":true,"summary":{"kind":"note","drawAsMessage":false,"object":"订单款项","purpose":"确认订单可以落库","result":"取得付款确认"},"waitRefs":[]},
    {"id":"purpose-notify","goalRef":"sem:P01:complete-order","invocationRefs":["invocation-notify"],"relatedGoalRefs":[],"defaultVisible":true,"summary":{"kind":"note","drawAsMessage":false,"object":"已创建订单","purpose":"告知订阅方有新订单","result":"通知已接收"},"waitRefs":[]}
  ],
  "segments": [
    {"id":"segment-charge","invocationRef":"invocation-charge","kind":"sequence","messages":["request-charge","return-charge"]},
    {"id":"segment-notify","invocationRef":"invocation-notify","kind":"sequence","messages":["request-notify","return-notify"]}
  ],
  "clauses": [
    {"id":"clause-charge","invocationRef":"invocation-charge","label":"扣取本次订单款项","evidenceRefs":["call:1","bb1"]},
    {"id":"clause-notify","invocationRef":"invocation-notify","label":"发送订单已创建通知","evidenceRefs":["call:2","bb3"]}
  ]
}
```

### `ledgers/endpoint-ledger.json`

```json
{"endpoints":[{"id":"endpoint-main","actorRef":"actor-main","kind":"body","canonical_path":"commerce::checkout::submit_order::{closure#0}"},{"id":"endpoint-charge","actorRef":"actor-charge","kind":"body","canonical_path":"payments::gateway::charge::{closure#0}"},{"id":"endpoint-notify","actorRef":"actor-notify","kind":"body","canonical_path":"notifications::orders::send_created::{closure#0}"}]}
```

这里只写 `canonical_path` selector，不写 hash。实体按调用处 MIR 目标身份与可调用种类约束后唯一解析，不按同名定义排序挑选。kind 由事实派生：已 pin 的可用 MIR 为 body；无 MIR 的 Fn/AssocFn 为 declaration；无 MIR 的 Closure 等必须回 S0 补 pin；主 body 必须是 body。

## S2 审查字段完整填写例

以下均为虚构 `submit_order` 的独立教学变体，引用只在各变体声明的 S1 facts 内解析，不是现存 body 或可直接运行的账本。源文件、BB、原边与调用引用均须在实际使用时换成本次事实。S2 先登记依据，S4/S5 再绑定相同引用；下面将后续绑定并列展示，避免空清单。

### broadRangeReason 与 G2：同一连续失败处理

假定完整函数为 `submit_order` 的10–49行（40行）；已逐操作复核：bb20 覆盖30–32行保全订单，bb21 覆盖34–38行构造并报告失败事件，bb22 覆盖40–43行生成并返回拒绝结果；33/39行与该处理无关，排除。原边 m20.0: bb20→bb21、m21.0: bb21→bb22，无中间业务判断。inclusive 并集为3+5+4=12行，即30%。以下是 S2 nodes 的完整相关记录；由这些 BB 派生 lineRanges，不手改生成范围。

```json
[
  {"id":"sem:P02:reject-order","kind":"goal","name":"保全失败订单并交付拒绝结果","condition":"提交失败","result":"订单可恢复且调用方收到拒绝结果","purpose":"保证失败交接完整","boundary":"从保全订单到返回拒绝结果","selection_basis":"同一连续失败协议，无中间业务判断","broadRangeReason":"30–32行保全待提交订单以支持恢复；34–38行构造并报告该失败事件以交接原因；40–43行生成并返回同一拒绝结果。三段均是本失败协议的必要操作，33/39行已排除；12/40行超过25%。","evidence":["bb20","bb21","bb22"],"members":["P02/A01.20"]},
  {"id":"P02/A01.20","kind":"action","name":"保全订单、报告失败并交还拒绝结果","condition":"提交失败","result":"保全与报告完成，返回拒绝结果","selection_basis":"保全→报告→返回连续执行，中间没有业务判断，合为一个 action；正常提交与恢复重试另建 action","broadRangeReason":"30–32行保全订单，34–38行构造并报告失败，40–43行生成并返回拒绝结果；均在本 action 覆盖的失败处理范围内，排除33/39行；必要高亮12/40行。","evidence":["bb20","bb21","bb22"],"members":["P02/A01.20/C20","P02/A01.20/C21","P02/A01.20/C22"]},
  {"id":"P02/A01.20/C20","kind":"bb_group","name":"保全待提交订单","evidence":["bb20"],"members":["bb20"]},
  {"id":"P02/A01.20/C21","kind":"bb_group","name":"构造并报告订单失败事件","evidence":["bb21"],"members":["bb21"]},
  {"id":"P02/A01.20/C22","kind":"bb_group","name":"生成并返回订单拒绝结果","evidence":["bb22"],"members":["bb22"]}
]
```

本变体按分支/汇合或局部描述需要划分 BB组；若 S1 显示三块可构成同一简单顺序片段，也可合为一个如实命名的 BB组，action 边界不变。phase 豁免25%理由要求。反例：用30–43包围区间多含无关行，再写“逻辑复杂”；或把连续失败步骤拆成三个 action；或把只覆盖 bb20 的组称为“保全并报告失败”。

### purposeGroups：S2 先固定业务调用的目的边界

S2 必须为每一个业务 invocation（来源：facts/call-bindings 中被 selection 选为业务调用的项，以及 memberGuards/controls 的 invocationRef）写一条 purposeGroups，不论 projection 是否已存在；每条固定 projectionRef（即 S5 将使用的 projection id）、object、purpose、condition（或 phase）、result、可解析 evidenceRefs。projectionRef 唯一；同一端点服务不同目的时分开写；不得用空数组。用 invocationRefs 或 bindingRefs 显式关联业务调用；已有证据中的真实 Call/调用 BB 也可用于覆盖核对。虚构 submit_order 正例：S2 尚无 projection，仍为扣款写 purpose-charge（订单款项、确认可落库、库存允许、付款确认、call:1/bb1），为通知写 purpose-notify（已创建订单、告知订阅方、订单已写入、通知已接收、call:2/bb3）。反例：等待 S5 再填、purposeGroups=[]，或因同一端点而合并不同目的。

S5：每个 purposeProjection 的 id 必须等于某条 S2 granularity.purposeGroups.projectionRef；两者一一对应，双方均不得遗漏或重复。S5 validate 同时报告缺 group 的 projection id 和缺 projection 的 projectionRef。沿用 S3 自动锁定的 S2 目的边界；需要改变边界时回到 S2/S3 重新审阅。

### memberGuards / ranges：可选成员与跨成员条件

独立变体假定 `submit_order` 的 bb0 按库存许可 decision-stock 分支：m0.0→bb1，m0.1→bb4；bb1 扣款、bb2 落库，m1.0→bb2，m2.0→bb4；bb4 为汇合。成员分别为 P01/A02.1 与 P01/A03.2。取值 allow/deny 穷尽且互斥。完整源清单如下：

```json
{
  "memberGuards": [
    {"memberActionRefs":["P01/A02.1"],"decisionRef":"decision-stock","takeValues":["allow"],"skipValues":["deny"],"condition":"库存允许提交","skip":"库存不足时直接到汇合点，不扣款","controlRef":"opt-charge","readingScopeRef":"scope-stock","evidenceRefs":["bb0","m0.0","bb1"],"bypassEvidenceRefs":["m0.1","bb4"]},
    {"memberActionRefs":["P01/A03.2"],"decisionRef":"decision-stock","takeValues":["allow"],"skipValues":["deny"],"condition":"库存允许提交","skip":"库存不足时直接到汇合点，不写订单","controlRef":"opt-write","readingScopeRef":"scope-stock","evidenceRefs":["bb0","m0.0","bb2"],"bypassEvidenceRefs":["m0.1","bb4"]}
  ],
  "ranges": [
    {"kind":"opt","decisionRef":"decision-stock","readingScopeRef":"scope-stock","entry":"bb0","memberActionRefs":["P01/A02.1","P01/A03.2"],"merge":"bb4","entryEvidenceRefs":["m0.0"],"bypassEvidenceRefs":["m0.1"],"mergeEvidenceRefs":["m2.0"],"evidenceRefs":["bb0","m0.0","bb1","m1.0","bb2","m2.0","m0.1","bb4"]}
  ]
}
```

S4 必须让 decision-stock 的 `values` 为 allow/deny，并绑定 scope-stock；scope 的 kind=opt、members 恰好是上述两个 action。opt-charge / opt-write 分别覆盖各成员的实际消息，写明同一 guard 和绕过路径；跨成员 scope 绑定 `originControlRef`，遵守控件唯一性。仅画 scope 不能替代逐成员 guard。反例：已有 opt 图框，便留下空 memberGuards / ranges。

### ranges：循环入口、成员、回边及出口

另一独立变体在 `submit_order` 中逐订单行校验：bb6 为入口和 decision-lines，m6.0→bb7（more），m7.0→bb8，m8.0→bb6 为回边；m6.1→bb9（done）为出口。bb7 校验、bb8 完成本行，两者 action 是 scope-lines 的全部成员，bb9 不属于循环。

```json
{
  "ranges": [
    {"kind":"loop","decisionRef":"decision-lines","readingScopeRef":"scope-lines","entry":"bb6","backEdge":"m8.0","exit":"bb9","entryEvidenceRefs":["bb6","m6.0"],"backEdgeEvidenceRefs":["m8.0"],"exitEvidenceRefs":["m6.1","bb9"],"evidenceRefs":["bb6","m6.0","bb7","m7.0","bb8","m8.0","m6.1","bb9"]}
  ]
}
```

S4 的 scope-lines.kind=loop，decision-lines 绑定该 scope，值域 more/done；repeat.entryActionRef=P01/A05.7，continueValues=[more]、exitValues=[done]，出口 bb9 对应 action 放 commonAfter。反例：有逐行循环却留下空 ranges，或额外成员未经 MIR 出口证明。loop 成员由 MIR 真实循环动作在阅读顺序中的最小连续区间派生；额外成员为环内出口，须证明不能回入口且所有路径只到 commonAfter 或已认证终点，否则失败并拆成精确范围。loop-exit 只指向 commonAfter 或已认证终点，进入环内出口动作使用普通 branch。确实无 guard/range 的变体才可用空数组，并在源审查中以覆盖源码/路径的证据说明不存在，不能用空清单本身证明无遗漏。

## 命名示例

| 层 | 好例 1 | 好例 2 | 坏例 1 | 坏例 2 |
|---|---|---|---|---|
| phase | “完成订单提交”——说清整体责任和完成点 | “处理付款失败并交还结果”——说清失败阶段的义务与结果 | “处理阶段”——没有对象和完成承诺 | “阶段一”——只有顺序，没有业务含义 |
| goal | “把可用库存转化为已付款订单”——说清输入、目的和结果 | “保全扣款失败信息并终止提交”——说清原因与交付 | “订单相关处理”——边界不明 | “调用 `charge`”——只描述实现手段，没说为什么 |
| action | “扣取本次订单款项”——动词与业务对象明确 | “持久化已付款订单”——状态变化和结果明确 | “执行调用”——不知道调用实现什么承诺 | “处理返回值”——是代码形式，不是业务责任 |
| BB组 | “读取并核对商品可售数量”——只描述本组的局部操作 | “向订阅方投递订单标识”——有具体对象与动作 | “检查当前状态并选择后续处理”——是可套在任何分支上的模板句 | “扣取本次订单款项的 MIR 片段”（即“`<父 action 名>的 MIR 片段`”）——抄父名且泄漏实现层术语 |

BB组编号副本也是坏例：“组装诊断记录 2” / “组装诊断记录 3”。编号不是含义，读者无法分辨两组的实际差别。

### 日志证明与归属

纯tracing日志BB逐操作证明后整块移到ROOT；S2从elements证明派生instrumentation记录，不手写副本、不生成derived-technical-blocks文件。纯日志未获证明是证据缺口，不能以日志业务组交付。混合BB留业务组，日志操作记录technicalIntervals；tokio/core/?/async宏不按日志分类。

## S4 控件决策表

同一 decision 分区与同一 BB 范围只表达一次。局部控件放在 `controls`；跨 action 的范围放在 `readingScopes`，必要时由无正文的 `originControlRef` 绑定，不再画第二个框。

| 选择 | 判据 | guard 绑定写法 | `submit_order` 虚构示例 |
|---|---|---|---|
| `alt` | 一个业务 decision 形成完整、互斥的替代分区 | `readingScopes[].decision.variable` 指向 decision；每个 `branches[].when` 绑定互斥值域，`branches[].members` 只放该分支成员；不再为同一分区建 opt | “库存充足”进入扣款，“库存不足”返回缺货结果 |
| `opt` | 只有一侧业务成员可选，另一侧只绕过 | `granularity.memberGuards[]` 写 `decisionRef`/`takeValues`/`skipValues`/`condition`/`skip`/`controlRef`；跨 action 时再写 `readingScopeRef`，并由 opt scope 的 `originControlRef` 指回控件 | 仅在开启“发送确认”时执行通知；关闭时绕过通知 |
| `loop` | loop 成员由 MIR 真实循环动作在阅读顺序中的最小连续区间派生；额外成员为环内出口，须证明不能回入口且所有路径只到 commonAfter 或已认证终点，否则失败并拆成精确范围。loop-exit 只指向 commonAfter 或已认证终点，进入环内出口动作使用普通 branch。 | `readingScopes[].decision` 绑定继续/退出值；`repeat.continueValues` 与 `repeat.exitValues` 互斥，execution 分支用同一 decision 证据绑定回边和出口；外部后继只放 `commonAfter` 或终止表达 | 订单行校验失败后修正当前行并重新校验；当所有行合法时退出循环进入扣款 |
| 不建控件 | 分支只是 poll/cleanup/unwind 等技术机制，或条件与结果已在现有可见表达中完整呈现 | 技术 decision 在 `granularity.decisions`（sourceInventory由S4投影） 记 `disposition: "mechanism"`、`foldedInto`、原因与证据；已表达的 guard 不再绑定第二个 control | async 扣款的 `Pending`/恢复分支只保留为机制证据，不画业务 alt |

loop 成员由 MIR 真实循环动作在阅读顺序中的最小连续区间派生；额外成员为环内出口，须证明不能回入口且所有路径只到 commonAfter 或已认证终点，否则失败并拆成精确范围。loop-exit 只指向 commonAfter 或已认证终点，进入环内出口动作使用普通 branch。具体失败教训见 [acceptance.md 的 A48](acceptance.md#a48-教训)。

### 闭包/coroutine 去向

S2 selection.items逐条使用elements的`body:<identity>`稳定id，值为shown/technical/folded。S5只写交互数据；shown执行体endpoint绑定构造与消费调用，folded给真实源码理由；去向与BB归属由check_model核对。S5不再写innerBodies。

### 统一元素去向与本地函数

调用、闭包/coroutine 的去向与 MIR 理由只按 [信息保持规则](s2-authoring.md#信息保持规则唯一选择定义) 推导；技术证明、BB归属和消息覆盖由统一模型检查，不另写本地函数折叠清单。

## 源码原词

节点名称、条件、结果与边标签中，来自源码的函数、类型、字段、变量、枚举值、模块以及 session、sampling、history、hook、token 等术语大致保留英文原文并放入反引号；连接语用中文。这是写作规则，不增加机器检查。

## S7 agent 审阅

唯一输入：`INPUTS/ledgers/stage7-review.json`，形如 `{"items":[{"principle":"G2","check":"action_boundary_semantics","question_sha256":"原则报告给出的 question_sha256","subject_sha256":"当前 renderer-input.json SHA256","decision":"pass","rationale":"逐项的源码/MIR判断与理由","evidence":[{"path":"raw-body.json","sha256":"当前文件SHA256","pointer":"/basic_blocks/0"}]}]}`。每个被触发的正确性 review 单独写一项；核对该项提示所要求的全集、边界、路径及反例，引用当前 work 内证据及 JSON pointer（源码文本可省略 pointer）。证据缺失、过期、无法决断均决定 fail 并记原因；写法提示直接 warning。修文案/结构后重跑 S7，重新核对改变的问题和证据；不用旧结论充当前证据。

浏览器类 review 在 rules.json 声明 environment_gate。环境不可用时 agent 只能引用该 gate 当前 `status:not-run` 的执行回执并决定 `warning`，说明未运行原因；这不代表浏览器通过。S7 acceptance 因对应环境 gate 未通过仍为 failed，S8 不发布；只用 rerun-env 补环境项。其他正确性 review 仍必须 pass/fail。
