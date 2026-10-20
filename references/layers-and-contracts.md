# 层级与唯一契约

## 目录

- [6 层结构](#6-层结构)
- [原边 ID](#原边-id)
- [唯一契约与边界](#唯一契约与边界)
- [渲染投影](#渲染投影)

## 6 层结构

| depth | 层 | ID 形式（示例） | 由谁推出 |
|---|---|---|---|
| 0 | ROOT | `ROOT` | 全部 phase |
| 1 | phase | `P{两位序号}` | 若干 goal 或独立 bb |
| 1.5 | goal | `sem:P{nn}:{英文短名}` | 若干 action |
| 2 | action | `P{nn}/A{两位序号}.{首个BB号}` | 若干 BB组 |
| 3 | BB组 | `{action id}/C{首个BB号}` | 顺序相连的 BB |
| 4 | BB | `bb{N}` | MIR 原始事实 |

## 原边 ID

原边 ID 用 `m{源bb}.{后继序号}`，例如 `m1.0`、`m1.1`。CFG 按多重有向图处理：同一对（源，目标）可以有多条原边，原边 ID 与条件、binding 全程成组，不按端点去重。

## 唯一契约与边界

- **出口与终结事件**：`exit_edge_ids` 只存有 BB 目标、跨容器的原边；`terminal_event_ids` 只存 `facts/terminal-events.json` 中无 BB 目标的 typed 事件。`port_transfer` 分别使用 `reachable_exit_edge_ids`、`reachable_exit_blocks`、`reachable_terminal_event_ids`。
- **业务完成与异步机制**：业务消息完成统一用 `returnContracts.meaning=normal-return`，包括业务结果为错误；Ready、Pending、构造返回及 poll 返回只存生命周期证据。
- **输入指纹**：Rust 文件、规则文件、definition 行文件按完整字节 SHA256；大型 definitions/MIR 容器记录路径、总字节数、commit/身份和每个实际消费 JSON 切片的 offset、字节数、SHA256，明确 `hash_scope=slice`。
- **event macro closure pin**：宏 closure 原始 MIR 字节放在 OUT 内并由 `input-pins.json.event_macro_closures[]` 固定；路径不得逃出 OUT，生成器和独立检查器都重新读取并哈希原始字节。
- **async-shell prelude pin**：`raw-body.json` 保存 inner；shell 原始 MIR 放在 OUT 内并由 `input-pins.json.async_shell_prelude` 固定。序言 BB 与有效技术 BB 必须不相交，并集恰为 shell 全部 BB。
- **kind 词表**：stage4 语义边只使用九种 kind；runtime/wait/resume 只存事实证据。renderer control/message/actor 的 kind 使用各自 schema 枚举。
- loop 成员由 MIR 真实循环动作在阅读顺序中的最小连续区间派生；额外成员为环内出口，须证明不能回入口且所有路径只到 commonAfter 或已认证终点，否则失败并拆成精确范围。loop-exit 只指向 commonAfter 或已认证终点，进入环内出口动作使用普通 branch。
- **跨阶段 scope**：alt/opt/loop 均允许跨 phase，成员必须是阅读顺序中的连续范围，父范围完整包含子范围，不得交叉、重排、复制阅读节点；共有后继必须在范围外且有路径证据。
- **主 body 与祖先闭包**：主 body 独立顶层且身份只出现一次；外部业务消息端点按 definitions ownership 保留 crate→module→body 祖先。
- **状态验证上限**：`execution.inconclusive` 是未完成验证，不是通过，不得删 decision/guard、切成独立测试或改 deliveryMode 规避。
- **预览与正式发布**：阶段 7 可组装候选站点运行检查；检查和审查关闭后，阶段 8 发布相同输入和渲染器。
- **ID 与源码精度**：内部 ID 只用于引用、data 属性和证据；展示使用业务 label。函数整体 span 不能充当 action/goal 精确归属证据。

## 渲染投影

BB组和 BB 保留事实包含关系与原 CFG 证据。controls 和 messages 经 `action.controlRefs` 挂在 action 上，只是渲染投影，不算独立层。
