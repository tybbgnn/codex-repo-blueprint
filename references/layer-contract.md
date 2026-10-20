# Depth 层级合同（生成文件）

唯一来源：stage-io.json；生成器：scripts/generate_stage2_contracts.py。

## 层级

|depth|名称|ID 形式|来源|
|---|---|---|---|
|0|ROOT|ROOT|S2 ownership; S6 semanticRoot|
|1|phase|P{two-digit sequence}|S2 ledger → S6|
|1.5|goal|sem:P{nn}:{short English name}|S2 ledger → S6|
|2|action|P{nn}/A{two-digit sequence}.{first BB number}|S2 ledger → S6|
|3|BB组|{action id}/C{first BB number}|S2 bb_group → S6 attach_source|
|4|BB|bb{N}|S1 facts → S2 derived leaves → S6|

## 渲染投影

controls and messages attach to actions through action.controlRefs; they are renderer projections, not hierarchy layers.
