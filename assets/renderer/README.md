# renderer（三层阅读 · 时序泳道）

阶段 8 候选保留本目录全部源码；`output_paths.py publish` 将最终页面发布到 body 的 `deliverable/`：

```
deliverable/
├── README.md
├── renderer-input.json / reading-summaries.json / basic-block-details.json
├── data.js
└── roundtrip/ index.html, style.css, app.bundle.js
```

双击发布后的 `roundtrip/index.html` 即可离线打开；也支持 HTTP。普通 script 加载内嵌 JSON 与 bundle，源模块开发模式仅在 HTTP 下 fetch。页脚 `../README.md` 同时适用于两种协议。

修改 renderer 源码后，使用本机 esbuild 重建：`ESBUILD_PATH=<已有 esbuild 模块> node scripts/build_browser_bundle.cjs`。`bundle-sources.json` 记录来源哈希，发布会拒绝过期 bundle。

## Producer invariants

Schema 只约束单字段形状；以下跨字段关系由 contract/execution 校验，生成者必须通过 `scripts/derive_contract_fields.py` 计算或复核。完整条件、正反例与负责阶段见 [rule index](../resources/rule-index.md)。

- `fixture` 深度等于 `{actors, messages: []}`；`initialState.expandedActorIds` 只含有非空 children 的 actor。
- `segments[].messages` 对全部 message ID 做一次且仅一次的分区。
- `controlOwners`、`messagePlacements`、`branchRoles` 与 controls 的实际遍历结果精确相等。
- purpose 的 invocationRefs/waitRefs 非空、唯一，且全部解析到真实 control `invocationRef`。
- `commonAfter.arrivals[].path` 精确为 alt 的非终止 branch ID、opt 的 `taken/skipped` 或 loop 的 `exit`。
- return contract 的 `branchRef` 等于该 return placement 的最后一个 branchPath；空路径对应 null。
- evidence quote 是所引用 artifact content 的逐字子串；claim 的 subject/targets 均可解析且 conditions 已规范化。
- prelude node 在除 `id`/`label`/`distinctionReason` 外字段集相同、`lineRanges` 深相等且其他字段相等时是同一内容；`basicBlockRefs` 的值不构成区别。此类节点必须合并，或每个节点写非空 `distinctionReason`。多 action goal 写 `mergeReason`；stage-2 账本证明相邻 goals 共享 completion contract/entry mode 时，每个 goal 写 `splitReason`。

- 契约校验：`node -e "import('./contract.mjs').then(m=>m.assertInput(JSON.parse(require('fs').readFileSync('renderer-input.json'))))"`，失败会抛出带错误码与 JSON 路径的异常
- 交互：侧栏常驻完整函数源码；非空 async-shell `prelude` 先显示“入口（shell）”，其节点与 goal/action、execution、BB组共用源码高亮和 `basic-block-details` 事实。prelude/relation/technical ledger 只接受 `shell:bbN`；主流程只接受 `bbN`，同号也不互相解析。属性字段行仅由 shell prelude 支撑；phase 清除选择但保留源码。

- 标准库交互冒烟：`node --experimental-vm-modules <renderer目录>/smoke.mjs <site目录> <报告路径>`。执行真实模块与点击 handler，检查三层摘要替换、全部消息、scope、完整源码、选择高亮与 phase 清除高亮；这是最小 DOM 检查，不声称浏览器像素布局已验证。

## Source contract

`functionSource` contains `file`, `sourcePath`, `definitionRef`, inclusive `startLine`/`endLine`, and `lines` (one string per source line, including blanks). Resolve async coroutine ownership to the actual function definition so the signature is included. `lines.length` must equal `endLine - startLine + 1`.

Prelude/phase/goal/action/execution nodes and `sourceGroups` (the BB groups) carry `basicBlockRefs` and `lineRanges: {startLine, endLine}[]`. Real-flow requires sorted, merged ranges within the function. A node without a precise semantic operation span records `sourceRangeReason` and an empty array; the provenance checker reproduces that absence using the generator. Goal/action/execution coverage over 25% of the inclusive function lines requires an explicit reviewed `broadRangeReason`; phases are exempt. Synthetic fixtures may omit source mappings. The converter calls `scripts/source_ranges.py:attach_source`; the principle checker compares the payload with the local definition, source and BB facts. The browser consumes these mappings without inferring source spans or changing graph semantics.

`showBasicBlocks(nodeId)` is the shared selection entrypoint. The execution/BB-group picker uses it; graph widgets can expose `data-execution-node` or `data-bb-group`. Selecting a phase clears highlights. Re-rendering the diagram preserves source scroll when selection is unchanged. The code pane applies wheel deltas synchronously so Chromium cannot replay an older wheel animation after a new selection; browser pinch/zoom and keyboard scrolling retain their native behavior.

Run `node renderer/test-source-contract.mjs <renderer-input.json>` for mapping mutations. Browser checks: `PLAYWRIGHT_PATH=<playwright module> BROWSER_PATH=<optional Chromium executable> node scripts/test_sidebar.cjs <roundtrip URL> <screenshot directory>`. This verifies scrolling with real geometry, overlapping wheel/selection/redraw across animation frames, and HTTP footer links; the minimal DOM smoke does not. `node renderer/test-footer-links.mjs` also checks that each local footer target ships in the renderer package.

The shared `classification-registry.mjs` defines exception kinds and required fields. The renderer checks source-less shape only; `scripts/classification_registry.py` authenticates MIR proofs. Independent decision/header verification is `scripts/verify_source_evidence.py`, run by P14, not by the browser.

Semantic labels occupy dedicated DOM slots. Smoke compares them exactly with declared labels (source terms may equal internal IDs). Unnamed local alternatives receive an owner-based result heading, phases show semantic titles and ordinal rails, and source intervals have compact numbered line markers. Reading headers wrap within the viewport with measured row heights; actor tooltips expose full semantic names.

发布与离线回归：`node renderer/test-file-protocol.mjs <renderer-input.json>` 会发布临时 fixture，在默认 Chrome 安全设置下验证 file:// 和临时 HTTP 端口，并检查三份内嵌数据、节点、sidebar 和相对链接。`batch_selftests.py` 包含此回归；测试资料保留供检查，HTTP 服务自动关闭。
