# 展示原则检查协议

阶段 2/5 写语义判断，阶段 6 只消费这些判断，阶段 7 运行 `scripts/check_principles.py` 并审查其 `review_items`。机器通过只证明所列结构约束，不证明业务选集正确。检查器不读取任何基线答案，也不按输出数量判定语义。

## 阶段 2：选择依据

在 `stage2/hierarchy.json` 的业务节点保存 `selection_basis`（职责、边界、源码/路径依据）。`ledgers/stage2.json.selection.items` 是唯一去向表；输出 selection.json 由它及层级推导。

```json
{"items":[{"id":"call:7","disposition":"folded","reason":"借用传入请求的只读字段视图。","semanticRole":"adapter","sourceRefs":["call:7"]}]}
```

每个Call和body元素恰好shown/technical/folded；分类及MIR理由只按 [信息保持规则](s2-authoring.md#信息保持规则唯一选择定义) 生成，不再使用本地callee类别清单或作者自述。ownerActionRef由层级推出，残留值必须相等。shown执行体以真实构造/消费证据连接交互，包装不重复计数；库内部操作使用原生self消息。

## 阶段 5：唯一成员与完整身份

`external.json` 保留 `identity_registry`（源 actor 记录，含 actorId、sourceNodeRef、bodyRef、ownership/definition 依据）及 `business_members`。成员使用 `id`、`invocationRef`、`bindingRef`、`purposeRef`、`targetActorRef`、`stageRole`、`basis`、`ownerActionRef`、条件/结果及证据。规范键为目的、实际端点、语义阶段、调用依据；三个层只引用成员 ID。`clauses` 中的必要关系有稳定 `id` 或 `invocationRef`。

`actors` 是全部业务消息端点的祖先闭包，不能用当前展开状态筛选。`facts/definitions-index.json` 若提供，用原 definition 的 body_available、原名及 ownership 校验身份；不完整索引只说明缺证据，不能证明无 body。原 trait poll 绑定保留在事实中，业务端点必须解析实际被等待对象。

## 阶段 6：源语义→转换结构→可见表达

写 `stage6/principle-lineage.json`：

```json
{
  "relations": [
    {
      "sourceRef": "semantic-relation-id",
      "evidenceRefs": ["m7.0"],
      "representations": [
        {"kind": "control", "ref": "control-id"},
        {"kind": "outcome", "ref": "branch-id", "field": "outcome"}
      ]
    }
  ]
}
```

清单覆盖 `stage4/edges.json` 的全部语义关系及 `stage5/external.json.clauses` 的必要关系。技术证据不放 stage4 业务集合。每个 sourceRef 唯一，保留独立来源，多个关系允许指向同一准确摘要。

`representations.kind` 支持：

| kind | ref / 可见性条件 |
|---|---|
| message | messageId，须由实际挂载的 control 引用 |
| control | control id，须挂在 action、phase boundary 或 root 上；必须有可显示内容 |
| readingScope | scope id，成员及条件可解析 |
| outcome | branch id 的 `outcome`，或 control id 的 `skip` / `notes` / `after`；field 必须指向非空展示文字 |
| destination | execution edge id，须有 readingScopeRef 和 evidence，符合 loop-markers 的源 action/decision owner 与可见目的地投影规则 |
| summary | 阅读节点 id，存在非空、kind 匹配的 summary；表达内容需审查 |

不能填写证据文件指针作为可见目标。程序验证引用、挂载、分支值和必要清单覆盖；是否准确表达条件、结果和去向仍须逐项审查。只写 source-record 不算完成。

每个 execution decision 用 `controlRef + branchBindings` 或 `readingScopeRef` 绑定实际展示。逐值覆盖，包括跳过、循环继续/退出和真实提前终止；局部调用 opt 不能替代跨 action 的条件范围。

## 阶段 7：报告解释

- `checks`：机器项的 pass/fail，缺少所需中间产物为 review；证据包含总数、失败数和定位示例。噪声按字段计数，类别可重叠，不把类别之和当唯一节点数。
- `review_items`：每条原则的语义/页面审查，加上缺输入、启发式命中等待确认项。缺证据不能改写为通过。
- `principles[].status`：只汇总机器项；`review_required` 与 `acceptance_complete=false` 独立报告。审查结论由 Agent 写入 `stage7/acceptance.json`，不让检查器自证。
- `counts`：顶层与递归 actor/control、消息对、await 标记、request stage 与阅读层计数。无 awaitRef 不等于同步；需结合成员生命周期核对。没有固定阈值或目标配额。

历史产物可只读运行；缺 stage 账本列为审查限制。旧基线不是豁免规则的白名单：真实缺陷如详情引用缺 BB、goal 成员不一致仍报告失败，另解释旧格式/缺证据与实际缺陷。
# 粒度账本

阶段 2 建 `stage2/granularity.json`，阶段 4/5 补全引用，阶段 6 保持源记录身份并填投影映射。此账本是语义判断的可核验依据，不属于 renderer schema。

- `businessFacts[]`：`id, kind, claim, actionRef, evidenceRefs`。kind 为 `call/decision/state_change/business_result`；每个 action 至少一项独立事实，机制 Call 的存在不能充当业务事实。evidenceRefs 使用可解析的 `bbN`、`call:N`、`mN.K`、execution evidence ID 或 `source/<文件名>:起行-止行`；引用必须在本次输入中存在。
- `boundaries[]`：`ref, purpose, completion, entry, exit, evidenceRefs`，覆盖每个 goal 和 phase；completion 解释成员共同完成了什么，entry/exit 解释实际交接。
- `decisions[]`：`id, disposition, evidenceRefs`；此清单的 disposition 仅为 business/mechanism（selection.items 使用 shown/technical/folded）。业务判断带 `decisionRef`；机制判断带 `foldedInto` 和理由。以源码条件和 MIR 分叉为起点，逐项核对是否影响业务成员/状态/结果；不得仅从已生成 execution 倒抄清单。
- `memberGuards[]`：`invocationRef`（调用）或 `memberActionRefs`（本地业务成员），以及 `decisionRef, takeValues, skipValues, condition, skip, controlRef, evidenceRefs, bypassEvidenceRefs`；只收真实可跳过的成员，列出 take 和 bypass 源路径。单侧可选成员必须由可见 opt control 覆盖；跨成员时另填 `readingScopeRef`。完整互斥业务替代可登记 `alternativeBranchRef`，指向同一 decision 的 alt readingScope 分支；各分支值域须完整互斥、业务成员非空且不重叠，takeValues 与选定分支一致，skipValues 是其补集，condition 与分支条件一致，成员或调用 owner 必须属于该分支。空分支绕过不适用此例外，仍须 opt。纯本地成员用 opt readingScope 的 `originControlRef` 连接对应 opt control。证据不足记 review；存在已证实的 guard 成员却没有 opt control 记 fail。
- `ranges[]`：`id, kind, memberActionRefs, decisionRef, readingScopeRef, evidenceRefs`；记录源业务循环与连续条件范围，局部仅含消息的范围改指 `controlRef` 并用 `invocationRefs` 代替 `memberActionRefs`。共享后继单独记录且不属于范围。提前 return 后的全部剩余流程不自动形成一个巨大 opt；共享尾部必须逐路径审查；opt/alt 必须是阅读树中的连续区间，不连续条件须拆成多个精确连续范围。
- `purposeGroups[]`：`id, projectionRef, object, purpose, result, evidenceRefs`，并记录适用阶段、条件、成员、真实端点；解释同 goal 内拆组或跨 goal 关联的原因。

G 检查的边界：G1 核对消息对唯一 action；G2 核对独立事实记录；G3 核对 goal/phase 边界字段；G4 核对已选 decision 值和源清单引用；G5 核对声明 guard 的消息范围；G6 核对范围账本，图推断的条件入口只报 review；G7 核对每个业务 invocation 在所属 goal 的目的投影；G8 核对请求/完成先后；G9 核对目的组依据。字段齐全不证明语义正确。历史缺账本记 review；新运行必须补齐并逐项审查。G6 从 execution 推出的其他可达范围仅是审查候选，不能把整个幸存尾部或共享尾部判成漏 scope。



### 声明端点（动态调用）

业务协作的静态 callee 若只是可调用声明，使用 Actor.kind=declaration，declarationRef=sourceNodeRef=完整声明 hash，implementationStatus=unresolved，禁止 bodyRef。按 definitions ownership 建 crate/module 祖先，按调用身份保留 request/return、binding 和 invocation。实现未知须留在阶段5审查记录；正常完成只描述调用者观测到的结果，不推断实现内部效果。P6 检查原始声明行、身份唯一、祖先及配对，P9 按声明身份去重。该有限结论可验收；缺声明或调用证据仍失败。

### S5 内层 body 覆盖

S5不再写内层体去向副本。check_model读取elements与S2唯一去向表，shown的闭包/coroutine必须有真实endpoint及绑定构造/消费调用的request/return；technical必须与构造/消费BB证明一致；folded保留源码理由。


## 混合 BB 的明确代价

渲染器按整 BB 展示。业务与 tracing 混合的 BB 整块留在业务 group，日志操作以 S1 elements 的 technicalIntervals 证明投影到 S2 granularity.technicalIntervals（statementIndices 与 terminator），S5/S7 检查投影相等。页面仍显示该 BB 的日志细节，不能声称实现了语句级隐藏。仅有 core 宏、? 或 async 脱糖的混合 BB 保持业务，不记日志技术区间。
