# 展示原则

## 目录

- [术语尺度](#术语尺度)
- [P1–P14](#p1p14)
- [控件唯一性](#控件唯一性)

## 术语尺度

| 位置 | 写法 |
|---|---|
| body 名、泳道名、列名 | 原函数名，如 `process_request` |
| 1 / 1.5 / 2 层的节点名、条件、结果、边标签 | 中文句子，内嵌源码术语 |
| JSON 的 kind、type、技术字段名 | 英文 |

语义边 kind 只能是：`goal_flow` `scope_entry` `scope_handoff` `collaboration` `wait_annotation` `resume_annotation` `result_annotation` `runtime_annotation` `internal_member_relation`。runtime/wait/resume 记录只留证据，不进入 stage4 业务选集。

调用生命周期术语：`construct_future` `poll` `Pending` `Ready` `normal_return` `unwind` `saved_state` `resume`。

任何中文结论都必须带 BB 号、原边 ID、terminator 或源码行号证据。不允许在转换器或渲染器中写死中文文案。

## P1–P14

1. **P1** 按独立业务含义选择节点，禁止按调用次数、中心度或配额选取；完整 BB 事实树与 phase→goal→action 阅读树分离。
2. **P2** 顶层按真实执行顺序阅读；分支、汇合和循环在顺序中表达，不按功能类别重排。
3. **P3** 下层事实决定边的存在、方向和条件，本层语义决定措辞；BB 边与逐调用 binding 只作证据。
4. **P4** 每条边只说自己的条件与结果；同端点的不同原边 ID、条件、路径和 binding 成组保留。
5. **P5** EX/RET 与共享 cleanup/return 容器退出 1/1.5/2 层展示节点和技术线；真实业务出口以结果注释表达。
6. **P6** 先按业务目的分组，再绑定真实参与者端点；同一 body 一个参与者，每次调用有独立身份和 request/return 对。
7. **P7** 业务展示去掉 async 机制、锁与迭代器、代码形式条件、底层编号、调试过程、分析器备注、重复长标签、被当内容的证据/替换字段；保留业务循环与 pending-input。
8. **P8** 没有独立业务地位的机制对象折叠进 action 或条件，不单独成列；不能按名字或 crate 黑名单机械排除。
9. **P9** 三个层引用同一个业务成员集合，不各生成一份调用副本。
10. **P10** 每项必要业务关系须落到 message、alt/opt/loop 范围、结果或目的地标记；逐项对账“源语义→转换结构→可见表达”。
11. **P11** 共享尾部保留目的地标记与循环范围，不画独立长返回线；只有符合窄证书的 `terminalOnly` 才可省略 `commonAfter`。
12. **P12** goal 继承成员 action 及真实入口/出口；goal 内部关系随成员折叠，不机械变成 goal 自环。
13. **P13** body 使用原函数名；goal/action/edge 使用中文并保留源码术语。
14. **P14** 详情常驻完整函数源码；goal/action/execution 节点或 BB组选择高亮其 BB 对应的全部源码范围，BB 列表默认折叠；phase 仅清除选择。

## 控件唯一性

同一 decision 分区与同一 BB 范围只表达一次。阶段 4 用 `scripts/canonicalize_controls.py` 的 `canonicalize(presentation, memberGuards, actionIds, readingSummaries)` 归并相邻、同 owner、同 guard 的调用控件，保留调用顺序、独立 invocation 和证据。

跨成员范围的 `originControlRef` 是无正文的 opt 绑定，由 readingScope 在成员范围绘制；不在判断 action 下再放空框。局部 opt 通过 decision 的 `takeValues/skipValues` 绑定完整互斥分区。相同端点的不同 guard 或调用身份仍保留。

分支条件已包含结果时省略重复 outcome；notes 只记录新增业务信息。空分支和 continue/terminate effect 仍须显式 outcome。不得靠改 ID、改写同义标题或删除路径来使重复计数归零。
