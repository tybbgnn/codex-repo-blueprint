# 运行失败与继续验收

遇到失败先读 failure.json 和原始证据，再分类；分类以原因而非脚本名称为准。

1. **账本错**：分层、BB 归属、消息或证据错误，修对应账本，从最早受影响阶段重新 validate → build。同一账本错误最多三次。
2. **环境缺失**：Playwright 未安装、PLAYWRIGHT_PATH 未设、浏览器启动被沙箱拒绝等，将该检查保留为 `passed:false,status:not-run`，记录原因与补跑命令。继续所有独立检查，产出 acceptance.json 和 e2e-summary.md；S7 build 不因此抛出或 stop。检查未运行不算通过，S8 补跑前以 failed 结束，环境可用时执行官方补跑命令。
3. **skill 机制 bug**：先以 MIR、源码或合同证明缺陷；只在 OUTPUT/run-fixes/ 写修正脚本，不改安装包。保留全部原则与原阈值、白名单、独立检查。注册后仅受影响阶段使用修正模块；其余阶段用原包。S7 仍对产出执行全部门禁。

注册修正（OUTPUT 是本次 --out）：

```sh
python3 -B scripts/run_fixes.py --out OUTPUT --stage 5 --script stage_engine.py \
  --fixed OUTPUT/run-fixes/stage_engine.py --bug '缺陷描述' \
  --judgment '从证据得到的判断' --change '通用机制修正' --evidence OUTPUT/work/raw-body.json
```

随后照常运行 blueprint.py 的 validate 和 build。runner 校验修正脚本、原脚本、证据 SHA；加载相应阶段的修正模块，并在 acceptance 和 e2e-summary 列出完整偏离。修正脚本应维持原模块接口，依赖从原包导入；不得修改检查来掩盖错误。`run_fixes.py` 和验收/交付生命周期不能自我替换。记录在 OUTPUT/run-fixes/deviations.json 与 deviations.md；有多项证据时重复 --evidence。修改修正脚本后必须重新登记，旧记录保存在 .history。

例如：S5 canonical_path 命中 AssocFn 与 Field 时，以 call 的 MIR 实体身份与可调用种类解析；S6 未声明 display 时按源码身份生成合同要求的对象。这两类修复都必须重新运行原始输出检查。

最终状态为 `passed`、`passed-with-deviations(N)` 或 `failed`；有未运行或失败检查仍为 failed。缺抽取范围的 MIR 另外标注“通过，但有 N 项缺 MIR”，绝不能称为干净通过。S3 自动锁定，S7 agent 决定必须附当前证据。

## 只补跑未运行环境检查

```sh
python3 -B scripts/blueprint.py rerun-env --out OUTPUT
```

仅重跑 acceptance 中 browser、batch、batch-reference 的 not-run 项；batch 已成功的子检查保留。已有原则、agent-review、偏离、缺 MIR 和其他检查原样保留，更新 acceptance 与 e2e-summary；失败项仍为 failed。环境始终不可用时写清证据后结束，不挂起。
