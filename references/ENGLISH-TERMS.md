# English Terms Preservation - 必须保留的英文术语

> 基于：rules.json（R01–R11）
> 原则：保持与Rust/MIR/harness原语的一致性，不翻译核心技术术语

---

## 目录

- [语义边类型](#1-语义边类型semantic-edge-kinds)
- [MIR/BB 结构术语](#2-mirbb-结构术语mir-structure-terms)
- [调用生命周期术语](#3-调用生命周期术语call-lifecycle-terms)
- [Converter 字段术语](#4-converter-字段术语converter-field-terms)
- [验证术语](#5-验证术语validation-terms)
- [Rules.json 术语](#6-rulesjson-术语rules-terminology)
- [使用指南](#7-使用指南)
- [扩展术语](#8-扩展术语可添加但需保持一致性)

## 1. 语义边类型（Semantic Edge Kinds）

**必须保留英文** - 这些是 1.5 层语义的 kind 字段值：

```
goal_flow                    # 同阶段不同目标的流转
scope_entry                  # 范围入口
scope_handoff                # 范围交接
collaboration                # 外部协作
wait_annotation             # 等待标注
resume_annotation           # 恢复标注
result_annotation           # 结果标注
runtime_annotation          # 运行时标注
internal_member_relation    # 内部成员关系
```

协作卡片/摘要、owner 等待、awaitable 实例属于其他对象类型，不可作为 stage4 语义边 kind。技术生命周期词仅用于事实证据；业务展示完成统一使用 normal-return（含业务错误结果）。

**使用场景**：
- JSON的`kind`字段必须使用这些英文值
- 中文描述放在`label`和`purpose_heading`字段
- kind 枚举保持原值；展示中文句子可内嵌反引号括起的源码原词

---

## 2. MIR/BB 结构术语（MIR Structure Terms）

**基础层级**：
```
basic blocks (BB)           # 基本块
leaves                      # 叶节点（BB层）
groups                      # 组节点（Layer 2-5）
nodes                       # 通用节点引用
```

**接口字段**（flow-model.json）：
```
entry_blocks                # 组外进入的BB列表
exit_blocks                 # 组内退出的BB列表
exit_edge_ids              # 有BB目标且离开容器的原边ID
terminal_event_ids          # 无BB目标的typed事件ID列表
port_transfer               # 端口传输（逐入口可达矩阵）
reachable_exit_blocks       # 从某入口可达的出口BB
reachable_exit_edge_ids     # 从某入口可达的跨容器原边ID
reachable_terminal_event_ids # 从某入口可达的typed事件
```

**原边字段**（raw MIR edges）：
```
edges                       # 边集合
flow_edges                  # 控制流边
entry_edges                 # 入口边
exit_edges                  # 出口边
successors                  # 后继列表
terminator                  # 终结器
statements                  # 语句列表
```

---

## 3. 调用生命周期术语（Call Lifecycle Terms）

**调用基础**：
```
binding                     # 调用绑定（唯一标识符）
caller                      # 调用方BB
callee                      # 被调用方body
call                        # 调用动作
return                      # 返回动作
normal                      # 正常返回路径
unwind                      # 异常展开路径
```

**异步协议**（rules.json R06-R07）：
```
construct_future            # 构造Future
poll                        # 轮询操作
Pending                     # 挂起状态（未完成）
Ready                       # 就绪状态（完成）
saved_state                 # 保存状态
resume                      # 恢复执行
IntoFuture                  # Future转换trait
Pin                         # 固定指针
```

**异常处理**（typed events）：
```
UnwindResume                # 恢复展开
UnwindTerminate             # 终止展开
UnwindContinue              # 继续展开
Unreachable                 # 不可达
```

---

## 4. Converter 字段术语（Converter Field Terms）

**来源字段**（阶段 2 的 hierarchy.json）：
```
<body名>                    # 源 body key（按本次 body 参数化）
nodes                       # 节点树
phase_order                 # 阶段顺序
participants                # 参与者树
root                        # 根节点
children                    # 子节点列表
```

**投影字段**（renderer-input.json）：
```
actors                      # 参与者列表
messages                    # 消息列表
phases                      # 阶段列表
controls                    # 控制结构列表
execution                   # 执行图
readingScopes              # 阅读范围
artifact                    # 证据引用
evidence                    # 证据内容
```

**生命周期字段**：
```
request                     # 请求消息
return                      # 返回消息
business-completion         # 业务完成
business-request            # 业务请求
awaitRef                    # await引用
bindingRef                  # binding引用
```

---

## 5. 验证术语（Validation Terms）

**检查类型**：
```
schema_version              # schema版本
mechanical                  # 机器验证
agent                       # agent 审阅
mechanical_and_agent        # 混合验证
```

**验证接口**（validation.json）：
```
passed                      # 通过
failed                      # 失败
candidate                   # 候选
evidence                    # 证据
witness                     # 见证
rationale                   # 理由
```

---

## 6. Rules.json 术语（Rules Terminology）

**规则引用**（保留原文）：
```
R01: 范围与事实基线 (scope and baseline)
R02: 先写本层主张，再对应下层事实 (claim then evidence)
R03: 同层流程与入口角色 (flow and entry roles)
R04: 逐层折叠与唯一默认表达 (fold and default expression)
R05: 外部协作按对象、目的、结果表达 (collaboration semantics)
R06: 调用生命周期和真实归属 (call lifecycle)
R07: Pending与恢复协议 (Pending and resume protocol)
R08: EX/RET层级与结果标注 (EX/RET hierarchy)
R09: 覆盖、未覆盖与统计口径 (coverage accounting)
R10: 最终案例作回归标准 (regression standard)
```

**关键概念**（中英对照）：
```
entry / 入口
exit / 出口
boundary / 边界
handoff / 交接
collaboration / 协作
resume / 恢复
annotation / 标注
summary / 摘要
member / 成员
witness / 见证
```

---

## 7. 使用指南

### ✅ 正确示例

**JSON结构**：
```json
{
  "kind": "goal_flow",
  "label": "容量准备完成，进入输入视图准备",
  "source": "goal:capacity",
  "target": null,
  "boundary": {
    "other_scope_or_goal_ref": "goal:requirements"
  }
}
```

**文档描述**：
```markdown
该edge的kind为`goal_flow`，表示从容量准备目标流向下一个阶段。
```

### ❌ 错误示例

**混用中英文**：
```json
{
  "kind": "目标flow",        // ❌ 错误：kind必须是英文
  "label": "goal_flow",       // ❌ 错误：label应该是中文业务描述
}
```

**翻译核心术语**：
```markdown
该边的类型为"目标流转"（goal_flow应该保持英文）   // ❌
```

### 规则总结（按已确认尺度）

| 位置 | 用什么语言 | 示例 |
|------|-----------|------|
| body / 列名 / 泳道名 | **原函数名**（英文） | `process_request`、`handle_inputs` |
| 深度 1.5 / 深度 2 的节点名与 edge 描述 | **中文句子**，内嵌源码术语 | "容量准备完成，进入需求准备" |
| JSON 的 kind / type / 技术字段名 | **英文** | `goal_flow`、`entry_blocks`、`port_transfer` |

补充细则：
1. 中文句子里保留 hook / session / sampling / Guardian / MIR / BB 等**源码术语**，不翻译成"钩子""会话""采样"
2. 技术字段名（entry_blocks, port_transfer 等）保持英文，不造中文别名
3. 文档引用首次出现用中英对照，后续可只用英文
4. 代码注释：技术术语保持英文，业务含义可用中文

---

## 8. 扩展术语（可添加，但需保持一致性）

新增术语必须：
1. 先在此文档登记
2. 说明使用场景
3. 提供中英对照
4. 标注首次引入的phase/version

**示例**：
```
shared_tail                 # 共有尾部
                                                      # 使用场景：标识多入口共享的收尾逻辑
```


## 源码原词与中文连接语

节点名称、条件、结果与边标签中，来自源码的函数、类型、字段、变量、枚举值、模块以及 session、sampling、history、hook、token 等术语大致保留英文原文并放入反引号；连接语用中文。这是写作规则，不增加机器检查。
既有 kind/字段枚举保持合同原值；展示文案中的源码术语遵循本节。
