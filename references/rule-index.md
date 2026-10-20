# Rule index

## 目录

- `page.*`：浏览器页面与交互合同
- `execution.*`、`control.*`、`scope.*`：执行图、控制结构与作用域合同
- `output.*`、`publish.*`：输出闭包与发布合同
- `source*`、`evidence.*`、`attribute-*`：源码归因与证据合同
- `shape.*`、`id.*`、`identity.*`、`actor.*`：结构、标识与 actor 合同
- `P*`、`G*`、`C*`：原则、目标与检查项
- 其余条目按下方 canonical key 直接检索。

### page.bbExpansion
Aliases: -
Enforced: tests/test_file_protocol.cjs:13
Condition: After clicking `.bb-blocks summary`, `.bb-blocks.open` must be true.
Stage: Stage 8
Required producer fields: rendered `.bb-blocks summary` and details open state
Pass example: Click changes open from false to true.
Fail example: Click leaves open=false.

### page.exactEmbeddedData
Aliases: -
Enforced: tests/test_file_protocol.cjs:13
Condition: For renderer-input.json, reading-summaries.json, and basic-block-details.json, `window.__BLUEPRINT_DATA__[name]` must deep-equal the parsed deliverable file.
Stage: Stage 8
Required producer fields: window.__BLUEPRINT_DATA__ and the three deliverable JSON files
Pass example: Embedded renderer-input phases `[p1]` equals the file phases `[p1]`.
Fail example: Embedded phases `[]` differs from file phases `[p1]`.

### page.http200
Aliases: -
Enforced: tests/test_file_protocol.cjs:13
Condition: Under HTTP, every non-data linked resource GET status must equal 200.
Stage: Stage 8
Required producer fields: HTTP href/src URLs and response status
Pass example: GET `/README.md` returns 200.
Fail example: GET `/README.md` returns 404.

### page.localFilesExist
Aliases: -
Enforced: tests/test_file_protocol.cjs:13
Condition: Under `file:`, every non-data linked URL must resolve to an existing regular file.
Stage: Stage 8
Required producer fields: file: href/src URLs and filesystem stat result
Pass example: `file:///site/README.md` resolves to a regular file.
Fail example: `file:///site/missing.md` does not exist.

### page.noBrowserErrors
Aliases: -
Enforced: tests/test_file_protocol.cjs:13
Condition: The collected pageerror, console-error, failed-request, and response-status>=400 list must deep-equal `[]`.
Stage: Stage 8
Required producer fields: pageerror/console/requestfailed/HTTP>=400 error collection
Pass example: Collected errors are `[]`.
Fail example: Collected errors are `["404 app.js"]`.

### page.noJsonFetch
Aliases: -
Enforced: tests/test_file_protocol.cjs:13
Condition: No observed browser request URL may match `\.json(?:$|\?)`.
Stage: Stage 8
Required producer fields: captured browser request URLs
Pass example: Observed requests are index.html, app.bundle.js, and style.css.
Fail example: Observed requests include `/renderer-input.json`.

### page.phaseRenders
Aliases: -
Enforced: tests/test_file_protocol.cjs:13
Condition: After load, `#diagram .phase` count must be greater than 0.
Stage: Stage 8
Required producer fields: rendered `#diagram .phase` elements
Pass example: DOM contains one `#diagram .phase`.
Fail example: DOM contains zero phase elements.

### page.safeLocalPath
Aliases: -
Enforced: tests/test_file_protocol.cjs:13
Condition: Every requested pathname, decoded and resolved under deliverable root, must start with `root + path.sep`.
Stage: Stage 8
Required producer fields: HTTP request URL pathname and resolved deliverable root path
Pass example: Server root `/site`; request `/roundtrip/index.html` resolves to `/site/roundtrip/index.html`.
Fail example: Server root `/site`; request `/../secret` resolves to `/secret`.

### page.sameProtocol
Aliases: -
Enforced: tests/test_file_protocol.cjs:13
Condition: Every non-data anchor/script/style URL protocol must equal the page URL protocol.
Stage: Stage 8
Required producer fields: page URL and resolved href/src protocols
Pass example: An HTTP page references only HTTP assets.
Fail example: An HTTP page references `file:///tmp/app.js`.

### page.selectableGoal
Aliases: -
Enforced: tests/test_file_protocol.cjs:13
Condition: A goal with nonempty lineRanges must exist; clicking it must set `#selection[data-source-node]` to that goal ID.
Stage: Stage 8
Required producer fields: phases[].goals[].id/lineRanges and `#selection[data-source-node]`
Pass example: Goal `g1` has a range; click leaves selected ID `g1`.
Fail example: No ranged goal exists, or clicking `g1` leaves selected ID empty.

### page.sourceHighlight
Aliases: -
Enforced: tests/test_file_protocol.cjs:13
Condition: Selecting the ranged goal must produce `.source-highlight` count greater than 0.
Stage: Stage 8
Required producer fields: selected goal lineRanges and rendered `.source-highlight` elements
Pass example: Selecting `g1` renders one highlight.
Fail example: Selecting ranged `g1` renders zero highlights.

Each entry is normative. Aliases preserve executable report IDs while the eight safe merge groups share one index entry.

### C.endpointLabel
Aliases: C3.same_endpoint_label, C6.same_endpoint_label_edges
Enforced: scripts/audit_duplicates.py:163, scripts/audit_duplicates.py:216
Condition: The executable comparison is satisfied: `add('C3', 'same_endpoint_label', [a[0], b[0]], severity='info' if distinct else 'error',`.
Stage: Stage 7
Required producer fields: duplicate audit C inputs: controls/readingScopes/messages/phases/execution; reading-summaries units; basic-block-details blocks; endpointLabel
Pass example: Inputs `duplicate audit C inputs: controls/readingScopes/messages/phases/execution; reading-summaries units; basic-block-details blocks; endpointLabel` with state `declared label="处理请求"; rendered label="处理请求"` -> accepted.
Fail example: Inputs `duplicate audit C inputs: controls/readingScopes/messages/phases/execution; reading-summaries units; basic-block-details blocks; endpointLabel` with state `declared label="处理请求"; rendered label="process"` -> rejected.

### C1.duplicateAudit
Aliases: P7.duplicates_C1
Enforced: scripts/check_principles.py:394
Condition: The enclosing failure condition is false: `if reason: bad.append({'invocation': inv, 'kinds': dict(kinds), 'reason': reason}) bad += [{'pair': p, 'invocations': sorted(v)} for p, v in pair_inv.items() if len(v) > 1] self.result(principle, 'invocation_pair_integrity', bad, invocations=len(invocations))  def check_p7(self): duplicate_report = audit_duplicates(self.data, self.details, self.granularity, {'units': self.summaries}) for category, findings in duplicate_report['inventory'].items(): self.result('P7', 'duplicates_' + category,`.
Stage: Stage 7
Required producer fields: duplicate audit C1 inputs: controls/readingScopes/messages/phases/execution; reading-summaries units; basic-block-details blocks; duplicateAudit
Pass example: Inputs `duplicate audit C1 inputs: controls/readingScopes/messages/phases/execution; reading-summaries units; basic-block-details blocks; duplicateAudit` with state `values=["a","b"]` -> accepted.
Fail example: Inputs `duplicate audit C1 inputs: controls/readingScopes/messages/phases/execution; reading-summaries units; basic-block-details blocks; duplicateAudit` with state `values=["a","a"]` -> rejected.

### C1.repeated_decision_guard
Aliases: -
Enforced: scripts/audit_duplicates.py:148
Condition: The enclosing failure condition is false: `if ra and rb and ra['bbs'] & rb['bbs'] and not any(set(v['ids']) == {a, b} for v in found['C1']): add('C1', 'repeated_decision_guard', [a, b], decision=gs[a]['decisionRef'],`.
Stage: Stage 7
Required producer fields: duplicate audit C1 inputs: controls/readingScopes/messages/phases/execution; reading-summaries units; basic-block-details blocks; repeated decision guard
Pass example: Inputs `duplicate audit C1 inputs: controls/readingScopes/messages/phases/execution; reading-summaries units; basic-block-details blocks; repeated decision guard` with state `declared="a1"; observed="a1"` -> accepted.
Fail example: Inputs `duplicate audit C1 inputs: controls/readingScopes/messages/phases/execution; reading-summaries units; basic-block-details blocks; repeated decision guard` with state `declared="a1"; observed="missing"` -> rejected.

### C1.repeated_guard
Aliases: -
Enforced: scripts/audit_duplicates.py:134
Condition: The enclosing failure condition is false: `if overlap and (same_parent or nested or linked or a['actions'] & b['actions']): add('C1', 'repeated_guard', [a['id'], b['id']], title=a['title'], bb_overlap=sorted(overlap),`.
Stage: Stage 7
Required producer fields: duplicate audit C1 inputs: controls/readingScopes/messages/phases/execution; reading-summaries units; basic-block-details blocks; repeated guard
Pass example: Inputs `duplicate audit C1 inputs: controls/readingScopes/messages/phases/execution; reading-summaries units; basic-block-details blocks; repeated guard` with state `declared label="处理请求"; rendered label="处理请求"` -> accepted.
Fail example: Inputs `duplicate audit C1 inputs: controls/readingScopes/messages/phases/execution; reading-summaries units; basic-block-details blocks; repeated guard` with state `declared label="处理请求"; rendered label="process"` -> rejected.

### C2.alternative_action_summary_echo
Aliases: -
Enforced: scripts/audit_duplicates.py:124
Condition: The enclosing failure condition is false: `if ref in action_parent and same_text(branch.get('outcome'), summary_units.get(ref, {}).get('text')): add('C2', 'alternative_action_summary_echo', [scope['id'], branch['id'], ref],`.
Stage: Stage 7
Required producer fields: duplicate audit C2 inputs: controls/readingScopes/messages/phases/execution; reading-summaries units; basic-block-details blocks; alternative action summary echo
Pass example: Inputs `duplicate audit C2 inputs: controls/readingScopes/messages/phases/execution; reading-summaries units; basic-block-details blocks; alternative action summary echo` with state `declared="a1"; observed="a1"` -> accepted.
Fail example: Inputs `duplicate audit C2 inputs: controls/readingScopes/messages/phases/execution; reading-summaries units; basic-block-details blocks; alternative action summary echo` with state `declared="a1"; observed="missing"` -> rejected.

### C2.branch_condition_echo
Aliases: -
Enforced: scripts/audit_duplicates.py:103
Condition: The enclosing failure condition is false: `if b.get('outcome') and norm(b['outcome']) == norm(b.get('condition')): add('C2', 'branch_condition_echo', [cid, b['id']], field='outcome', layer='sequence')`.
Stage: Stage 7
Required producer fields: duplicate audit C2 inputs: controls/readingScopes/messages/phases/execution; reading-summaries units; basic-block-details blocks; branch condition echo
Pass example: Inputs `duplicate audit C2 inputs: controls/readingScopes/messages/phases/execution; reading-summaries units; basic-block-details blocks; branch condition echo` with state `branch.condition="ready"; branch.outcome="returns cached result"` -> accepted.
Fail example: Inputs `duplicate audit C2 inputs: controls/readingScopes/messages/phases/execution; reading-summaries units; basic-block-details blocks; branch condition echo` with state `branch.condition="ready"; branch.outcome="ready"` -> rejected.

### C2.duplicateAudit
Aliases: P7.duplicates_C2
Enforced: scripts/check_principles.py:394
Condition: The enclosing failure condition is false: `if reason: bad.append({'invocation': inv, 'kinds': dict(kinds), 'reason': reason}) bad += [{'pair': p, 'invocations': sorted(v)} for p, v in pair_inv.items() if len(v) > 1] self.result(principle, 'invocation_pair_integrity', bad, invocations=len(invocations))  def check_p7(self): duplicate_report = audit_duplicates(self.data, self.details, self.granularity, {'units': self.summaries}) for category, findings in duplicate_report['inventory'].items(): self.result('P7', 'duplicates_' + category,`.
Stage: Stage 7
Required producer fields: duplicate audit C2 inputs: controls/readingScopes/messages/phases/execution; reading-summaries units; basic-block-details blocks; duplicateAudit
Pass example: Inputs `duplicate audit C2 inputs: controls/readingScopes/messages/phases/execution; reading-summaries units; basic-block-details blocks; duplicateAudit` with state `values=["a","b"]` -> accepted.
Fail example: Inputs `duplicate audit C2 inputs: controls/readingScopes/messages/phases/execution; reading-summaries units; basic-block-details blocks; duplicateAudit` with state `values=["a","a"]` -> rejected.

### C2.message_free_label_echo
Aliases: -
Enforced: scripts/audit_duplicates.py:107
Condition: The enclosing failure condition is false: `if ts and not messages(c) and all(norm(t) in labels for t in ts): add('C2', 'message_free_label_echo', [cid], field=k, layer='sequence')`.
Stage: Stage 7
Required producer fields: duplicate audit C2 inputs: controls/readingScopes/messages/phases/execution; reading-summaries units; basic-block-details blocks; message free label echo
Pass example: Inputs `duplicate audit C2 inputs: controls/readingScopes/messages/phases/execution; reading-summaries units; basic-block-details blocks; message free label echo` with state `declared label="处理请求"; rendered label="处理请求"` -> accepted.
Fail example: Inputs `duplicate audit C2 inputs: controls/readingScopes/messages/phases/execution; reading-summaries units; basic-block-details blocks; message free label echo` with state `declared label="处理请求"; rendered label="process"` -> rejected.

### C2.missing_alternative_outcome
Aliases: -
Enforced: scripts/audit_duplicates.py:121
Condition: The enclosing failure condition is false: `if not branch.get('outcome') and (branch.get('effect') or ref not in action_parent or not summary_units.get(ref, {}).get('text', '').strip()): add('C2', 'missing_alternative_outcome', [scope['id'], branch['id']],`.
Stage: Stage 7
Required producer fields: duplicate audit C2 inputs: controls/readingScopes/messages/phases/execution; reading-summaries units; basic-block-details blocks; missing alternative outcome
Pass example: Inputs `duplicate audit C2 inputs: controls/readingScopes/messages/phases/execution; reading-summaries units; basic-block-details blocks; missing alternative outcome` with state `declaredRefs=["a1"]; observedRefs=["a1"]` -> accepted.
Fail example: Inputs `duplicate audit C2 inputs: controls/readingScopes/messages/phases/execution; reading-summaries units; basic-block-details blocks; missing alternative outcome` with state `declaredRefs=["a1"]; observedRefs=[]` -> rejected.

### C2.reading_summary_title_echo
Aliases: -
Enforced: scripts/audit_duplicates.py:191
Condition: The enclosing failure condition is false: `if label and (value == label or value.startswith(label + '；') or value.startswith(label + ';')): add('C2', 'reading_summary_title_echo', [uid], field='reading-summaries/text',`.
Stage: Stage 7
Required producer fields: duplicate audit C2 inputs: controls/readingScopes/messages/phases/execution; reading-summaries units; basic-block-details blocks; reading summary title echo
Pass example: Inputs `duplicate audit C2 inputs: controls/readingScopes/messages/phases/execution; reading-summaries units; basic-block-details blocks; reading summary title echo` with state `declared label="处理请求"; rendered label="处理请求"` -> accepted.
Fail example: Inputs `duplicate audit C2 inputs: controls/readingScopes/messages/phases/execution; reading-summaries units; basic-block-details blocks; reading summary title echo` with state `declared label="处理请求"; rendered label="process"` -> rejected.

### C3.adjacent_message_rows
Aliases: -
Enforced: scripts/audit_duplicates.py:173
Condition: The enclosing failure condition is false: `if any(f['ids'] == ids for f in found['C3']): continue distinct = (a.get('bindingRef') and b.get('bindingRef') and a['bindingRef'] != b['bindingRef'] and a.get('invocationRef') != b.get('invocationRef')) add('C3', 'adjacent_message_rows', ids, severity='info' if distinct else 'error',`.
Stage: Stage 7
Required producer fields: duplicate audit C3 inputs: controls/readingScopes/messages/phases/execution; reading-summaries units; basic-block-details blocks; adjacent message rows
Pass example: Inputs `duplicate audit C3 inputs: controls/readingScopes/messages/phases/execution; reading-summaries units; basic-block-details blocks; adjacent message rows` with state `declared="a1"; observed="a1"` -> accepted.
Fail example: Inputs `duplicate audit C3 inputs: controls/readingScopes/messages/phases/execution; reading-summaries units; basic-block-details blocks; adjacent message rows` with state `declared="a1"; observed="missing"` -> rejected.

### C3.duplicateAudit
Aliases: P7.duplicates_C3
Enforced: scripts/check_principles.py:394
Condition: The enclosing failure condition is false: `if reason: bad.append({'invocation': inv, 'kinds': dict(kinds), 'reason': reason}) bad += [{'pair': p, 'invocations': sorted(v)} for p, v in pair_inv.items() if len(v) > 1] self.result(principle, 'invocation_pair_integrity', bad, invocations=len(invocations))  def check_p7(self): duplicate_report = audit_duplicates(self.data, self.details, self.granularity, {'units': self.summaries}) for category, findings in duplicate_report['inventory'].items(): self.result('P7', 'duplicates_' + category,`.
Stage: Stage 7
Required producer fields: duplicate audit C3 inputs: controls/readingScopes/messages/phases/execution; reading-summaries units; basic-block-details blocks; duplicateAudit
Pass example: Inputs `duplicate audit C3 inputs: controls/readingScopes/messages/phases/execution; reading-summaries units; basic-block-details blocks; duplicateAudit` with state `values=["a","b"]` -> accepted.
Fail example: Inputs `duplicate audit C3 inputs: controls/readingScopes/messages/phases/execution; reading-summaries units; basic-block-details blocks; duplicateAudit` with state `values=["a","a"]` -> rejected.

### C4.duplicateAudit
Aliases: P7.duplicates_C4
Enforced: scripts/check_principles.py:394
Condition: The enclosing failure condition is false: `if reason: bad.append({'invocation': inv, 'kinds': dict(kinds), 'reason': reason}) bad += [{'pair': p, 'invocations': sorted(v)} for p, v in pair_inv.items() if len(v) > 1] self.result(principle, 'invocation_pair_integrity', bad, invocations=len(invocations))  def check_p7(self): duplicate_report = audit_duplicates(self.data, self.details, self.granularity, {'units': self.summaries}) for category, findings in duplicate_report['inventory'].items(): self.result('P7', 'duplicates_' + category,`.
Stage: Stage 7
Required producer fields: duplicate audit C4 inputs: controls/readingScopes/messages/phases/execution; reading-summaries units; basic-block-details blocks; duplicateAudit
Pass example: Inputs `duplicate audit C4 inputs: controls/readingScopes/messages/phases/execution; reading-summaries units; basic-block-details blocks; duplicateAudit` with state `values=["a","b"]` -> accepted.
Fail example: Inputs `duplicate audit C4 inputs: controls/readingScopes/messages/phases/execution; reading-summaries units; basic-block-details blocks; duplicateAudit` with state `values=["a","a"]` -> rejected.

### C4.repeated_reading_title
Aliases: -
Enforced: scripts/audit_duplicates.py:182
Condition: The enclosing failure condition is false: `if title: for a, b in combinations(ids, 2): add('C4', 'repeated_reading_title', [a, b], title=title, layers=[units[a][1], units[b][1]], bb_overlap=sorted(spans[a] & spans[b]))`.
Stage: Stage 7
Required producer fields: duplicate audit C4 inputs: controls/readingScopes/messages/phases/execution; reading-summaries units; basic-block-details blocks; repeated reading title
Pass example: Inputs `duplicate audit C4 inputs: controls/readingScopes/messages/phases/execution; reading-summaries units; basic-block-details blocks; repeated reading title` with state `functionSource L10-L12; lineRanges=[L10-L11]` -> accepted.
Fail example: Inputs `duplicate audit C4 inputs: controls/readingScopes/messages/phases/execution; reading-summaries units; basic-block-details blocks; repeated reading title` with state `functionSource L10-L12; lineRanges=[L9-L11]` -> rejected.

### C5.boilerplate
Aliases: -
Enforced: scripts/audit_duplicates.py:207
Condition: The enclosing failure condition is false: `if filler.search(norm(value)): add('C5', 'boilerplate', [uid], path=path, text=value)`.
Stage: Stage 7
Required producer fields: labels/titles/summaries/outcomes inspected by audit_duplicates filler regex
Pass example: Inputs `labels/titles/summaries/outcomes inspected by audit_duplicates filler regex` with state `action.label="提交响应"` -> accepted.
Fail example: Inputs `labels/titles/summaries/outcomes inspected by audit_duplicates filler regex` with state `action.label="处理相关逻辑"` -> rejected.

### C5.duplicateAudit
Aliases: P7.duplicates_C5
Enforced: scripts/check_principles.py:394
Condition: The enclosing failure condition is false: `if reason: bad.append({'invocation': inv, 'kinds': dict(kinds), 'reason': reason}) bad += [{'pair': p, 'invocations': sorted(v)} for p, v in pair_inv.items() if len(v) > 1] self.result(principle, 'invocation_pair_integrity', bad, invocations=len(invocations))  def check_p7(self): duplicate_report = audit_duplicates(self.data, self.details, self.granularity, {'units': self.summaries}) for category, findings in duplicate_report['inventory'].items(): self.result('P7', 'duplicates_' + category,`.
Stage: Stage 7
Required producer fields: duplicate audit C5 inputs: controls/readingScopes/messages/phases/execution; reading-summaries units; basic-block-details blocks; duplicateAudit
Pass example: Inputs `duplicate audit C5 inputs: controls/readingScopes/messages/phases/execution; reading-summaries units; basic-block-details blocks; duplicateAudit` with state `values=["a","b"]` -> accepted.
Fail example: Inputs `duplicate audit C5 inputs: controls/readingScopes/messages/phases/execution; reading-summaries units; basic-block-details blocks; duplicateAudit` with state `values=["a","a"]` -> rejected.

### C6.duplicateAudit
Aliases: P7.duplicates_C6
Enforced: scripts/check_principles.py:394
Condition: The enclosing failure condition is false: `if reason: bad.append({'invocation': inv, 'kinds': dict(kinds), 'reason': reason}) bad += [{'pair': p, 'invocations': sorted(v)} for p, v in pair_inv.items() if len(v) > 1] self.result(principle, 'invocation_pair_integrity', bad, invocations=len(invocations))  def check_p7(self): duplicate_report = audit_duplicates(self.data, self.details, self.granularity, {'units': self.summaries}) for category, findings in duplicate_report['inventory'].items(): self.result('P7', 'duplicates_' + category,`.
Stage: Stage 7
Required producer fields: duplicate audit C6 inputs: controls/readingScopes/messages/phases/execution; reading-summaries units; basic-block-details blocks; duplicateAudit
Pass example: Inputs `duplicate audit C6 inputs: controls/readingScopes/messages/phases/execution; reading-summaries units; basic-block-details blocks; duplicateAudit` with state `values=["a","b"]` -> accepted.
Fail example: Inputs `duplicate audit C6 inputs: controls/readingScopes/messages/phases/execution; reading-summaries units; basic-block-details blocks; duplicateAudit` with state `values=["a","a"]` -> rejected.

### C6.same_title_span_nodes
Aliases: -
Enforced: scripts/audit_duplicates.py:229
Condition: The enclosing failure condition is false: `if title and blocks: ng[(norm(title), tuple(sorted(blocks)))].append(n['id']) for (title, blocks), ids in ng.items(): for a, b in combinations(ids, 2): add('C6', 'same_title_span_nodes', [a, b], title=title, bbs=blocks, layer='execution')`.
Stage: Stage 7
Required producer fields: duplicate audit C6 inputs: controls/readingScopes/messages/phases/execution; reading-summaries units; basic-block-details blocks; same title span nodes
Pass example: Inputs `duplicate audit C6 inputs: controls/readingScopes/messages/phases/execution; reading-summaries units; basic-block-details blocks; same title span nodes` with state `functionSource L10-L12; lineRanges=[L10-L11]` -> accepted.
Fail example: Inputs `duplicate audit C6 inputs: controls/readingScopes/messages/phases/execution; reading-summaries units; basic-block-details blocks; same title span nodes` with state `functionSource L10-L12; lineRanges=[L9-L11]` -> rejected.

### G1.unique_action_per_business_pair
Aliases: -
Enforced: scripts/check_principles.py:794
Condition: Each pair has exactly one request and one return, each owned by exactly one and the same action.
Stage: Stage 7
Required producer fields: G1 inputs in renderer-input and stage2/granularity.json: unique action per business pair
Pass example: Inputs `G1 inputs in renderer-input and stage2/granularity.json: unique action per business pair` with state `pair p has request m1 and return m2; both message placements resolve to action a1` -> accepted.
Fail example: Inputs `G1 inputs in renderer-input and stage2/granularity.json: unique action per business pair` with state `pair p request m1 resolves to action a1 while return m2 resolves to action a2` -> rejected.

### G10.pure_loop_handoff_boundary
Aliases: -
Enforced: scripts/check_principles.py:1158
Condition: The concrete failure collection passed to `self.result` is empty; executable comparison: `unassigned_without_technical_exemption=missing) self.check_shell_prelude_g10() bad_handoffs, handoff_count = classifications.handoff_boundaries(self.data, raw, self.actions, self.goals) self.result('G10', 'pure_loop_handoff_boundary', bad_handoffs, handoff_actions=handoff_count) self.review('G10', 'technical_purity_and_common_tail', '核对技术豁免逐块纯度与类别；笼统的 cleanup/state/terminal/drop 说明不构成类别证明。循环回入口前共同收尾必须有 action，不能由 continue 标记替代。')`.
Stage: Stage 7
Required producer fields: G10 inputs in renderer-input and stage2/granularity.json: pure loop handoff boundary
Pass example: Inputs `G10 inputs in renderer-input and stage2/granularity.json: pure loop handoff boundary` with state `declaredRefs=["a1"]; observedRefs=["a1"]` -> accepted.
Fail example: Inputs `G10 inputs in renderer-input and stage2/granularity.json: pure loop handoff boundary` with state `declaredRefs=["a1"]; observedRefs=[]` -> rejected.

### G10.reading_tree_bb_coverage
Aliases: -
Enforced: scripts/check_principles.py:1153
Condition: Fact BB IDs equal action-assigned BB IDs union valid technical BB IDs.
Stage: Stage 7
Required producer fields: stage2/facts.json blocks[].bbId; action fact ownership; technicalBlocks[].bbId
Pass example: Inputs `stage2/facts.json blocks[].bbId; action fact ownership; technicalBlocks[].bbId` with state `factBBs=["bb0","bb1"]; actionBBs=["bb0"]; technicalBBs=["bb1"]` -> accepted.
Fail example: Inputs `stage2/facts.json blocks[].bbId; action fact ownership; technicalBlocks[].bbId` with state `factBBs=["bb0","bb1"]; actionBBs=["bb0"]; technicalBBs=[]` -> rejected.

### G10.shell_prelude_bb_coverage
Aliases: -
Enforced: scripts/check_principles.py:1195, scripts/check_principles.py:1234, scripts/check_principles.py:1255
Condition: The enclosing failure condition is false: `if not isinstance(relation, dict): failures.append({'code': 'missing-shell-relation'}) self.result('G10', 'shell_prelude_ledger', failures, technical_records=0) self.result('G10', 'shell_prelude_bb_coverage', failures,`.
Stage: Stage 7
Required producer fields: G10 inputs in renderer-input and stage2/granularity.json: shell prelude bb coverage
Pass example: Inputs `G10 inputs in renderer-input and stage2/granularity.json: shell prelude bb coverage` with state `declaredRefs=["a1"]; observedRefs=["a1"]` -> accepted.
Fail example: Inputs `G10 inputs in renderer-input and stage2/granularity.json: shell prelude bb coverage` with state `declaredRefs=["a1"]; observedRefs=[]` -> rejected.

### G10.shell_prelude_ledger
Aliases: -
Enforced: scripts/check_principles.py:1194, scripts/check_principles.py:1226
Condition: The enclosing failure condition is false: `if not isinstance(relation, dict): failures.append({'code': 'missing-shell-relation'}) self.result('G10', 'shell_prelude_ledger', failures, technical_records=0)`.
Stage: Stage 7
Required producer fields: G10 inputs in renderer-input and stage2/granularity.json: shell prelude ledger
Pass example: Inputs `G10 inputs in renderer-input and stage2/granularity.json: shell prelude ledger` with state `declaredRefs=["a1"]; observedRefs=["a1"]` -> accepted.
Fail example: Inputs `G10 inputs in renderer-input and stage2/granularity.json: shell prelude ledger` with state `declaredRefs=["a1"]; observedRefs=[]` -> rejected.

### G10.technical_block_ledger
Aliases: -
Enforced: scripts/check_principles.py:1149
Condition: The enclosing failure condition is false: `if (bb not in universe or bb in technical or not self.anchors_valid(record.get('evidenceRefs')) or not classifications.technical_record_valid(raw, block_map[bb], record, event_macro_artifacts)): invalid.append(record) else: technical[bb] = record['category'] self.result('G10', 'technical_block_ledger', invalid, categories=dict(Counter(technical.values())))`.
Stage: Stage 7
Required producer fields: G10 inputs in renderer-input and stage2/granularity.json: technical block ledger
Pass example: Inputs `G10 inputs in renderer-input and stage2/granularity.json: technical block ledger` with state `expected=["yes","no"]; observed=["yes","no"]` -> accepted.
Fail example: Inputs `G10 inputs in renderer-input and stage2/granularity.json: technical block ledger` with state `expected=["yes","no"]; observed=["yes"]` -> rejected.

### G11.cross_phase_loop_scope
Aliases: -
Enforced: scripts/check_principles.py:1286
Condition: The enclosing failure condition is false: `if not matching: bad.append(record) self.result('G11', 'cross_phase_loop_scope', bad, cross_phase_components=components)`.
Stage: Stage 7
Required producer fields: G11 inputs in renderer-input and stage2/granularity.json: cross phase loop scope
Pass example: Inputs `G11 inputs in renderer-input and stage2/granularity.json: cross phase loop scope` with state `declared="a1"; observed="a1"` -> accepted.
Fail example: Inputs `G11 inputs in renderer-input and stage2/granularity.json: cross phase loop scope` with state `declared="a1"; observed="missing"` -> rejected.

### G11.phase_execution_order
Aliases: -
Enforced: scripts/check_principles.py:1312
Condition: After loop-continue edges are removed, no action reaches an action in an earlier phase.
Stage: Stage 7
Required producer fields: phases[].goals[].actions[].id; execution.edges[].from/to/kind; action-node actionRef
Pass example: Inputs `phases[].goals[].actions[].id; execution.edges[].from/to/kind; action-node actionRef` with state `after removing loop-continue, reachability is a1(phase1)->a2(phase2)` -> accepted.
Fail example: Inputs `phases[].goals[].actions[].id; execution.edges[].from/to/kind; action-node actionRef` with state `after removing loop-continue, reachability is a2(phase2)->a1(phase1)` -> rejected.

### G2.business_fact_records
Aliases: -
Enforced: scripts/check_principles.py:803
Condition: The concrete failure collection passed to `self.result` is empty; executable comparison: `valid = {'call', 'decision', 'state_change', 'business_result'} proven = {f.get('actionRef') for f in facts if f.get('kind') in valid and self.anchors_valid(f.get('evidenceRefs')) and f.get('claim')} bad = [f for f in facts if f.get('kind') not in valid or not self.anchors_valid(f.get('evidenceRefs')) or not f.get('claim') or f.get('actionRef') not in {a['id'] for a in self.actions}] self.result('G2', 'business_fact_records', bad, call_backed_actions=len(calls), declared_facts=len(facts)) raw = self.read('raw-body.json') or {}`.
Stage: Stage 7
Required producer fields: G2 inputs in renderer-input and stage2/granularity.json: business fact records
Pass example: Inputs `G2 inputs in renderer-input and stage2/granularity.json: business fact records` with state `declared="a1"; observed="a1"` -> accepted.
Fail example: Inputs `G2 inputs in renderer-input and stage2/granularity.json: business fact records` with state `declared="a1"; observed="missing"` -> rejected.

### G2.independent_fact_per_action
Aliases: -
Enforced: scripts/check_principles.py:812, scripts/check_principles.py:814
Condition: The enclosing failure condition is false: `if self.granularity is None: self.review('G2', 'independent_fact_per_action', '无消息不等于无业务事实；需提供业务判断、状态变化或结果交付的源码证据。', actions=missing) else: self.result('G2', 'independent_fact_per_action', missing)`.
Stage: Stage 7
Required producer fields: G2 inputs in renderer-input and stage2/granularity.json: independent fact per action
Pass example: Inputs `G2 inputs in renderer-input and stage2/granularity.json: independent fact per action` with state `declaredRefs=["a1"]; observedRefs=["a1"]` -> accepted.
Fail example: Inputs `G2 inputs in renderer-input and stage2/granularity.json: independent fact per action` with state `declaredRefs=["a1"]; observedRefs=[]` -> rejected.

### G3.consecutive_single_action_goals
Aliases: -
Enforced: scripts/check_principles.py:821
Condition: Every run of at least three consecutive single-action goals with equal nonempty contractRef and entryMode is a failure.
Stage: Stage 7
Required producer fields: G3 inputs in renderer-input and stage2/granularity.json: consecutive single action goals
Pass example: Inputs `G3 inputs in renderer-input and stage2/granularity.json: consecutive single action goals` with state `two adjacent one-action goals share contract done/normal` -> accepted.
Fail example: Inputs `G3 inputs in renderer-input and stage2/granularity.json: consecutive single action goals` with state `three adjacent one-action goals share contract done/normal` -> rejected.

### G3.goal_completion_contracts
Aliases: -
Enforced: scripts/check_principles.py:867
Condition: The enclosing failure condition is false: `if issues: failures.append({'goalRef': gid, 'issues': issues}) self.result('G3', 'goal_completion_contracts', failures, goals=len(known), records=len(records))`.
Stage: Stage 7
Required producer fields: G3 inputs in renderer-input and stage2/granularity.json: goal completion contracts
Pass example: Inputs `G3 inputs in renderer-input and stage2/granularity.json: goal completion contracts` with state `declared="a1"; observed="a1"` -> accepted.
Fail example: Inputs `G3 inputs in renderer-input and stage2/granularity.json: goal completion contracts` with state `declared="a1"; observed="missing"` -> rejected.

### G3.goal_phase_boundaries
Aliases: -
Enforced: scripts/check_principles.py:849
Condition: The enclosing failure condition is false: `if not all(b.get(k) for k in ['purpose', 'completion', 'entry', 'exit']) or not self.anchors_valid(b.get('evidenceRefs')): bad.append(unit['id']) self.result('G3', 'goal_phase_boundaries', bad)`.
Stage: Stage 7
Required producer fields: G3 inputs in renderer-input and stage2/granularity.json: goal phase boundaries
Pass example: Inputs `G3 inputs in renderer-input and stage2/granularity.json: goal phase boundaries` with state `declared="a1"; observed="a1"` -> accepted.
Fail example: Inputs `G3 inputs in renderer-input and stage2/granularity.json: goal phase boundaries` with state `declared="a1"; observed="missing"` -> rejected.

### G4.source_decision_inventory
Aliases: -
Enforced: scripts/check_principles.py:888
Condition: The enclosing failure condition is false: `if inventory is None: self.review('G4', 'source_decision_inventory', '缺少源业务判断清单；已选 decision 全覆盖不能证明没有漏选源码分支。') return known = {d['id'] for d in self.execution.get('decisions', [])} bad = [r for r in inventory if not self.anchors_valid(r.get('evidenceRefs')) or (r.get('disposition') == 'business' and r.get('decisionRef') not in known) or (r.get('disposition') == 'mechanism' and not r.get('foldedInto')) or r.get('disposition') not in {'business', 'mechanism'}] self.result('G4', 'source_decision_inventory', bad, decisions=len(inventory))`.
Stage: Stage 7
Required producer fields: G4 inputs in renderer-input and stage2/granularity.json: source decision inventory
Pass example: Inputs `G4 inputs in renderer-input and stage2/granularity.json: source decision inventory` with state `declared="a1"; observed="a1"` -> accepted.
Fail example: Inputs `G4 inputs in renderer-input and stage2/granularity.json: source decision inventory` with state `declared="a1"; observed="missing"` -> rejected.

### G5.guarded_members_require_nonzero_opt
Aliases: -
Enforced: scripts/check_principles.py:964
Condition: If proven guarded members outnumber alternative members, visible opt count is greater than zero.
Stage: Stage 7
Required producer fields: G5 inputs in renderer-input and stage2/granularity.json: guarded members require nonzero opt
Pass example: Inputs `G5 inputs in renderer-input and stage2/granularity.json: guarded members require nonzero opt` with state `expected=["yes","no"]; observed=["yes","no"]` -> accepted.
Fail example: Inputs `G5 inputs in renderer-input and stage2/granularity.json: guarded members require nonzero opt` with state `expected=["yes","no"]; observed=["yes"]` -> rejected.

### G5.member_guard_coverage
Aliases: -
Enforced: scripts/check_principles.py:963
Condition: The enclosing failure condition is false: `if not visible_opt or not covered: bad.append({**g, 'reason': 'guarded business member requires an enclosing visible opt control'}) self.result('G5', 'member_guard_coverage', bad, guarded_members=len(guards), proven_members=len(proven))`.
Stage: Stage 7
Required producer fields: G5 inputs in renderer-input and stage2/granularity.json: member guard coverage
Pass example: Inputs `G5 inputs in renderer-input and stage2/granularity.json: member guard coverage` with state `declaredRefs=["a1"]; observedRefs=["a1"]` -> accepted.
Fail example: Inputs `G5 inputs in renderer-input and stage2/granularity.json: member guard coverage` with state `declaredRefs=["a1"]; observedRefs=[]` -> rejected.

### G6.bounded_conditional_entries
Aliases: -
Enforced: scripts/check_principles.py:1084
Condition: The enclosing failure condition is false: `if missing: self.review('G6', 'bounded_conditional_entries', '这些较早的条件入口没有绑定同一 decision 的范围；需回源码判定为遗漏、局部条件表达或其他等价范围，不凭图形候选直接判错。', candidate_ranges=len(candidates), count=len(missing), examples=missing) else: self.result('G6', 'bounded_conditional_entries', [], candidate_ranges=len(candidates))`.
Stage: Stage 7
Required producer fields: G6 inputs in renderer-input and stage2/granularity.json: bounded conditional entries
Pass example: Inputs `G6 inputs in renderer-input and stage2/granularity.json: bounded conditional entries` with state `functionSource L10-L12; lineRanges=[L10-L11]` -> accepted.
Fail example: Inputs `G6 inputs in renderer-input and stage2/granularity.json: bounded conditional entries` with state `functionSource L10-L12; lineRanges=[L9-L11]` -> rejected.

### G6.business_loop_reading_scopes
Aliases: -
Enforced: scripts/check_principles.py:997
Condition: The enclosing failure condition is false: `if actions and not any(actions <= members for members in loop_members.values()): missing_loops.append({'scc_actions': sorted(actions)}) self.result('G6', 'business_loop_reading_scopes', missing_loops)`.
Stage: Stage 7
Required producer fields: G6 inputs in renderer-input and stage2/granularity.json: business loop reading scopes
Pass example: Inputs `G6 inputs in renderer-input and stage2/granularity.json: business loop reading scopes` with state `declaredRefs=["a1"]; observedRefs=["a1"]` -> accepted.
Fail example: Inputs `G6 inputs in renderer-input and stage2/granularity.json: business loop reading scopes` with state `declaredRefs=["a1"]; observedRefs=[]` -> rejected.

### G6.declared_ranges
Aliases: -
Enforced: scripts/check_principles.py:1020
Condition: The enclosing failure condition is false: `if not exact or not self.anchors_valid(r.get('evidenceRefs')): bad.append(r) self.result('G6', 'declared_ranges', bad, ranges=len(declared))`.
Stage: Stage 7
Required producer fields: G6 inputs in renderer-input and stage2/granularity.json: declared ranges
Pass example: Inputs `G6 inputs in renderer-input and stage2/granularity.json: declared ranges` with state `functionSource L10-L12; lineRanges=[L10-L11]` -> accepted.
Fail example: Inputs `G6 inputs in renderer-input and stage2/granularity.json: declared ranges` with state `functionSource L10-L12; lineRanges=[L9-L11]` -> rejected.

### G7.purpose_covers_business_members
Aliases: -
Enforced: scripts/check_principles.py:1101
Condition: The enclosing failure condition is false: `if m['kind'] == 'request': inv_goals[m.get('invocationRef')].update(action_goal[a] for a in owners[m['messageId']]) covered = defaultdict(set) for p in self.data.get('purposeProjections', []): for inv in p.get('invocationRefs', []) + p.get('waitRefs', []): covered[inv].update([p.get('goalRef'), *p.get('relatedGoalRefs', [])]) bad = [{'invocation': inv, 'missing_goals': sorted(gs-covered[inv])} for inv, gs in inv_goals.items() if not gs <= covered[inv]] self.result('G7', 'purpose_covers_business_members', bad, business_goals=len(set.union(set(), *inv_goals.values())), local_only_goals=len(self.goals)-len(set.union(set(), *inv_goals.values())))`.
Stage: Stage 7
Required producer fields: G7 inputs in renderer-input and stage2/granularity.json: purpose covers business members
Pass example: Inputs `G7 inputs in renderer-input and stage2/granularity.json: purpose covers business members` with state `declaredRefs=["a1"]; observedRefs=["a1"]` -> accepted.
Fail example: Inputs `G7 inputs in renderer-input and stage2/granularity.json: purpose covers business members` with state `declaredRefs=["a1"]; observedRefs=[]` -> rejected.

### G8.sequence_preserves_call_order
Aliases: -
Enforced: scripts/check_principles.py:1112
Condition: Within each action control traversal, every return has an earlier request with the same pair.
Stage: Stage 7
Required producer fields: G8 inputs in renderer-input and stage2/granularity.json: sequence preserves call order
Pass example: Inputs `G8 inputs in renderer-input and stage2/granularity.json: sequence preserves call order` with state `declared="a1"; observed="a1"` -> accepted.
Fail example: Inputs `G8 inputs in renderer-input and stage2/granularity.json: sequence preserves call order` with state `declared="a1"; observed="missing"` -> rejected.

### G9.purpose_group_boundaries
Aliases: -
Enforced: scripts/check_principles.py:1123
Condition: The enclosing failure condition is false: `if groups is None: self.review('G9', 'purpose_group_boundaries', '缺少对象—业务目的—阶段/条件—结果分组依据；一个 goal 可以有多个目的组，不能直接按 goal 或 callee 聚合。') return refs = {p['id'] for p in self.data.get('purposeProjections', [])} bad = [g for g in groups if g.get('projectionRef') not in refs or not all(g.get(k) for k in ['object', 'purpose', 'result']) or not self.anchors_valid(g.get('evidenceRefs'))] bad += [{'missing_projection_basis': ref} for ref in refs - {g.get('projectionRef') for g in groups}] self.result('G9', 'purpose_group_boundaries', bad)`.
Stage: Stage 7
Required producer fields: G9 inputs in renderer-input and stage2/granularity.json: purpose group boundaries
Pass example: Inputs `G9 inputs in renderer-input and stage2/granularity.json: purpose group boundaries` with state `declaredRefs=["a1"]; observedRefs=["a1"]` -> accepted.
Fail example: Inputs `G9 inputs in renderer-input and stage2/granularity.json: purpose group boundaries` with state `declaredRefs=["a1"]; observedRefs=[]` -> rejected.

### P1.complete_fact_tree
Aliases: -
Enforced: scripts/check_principles.py:230
Condition: The facts/blocks IDs plus prelude `shell:bbN` refs equal basic-block-details.blocks keys exactly.
Stage: Stage 7
Required producer fields: stage2/facts.json blocks[].bbId; basic-block-details.json blocks keys; prelude.nodes[].basicBlockRefs
Pass example: Inputs `stage2/facts.json blocks[].bbId; basic-block-details.json blocks keys; prelude.nodes[].basicBlockRefs` with state `fact/prelude BBs=["bb0","shell:bb0"]; detail keys=["bb0","shell:bb0"]` -> accepted.
Fail example: Inputs `stage2/facts.json blocks[].bbId; basic-block-details.json blocks keys; prelude.nodes[].basicBlockRefs` with state `fact/prelude BBs=["bb0"]; detail keys=["bb0","shell:bb0"]` -> rejected.

### P1.reading_tree_separated
Aliases: -
Enforced: scripts/check_principles.py:218
Condition: No phase, goal, or action ID matches `bb[0-9]+` case-insensitively.
Stage: Stage 7
Required producer fields: P1 inputs in renderer-input, stage2 facts/hierarchy/presentation/granularity, and basic-block-details: reading tree separated
Pass example: Inputs `P1 inputs in renderer-input, stage2 facts/hierarchy/presentation/granularity, and basic-block-details: reading tree separated` with state `declared="a1"; observed="a1"` -> accepted.
Fail example: Inputs `P1 inputs in renderer-input, stage2 facts/hierarchy/presentation/granularity, and basic-block-details: reading tree separated` with state `declared="a1"; observed="missing"` -> rejected.

### P10.collapsed_summary_coverage
Aliases: -
Enforced: scripts/check_principles.py:506
Condition: The enclosing failure condition is false: `if values != covered: bad.append({'decision': d['id'], 'missing_values': sorted(values-covered), 'extra_values': sorted(covered-values), 'controlRef': d.get('controlRef'), 'readingScopeRef': d.get('readingScopeRef')}) else: bound += 1 self.result('P10', 'decision_visible_value_coverage', bad, decisions=len(self.execution.get('decisions', [])), fully_bound=bound) bad = [{'id': u['id'], 'kind': kind} for u, kind in self.units if self.summaries.get(u['id'], {}).get('kind') != kind or not self.summaries.get(u['id'], {}).get('text', '').strip()] self.result('P10', 'collapsed_summary_coverage', bad, reading_nodes=len(self.units))`.
Stage: Stage 7
Required producer fields: P10 inputs in renderer-input, stage2 facts/hierarchy/presentation/granularity, and basic-block-details: collapsed summary coverage
Pass example: Inputs `P10 inputs in renderer-input, stage2 facts/hierarchy/presentation/granularity, and basic-block-details: collapsed summary coverage` with state `declaredRefs=["a1"]; observedRefs=["a1"]` -> accepted.
Fail example: Inputs `P10 inputs in renderer-input, stage2 facts/hierarchy/presentation/granularity, and basic-block-details: collapsed summary coverage` with state `declaredRefs=["a1"]; observedRefs=[]` -> rejected.

### P10.decision_visible_value_coverage
Aliases: -
Enforced: scripts/check_principles.py:504
Condition: For each decision, values exposed by attached controls and valid scope equal decisions[].values exactly.
Stage: Stage 7
Required producer fields: P10 inputs in renderer-input, stage2 facts/hierarchy/presentation/granularity, and basic-block-details: decision visible value coverage
Pass example: Inputs `P10 inputs in renderer-input, stage2 facts/hierarchy/presentation/granularity, and basic-block-details: decision visible value coverage` with state `declaredRefs=["a1"]; observedRefs=["a1"]` -> accepted.
Fail example: Inputs `P10 inputs in renderer-input, stage2 facts/hierarchy/presentation/granularity, and basic-block-details: decision visible value coverage` with state `declaredRefs=["a1"]; observedRefs=[]` -> rejected.

### P10.message_render_attachments
Aliases: -
Enforced: scripts/check_principles.py:508
Condition: The enclosing failure condition is false: `if values != covered: bad.append({'decision': d['id'], 'missing_values': sorted(values-covered), 'extra_values': sorted(covered-values), 'controlRef': d.get('controlRef'), 'readingScopeRef': d.get('readingScopeRef')}) else: bound += 1 self.result('P10', 'decision_visible_value_coverage', bad, decisions=len(self.execution.get('decisions', [])), fully_bound=bound) bad = [{'id': u['id'], 'kind': kind} for u, kind in self.units if self.summaries.get(u['id'], {}).get('kind') != kind or not self.summaries.get(u['id'], {}).get('text', '').strip()] self.result('P10', 'collapsed_summary_coverage', bad, reading_nodes=len(self.units)) hidden = [m['messageId'] for m in self.messages if m['messageId'] no`.
Stage: Stage 7
Required producer fields: P10 inputs in renderer-input, stage2 facts/hierarchy/presentation/granularity, and basic-block-details: message render attachments
Pass example: Inputs `P10 inputs in renderer-input, stage2 facts/hierarchy/presentation/granularity, and basic-block-details: message render attachments` with state `declaredRefs=["a1"]; observedRefs=["a1"]` -> accepted.
Fail example: Inputs `P10 inputs in renderer-input, stage2 facts/hierarchy/presentation/granularity, and basic-block-details: message render attachments` with state `declaredRefs=["a1"]; observedRefs=[]` -> rejected.

### P10.source_to_visible_reconciliation
Aliases: -
Enforced: scripts/check_principles.py:525
Condition: The enclosing failure condition is false: `if not r.get('evidenceRefs') or not reps or any(not self.representation_valid(v) for v in reps): bad.append({'source': r['sourceRef'], 'representations': reps, 'reason': 'missing evidence or nonvisible target'}) self.result('P10', 'source_to_visible_reconciliation', bad, required_relations=len(expected), mapped_relations=len(records))`.
Stage: Stage 7
Required producer fields: P10 inputs in renderer-input, stage2 facts/hierarchy/presentation/granularity, and basic-block-details: source to visible reconciliation
Pass example: Inputs `P10 inputs in renderer-input, stage2 facts/hierarchy/presentation/granularity, and basic-block-details: source to visible reconciliation` with state `declaredRefs=["a1"]; observedRefs=["a1"]` -> accepted.
Fail example: Inputs `P10 inputs in renderer-input, stage2 facts/hierarchy/presentation/granularity, and basic-block-details: source to visible reconciliation` with state `declaredRefs=["a1"]; observedRefs=[]` -> rejected.

### P11.loop_destinations
Aliases: -
Enforced: scripts/check_principles.py:667
Condition: The enclosing failure condition is false: `if e['kind'] in {'loop-continue', 'loop-exit'} and (e.get('readingScopeRef') not in self.scopes or not e.get('evidenceRefs')): bad.append({'edge': e['id'], 'reason': 'missing loop scope/evidence'}) self.result('P11', 'loop_destinations', bad, loop_scopes=len(loops))`.
Stage: Stage 7
Required producer fields: P11 inputs in renderer-input, stage2 facts/hierarchy/presentation/granularity, and basic-block-details: loop destinations
Pass example: Inputs `P11 inputs in renderer-input, stage2 facts/hierarchy/presentation/granularity, and basic-block-details: loop destinations` with state `declaredRefs=["a1"]; observedRefs=["a1"]` -> accepted.
Fail example: Inputs `P11 inputs in renderer-input, stage2 facts/hierarchy/presentation/granularity, and basic-block-details: loop destinations` with state `declaredRefs=["a1"]; observedRefs=[]` -> rejected.

### P12.goal_inherits_action_blocks
Aliases: -
Enforced: scripts/check_principles.py:679
Condition: Each goal detail BB set equals the union of its member action detail BB sets.
Stage: Stage 7
Required producer fields: P12 inputs in renderer-input, stage2 facts/hierarchy/presentation/granularity, and basic-block-details: goal inherits action blocks
Pass example: Inputs `P12 inputs in renderer-input, stage2 facts/hierarchy/presentation/granularity, and basic-block-details: goal inherits action blocks` with state `declared="a1"; observed="a1"` -> accepted.
Fail example: Inputs `P12 inputs in renderer-input, stage2 facts/hierarchy/presentation/granularity, and basic-block-details: goal inherits action blocks` with state `declared="a1"; observed="missing"` -> rejected.

### P12.internal_edges_not_goal_self_loops
Aliases: -
Enforced: scripts/check_principles.py:692
Condition: The enclosing failure condition is false: `if members and all(m['source'] in bbs and m['target'] in bbs for m in members): bad.append({'edge': e['id'], 'goal': e['source'], 'members': e['members'], 'kind': e['kind']}) self.result('P12', 'internal_edges_not_goal_self_loops', bad, goal_self_edges=sum(e.get('depth') == 1.5 and e['source'] == e['target'] for e in self.semantic_edges()))`.
Stage: Stage 7
Required producer fields: execution goal-level edges source/target/memberEdgeRefs; member execution edges from/to; goal action BB sets
Pass example: Inputs `execution goal-level edges source/target/memberEdgeRefs; member execution edges from/to; goal action BB sets` with state `goal edge g1->g2 has member edge n1->n2 crossing the goal BB sets` -> accepted.
Fail example: Inputs `execution goal-level edges source/target/memberEdgeRefs; member execution edges from/to; goal action BB sets` with state `goal edge g1->g1 contains only member edges internal to g1` -> rejected.

### P13.chinese_semantic_labels
Aliases: -
Enforced: scripts/check_principles.py:699
Condition: Every goal and action label contains a U+3400–U+9FFF character.
Stage: Stage 7
Required producer fields: P13 inputs in renderer-input, stage2 facts/hierarchy/presentation/granularity, and basic-block-details: chinese semantic labels
Pass example: Inputs `P13 inputs in renderer-input, stage2 facts/hierarchy/presentation/granularity, and basic-block-details: chinese semantic labels` with state `declared label="处理请求"; rendered label="处理请求"` -> accepted.
Fail example: Inputs `P13 inputs in renderer-input, stage2 facts/hierarchy/presentation/granularity, and basic-block-details: chinese semantic labels` with state `declared label="处理请求"; rendered label="process"` -> rejected.

### P13.execution_semantic_labels
Aliases: -
Enforced: scripts/check_principles.py:703
Condition: Every execution label or inherited action label contains a U+3400–U+9FFF character.
Stage: Stage 7
Required producer fields: P13 inputs in renderer-input, stage2 facts/hierarchy/presentation/granularity, and basic-block-details: execution semantic labels
Pass example: Inputs `P13 inputs in renderer-input, stage2 facts/hierarchy/presentation/granularity, and basic-block-details: execution semantic labels` with state `declared label="处理请求"; rendered label="处理请求"` -> accepted.
Fail example: Inputs `P13 inputs in renderer-input, stage2 facts/hierarchy/presentation/granularity, and basic-block-details: execution semantic labels` with state `declared label="处理请求"; rendered label="process"` -> rejected.

### P13.original_body_names
Aliases: -
Enforced: scripts/check_principles.py:713
Condition: Body labels derive from the nearest named source item, retaining impl type and closure suffix; add source path segments until peer identities are distinct (body_labels.labels).
Stage: Stage 7
Required producer fields: P13 inputs in renderer-input, stage2 facts/hierarchy/presentation/granularity, and basic-block-details: original body names
Pass example: Inputs `P13 inputs in renderer-input, stage2 facts/hierarchy/presentation/granularity, and basic-block-details: original body names` with state `declared label="处理请求"; rendered label="处理请求"` -> accepted.
Fail example: Inputs `P13 inputs in renderer-input, stage2 facts/hierarchy/presentation/granularity, and basic-block-details: original body names` with state `declared label="处理请求"; rendered label="process"` -> rejected.

### P14.detail_scope_and_source
Aliases: -
Enforced: scripts/check_principles.py:751
Condition: The enclosing failure condition is false: `if n.get('depth') != depth or not bbs or len(bbs) != len(set(bbs)) or any(bb not in self.details['blocks'] for bb in bbs) or (not snippets and not source_less_handoff) or any(not s.get('code', '').strip() for s in snippets): bad.append({'node': ref, 'depth': n.get('depth'), 'bb_count': len(bbs), 'missing_blocks': sorted(set(bbs)-set(self.details['blocks'])), 'source_snippets': len(snippets)}) self.result('P14', 'detail_scope_and_source', bad, expected_nodes=len(expected), actual_nodes=len(nodes), phase_details=sum(p['id'] in nodes for p in self.phases))`.
Stage: Stage 7
Required producer fields: P14 inputs in renderer-input, stage2 facts/hierarchy/presentation/granularity, and basic-block-details: detail scope and source
Pass example: Inputs `P14 inputs in renderer-input, stage2 facts/hierarchy/presentation/granularity, and basic-block-details: detail scope and source` with state `declaredRefs=["a1"]; observedRefs=["a1"]` -> accepted.
Fail example: Inputs `P14 inputs in renderer-input, stage2 facts/hierarchy/presentation/granularity, and basic-block-details: detail scope and source` with state `declaredRefs=["a1"]; observedRefs=[]` -> rejected.

### P14.full_function_source_and_node_ranges
Aliases: -
Enforced: scripts/check_principles.py:723
Condition: The enclosing failure condition is false: `if source_path.is_relative_to(self.out / 'source') and source_path.is_file(): raw = source_path.read_bytes() self.inputs[str(source_path.relative_to(self.out))] = {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()} self.result('P14', 'full_function_source_and_node_ranges', check_source(self.data, self.out))`.
Stage: Stage 7
Required producer fields: P14 inputs in renderer-input, stage2 facts/hierarchy/presentation/granularity, and basic-block-details: full function source and node ranges
Pass example: Inputs `P14 inputs in renderer-input, stage2 facts/hierarchy/presentation/granularity, and basic-block-details: full function source and node ranges` with state `declared sha256="abc"; computed sha256="abc"` -> accepted.
Fail example: Inputs `P14 inputs in renderer-input, stage2 facts/hierarchy/presentation/granularity, and basic-block-details: full function source and node ranges` with state `declared sha256="abc"; computed sha256="def"` -> rejected.

### P14.independent_async_shell_relation
Aliases: -
Enforced: scripts/check_principles.py:731
Condition: The enclosing failure condition is false: `if async_shell_result.get('status') != 'not-applicable': self.result('P14', 'independent_async_shell_relation',`.
Stage: Stage 7
Required producer fields: P14 inputs in renderer-input, stage2 facts/hierarchy/presentation/granularity, and basic-block-details: independent async shell relation
Pass example: Inputs `P14 inputs in renderer-input, stage2 facts/hierarchy/presentation/granularity, and basic-block-details: independent async shell relation` with state `declared="a1"; observed="a1"` -> accepted.
Fail example: Inputs `P14 inputs in renderer-input, stage2 facts/hierarchy/presentation/granularity, and basic-block-details: independent async shell relation` with state `declared="a1"; observed="missing"` -> rejected.

### P14.independent_operation_source_bounds
Aliases: -
Enforced: scripts/check_principles.py:726
Condition: The enclosing failure condition is false: `if source_path.is_relative_to(self.out / 'source') and source_path.is_file(): raw = source_path.read_bytes() self.inputs[str(source_path.relative_to(self.out))] = {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()} self.result('P14', 'full_function_source_and_node_ranges', check_source(self.data, self.out)) from verify_source_evidence import verify, load_independent_context independent_context = load_independent_context(self.out) self.result('P14', 'independent_operation_source_bounds',`.
Stage: Stage 7
Required producer fields: P14 inputs in renderer-input, stage2 facts/hierarchy/presentation/granularity, and basic-block-details: independent operation source bounds
Pass example: Inputs `P14 inputs in renderer-input, stage2 facts/hierarchy/presentation/granularity, and basic-block-details: independent operation source bounds` with state `declared sha256="abc"; computed sha256="abc"` -> accepted.
Fail example: Inputs `P14 inputs in renderer-input, stage2 facts/hierarchy/presentation/granularity, and basic-block-details: independent operation source bounds` with state `declared sha256="abc"; computed sha256="def"` -> rejected.

### P2.source_phase_order
Aliases: -
Enforced: scripts/check_principles.py:244
Condition: The ordered phases[].id list equals hierarchy.phase_order, or the sole converted root children list, exactly.
Stage: Stage 7
Required producer fields: phases[].id; stage2/hierarchy.json phase_order or converted root children
Pass example: Inputs `phases[].id; stage2/hierarchy.json phase_order or converted root children` with state `phases=["p1","p2"]; hierarchy.phase_order=["p1","p2"]` -> accepted.
Fail example: Inputs `phases[].id; stage2/hierarchy.json phase_order or converted root children` with state `phases=["p2","p1"]; hierarchy.phase_order=["p1","p2"]` -> rejected.

### P3.execution_edge_evidence
Aliases: -
Enforced: scripts/check_principles.py:255
Condition: Every execution edge has nonempty evidenceRefs and each ref exists in execution.evidence.
Stage: Stage 7
Required producer fields: P3 inputs in renderer-input, stage2 facts/hierarchy/presentation/granularity, and basic-block-details: execution edge evidence
Pass example: Inputs `P3 inputs in renderer-input, stage2 facts/hierarchy/presentation/granularity, and basic-block-details: execution edge evidence` with state `declaredRefs=["a1"]; observedRefs=["a1"]` -> accepted.
Fail example: Inputs `P3 inputs in renderer-input, stage2 facts/hierarchy/presentation/granularity, and basic-block-details: execution edge evidence` with state `declaredRefs=["a1"]; observedRefs=[]` -> rejected.

### P3.technical_edges_promoted
Aliases: -
Enforced: scripts/check_principles.py:252
Condition: No semantic edge kind is runtime_annotation, resume_annotation, or wait_annotation.
Stage: Stage 7
Required producer fields: execution.edges[].kind/from/to; execution.nodes[].kind; technical BB classifications
Pass example: Inputs `execution.edges[].kind/from/to; execution.nodes[].kind; technical BB classifications` with state `technical runtime_annotation relation remains in the technical ledger` -> accepted.
Fail example: Inputs `execution.edges[].kind/from/to; execution.nodes[].kind; technical BB classifications` with state `runtime_annotation relation is emitted as a semantic execution edge` -> rejected.

### P4.original_edge_identity
Aliases: -
Enforced: scripts/check_principles.py:274
Condition: The enclosing failure condition is false: `if ref and (ref not in members or any(c.get(k) != original.get(ref, {}).get(v) for k, v in [('source_bb', 'source'), ('target_bb', 'target'), ('bindingRef', 'bindingRef')] if k in c)): bad.append({'edge': e['id'], 'clause': c, 'reason': 'original identity mismatch'}) endpoint_groups = Counter((e['source'], e['target']) for e in facts) self.result('P4', 'original_edge_identity', bad, original_edges=len(facts), multiedge_endpoint_groups=sum(n > 1 for n in endpoint_groups.values()))`.
Stage: Stage 7
Required producer fields: P4 inputs in renderer-input, stage2 facts/hierarchy/presentation/granularity, and basic-block-details: original edge identity
Pass example: Inputs `P4 inputs in renderer-input, stage2 facts/hierarchy/presentation/granularity, and basic-block-details: original edge identity` with state `expected=["yes","no"]; observed=["yes","no"]` -> accepted.
Fail example: Inputs `P4 inputs in renderer-input, stage2 facts/hierarchy/presentation/granularity, and basic-block-details: original edge identity` with state `expected=["yes","no"]; observed=["yes"]` -> rejected.

### P5.cleanup_technical_lines
Aliases: -
Enforced: scripts/check_principles.py:293
Condition: No runtime_annotation semantic edge contains a fact edge whose target BB has is_cleanup=true.
Stage: Stage 7
Required producer fields: stage2/presentation cleanup lines; technical BB classifications/evidence
Pass example: Inputs `stage2/presentation cleanup lines; technical BB classifications/evidence` with state `cleanup line "drop temporary" cites technical bb7` -> accepted.
Fail example: Inputs `stage2/presentation cleanup lines; technical BB classifications/evidence` with state `cleanup line "submit order" cites business bb3` -> rejected.

### P5.technical_containers_absent
Aliases: -
Enforced: scripts/check_principles.py:283
Condition: The concrete failure collection passed to `self.result` is empty; executable comparison: `nodes = (self.hierarchy or {}).get('nodes', {}) excluded = {key for key, n in nodes.items() if n.get('kind') in technical or key in technical} bad += [{'edge': e['id'], 'endpoint': ref} for e in self.semantic_edges() for ref in [e.get('source'), e.get('target')] if ref in technical or ref in excluded] self.result('P5', 'technical_containers_absent', bad) if self.fact_blocks is not None and self.fact_edges is not None:`.
Stage: Stage 7
Required producer fields: P5 inputs in renderer-input, stage2 facts/hierarchy/presentation/granularity, and basic-block-details: technical containers absent
Pass example: Inputs `P5 inputs in renderer-input, stage2 facts/hierarchy/presentation/granularity, and basic-block-details: technical containers absent` with state `expected=["yes","no"]; observed=["yes","no"]` -> accepted.
Fail example: Inputs `P5 inputs in renderer-input, stage2 facts/hierarchy/presentation/granularity, and basic-block-details: technical containers absent` with state `expected=["yes","no"]; observed=["yes"]` -> rejected.

### P6.declaration_endpoint_identity
Aliases: -
Enforced: scripts/check_principles.py:334
Condition: The enclosing failure condition is false: `if (not key or a.get('sourceNodeRef') != key or 'bodyRef' in a or a.get('implementationStatus') != 'unresolved' or not definition or definition.get('rustc', {}).get('def_kind') not in ('Fn', 'AssocFn')): bad.append({'actor': a['actorId'], 'reason': 'declaration must have exact callable definition, explicit unresolved implementation, and no bodyRef'}) bad += [{'declarationRef': key, 'actors': ids} for key, ids in declaration_ids.items() if len(ids) != 1] self.result('P6', 'declaration_endpoint_identity', bad, declaration_actors=len(declarations))`.
Stage: Stage 7
Required producer fields: P6 inputs in renderer-input, stage2 facts/hierarchy/presentation/granularity, and basic-block-details: declaration endpoint identity
Pass example: Inputs `P6 inputs in renderer-input, stage2 facts/hierarchy/presentation/granularity, and basic-block-details: declaration endpoint identity` with state `declared="a1"; observed="a1"` -> accepted.
Fail example: Inputs `P6 inputs in renderer-input, stage2 facts/hierarchy/presentation/granularity, and basic-block-details: declaration endpoint identity` with state `declared="a1"; observed="missing"` -> rejected.

### P6.definition_ownership
Aliases: -
Enforced: scripts/check_principles.py:368
Condition: The enclosing failure condition is false: `if owner.get(field) and not any(x['kind'] == kind and owner[field] in x.get('sourceNodeRef', '') for x in ancestors): wrong_ownership.append({'actor': a['actorId'], 'kind': kind, 'expected_definition': owner[field]}) self.result('P6', 'known_body_available', invalid, checked=sum((body_key(a.get('bodyRef', '')) or '').split('|')[0] in self.definitions for a in bodies)) self.result('P6', 'definition_ownership', wrong_ownership)`.
Stage: Stage 7
Required producer fields: P6 inputs in renderer-input, stage2 facts/hierarchy/presentation/granularity, and basic-block-details: definition ownership
Pass example: Inputs `P6 inputs in renderer-input, stage2 facts/hierarchy/presentation/granularity, and basic-block-details: definition ownership` with state `declared="a1"; observed="a1"` -> accepted.
Fail example: Inputs `P6 inputs in renderer-input, stage2 facts/hierarchy/presentation/granularity, and basic-block-details: definition ownership` with state `declared="a1"; observed="missing"` -> rejected.

### P6.endpoint_ancestor_closure
Aliases: -
Enforced: scripts/check_principles.py:313
Condition: The concrete failure collection passed to `self.result` is empty; executable comparison: `bad = [{'unused_actor': x} for x in sorted(actual-required)] + [{'missing_actor': x} for x in sorted(required-actual)] counts = Counter(a['actorId'] for a in self.actors) bad += [{'duplicate_actor_id': k} for k, n in counts.items() if n > 1] self.result('P6', 'endpoint_ancestor_closure', bad, actors_top=len(self.data['actors']), actors_recursive=len(self.actors), endpoints=len(used)) bodies = [a for a in self.actors if a['kind'] == 'body']`.
Stage: Stage 7
Required producer fields: P6 inputs in renderer-input, stage2 facts/hierarchy/presentation/granularity, and basic-block-details: endpoint ancestor closure
Pass example: Inputs `P6 inputs in renderer-input, stage2 facts/hierarchy/presentation/granularity, and basic-block-details: endpoint ancestor closure` with state `values=["a","b"]` -> accepted.
Fail example: Inputs `P6 inputs in renderer-input, stage2 facts/hierarchy/presentation/granularity, and basic-block-details: endpoint ancestor closure` with state `values=["a","a"]` -> rejected.

### P6.external_body_ancestors
Aliases: -
Enforced: scripts/check_principles.py:345
Condition: The enclosing failure condition is false: `if not chain or chain[0] != 'module' or 'crate' not in chain: bad.append({'actor': a['actorId'], 'label': a['label'], 'ancestor_kinds': chain}) self.result('P6', 'external_body_ancestors', bad)`.
Stage: Stage 7
Required producer fields: P6 inputs in renderer-input, stage2 facts/hierarchy/presentation/granularity, and basic-block-details: external body ancestors
Pass example: Inputs `P6 inputs in renderer-input, stage2 facts/hierarchy/presentation/granularity, and basic-block-details: external body ancestors` with state `declared label="处理请求"; rendered label="处理请求"` -> accepted.
Fail example: Inputs `P6 inputs in renderer-input, stage2 facts/hierarchy/presentation/granularity, and basic-block-details: external body ancestors` with state `declared label="处理请求"; rendered label="process"` -> rejected.

### P6.known_body_available
Aliases: -
Enforced: scripts/check_principles.py:367
Condition: Every indexed body actor has representations.mir.body_available exactly true.
Stage: Stage 7
Required producer fields: P6 inputs in renderer-input, stage2 facts/hierarchy/presentation/granularity, and basic-block-details: known body available
Pass example: Inputs `P6 inputs in renderer-input, stage2 facts/hierarchy/presentation/granularity, and basic-block-details: known body available` with state `declared="a1"; observed="a1"` -> accepted.
Fail example: Inputs `P6 inputs in renderer-input, stage2 facts/hierarchy/presentation/granularity, and basic-block-details: known body available` with state `declared="a1"; observed="missing"` -> rejected.

### P6.unique_body_identity
Aliases: -
Enforced: scripts/check_principles.py:322
Condition: The concrete failure collection passed to `self.result` is empty; executable comparison: `identities[body_key(a.get('bodyRef'))].append(a['actorId']) bad = [{'bodyRef': k, 'actors': v} for k, v in identities.items() if not k or len(v) != 1] bad += [{'actor': a['actorId'], 'reason': 'sourceNodeRef missing'} for a in self.actors if not a.get('sourceNodeRef')] self.result('P6', 'unique_body_identity', bad, body_actors=len(bodies)) declaration_ids = defaultdict(list)`.
Stage: Stage 7
Required producer fields: P6 inputs in renderer-input, stage2 facts/hierarchy/presentation/granularity, and basic-block-details: unique body identity
Pass example: Inputs `P6 inputs in renderer-input, stage2 facts/hierarchy/presentation/granularity, and basic-block-details: unique body identity` with state `values=["a","b"]` -> accepted.
Fail example: Inputs `P6 inputs in renderer-input, stage2 facts/hierarchy/presentation/granularity, and basic-block-details: unique body identity` with state `values=["a","a"]` -> rejected.

### P7.duplicates_
Aliases: -
Enforced: scripts/check_principles.py:407
Condition: The enclosing failure condition is false: `if reason: bad.append({'invocation': inv, 'kinds': dict(kinds), 'reason': reason}) bad += [{'pair': p, 'invocations': sorted(v)} for p, v in pair_inv.items() if len(v) > 1] self.result(principle, 'invocation_pair_integrity', bad, invocations=len(invocations))  def check_p7(self): duplicate_report = audit_duplicates(self.data, self.details, self.granularity, {'units': self.summaries}) for category, findings in duplicate_report['inventory'].items(): self.result('P7', 'duplicates_' + category,`.
Stage: Stage 7
Required producer fields: P7 inputs in renderer-input, stage2 facts/hierarchy/presentation/granularity, and basic-block-details: duplicates 
Pass example: Inputs `P7 inputs in renderer-input, stage2 facts/hierarchy/presentation/granularity, and basic-block-details: duplicates ` with state `values=["a","b"]` -> accepted.
Fail example: Inputs `P7 inputs in renderer-input, stage2 facts/hierarchy/presentation/granularity, and basic-block-details: duplicates ` with state `values=["a","a"]` -> rejected.

### P7.runtime_display_structures
Aliases: -
Enforced: scripts/check_principles.py:426
Condition: No branch role is ready/pending/unwind and no return meaning is future-handle/poll-pending.
Stage: Stage 7
Required producer fields: renderer controls/readingScopes/execution nodes and runtime-only classification records
Pass example: Inputs `renderer controls/readingScopes/execution nodes and runtime-only classification records` with state `runtime-only bb7 appears only in technical records` -> accepted.
Fail example: Inputs `renderer controls/readingScopes/execution nodes and runtime-only classification records` with state `runtime-only bb7 is rendered as action a7` -> rejected.

### P8.local_mechanism_columns
Aliases: -
Enforced: scripts/check_principles.py:447
Condition: The enclosing failure condition is false: `if self.selection is None: self.review('P8', 'local_mechanism_columns', '缺少对象语义选择账本；不能按函数名自动裁定机制对象。') return local = [x for x in self.selection['items'] if x['disposition'] == 'local_mechanism'] bad = [x for x in local if x.get('actorRef') in self.actor_by_id or x.get('ownerActionRef') not in {a['id'] for a in self.actions} or not x.get('businessMeaning') or not x.get('sourceRefs')] self.result('P8', 'local_mechanism_columns', bad, local_objects=len(local))`.
Stage: Stage 7
Required producer fields: P8 inputs in renderer-input, stage2 facts/hierarchy/presentation/granularity, and basic-block-details: local mechanism columns
Pass example: Inputs `P8 inputs in renderer-input, stage2 facts/hierarchy/presentation/granularity, and basic-block-details: local mechanism columns` with state `declared="a1"; observed="a1"` -> accepted.
Fail example: Inputs `P8 inputs in renderer-input, stage2 facts/hierarchy/presentation/granularity, and basic-block-details: local mechanism columns` with state `declared="a1"; observed="missing"` -> rejected.

### P9.canonical_member_uniqueness
Aliases: -
Enforced: scripts/check_principles.py:468
Condition: The enclosing failure condition is false: `if key is None: key = [m.get('purposeRef'), m.get('targetActorRef'), m.get('stageRole'), m.get('basis')] canonical[json.dumps(key, sort_keys=True)].append(m.get('invocationRef')) bad = [{'canonical_key': k, 'invocations': v} for k, v in canonical.items() if len(v) > 1] self.result('P9', 'canonical_member_uniqueness', bad, members=len(members))`.
Stage: Stage 7
Required producer fields: P9 inputs in renderer-input, stage2 facts/hierarchy/presentation/granularity, and basic-block-details: canonical member uniqueness
Pass example: Inputs `P9 inputs in renderer-input, stage2 facts/hierarchy/presentation/granularity, and basic-block-details: canonical member uniqueness` with state `values=["a","b"]` -> accepted.
Fail example: Inputs `P9 inputs in renderer-input, stage2 facts/hierarchy/presentation/granularity, and basic-block-details: canonical member uniqueness` with state `values=["a","a"]` -> rejected.

### P9.purpose_member_references
Aliases: -
Enforced: scripts/check_principles.py:474
Condition: The enclosing failure condition is false: `if duplicates: self.review('P9', 'same_call_endpoint_requests', '相同调用依据/端点有多个请求，需核验是否独立角色或跨层副本。', count=len(duplicates), examples=duplicates[:8]) else: self.result('P9', 'same_call_endpoint_requests', [], request_members=len(by_basis)) bad = [{'purpose': p['id'], 'invocation': inv} for p in self.data.get('purposeProjections', []) for inv in p.get('invocationRefs', []) if inv not in invs and inv not in {c.get('invocationRef') for c in self.controls}] self.result('P9', 'purpose_member_references', bad)`.
Stage: Stage 7
Required producer fields: P9 inputs in renderer-input, stage2 facts/hierarchy/presentation/granularity, and basic-block-details: purpose member references
Pass example: Inputs `P9 inputs in renderer-input, stage2 facts/hierarchy/presentation/granularity, and basic-block-details: purpose member references` with state `values=["a","b"]` -> accepted.
Fail example: Inputs `P9 inputs in renderer-input, stage2 facts/hierarchy/presentation/granularity, and basic-block-details: purpose member references` with state `values=["a","a"]` -> rejected.

### P9.same_call_endpoint_requests
Aliases: -
Enforced: scripts/check_principles.py:472
Condition: The enclosing failure condition is false: `if duplicates: self.review('P9', 'same_call_endpoint_requests', '相同调用依据/端点有多个请求，需核验是否独立角色或跨层副本。', count=len(duplicates), examples=duplicates[:8]) else: self.result('P9', 'same_call_endpoint_requests', [], request_members=len(by_basis))`.
Stage: Stage 7
Required producer fields: P9 inputs in renderer-input, stage2 facts/hierarchy/presentation/granularity, and basic-block-details: same call endpoint requests
Pass example: Inputs `P9 inputs in renderer-input, stage2 facts/hierarchy/presentation/granularity, and basic-block-details: same call endpoint requests` with state `values=["a","b"]` -> accepted.
Fail example: Inputs `P9 inputs in renderer-input, stage2 facts/hierarchy/presentation/granularity, and basic-block-details: same call endpoint requests` with state `values=["a","a"]` -> rejected.

### actor.bodyChildren
Aliases: -
Enforced: assets/renderer/contract.mjs:26
Condition: Fails exactly when the enforcing predicate reports: `callable leaf required`.
Stage: Stage 7
Required producer fields: actors[].kind; actors[].children
Pass example: Inputs `actors[].kind; actors[].children` with state `{"actors":[{"actorId":"a","kind":"body","children":[]}]}` -> accepted.
Fail example: Inputs `actors[].kind; actors[].children` with state `{"actors":[{"actorId":"a","kind":"body","children":[{"actorId":"nested","kind":"body"}]}]}` -> rejected.

### actor.declaration
Aliases: -
Enforced: assets/renderer/contract.mjs:26
Condition: Fails exactly when the enforcing predicate reports: `exact declaration identity without a fabricated implementation body required`.
Stage: Stage 7
Required producer fields: actors[].kind; actors[].bodyRef; actors[].sourceNodeRef; actors[].declarationRef; actors[].implementationStatus
Pass example: Inputs `actors[].kind; actors[].bodyRef; actors[].sourceNodeRef; actors[].declarationRef; actors[].implementationStatus` with state `declaredRefs=["a1"]; observedRefs=["a1"]` -> accepted.
Fail example: Inputs `actors[].kind; actors[].bodyRef; actors[].sourceNodeRef; actors[].declarationRef; actors[].implementationStatus` with state `declaredRefs=["a1"]; observedRefs=[]` -> rejected.

### actor.hierarchy
Aliases: -
Enforced: assets/renderer/contract.mjs:26
Condition: Fails exactly when the enforcing predicate reports: `crate→module→body/declaration`.
Stage: Stage 7
Required producer fields: actors[].kind; actors[].children[].kind
Pass example: Inputs `actors[].kind; actors[].children[].kind` with state `declared="a1"; observed="a1"` -> accepted.
Fail example: Inputs `actors[].kind; actors[].children[].kind` with state `declared="a1"; observed="missing"` -> rejected.

### actor.parent
Aliases: -
Enforced: assets/renderer/contract.mjs:26
Condition: Fails exactly when the enforcing predicate reports: `wrong parent`.
Stage: Stage 7
Required producer fields: actors[].actorId; actors[].parentActorId; enclosing actors[].actorId
Pass example: Inputs `actors[].actorId; actors[].parentActorId; enclosing actors[].actorId` with state `declared="a1"; observed="a1"` -> accepted.
Fail example: Inputs `actors[].actorId; actors[].parentActorId; enclosing actors[].actorId` with state `declared="a1"; observed="missing"` -> rejected.

### actor.root
Aliases: -
Enforced: assets/renderer/contract.mjs:69
Condition: Fails exactly when the enforcing predicate reports: `root actor is body or crate`.
Stage: Stage 7
Required producer fields: top-level actors[].kind
Pass example: Inputs `top-level actors[].kind` with state `declared="a1"; observed="a1"` -> accepted.
Fail example: Inputs `top-level actors[].kind` with state `declared="a1"; observed="missing"` -> rejected.

### async-shell-binding-failed
Aliases: -
Enforced: scripts/async_shell_verifier.py:492
Condition: The enclosing failure condition is false: `if not binding and not strict: failures.append({'code': 'async-shell-binding-failed',`.
Stage: Stage 7
Required producer fields: classification.async_shell; shell/inner owner hashes; selected definition hash; relation shellBodyId/innerBodyId
Pass example: Inputs `classification.async_shell; shell/inner owner hashes; selected definition hash; relation shellBodyId/innerBodyId` with state `shell owner="h-shell" and inner owner="h-inner" match the selected async binding` -> accepted.
Fail example: Inputs `classification.async_shell; shell/inner owner hashes; selected definition hash; relation shellBodyId/innerBodyId` with state `relation innerBodyId="h-other" while selected inner owner="h-inner"` -> rejected.

### async-shell-claim-mismatch
Aliases: -
Enforced: scripts/async_shell_verifier.py:512
Condition: The enclosing failure condition is false: `if claim.get(field) != computed[field]: failures.append({'code': 'async-shell-claim-mismatch', 'field': field,`.
Stage: Stage 7
Required producer fields: raw MIR blocks/terminators/source_info; renderer-input functionSource and node basicBlockRefs/lineRanges; verifier pin/relation/classification/certificate record; async shell claim mismatch proof fields
Pass example: Inputs `raw MIR blocks/terminators/source_info; renderer-input functionSource and node basicBlockRefs/lineRanges; verifier pin/relation/classification/certificate record; async shell claim mismatch proof fields` with state `declared="a1"; observed="a1"` -> accepted.
Fail example: Inputs `raw MIR blocks/terminators/source_info; renderer-input functionSource and node basicBlockRefs/lineRanges; verifier pin/relation/classification/certificate record; async shell claim mismatch proof fields` with state `declared="a1"; observed="missing"` -> rejected.

### async-shell-relation-mismatch
Aliases: -
Enforced: scripts/async_shell_verifier.py:516
Condition: The enclosing failure condition is false: `if claimed_relation.get(field) != value: failures.append({'code': 'async-shell-relation-mismatch', 'field': field,`.
Stage: Stage 7
Required producer fields: raw MIR blocks/terminators/source_info; renderer-input functionSource and node basicBlockRefs/lineRanges; verifier pin/relation/classification/certificate record; async shell relation mismatch proof fields
Pass example: Inputs `raw MIR blocks/terminators/source_info; renderer-input functionSource and node basicBlockRefs/lineRanges; verifier pin/relation/classification/certificate record; async shell relation mismatch proof fields` with state `declared="a1"; observed="a1"` -> accepted.
Fail example: Inputs `raw MIR blocks/terminators/source_info; renderer-input functionSource and node basicBlockRefs/lineRanges; verifier pin/relation/classification/certificate record; async shell relation mismatch proof fields` with state `declared="a1"; observed="missing"` -> rejected.

### attribute-lines-mismatch
Aliases: -
Enforced: scripts/attribute_source_verifier.py:224
Condition: functionSource.attributeLines equals the minimum startLine through maximum endLine of qualifying attributes.
Stage: Stage 7
Required producer fields: raw MIR blocks/terminators/source_info; renderer-input functionSource and node basicBlockRefs/lineRanges; verifier pin/relation/classification/certificate record; attribute lines mismatch proof fields
Pass example: Inputs `raw MIR blocks/terminators/source_info; renderer-input functionSource and node basicBlockRefs/lineRanges; verifier pin/relation/classification/certificate record; attribute lines mismatch proof fields` with state `functionSource L10-L12; lineRanges=[L10-L11]` -> accepted.
Fail example: Inputs `raw MIR blocks/terminators/source_info; renderer-input functionSource and node basicBlockRefs/lineRanges; verifier pin/relation/classification/certificate record; attribute lines mismatch proof fields` with state `functionSource L10-L12; lineRanges=[L9-L11]` -> rejected.

### attribute-lines-without-operation
Aliases: -
Enforced: scripts/attribute_source_verifier.py:231
Condition: The enclosing failure condition is false: `if claimed_attribute is not None: errors.append({'code': 'attribute-lines-without-operation',`.
Stage: Stage 7
Required producer fields: functionSource.attributeLines; independently derived qualifying attribute operation
Pass example: Inputs `functionSource.attributeLines; independently derived qualifying attribute operation` with state `attributeLines is absent when no qualifying attribute operation exists` -> accepted.
Fail example: Inputs `functionSource.attributeLines; independently derived qualifying attribute operation` with state `attributeLines={startLine:1,endLine:1} while no qualifying attribute operation exists` -> rejected.

### attribute-range-without-node-operation
Aliases: -
Enforced: scripts/attribute_source_verifier.py:258, scripts/attribute_source_verifier.py:274
Condition: The enclosing failure condition is false: `elif exact not in supported: errors.append({'code': 'attribute-range-without-node-operation',`.
Stage: Stage 7
Required producer fields: raw MIR blocks/terminators/source_info; renderer-input functionSource and node basicBlockRefs/lineRanges; verifier pin/relation/classification/certificate record; attribute range without node operation proof fields
Pass example: Inputs `raw MIR blocks/terminators/source_info; renderer-input functionSource and node basicBlockRefs/lineRanges; verifier pin/relation/classification/certificate record; attribute range without node operation proof fields` with state `functionSource L10-L12; lineRanges=[L10-L11]` -> accepted.
Fail example: Inputs `raw MIR blocks/terminators/source_info; renderer-input functionSource and node basicBlockRefs/lineRanges; verifier pin/relation/classification/certificate record; attribute range without node operation proof fields` with state `functionSource L10-L12; lineRanges=[L9-L11]` -> rejected.

### attribute-source-tokenizer
Aliases: -
Enforced: scripts/attribute_source_verifier.py:205
Condition: The enclosing failure condition is false: `if source_bytes is None: source_bytes = (('\n' * max(0, source.get('startLine', 1)-1)) + '\n'.join(source.get('lines', []))).encode('utf-8') errors = [] try: attributes, signature_line = _attached_attributes(source_bytes, source) except (UnicodeDecodeError, ValueError) as error: return [{'code': 'attribute-source-tokenizer', 'detail': str(error)}]`.
Stage: Stage 7
Required producer fields: raw MIR blocks/terminators/source_info; renderer-input functionSource and node basicBlockRefs/lineRanges; verifier pin/relation/classification/certificate record; record fields startLine, lines
Pass example: Inputs `raw MIR blocks/terminators/source_info; renderer-input functionSource and node basicBlockRefs/lineRanges; verifier pin/relation/classification/certificate record; record fields startLine, lines` with state `functionSource L10-L12; lineRanges=[L10-L11]` -> accepted.
Fail example: Inputs `raw MIR blocks/terminators/source_info; renderer-input functionSource and node basicBlockRefs/lineRanges; verifier pin/relation/classification/certificate record; record fields startLine, lines` with state `functionSource L10-L12; lineRanges=[L9-L11]` -> rejected.

### bb-namespace
Aliases: -
Enforced: scripts/verify_source_evidence.py:156
Condition: The enclosing failure condition is false: `elif re.fullmatch(r'shell:bb[0-9]+', ref): table, types, body_raw = shell_blocks, shell_types, shell_raw or {} else: errors.append(dict(code='bb-namespace', node=node['id'], bbRef=ref))`.
Stage: Stage 7
Required producer fields: raw MIR blocks/terminators/source_info; renderer-input functionSource and node basicBlockRefs/lineRanges; verifier pin/relation/classification/certificate record; record fields id; read operation: bb namespace
Pass example: Inputs `raw MIR blocks/terminators/source_info; renderer-input functionSource and node basicBlockRefs/lineRanges; verifier pin/relation/classification/certificate record; record fields id; read operation: bb namespace` with state `basicBlockRefs=["shell:bb0"]` -> accepted.
Fail example: Inputs `raw MIR blocks/terminators/source_info; renderer-input functionSource and node basicBlockRefs/lineRanges; verifier pin/relation/classification/certificate record; record fields id; read operation: bb namespace` with state `basicBlockRefs=["bb0"]` -> rejected.

### control.alt
Aliases: -
Enforced: assets/renderer/contract.mjs:22
Condition: Fails exactly when the enforcing predicate reports: `alt needs explicit alternatives`.
Stage: Stage 7
Required producer fields: controls[].kind; controls[].branches
Pass example: Inputs `controls[].kind; controls[].branches` with state `{"controls":[{"id":"c","kind":"alt","branches":[{"id":"yes"},{"id":"no"}]}]}` -> accepted.
Fail example: Inputs `controls[].kind; controls[].branches` with state `{"controls":[{"id":"c","kind":"alt","branches":[{"id":"yes"}]}]}` -> rejected.

### control.loop
Aliases: -
Enforced: assets/renderer/contract.mjs:22
Condition: Fails exactly when the enforcing predicate reports: `loop needs continue/exit`.
Stage: Stage 7
Required producer fields: controls[].kind; controls[].repeat.continue; controls[].repeat.exit
Pass example: Inputs `controls[].kind; controls[].repeat.continue; controls[].repeat.exit` with state `declared="a1"; observed="a1"` -> accepted.
Fail example: Inputs `controls[].kind; controls[].repeat.continue; controls[].repeat.exit` with state `declared="a1"; observed="missing"` -> rejected.

### control.multipleOwners
Aliases: -
Enforced: assets/renderer/contract.mjs:16
Condition: The executable comparison is satisfied: `function own(ref,scope){if(!roots.has(ref))fail('reference.control',scope,ref);if(ownership.has(ref))fail('control.multipleOwners',scope,ref);ownership.set(ref,scope);}`.
Stage: Stage 7
Required producer fields: rootControlRefs; phases[].boundaryControlRefs; phases[].goals[].actions[].controlRefs
Pass example: Inputs `rootControlRefs; phases[].boundaryControlRefs; phases[].goals[].actions[].controlRefs` with state `declared="a1"; observed="a1"` -> accepted.
Fail example: Inputs `rootControlRefs; phases[].boundaryControlRefs; phases[].goals[].actions[].controlRefs` with state `declared="a1"; observed="missing"` -> rejected.

### control.opt
Aliases: -
Enforced: assets/renderer/contract.mjs:22
Condition: Fails exactly when the enforcing predicate reports: `opt needs bypass`.
Stage: Stage 7
Required producer fields: controls[].kind; controls[].skip
Pass example: Inputs `controls[].kind; controls[].skip` with state `declared="a1"; observed="a1"` -> accepted.
Fail example: Inputs `controls[].kind; controls[].skip` with state `declared="a1"; observed="missing"` -> rejected.

### control.unowned
Aliases: -
Enforced: assets/renderer/contract.mjs:19
Condition: Fails exactly when the enforcing predicate reports: `controls`.
Stage: Stage 7
Required producer fields: controls[].id; rootControlRefs; phases[].boundaryControlRefs; phases[].goals[].actions[].controlRefs
Pass example: Inputs `controls[].id; rootControlRefs; phases[].boundaryControlRefs; phases[].goals[].actions[].controlRefs` with state `declaredRefs=["a1"]; observedRefs=["a1"]` -> accepted.
Fail example: Inputs `controls[].id; rootControlRefs; phases[].boundaryControlRefs; phases[].goals[].actions[].controlRefs` with state `declaredRefs=["a1"]; observedRefs=[]` -> rejected.

### decision-outside-operation
Aliases: -
Enforced: scripts/verify_source_evidence.py:128
Condition: Each claimed decision line is in the independently derived SwitchInt/Call/selector-Discriminant source-line set.
Stage: Stage 7
Required producer fields: node lineRanges/basicBlockRefs; independently derived SwitchInt/Call/selector-Discriminant source lines
Pass example: Inputs `node lineRanges/basicBlockRefs; independently derived SwitchInt/Call/selector-Discriminant source lines` with state `decision line 12 is in derived operation lines [12]` -> accepted.
Fail example: Inputs `node lineRanges/basicBlockRefs; independently derived SwitchInt/Call/selector-Discriminant source lines` with state `decision line 11 is outside derived operation lines [12]` -> rejected.

### derived.branchRoles
Aliases: -
Enforced: assets/renderer/contract.mjs:78
Condition: Sorting by branchRef, branchRoles with role removed must equal every control branch's `{branchRef,controlRef}` pair exactly.
Stage: Stage 6
Required producer fields: branchRoles[].branchRef/controlRef; controls tree branches[].id
Pass example: Inputs `branchRoles[].branchRef/controlRef; controls tree branches[].id` with state `declared="a1"; observed="a1"` -> accepted.
Fail example: Inputs `branchRoles[].branchRef/controlRef; controls tree branches[].id` with state `declared="a1"; observed="missing"` -> rejected.

### derived.controlOwners
Aliases: -
Enforced: assets/renderer/contract.mjs:74
Condition: Sorted controlOwners must equal ownership derived from rootControlRefs, phase boundaryControlRefs, and action controlRefs exactly.
Stage: Stage 6
Required producer fields: controlOwners[].controlRef/owner; rootControlRefs; phases[].boundaryControlRefs; actions[].controlRefs
Pass example: Inputs `controlOwners[].controlRef/owner; rootControlRefs; phases[].boundaryControlRefs; actions[].controlRefs` with state `declared="a1"; observed="a1"` -> accepted.
Fail example: Inputs `controlOwners[].controlRef/owner; rootControlRefs; phases[].boundaryControlRefs; actions[].controlRefs` with state `declared="a1"; observed="missing"` -> rejected.

### derived.fixture
Aliases: -
Enforced: assets/renderer/contract.mjs:31
Condition: fixture must deep-equal `{actors:data.actors,messages:[]}`, including actor order and every actor field.
Stage: Stage 6
Required producer fields: fixture.actors; fixture.messages; actors
Pass example: Inputs `fixture.actors; fixture.messages; actors` with state `{"actors":[{"actorId":"a","kind":"body","children":[]}],"fixture":{"actors":[{"actorId":"a","kind":"body","children":[]}],"messages":[]}}` -> accepted.
Fail example: Inputs `fixture.actors; fixture.messages; actors` with state `{"actors":[{"actorId":"a","kind":"body","children":[]}],"fixture":{"actors":[{"actorId":"a","kind":"body","children":[]}],"messages":[{"messageId":"m1"}]}}` -> rejected.

### derived.messagePlacements
Aliases: -
Enforced: assets/renderer/contract.mjs:77
Condition: Sorted messagePlacements must equal control traversal output `{messageRef,controlRef,rootControlRef,branchPath}` exactly.
Stage: Stage 6
Required producer fields: messagePlacements[].messageRef/controlRef/rootControlRef/branchPath; controls tree messages
Pass example: Inputs `messagePlacements[].messageRef/controlRef/rootControlRef/branchPath; controls tree messages` with state `declared="a1"; observed="a1"` -> accepted.
Fail example: Inputs `messagePlacements[].messageRef/controlRef/rootControlRef/branchPath; controls tree messages` with state `declared="a1"; observed="missing"` -> rejected.

### duplicate-prelude-bb
Aliases: -
Enforced: scripts/async_shell_verifier.py:443
Condition: The enclosing failure condition is false: `if len(refs) != len(actual): failures.append({'code': 'duplicate-prelude-bb'})`.
Stage: Stage 7
Required producer fields: raw MIR blocks/terminators/source_info; renderer-input functionSource and node basicBlockRefs/lineRanges; verifier pin/relation/classification/certificate record; duplicate prelude bb proof fields
Pass example: Inputs `raw MIR blocks/terminators/source_info; renderer-input functionSource and node basicBlockRefs/lineRanges; verifier pin/relation/classification/certificate record; duplicate prelude bb proof fields` with state `values=["a","b"]` -> accepted.
Fail example: Inputs `raw MIR blocks/terminators/source_info; renderer-input functionSource and node basicBlockRefs/lineRanges; verifier pin/relation/classification/certificate record; duplicate prelude bb proof fields` with state `values=["a","a"]` -> rejected.

### duplicate-shell-technical-bb
Aliases: -
Enforced: scripts/async_shell_verifier.py:406
Condition: The enclosing failure condition is false: `if duplicate_records: failures.append({'code': 'duplicate-shell-technical-bb',`.
Stage: Stage 7
Required producer fields: raw MIR blocks/terminators/source_info; renderer-input functionSource and node basicBlockRefs/lineRanges; verifier pin/relation/classification/certificate record; duplicate shell technical bb proof fields
Pass example: Inputs `raw MIR blocks/terminators/source_info; renderer-input functionSource and node basicBlockRefs/lineRanges; verifier pin/relation/classification/certificate record; duplicate shell technical bb proof fields` with state `values=["a","b"]` -> accepted.
Fail example: Inputs `raw MIR blocks/terminators/source_info; renderer-input functionSource and node basicBlockRefs/lineRanges; verifier pin/relation/classification/certificate record; duplicate shell technical bb proof fields` with state `values=["a","a"]` -> rejected.

### event-macro-proof-mismatch
Aliases: -
Enforced: scripts/event_macro_verifier.py:331
Condition: The enclosing failure condition is false: `elif record.get('eventMacroProof') != block: errors.append({'code': 'event-macro-proof-mismatch', 'bbRef': ref})`.
Stage: Stage 7
Required producer fields: raw MIR blocks/terminators/source_info; renderer-input functionSource and node basicBlockRefs/lineRanges; verifier pin/relation/classification/certificate record; record fields eventMacroProof
Pass example: Inputs `raw MIR blocks/terminators/source_info; renderer-input functionSource and node basicBlockRefs/lineRanges; verifier pin/relation/classification/certificate record; record fields eventMacroProof` with state `declared="a1"; observed="a1"` -> accepted.
Fail example: Inputs `raw MIR blocks/terminators/source_info; renderer-input functionSource and node basicBlockRefs/lineRanges; verifier pin/relation/classification/certificate record; record fields eventMacroProof` with state `declared="a1"; observed="missing"` -> rejected.

### evidence.claim
Aliases: -
Enforced: assets/renderer/execution.mjs:38
Condition: Each claim's subjectRef and every target must resolve to a known execution/reading/control/message/scope/task ID, and conditions must be normalized non-empty distinct strings.
Stage: Stage 6
Required producer fields: execution.evidence[].id/artifactRef/claim.kind/subjectRef/targets/conditions; evidenceRefs on the proving record
Pass example: Inputs `execution.evidence[].id/artifactRef/claim.kind/subjectRef/targets/conditions; evidenceRefs on the proving record` with state `declared="a1"; observed="a1"` -> accepted.
Fail example: Inputs `execution.evidence[].id/artifactRef/claim.kind/subjectRef/targets/conditions; evidenceRefs on the proving record` with state `declared="a1"; observed="missing"` -> rejected.

### evidence.digest
Aliases: -
Enforced: assets/renderer/execution.mjs:34
Condition: Fails exactly when the enforcing predicate reports: `snapshot content differs from declared SHA-256`.
Stage: Stage 7
Required producer fields: execution.artifacts[].content/sha256
Pass example: Inputs `execution.artifacts[].content/sha256` with state `declared sha256="abc"; computed sha256="abc"` -> accepted.
Fail example: Inputs `execution.artifacts[].content/sha256` with state `declared sha256="abc"; computed sha256="def"` -> rejected.

### evidence.quote
Aliases: -
Enforced: assets/renderer/execution.mjs:35
Condition: evidence.quote must be a literal substring of content in the artifact selected by evidence.artifactRef.
Stage: Stage 6
Required producer fields: execution.evidence[].artifactRef/quote; execution.artifacts[].id/content
Pass example: Inputs `execution.evidence[].artifactRef/quote; execution.artifacts[].id/content` with state `declared="a1"; observed="a1"` -> accepted.
Fail example: Inputs `execution.evidence[].artifactRef/quote; execution.artifacts[].id/content` with state `declared="a1"; observed="missing"` -> rejected.

### execution.actionNodes
Aliases: -
Enforced: assets/renderer/execution.mjs:43
Condition: Fails exactly when the enforcing predicate reports: `one execution node per required displayed action`.
Stage: Stage 7
Required producer fields: execution.inventory.actionRefs; execution.nodes[].kind/actionRef
Pass example: Inputs `execution.inventory.actionRefs; execution.nodes[].kind/actionRef` with state `declaredRefs=["a1"]; observedRefs=["a1"]` -> accepted.
Fail example: Inputs `execution.inventory.actionRefs; execution.nodes[].kind/actionRef` with state `declaredRefs=["a1"]; observedRefs=[]` -> rejected.

### execution.actionRef
Aliases: -
Enforced: assets/renderer/execution.mjs:46
Condition: Fails exactly when the enforcing predicate reports: `unknown action`.
Stage: Stage 7
Required producer fields: execution.nodes[].kind/actionRef; phases[].goals[].actions[].id
Pass example: Inputs `execution.nodes[].kind/actionRef; phases[].goals[].actions[].id` with state `{"phases":[{"goals":[{"actions":[{"id":"a1"}]}]}],"execution":{"nodes":[{"id":"n1","kind":"action","actionRef":"a1"}]}}` -> accepted.
Fail example: Inputs `execution.nodes[].kind/actionRef; phases[].goals[].actions[].id` with state `{"phases":[{"goals":[{"actions":[{"id":"a1"}]}]}],"execution":{"nodes":[{"id":"n1","kind":"action","actionRef":"missing"}]}}` -> rejected.

### execution.afterTerminal
Aliases: -
Enforced: assets/renderer/execution.mjs:60
Condition: Fails exactly when the enforcing predicate reports: `no normal continuation after return/error/unwind/Pending`.
Stage: Stage 7
Required producer fields: execution.nodes[].kind/outcome; execution.edges[].from/kind
Pass example: Inputs `execution.nodes[].kind/outcome; execution.edges[].from/kind` with state `declared="a1"; observed="a1"` -> accepted.
Fail example: Inputs `execution.nodes[].kind/outcome; execution.edges[].from/kind` with state `declared="a1"; observed="missing"` -> rejected.

### execution.annotationCoverage
Aliases: -
Enforced: assets/renderer/execution.mjs:67
Condition: Fails exactly when the enforcing predicate reports: `draw-false annotation must be attached to a reached owner`.
Stage: Stage 7
Required producer fields: scopeAnnotations[].id; purposeProjections[].id; execution.attachments[].scopeAnnotationRef/purposeRef
Pass example: Inputs `scopeAnnotations[].id; purposeProjections[].id; execution.attachments[].scopeAnnotationRef/purposeRef` with state `declaredRefs=["a1"]; observedRefs=["a1"]` -> accepted.
Fail example: Inputs `scopeAnnotations[].id; purposeProjections[].id; execution.attachments[].scopeAnnotationRef/purposeRef` with state `declaredRefs=["a1"]; observedRefs=[]` -> rejected.

### execution.arrivalWitness
Aliases: -
Enforced: assets/renderer/execution.mjs:82
Condition: Fails exactly when the enforcing predicate reports: `declared shared successor needs a feasible arrival for each stated branch/bypass/exit`.
Stage: Stage 7
Required producer fields: readingScopes[].commonAfter; execution.decisions[].values; reachable execution edge guards
Pass example: Inputs `readingScopes[].commonAfter; execution.decisions[].values; reachable execution edge guards` with state `declared="a1"; observed="a1"` -> accepted.
Fail example: Inputs `readingScopes[].commonAfter; execution.decisions[].values; reachable execution edge guards` with state `declared="a1"; observed="missing"` -> rejected.

### execution.attachmentOwner
Aliases: -
Enforced: assets/renderer/execution.mjs:66
Condition: Fails exactly when the enforcing predicate reports: `attachment belongs to an executable owner`.
Stage: Stage 7
Required producer fields: execution.attachments[].ownerActionRef; phases[].goals[].actions[].id
Pass example: Inputs `execution.attachments[].ownerActionRef; phases[].goals[].actions[].id` with state `declared="a1"; observed="a1"` -> accepted.
Fail example: Inputs `execution.attachments[].ownerActionRef; phases[].goals[].actions[].id` with state `declared="a1"; observed="missing"` -> rejected.

### execution.attachmentRef
Aliases: -
Enforced: assets/renderer/execution.mjs:66
Condition: Fails exactly when the enforcing predicate reports: `one exact existing displayed annotation/control reference required`.
Stage: Stage 7
Required producer fields: execution.attachments[].controlRef/scopeAnnotationRef/purposeRef; controls/annotations/purposes IDs
Pass example: Inputs `execution.attachments[].controlRef/scopeAnnotationRef/purposeRef; controls/annotations/purposes IDs` with state `declaredRefs=["a1"]; observedRefs=["a1"]` -> accepted.
Fail example: Inputs `execution.attachments[].controlRef/scopeAnnotationRef/purposeRef; controls/annotations/purposes IDs` with state `declaredRefs=["a1"]; observedRefs=[]` -> rejected.

### execution.await
Aliases: -
Enforced: assets/renderer/execution.mjs:55
Condition: Fails exactly when the enforcing predicate reports: `await must hand off to same registered task`.
Stage: Stage 7
Required producer fields: execution.edges[].kind/to/taskId; execution.nodes[].kind/event/taskId
Pass example: Inputs `execution.edges[].kind/to/taskId; execution.nodes[].kind/event/taskId` with state `declared="a1"; observed="a1"` -> accepted.
Fail example: Inputs `execution.edges[].kind/to/taskId; execution.nodes[].kind/event/taskId` with state `declared="a1"; observed="missing"` -> rejected.

### execution.branchPartition
Aliases: -
Enforced: assets/renderer/execution.mjs:60
Condition: Fails exactly when the enforcing predicate reports: `one explicit outgoing alternative for every declared decision value`.
Stage: Stage 7
Required producer fields: execution.nodes[].decisionRef; execution.edges[].from/kind/guards; execution.decisions[].id/values
Pass example: Inputs `execution.nodes[].decisionRef; execution.edges[].from/kind/guards; execution.decisions[].id/values` with state `{"decision":{"id":"d","values":["yes","no"]},"outgoingGuards":["d=yes","d=no"]}` -> accepted.
Fail example: Inputs `execution.nodes[].decisionRef; execution.edges[].from/kind/guards; execution.decisions[].id/values` with state `{"decision":{"id":"d","values":["yes","no"]},"outgoingGuards":["d=yes"]}` -> rejected.

### execution.construct
Aliases: -
Enforced: assets/renderer/execution.mjs:49
Condition: Fails exactly when the enforcing predicate reports: `constructor must be unique registered origin`.
Stage: Stage 7
Required producer fields: execution.nodes[].event/taskId; execution.tasks[].constructNodeRef
Pass example: Inputs `execution.nodes[].event/taskId; execution.tasks[].constructNodeRef` with state `values=["a","b"]` -> accepted.
Fail example: Inputs `execution.nodes[].event/taskId; execution.tasks[].constructNodeRef` with state `values=["a","a"]` -> rejected.

### execution.controlCoverage
Aliases: -
Enforced: assets/renderer/execution.mjs:64
Condition: Fails exactly when the enforcing predicate reports: `all control roots need exact execution binding`.
Stage: Stage 7
Required producer fields: execution.controlBindings[].controlRef; controls[].id
Pass example: Inputs `execution.controlBindings[].controlRef; controls[].id` with state `declaredRefs=["a1"]; observedRefs=["a1"]` -> accepted.
Fail example: Inputs `execution.controlBindings[].controlRef; controls[].id` with state `declaredRefs=["a1"]; observedRefs=[]` -> rejected.

### execution.controlDecision
Aliases: -
Enforced: assets/renderer/execution.mjs:61
Condition: Fails exactly when the enforcing predicate reports: `opt requires exact disjoint take/skip partition`; `local control alternatives require exact branch/value bindings`.
Stage: Stage 7
Required producer fields: execution.decisions[].controlRef/values/branchBindings/takeValues/skipValues; controls[].kind/branches
Pass example: Inputs `execution.decisions[].controlRef/values/branchBindings/takeValues/skipValues; controls[].kind/branches` with state `expected=["yes","no"]; observed=["yes","no"]` -> accepted.
Fail example: Inputs `execution.decisions[].controlRef/values/branchBindings/takeValues/skipValues; controls[].kind/branches` with state `expected=["yes","no"]; observed=["yes"]` -> rejected.

### execution.controlOwner
Aliases: -
Enforced: assets/renderer/execution.mjs:65
Condition: Fails exactly when the enforcing predicate reports: `execution binding must retain displayed owner`.
Stage: Stage 7
Required producer fields: execution.controlBindings[].controlRef/nodeRef; controlOwners[].controlRef/owner; execution.nodes[].actionRef
Pass example: Inputs `execution.controlBindings[].controlRef/nodeRef; controlOwners[].controlRef/owner; execution.nodes[].actionRef` with state `declared="a1"; observed="a1"` -> accepted.
Fail example: Inputs `execution.controlBindings[].controlRef/nodeRef; controlOwners[].controlRef/owner; execution.nodes[].actionRef` with state `declared="a1"; observed="missing"` -> rejected.

### execution.deadEnd
Aliases: -
Enforced: assets/renderer/execution.mjs:60
Condition: Fails exactly when the enforcing predicate reports: `nonterminal path requires an evidenced continuation or explicit termination`.
Stage: Stage 7
Required producer fields: execution.nodes[].id/kind; execution.edges[].from; read operation: deadEnd
Pass example: Inputs `execution.nodes[].id/kind; execution.edges[].from; read operation: deadEnd` with state `declaredRefs=["a1"]; observedRefs=["a1"]` -> accepted.
Fail example: Inputs `execution.nodes[].id/kind; execution.edges[].from; read operation: deadEnd` with state `declaredRefs=["a1"]; observedRefs=[]` -> rejected.

### execution.decisionRef
Aliases: -
Enforced: assets/renderer/execution.mjs:47
Condition: Fails exactly when the enforcing predicate reports: `unknown decision`.
Stage: Stage 7
Required producer fields: execution.nodes[].decisionRef; execution.decisions[].id
Pass example: Inputs `execution.nodes[].decisionRef; execution.decisions[].id` with state `declared="a1"; observed="a1"` -> accepted.
Fail example: Inputs `execution.nodes[].decisionRef; execution.decisions[].id` with state `declared="a1"; observed="missing"` -> rejected.

### execution.duplicate
Aliases: -
Enforced: assets/renderer/execution.mjs:31, assets/renderer/execution.mjs:66
Condition: Fails exactly when the enforcing predicate reports: `attachments`.
Stage: Stage 7
Required producer fields: execution artifacts/evidence/nodes/edges/decisions/tasks/attachments IDs
Pass example: Inputs `execution artifacts/evidence/nodes/edges/decisions/tasks/attachments IDs` with state `values=["a","b"]` -> accepted.
Fail example: Inputs `execution artifacts/evidence/nodes/edges/decisions/tasks/attachments IDs` with state `values=["a","a"]` -> rejected.

### execution.edgeRef
Aliases: -
Enforced: assets/renderer/execution.mjs:53
Condition: Fails exactly when the enforcing predicate reports: `exact source/target nodes required`.
Stage: Stage 7
Required producer fields: execution.edges[].from/to; execution.nodes[].id
Pass example: Inputs `execution.edges[].from/to; execution.nodes[].id` with state `declaredRefs=["a1"]; observedRefs=["a1"]` -> accepted.
Fail example: Inputs `execution.edges[].from/to; execution.nodes[].id` with state `declaredRefs=["a1"]; observedRefs=[]` -> rejected.

### execution.entry
Aliases: -
Enforced: assets/renderer/execution.mjs:42
Condition: Fails exactly when the enforcing predicate reports: `one evidenced entry belonging to semanticRoot is required`.
Stage: Stage 7
Required producer fields: execution.rootActorRef/entryNodeRef; semanticRoot.actorRef; execution.nodes[].kind
Pass example: Inputs `execution.rootActorRef/entryNodeRef; semanticRoot.actorRef; execution.nodes[].kind` with state `declaredRefs=["a1"]; observedRefs=["a1"]` -> accepted.
Fail example: Inputs `execution.rootActorRef/entryNodeRef; semanticRoot.actorRef; execution.nodes[].kind` with state `declaredRefs=["a1"]; observedRefs=[]` -> rejected.

### execution.guardDuplicate
Aliases: -
Enforced: assets/renderer/execution.mjs:53
Condition: Fails exactly when the enforcing predicate reports: `one value per decision on an edge`.
Stage: Stage 7
Required producer fields: execution.edges[].guards[].decisionRef
Pass example: Inputs `execution.edges[].guards[].decisionRef` with state `values=["a","b"]` -> accepted.
Fail example: Inputs `execution.edges[].guards[].decisionRef` with state `values=["a","a"]` -> rejected.

### execution.guardRef
Aliases: -
Enforced: assets/renderer/execution.mjs:53
Condition: Fails exactly when the enforcing predicate reports: `declared decision value required`.
Stage: Stage 7
Required producer fields: execution.edges[].guards[].decisionRef/value; execution.decisions[].id/values
Pass example: Inputs `execution.edges[].guards[].decisionRef/value; execution.decisions[].id/values` with state `declaredRefs=["a1"]; observedRefs=["a1"]` -> accepted.
Fail example: Inputs `execution.edges[].guards[].decisionRef/value; execution.decisions[].id/values` with state `declaredRefs=["a1"]; observedRefs=[]` -> rejected.

### execution.inconclusive
Aliases: -
Enforced: assets/renderer/execution.mjs:75
Condition: Fails exactly when the enforcing predicate reports: `reachability`.
Stage: Stage 7
Required producer fields: execution.nodes[].id; execution.edges[].from/to/guards/resetDecisionRefs; verifier visited-state count
Pass example: Inputs `execution.nodes[].id; execution.edges[].from/to/guards/resetDecisionRefs; verifier visited-state count` with state `declared="a1"; observed="a1"` -> accepted.
Fail example: Inputs `execution.nodes[].id; execution.edges[].from/to/guards/resetDecisionRefs; verifier visited-state count` with state `declared="a1"; observed="missing"` -> rejected.

### execution.inventoryActions
Aliases: -
Enforced: assets/renderer/execution.mjs:39
Condition: Fails exactly when the enforcing predicate reports: `required source action inventory must equal displayed action facts`.
Stage: Stage 7
Required producer fields: execution.inventory.actionRefs; phases[].goals[].actions[].id
Pass example: Inputs `execution.inventory.actionRefs; phases[].goals[].actions[].id` with state `declaredRefs=["a1"]; observedRefs=["a1"]` -> accepted.
Fail example: Inputs `execution.inventory.actionRefs; phases[].goals[].actions[].id` with state `declaredRefs=["a1"]; observedRefs=[]` -> rejected.

### execution.inventoryControls
Aliases: -
Enforced: assets/renderer/execution.mjs:40
Condition: Fails exactly when the enforcing predicate reports: `required source controls must equal control roots`.
Stage: Stage 7
Required producer fields: execution.inventory.controlRefs; controls[].id
Pass example: Inputs `execution.inventory.controlRefs; controls[].id` with state `declaredRefs=["a1"]; observedRefs=["a1"]` -> accepted.
Fail example: Inputs `execution.inventory.controlRefs; controls[].id` with state `declaredRefs=["a1"]; observedRefs=[]` -> rejected.

### execution.localDecisionEvidence
Aliases: -
Enforced: assets/renderer/execution.mjs:63
Condition: Fails exactly when the enforcing predicate reports: `local alternatives need evidence-bound decision`.
Stage: Stage 7
Required producer fields: controls[].kind/id; execution.decisions[].controlRef
Pass example: Inputs `controls[].kind/id; execution.decisions[].controlRef` with state `declared="a1"; observed="a1"` -> accepted.
Fail example: Inputs `controls[].kind/id; execution.decisions[].controlRef` with state `declared="a1"; observed="missing"` -> rejected.

### execution.loopTarget
Aliases: -
Enforced: assets/renderer/execution.mjs:58
Condition: Fails exactly when the enforcing predicate reports: `exact declared loop entry, outside successor, or certified terminal required`.
Stage: Stage 7
Required producer fields: execution.edges[].kind/to/readingScopeRef; readingScopes[].repeat.entryActionRef/commonAfter.actionRef/terminalOnly.terminalNodeRefs
Pass example: Inputs `execution.edges[].kind/to/readingScopeRef; readingScopes[].repeat.entryActionRef/commonAfter.actionRef/terminalOnly.terminalNodeRefs` with state `declaredRefs=["a1"]; observedRefs=["a1"]` -> accepted.
Fail example: Inputs `execution.edges[].kind/to/readingScopeRef; readingScopes[].repeat.entryActionRef/commonAfter.actionRef/terminalOnly.terminalNodeRefs` with state `declaredRefs=["a1"]; observedRefs=[]` -> rejected.

### execution.readingDecision
Aliases: -
Enforced: assets/renderer/execution.mjs:61
Condition: Fails exactly when the enforcing predicate reports: `displayed scope domain differs`.
Stage: Stage 7
Required producer fields: execution.decisions[].readingScopeRef/values; readingScopes[].decision.values
Pass example: Inputs `execution.decisions[].readingScopeRef/values; readingScopes[].decision.values` with state `declared="a1"; observed="a1"` -> accepted.
Fail example: Inputs `execution.decisions[].readingScopeRef/values; readingScopes[].decision.values` with state `declared="a1"; observed="missing"` -> rejected.

### execution.reset
Aliases: -
Enforced: assets/renderer/execution.mjs:57
Condition: Fails exactly when the enforcing predicate reports: `only explicit loop re-entry can reset iteration-local decisions`.
Stage: Stage 7
Required producer fields: execution.edges[].kind/resetDecisionRefs; execution.decisions[].id/stability
Pass example: Inputs `execution.edges[].kind/resetDecisionRefs; execution.decisions[].id/stability` with state `declared="a1"; observed="a1"` -> accepted.
Fail example: Inputs `execution.edges[].kind/resetDecisionRefs; execution.decisions[].id/stability` with state `declared="a1"; observed="missing"` -> rejected.

### execution.resume
Aliases: -
Enforced: assets/renderer/execution.mjs:54
Condition: Fails exactly when the enforcing predicate reports: `resume keeps suspended task; never constructs another task`.
Stage: Stage 7
Required producer fields: execution.edges[].kind/from/to/taskId; execution.nodes[].kind/outcome/event/taskId
Pass example: Inputs `execution.edges[].kind/from/to/taskId; execution.nodes[].kind/outcome/event/taskId` with state `declared="a1"; observed="a1"` -> accepted.
Fail example: Inputs `execution.edges[].kind/from/to/taskId; execution.nodes[].kind/outcome/event/taskId` with state `declared="a1"; observed="missing"` -> rejected.

### execution.scopeEvidence
Aliases: -
Enforced: assets/renderer/execution.mjs:62
Condition: Fails exactly when the enforcing predicate reports: `displayed scope needs one evidenced decision domain`.
Stage: Stage 7
Required producer fields: readingScopes[].id; execution.decisions[].readingScopeRef
Pass example: Inputs `readingScopes[].id; execution.decisions[].readingScopeRef` with state `expected=["yes","no"]; observed=["yes","no"]` -> accepted.
Fail example: Inputs `readingScopes[].id; execution.decisions[].readingScopeRef` with state `expected=["yes","no"]; observed=["yes"]` -> rejected.

### execution.scopeGuard
Aliases: -
Enforced: assets/renderer/execution.mjs:81
Condition: Fails exactly when the enforcing predicate reports: `actual reached paths must satisfy displayed branch/take condition`.
Stage: Stage 7
Required producer fields: readingScopes[].members/branches/takeValues; execution edge guards; reachable node states
Pass example: Inputs `readingScopes[].members/branches/takeValues; execution edge guards; reachable node states` with state `declared="a1"; observed="a1"` -> accepted.
Fail example: Inputs `readingScopes[].members/branches/takeValues; execution edge guards; reachable node states` with state `declared="a1"; observed="missing"` -> rejected.

### execution.task
Aliases: -
Enforced: assets/renderer/execution.mjs:49
Condition: Fails exactly when the enforcing predicate reports: `task registry and handoff stage required`.
Stage: Stage 7
Required producer fields: execution.nodes[].kind/taskId/event; execution.tasks[].id
Pass example: Inputs `execution.nodes[].kind/taskId/event; execution.tasks[].id` with state `declaredRefs=["a1"]; observedRefs=["a1"]` -> accepted.
Fail example: Inputs `execution.nodes[].kind/taskId/event; execution.tasks[].id` with state `declaredRefs=["a1"]; observedRefs=[]` -> rejected.

### execution.taskOrigin
Aliases: -
Enforced: assets/renderer/execution.mjs:51
Condition: Fails exactly when the enforcing predicate reports: `constructed task needs exact constructor`; `input task cannot be reconstructed`.
Stage: Stage 7
Required producer fields: execution.tasks[].origin/constructNodeRef; execution.nodes[].event/taskId
Pass example: Inputs `execution.tasks[].origin/constructNodeRef; execution.nodes[].event/taskId` with state `declared="a1"; observed="a1"` -> accepted.
Fail example: Inputs `execution.tasks[].origin/constructNodeRef; execution.nodes[].event/taskId` with state `declared="a1"; observed="missing"` -> rejected.

### execution.taskRef
Aliases: -
Enforced: assets/renderer/execution.mjs:56
Condition: Fails exactly when the enforcing predicate reports: `unknown task`.
Stage: Stage 7
Required producer fields: execution.edges[].taskId; execution.tasks[].id
Pass example: Inputs `execution.edges[].taskId; execution.tasks[].id` with state `declared="a1"; observed="a1"` -> accepted.
Fail example: Inputs `execution.edges[].taskId; execution.tasks[].id` with state `declared="a1"; observed="missing"` -> rejected.

### execution.terminal
Aliases: -
Enforced: assets/renderer/execution.mjs:48
Condition: Fails exactly when the enforcing predicate reports: `explicit return/error/unwind/suspend outcome required`.
Stage: Stage 7
Required producer fields: execution.nodes[].kind/outcome
Pass example: Inputs `execution.nodes[].kind/outcome` with state `declaredRefs=["a1"]; observedRefs=["a1"]` -> accepted.
Fail example: Inputs `execution.nodes[].kind/outcome` with state `declaredRefs=["a1"]; observedRefs=[]` -> rejected.

### execution.terminalLoopCoverage
Aliases: -
Enforced: assets/renderer/execution.mjs:16
Condition: Fails exactly when the enforcing predicate reports: `every non-continue loop exit edge must be declared exactly once`.
Stage: Stage 7
Required producer fields: terminalOnly.exitEdgeRefs; execution.edges[].kind/readingScopeRef
Pass example: Inputs `terminalOnly.exitEdgeRefs; execution.edges[].kind/readingScopeRef` with state `declaredRefs=["a1"]; observedRefs=["a1"]` -> accepted.
Fail example: Inputs `terminalOnly.exitEdgeRefs; execution.edges[].kind/readingScopeRef` with state `declaredRefs=["a1"]; observedRefs=[]` -> rejected.

### execution.terminalLoopEdge
Aliases: -
Enforced: assets/renderer/execution.mjs:23
Condition: Fails exactly when the enforcing predicate reports: `terminal-only exits require a scope member action or member-backed guarded decision and a declared return/error terminal`.
Stage: Stage 7
Required producer fields: execution.edges[].from/to/guards; execution.nodes[].kind/actionRef/outcome; terminalOnly.terminalNodeRefs
Pass example: Inputs `execution.edges[].from/to/guards; execution.nodes[].kind/actionRef/outcome; terminalOnly.terminalNodeRefs` with state `declared="a1"; observed="a1"` -> accepted.
Fail example: Inputs `execution.edges[].from/to/guards; execution.nodes[].kind/actionRef/outcome; terminalOnly.terminalNodeRefs` with state `declared="a1"; observed="missing"` -> rejected.

### execution.terminalLoopExclusive
Aliases: -
Enforced: assets/renderer/execution.mjs:9
Condition: Fails exactly when the enforcing predicate reports: `commonAfter and terminalOnly are mutually exclusive`.
Stage: Stage 7
Required producer fields: readingScopes[].commonAfter; readingScopes[].terminalOnly; read operation: terminalLoopExclusive
Pass example: Inputs `readingScopes[].commonAfter; readingScopes[].terminalOnly; read operation: terminalLoopExclusive` with state `declared="a1"; observed="a1"` -> accepted.
Fail example: Inputs `readingScopes[].commonAfter; readingScopes[].terminalOnly; read operation: terminalLoopExclusive` with state `declared="a1"; observed="missing"` -> rejected.

### execution.terminalLoopMembers
Aliases: -
Enforced: assets/renderer/execution.mjs:13
Condition: Fails exactly when the enforcing predicate reports: `certificate member BBs must equal this scope members`.
Stage: Stage 7
Required producer fields: readingScopes[].members; action basicBlockRefs; certificate.memberBBs
Pass example: Inputs `readingScopes[].members; action basicBlockRefs; certificate.memberBBs` with state `declared="a1"; observed="a1"` -> accepted.
Fail example: Inputs `readingScopes[].members; action basicBlockRefs; certificate.memberBBs` with state `declared="a1"; observed="missing"` -> rejected.

### execution.terminalLoopNamespace
Aliases: -
Enforced: assets/renderer/execution.mjs:14
Condition: Fails exactly when the enforcing predicate reports: `terminal-loop evidence is inner-only bbN`.
Stage: Stage 7
Required producer fields: action basicBlockRefs; certificate.memberBBs/terminalBBs
Pass example: Inputs `action basicBlockRefs; certificate.memberBBs/terminalBBs` with state `basicBlockRefs=["bb0"]` -> accepted.
Fail example: Inputs `action basicBlockRefs; certificate.memberBBs/terminalBBs` with state `basicBlockRefs=["shell:bb0"]` -> rejected.

### execution.terminalLoopNode
Aliases: -
Enforced: assets/renderer/execution.mjs:15
Condition: Fails exactly when the enforcing predicate reports: `declared terminal must be a certificate-backed return/error node`.
Stage: Stage 7
Required producer fields: terminalOnly.terminalNodeRefs; execution.nodes[].kind/outcome/basicBlockRefs; certificate.terminalBBs
Pass example: Inputs `terminalOnly.terminalNodeRefs; execution.nodes[].kind/outcome/basicBlockRefs; certificate.terminalBBs` with state `declared="a1"; observed="a1"` -> accepted.
Fail example: Inputs `terminalOnly.terminalNodeRefs; execution.nodes[].kind/outcome/basicBlockRefs; certificate.terminalBBs` with state `declared="a1"; observed="missing"` -> rejected.

### execution.terminalLoopProof
Aliases: -
Enforced: assets/renderer/execution.mjs:12
Condition: Fails exactly when the enforcing predicate reports: `proofRef must resolve to a versioned certificate bound to this scope and immutable MIR artifact`.
Stage: Stage 7
Required producer fields: readingScopes[].terminalOnly.proofRef; execution.evidence/artifacts; certificateKind/version/scopeId/memberBBs/exitEdges/terminalBBs/rawSha256
Pass example: Inputs `readingScopes[].terminalOnly.proofRef; execution.evidence/artifacts; certificateKind/version/scopeId/memberBBs/exitEdges/terminalBBs/rawSha256` with state `declared="a1"; observed="a1"` -> accepted.
Fail example: Inputs `readingScopes[].terminalOnly.proofRef; execution.evidence/artifacts; certificateKind/version/scopeId/memberBBs/exitEdges/terminalBBs/rawSha256` with state `declared="a1"; observed="missing"` -> rejected.

### execution.terminationBinding
Aliases: -
Enforced: assets/renderer/execution.mjs:80
Condition: Fails exactly when the enforcing predicate reports: `declared whole-turn termination cannot execute later actions`.
Stage: Stage 7
Required producer fields: readingScopes[].branches[].effect; execution.decisions/edges guards; execution.nodes[].kind
Pass example: Inputs `readingScopes[].branches[].effect; execution.decisions/edges guards; execution.nodes[].kind` with state `declared="a1"; observed="a1"` -> accepted.
Fail example: Inputs `readingScopes[].branches[].effect; execution.decisions/edges guards; execution.nodes[].kind` with state `declared="a1"; observed="missing"` -> rejected.

### execution.unqualifiedFork
Aliases: -
Enforced: assets/renderer/execution.mjs:60
Condition: Fails exactly when the enforcing predicate reports: `alternatives require an explicit decision node, not implicit sequencing`.
Stage: Stage 7
Required producer fields: execution.nodes[].id/kind; execution.edges[].from; read operation: unqualifiedFork
Pass example: Inputs `execution.nodes[].id/kind; execution.edges[].from; read operation: unqualifiedFork` with state `declared="a1"; observed="a1"` -> accepted.
Fail example: Inputs `execution.nodes[].id/kind; execution.edges[].from; read operation: unqualifiedFork` with state `declared="a1"; observed="missing"` -> rejected.

### execution.unreachable
Aliases: -
Enforced: assets/renderer/execution.mjs:84
Condition: Fails exactly when the enforcing predicate reports: `no evidenced satisfiable path from semanticRoot entry; containment or local cycle is not connectivity`.
Stage: Stage 7
Required producer fields: execution.entryNodeRef; execution.nodes[].id; execution.edges[].from/to/guards
Pass example: Inputs `execution.entryNodeRef; execution.nodes[].id; execution.edges[].from/to/guards` with state `declared="a1"; observed="a1"` -> accepted.
Fail example: Inputs `execution.entryNodeRef; execution.nodes[].id; execution.edges[].from/to/guards` with state `declared="a1"; observed="missing"` -> rejected.

### function-source-start
Aliases: -
Enforced: scripts/attribute_source_verifier.py:227, scripts/attribute_source_verifier.py:234
Condition: functionSource.startLine equals the qualifying attribute start, or the signature line when no qualifying attribute exists.
Stage: Stage 7
Required producer fields: raw MIR blocks/terminators/source_info; renderer-input functionSource and node basicBlockRefs/lineRanges; verifier pin/relation/classification/certificate record; function source start proof fields
Pass example: Inputs `raw MIR blocks/terminators/source_info; renderer-input functionSource and node basicBlockRefs/lineRanges; verifier pin/relation/classification/certificate record; function source start proof fields` with state `functionSource L10-L12; lineRanges=[L10-L11]` -> accepted.
Fail example: Inputs `raw MIR blocks/terminators/source_info; renderer-input functionSource and node basicBlockRefs/lineRanges; verifier pin/relation/classification/certificate record; function source start proof fields` with state `functionSource L10-L12; lineRanges=[L9-L11]` -> rejected.

### functionSource
Aliases: -
Enforced: assets/renderer/contract.mjs:92, assets/renderer/contract.mjs:93
Condition: Fails exactly when the enforcing predicate reports: `complete owning function source required`; `line count must equal inclusive function span`.
Stage: Stage 7
Required producer fields: functionSource.startLine/endLine/lines
Pass example: Inputs `functionSource.startLine/endLine/lines` with state `functionSource L10-L12; lineRanges=[L10-L11]` -> accepted.
Fail example: Inputs `functionSource.startLine/endLine/lines` with state `functionSource L10-L12; lineRanges=[L9-L11]` -> rejected.

### functionSource.attributeLines
Aliases: -
Enforced: assets/renderer/contract.mjs:97
Condition: Fails exactly when the enforcing predicate reports: `source starts at attributeLines.startLine and the attribute ends before the signature`.
Stage: Stage 7
Required producer fields: functionSource.startLine; functionSource.attributeLines.startLine/endLine
Pass example: Inputs `functionSource.startLine; functionSource.attributeLines.startLine/endLine` with state `functionSource L10-L12; lineRanges=[L10-L11]` -> accepted.
Fail example: Inputs `functionSource.startLine; functionSource.attributeLines.startLine/endLine` with state `functionSource L10-L12; lineRanges=[L9-L11]` -> rejected.

### functionSource.startLine
Aliases: -
Enforced: assets/renderer/contract.mjs:98
Condition: Fails exactly when the enforcing predicate reports: `source without attributeLines starts at the signature`.
Stage: Stage 7
Required producer fields: functionSource.startLine; functionSource.attributeLines; parsed signature line
Pass example: Inputs `functionSource.startLine; functionSource.attributeLines; parsed signature line` with state `functionSource L10-L12; lineRanges=[L10-L11]` -> accepted.
Fail example: Inputs `functionSource.startLine; functionSource.attributeLines; parsed signature line` with state `functionSource L10-L12; lineRanges=[L9-L11]` -> rejected.

### header-bookkeeping
Aliases: -
Enforced: scripts/verify_source_evidence.py:173
Condition: The enclosing failure condition is false: `if claimed-real: errors.append(dict(code='header-bookkeeping', node=node['id'], bbRefs=node.get('basicBlockRefs', []), extraLines=sorted(claimed-real)))`.
Stage: Stage 7
Required producer fields: raw MIR blocks/terminators/source_info; renderer-input functionSource and node basicBlockRefs/lineRanges; verifier pin/relation/classification/certificate record; record fields basicBlockRefs, id
Pass example: Inputs `raw MIR blocks/terminators/source_info; renderer-input functionSource and node basicBlockRefs/lineRanges; verifier pin/relation/classification/certificate record; record fields basicBlockRefs, id` with state `declared="a1"; observed="a1"` -> accepted.
Fail example: Inputs `raw MIR blocks/terminators/source_info; renderer-input functionSource and node basicBlockRefs/lineRanges; verifier pin/relation/classification/certificate record; record fields basicBlockRefs, id` with state `declared="a1"; observed="missing"` -> rejected.

### id.unique
Aliases: id.duplicate, source.idCollision
Enforced: assets/renderer/contract.mjs:10, assets/renderer/contract.mjs:23, assets/renderer/contract.mjs:65, scripts/source_ranges.py:654
Condition: Fails exactly when the enforcing predicate reports: `branches`; `IDs must be unique`.
Stage: Stage 7
Required producer fields: actorId/messageId/control id/branch id/phase id/goal id/action id/renderId/segment id
Pass example: Inputs `actorId/messageId/control id/branch id/phase id/goal id/action id/renderId/segment id` with state `values=["a","b"]` -> accepted.
Fail example: Inputs `actorId/messageId/control id/branch id/phase id/goal id/action id/renderId/segment id` with state `values=["a","a"]` -> rejected.

### identity.conflict
Aliases: -
Enforced: assets/renderer/contract.mjs:27
Condition: The executable comparison is satisfied: `const pairs=new Map(),handles=new Map();for(const m of d.messages){for(const k of ['fromActorId','toActorId'])if(!['body','declaration'].includes(aa.get(m[k])?.kind))fail('message.endpoint',m.messageId,m[k]);if(m.kind==='self'&&(m.fromActorId!==m.toActorId||m.pair!==null))fail('message.self',m.messageId,'invalid self');if(m.kind!=='self'&&(m.pair===null||m.fromActorId===m.toActorId))fail('pair.required',m.messageId,'pair and two distinct callable endpoints required');if(m.pair){const a=pairs.get(m.pair)??[];a.push(m);pairs.set(m.pair,a);}for(const k of ['handleId','wrapperId'])if(m[k]){if(!m.taskId)fail('identity.task',m.messageId,k);const t=handles.get(m[k]);if(t&&t!==m.taskId)fail('identit`.
Stage: Stage 7
Required producer fields: messages[].handleId/wrapperId/taskId; read operation: conflict
Pass example: Inputs `messages[].handleId/wrapperId/taskId; read operation: conflict` with state `declaredRefs=["a1"]; observedRefs=["a1"]` -> accepted.
Fail example: Inputs `messages[].handleId/wrapperId/taskId; read operation: conflict` with state `declaredRefs=["a1"]; observedRefs=[]` -> rejected.

### identity.task
Aliases: -
Enforced: assets/renderer/contract.mjs:27
Condition: The executable comparison is satisfied: `const pairs=new Map(),handles=new Map();for(const m of d.messages){for(const k of ['fromActorId','toActorId'])if(!['body','declaration'].includes(aa.get(m[k])?.kind))fail('message.endpoint',m.messageId,m[k]);if(m.kind==='self'&&(m.fromActorId!==m.toActorId||m.pair!==null))fail('message.self',m.messageId,'invalid self');if(m.kind!=='self'&&(m.pair===null||m.fromActorId===m.toActorId))fail('pair.required',m.messageId,'pair and two distinct callable endpoints required');if(m.pair){const a=pairs.get(m.pair)??[];a.push(m);pairs.set(m.pair,a);}for(const k of ['handleId','wrapperId'])if(m[k]){if(!m.taskId)fail('identity.task',m.messageId,k);const t=handles.get(m[k]);if(t&&t!==m.taskId)fail('identit`.
Stage: Stage 7
Required producer fields: messages[].handleId/wrapperId/taskId; read operation: task
Pass example: Inputs `messages[].handleId/wrapperId/taskId; read operation: task` with state `declaredRefs=["a1"]; observedRefs=["a1"]` -> accepted.
Fail example: Inputs `messages[].handleId/wrapperId/taskId; read operation: task` with state `declaredRefs=["a1"]; observedRefs=[]` -> rejected.

### identity.wrapper
Aliases: -
Enforced: assets/renderer/contract.mjs:27
Condition: Fails exactly when the enforcing predicate reports: `wrapper distinct`.
Stage: Stage 7
Required producer fields: messages[].wrapperId/taskId
Pass example: Inputs `messages[].wrapperId/taskId` with state `declared="a1"; observed="a1"` -> accepted.
Fail example: Inputs `messages[].wrapperId/taskId` with state `declared="a1"; observed="missing"` -> rejected.

### initial.actorContainer
Aliases: -
Enforced: assets/renderer/contract.mjs:70
Condition: Every initialState.expandedActorIds value must resolve to an actor whose children array is non-empty.
Stage: Stage 6
Required producer fields: initialState.expandedActorIds; actors[].actorId/children
Pass example: Inputs `initialState.expandedActorIds; actors[].actorId/children` with state `expandedActorIds=["module"]; actor module has children=["body"]` -> accepted.
Fail example: Inputs `initialState.expandedActorIds; actors[].actorId/children` with state `expandedActorIds=["body"]; actor body has children=[]` -> rejected.

### initial.duplicate
Aliases: -
Enforced: assets/renderer/contract.mjs:32
Condition: Fails exactly when the enforcing predicate reports: `duplicate`.
Stage: Stage 7
Required producer fields: initialState.expandedActorIds/expandedPhaseIds/expandedGoalIds/expandedActionIds
Pass example: Inputs `initialState.expandedActorIds/expandedPhaseIds/expandedGoalIds/expandedActionIds` with state `values=["a","b"]` -> accepted.
Fail example: Inputs `initialState.expandedActorIds/expandedPhaseIds/expandedGoalIds/expandedActionIds` with state `values=["a","a"]` -> rejected.

### initial.reference
Aliases: -
Enforced: assets/renderer/contract.mjs:32
Condition: The executable comparison is satisfied: `for(const [k,m]of [['expandedActorIds',aa],['expandedPhaseIds',pp],['expandedGoalIds',gg],['expandedActionIds',acts]]){if(new Set(d.initialState[k]).size!==d.initialState[k].length)fail('initial.duplicate',k,'duplicate');for(const id of d.initialState[k])if(!m.has(id))fail('initial.reference',k,id);}`.
Stage: Stage 7
Required producer fields: initialState expanded ID arrays; actor/phase/goal/action ID registries
Pass example: Inputs `initialState expanded ID arrays; actor/phase/goal/action ID registries` with state `values=["a","b"]` -> accepted.
Fail example: Inputs `initialState expanded ID arrays; actor/phase/goal/action ID registries` with state `values=["a","a"]` -> rejected.

### inner-bb-namespace
Aliases: -
Enforced: scripts/verify_source_evidence.py:111
Condition: The enclosing failure condition is false: `if not re.fullmatch(r'bb[0-9]+', ref): errors.append(dict(code='inner-bb-namespace', node=node['id'], bbRef=ref))`.
Stage: Stage 7
Required producer fields: raw MIR blocks/terminators/source_info; renderer-input functionSource and node basicBlockRefs/lineRanges; verifier pin/relation/classification/certificate record; record fields id; read operation: inner bb namespace
Pass example: Inputs `raw MIR blocks/terminators/source_info; renderer-input functionSource and node basicBlockRefs/lineRanges; verifier pin/relation/classification/certificate record; record fields id; read operation: inner bb namespace` with state `basicBlockRefs=["bb0"]` -> accepted.
Fail example: Inputs `raw MIR blocks/terminators/source_info; renderer-input functionSource and node basicBlockRefs/lineRanges; verifier pin/relation/classification/certificate record; record fields id; read operation: inner bb namespace` with state `basicBlockRefs=["shell:bb0"]` -> rejected.

### inner-canonical-path-mismatch
Aliases: -
Enforced: scripts/async_shell_verifier.py:483
Condition: Inner canonical_path equals shell canonical_path plus `::{closure#0}`.
Stage: Stage 7
Required producer fields: raw MIR blocks/terminators/source_info; renderer-input functionSource and node basicBlockRefs/lineRanges; verifier pin/relation/classification/certificate record; inner canonical path mismatch proof fields
Pass example: Inputs `raw MIR blocks/terminators/source_info; renderer-input functionSource and node basicBlockRefs/lineRanges; verifier pin/relation/classification/certificate record; inner canonical path mismatch proof fields` with state `declared="a1"; observed="a1"` -> accepted.
Fail example: Inputs `raw MIR blocks/terminators/source_info; renderer-input functionSource and node basicBlockRefs/lineRanges; verifier pin/relation/classification/certificate record; inner canonical path mismatch proof fields` with state `declared="a1"; observed="missing"` -> rejected.

### inner-node-attribute-range
Aliases: -
Enforced: scripts/attribute_source_verifier.py:250
Condition: The enclosing failure condition is false: `if touched and async_inner: errors.append({'code': 'inner-node-attribute-range', 'node': node.get('id'),`.
Stage: Stage 7
Required producer fields: raw MIR blocks/terminators/source_info; renderer-input functionSource and node basicBlockRefs/lineRanges; verifier pin/relation/classification/certificate record; record fields id; read operation: inner node attribute range
Pass example: Inputs `raw MIR blocks/terminators/source_info; renderer-input functionSource and node basicBlockRefs/lineRanges; verifier pin/relation/classification/certificate record; record fields id; read operation: inner node attribute range` with state `functionSource L10-L12; lineRanges=[L10-L11]` -> accepted.
Fail example: Inputs `raw MIR blocks/terminators/source_info; renderer-input functionSource and node basicBlockRefs/lineRanges; verifier pin/relation/classification/certificate record; record fields id; read operation: inner node attribute range` with state `functionSource L10-L12; lineRanges=[L9-L11]` -> rejected.

### inner-owner-relation-mismatch
Aliases: -
Enforced: scripts/async_shell_verifier.py:488
Condition: definition_row.def_path_hash equals inner owner and ownership.parent_def_path_hash equals shell owner.
Stage: Stage 7
Required producer fields: raw MIR blocks/terminators/source_info; renderer-input functionSource and node basicBlockRefs/lineRanges; verifier pin/relation/classification/certificate record; inner owner relation mismatch proof fields
Pass example: Inputs `raw MIR blocks/terminators/source_info; renderer-input functionSource and node basicBlockRefs/lineRanges; verifier pin/relation/classification/certificate record; inner owner relation mismatch proof fields` with state `declared="a1"; observed="a1"` -> accepted.
Fail example: Inputs `raw MIR blocks/terminators/source_info; renderer-input functionSource and node basicBlockRefs/lineRanges; verifier pin/relation/classification/certificate record; inner owner relation mismatch proof fields` with state `declared="a1"; observed="missing"` -> rejected.

### invalid-
Aliases: -
Enforced: scripts/async_shell_verifier.py:479
Condition: The enclosing failure condition is false: `if (body.get('capture_stage') != 'mir_drops_elaborated_and_const_checked' or body.get('body_id') != 'main' or not body.get('basic_blocks')): failures.append({'code': 'invalid-' + role + '-mir'})`.
Stage: Stage 7
Required producer fields: raw MIR capture_stage/body_id/basic_blocks; selected body identity
Pass example: Inputs `raw MIR capture_stage/body_id/basic_blocks; selected body identity` with state `capture_stage="optimized"; body_id="inner"; basic_blocks contains bb0` -> accepted.
Fail example: Inputs `raw MIR capture_stage/body_id/basic_blocks; selected body identity` with state `capture_stage is absent and basic_blocks is not an array` -> rejected.

### invalid-inner-mir
Aliases: -
Enforced: scripts/async_shell_verifier.py:479
Condition: The enclosing failure condition is false: `if (body.get('capture_stage') != 'mir_drops_elaborated_and_const_checked' or body.get('body_id') != 'main' or not body.get('basic_blocks')): failures.append({'code': 'invalid-' + role + '-mir'})`.
Stage: Stage 7
Required producer fields: inner raw MIR capture_stage/body_id/basic_blocks
Pass example: Inputs `inner raw MIR capture_stage/body_id/basic_blocks` with state `inner MIR has body_id="inner" and basic_blocks=[bb0]` -> accepted.
Fail example: Inputs `inner raw MIR capture_stage/body_id/basic_blocks` with state `inner MIR has body_id="inner" and basic_blocks=null` -> rejected.

### invalid-shell-mir
Aliases: -
Enforced: scripts/async_shell_verifier.py:479
Condition: The enclosing failure condition is false: `if (body.get('capture_stage') != 'mir_drops_elaborated_and_const_checked' or body.get('body_id') != 'main' or not body.get('basic_blocks')): failures.append({'code': 'invalid-' + role + '-mir'})`.
Stage: Stage 7
Required producer fields: shell raw MIR capture_stage/body_id/basic_blocks
Pass example: Inputs `shell raw MIR capture_stage/body_id/basic_blocks` with state `shell MIR has body_id="shell" and basic_blocks=[bb0]` -> accepted.
Fail example: Inputs `shell raw MIR capture_stage/body_id/basic_blocks` with state `shell MIR has body_id="shell" and basic_blocks=null` -> rejected.

### invalid-shell-pin
Aliases: -
Enforced: scripts/async_shell_verifier.py:363
Condition: The enclosing failure condition is false: `if shell.get('owner_def_path_hash') != pin.get('def_path_hash'): failures.append({'code': 'shell-pin-owner-mismatch', 'pinnedOwner': pin.get('def_path_hash'), 'rawOwner': shell.get('owner_def_path_hash')}) return shell, expected except (KeyError, OSError, TypeError, ValueError, UnicodeDecodeError): failures.append({'code': 'invalid-shell-pin'})`.
Stage: Stage 7
Required producer fields: raw MIR blocks/terminators/source_info; renderer-input functionSource and node basicBlockRefs/lineRanges; verifier pin/relation/classification/certificate record; record fields owner_def_path_hash, def_path_hash; read operation: invalid shell pin
Pass example: Inputs `raw MIR blocks/terminators/source_info; renderer-input functionSource and node basicBlockRefs/lineRanges; verifier pin/relation/classification/certificate record; record fields owner_def_path_hash, def_path_hash; read operation: invalid shell pin` with state `declared="a1"; observed="a1"` -> accepted.
Fail example: Inputs `raw MIR blocks/terminators/source_info; renderer-input functionSource and node basicBlockRefs/lineRanges; verifier pin/relation/classification/certificate record; record fields owner_def_path_hash, def_path_hash; read operation: invalid shell pin` with state `declared="a1"; observed="missing"` -> rejected.

### invalid-shell-technical-namespace
Aliases: -
Enforced: scripts/async_shell_verifier.py:420
Condition: The enclosing failure condition is false: `if len(local_records) != len(records): failures.append({'code': 'invalid-shell-technical-namespace'})`.
Stage: Stage 7
Required producer fields: raw MIR blocks/terminators/source_info; renderer-input functionSource and node basicBlockRefs/lineRanges; verifier pin/relation/classification/certificate record; invalid shell technical namespace proof fields
Pass example: Inputs `raw MIR blocks/terminators/source_info; renderer-input functionSource and node basicBlockRefs/lineRanges; verifier pin/relation/classification/certificate record; invalid shell technical namespace proof fields` with state `basicBlockRefs=["shell:bb0"]` -> accepted.
Fail example: Inputs `raw MIR blocks/terminators/source_info; renderer-input functionSource and node basicBlockRefs/lineRanges; verifier pin/relation/classification/certificate record; invalid shell technical namespace proof fields` with state `basicBlockRefs=["bb0"]` -> rejected.

### invalid-shell-technical-proof
Aliases: -
Enforced: scripts/async_shell_verifier.py:412
Condition: The enclosing failure condition is false: `if bad_fingerprints: failures.append({'code': 'invalid-shell-technical-proof', 'bbRefs': bad_fingerprints})`.
Stage: Stage 7
Required producer fields: raw MIR blocks/terminators/source_info; renderer-input functionSource and node basicBlockRefs/lineRanges; verifier pin/relation/classification/certificate record; invalid shell technical proof proof fields
Pass example: Inputs `raw MIR blocks/terminators/source_info; renderer-input functionSource and node basicBlockRefs/lineRanges; verifier pin/relation/classification/certificate record; invalid shell technical proof proof fields` with state `declared="a1"; observed="a1"` -> accepted.
Fail example: Inputs `raw MIR blocks/terminators/source_info; renderer-input functionSource and node basicBlockRefs/lineRanges; verifier pin/relation/classification/certificate record; invalid shell technical proof proof fields` with state `declared="a1"; observed="missing"` -> rejected.

### invocation.duplicate
Aliases: -
Enforced: assets/renderer/contract.mjs:82
Condition: The executable comparison is satisfied: `const invocation=new Map();for(const entry of entries){const c=entry.node;if(c.invocationRef){if(invocation.has(c.invocationRef))fail('invocation.duplicate',c.id,c.invocationRef);invocation.set(c.invocationRef,entry);}}`.
Stage: Stage 7
Required producer fields: controls tree invocationRef
Pass example: Inputs `controls tree invocationRef` with state `values=["a","b"]` -> accepted.
Fail example: Inputs `controls tree invocationRef` with state `values=["a","a"]` -> rejected.

### message.endpoint
Aliases: -
Enforced: assets/renderer/contract.mjs:27
Condition: The executable comparison is satisfied: `const pairs=new Map(),handles=new Map();for(const m of d.messages){for(const k of ['fromActorId','toActorId'])if(!['body','declaration'].includes(aa.get(m[k])?.kind))fail('message.endpoint',m.messageId,m[k]);if(m.kind==='self'&&(m.fromActorId!==m.toActorId||m.pair!==null))fail('message.self',m.messageId,'invalid self');if(m.kind!=='self'&&(m.pair===null||m.fromActorId===m.toActorId))fail('pair.required',m.messageId,'pair and two distinct callable endpoints required');if(m.pair){const a=pairs.get(m.pair)??[];a.push(m);pairs.set(m.pair,a);}for(const k of ['handleId','wrapperId'])if(m[k]){if(!m.taskId)fail('identity.task',m.messageId,k);const t=handles.get(m[k]);if(t&&t!==m.taskId)fail('identit`.
Stage: Stage 7
Required producer fields: messages[].fromActorId/toActorId; actors[].actorId/kind
Pass example: Inputs `messages[].fromActorId/toActorId; actors[].actorId/kind` with state `declaredRefs=["a1"]; observedRefs=["a1"]` -> accepted.
Fail example: Inputs `messages[].fromActorId/toActorId; actors[].actorId/kind` with state `declaredRefs=["a1"]; observedRefs=[]` -> rejected.

### message.multipleOwners
Aliases: -
Enforced: assets/renderer/contract.mjs:21
Condition: The executable comparison is satisfied: `for(const id of n.messages??[]){if(!mm.has(id))fail('reference.message',n.id,id);if(msgOwner.has(id))fail('message.multipleOwners',n.id,id);msgOwner.set(id,{root,node:n.id,ordinal:ordinal++,branchPath,guardPath,invocationControlRef});}`.
Stage: Stage 7
Required producer fields: controls tree messages[]; messages[].messageId; read operation: multipleOwners
Pass example: Inputs `controls tree messages[]; messages[].messageId; read operation: multipleOwners` with state `declared="a1"; observed="a1"` -> accepted.
Fail example: Inputs `controls tree messages[]; messages[].messageId; read operation: multipleOwners` with state `declared="a1"; observed="missing"` -> rejected.

### message.self
Aliases: -
Enforced: assets/renderer/contract.mjs:27
Condition: Fails exactly when the enforcing predicate reports: `invalid self`.
Stage: Stage 7
Required producer fields: messages[].kind/fromActorId/toActorId/pair
Pass example: Inputs `messages[].kind/fromActorId/toActorId/pair` with state `declared="a1"; observed="a1"` -> accepted.
Fail example: Inputs `messages[].kind/fromActorId/toActorId/pair` with state `declared="a1"; observed="missing"` -> rejected.

### message.unowned
Aliases: -
Enforced: assets/renderer/contract.mjs:25
Condition: Fails exactly when the enforcing predicate reports: `messages`.
Stage: Stage 7
Required producer fields: messages[].messageId; controls tree messages[]
Pass example: Inputs `messages[].messageId; controls tree messages[]` with state `declaredRefs=["a1"]; observedRefs=["a1"]` -> accepted.
Fail example: Inputs `messages[].messageId; controls tree messages[]` with state `declaredRefs=["a1"]; observedRefs=[]` -> rejected.

### missing-primary-inner
Aliases: -
Enforced: scripts/async_shell_verifier.py:460
Condition: The executable comparison is satisfied: `return {'status': 'needs-evidence', 'failures': [{'code': 'missing-primary-inner'}]}`.
Stage: Stage 7
Required producer fields: raw MIR blocks/terminators/source_info; renderer-input functionSource and node basicBlockRefs/lineRanges; verifier pin/relation/classification/certificate record; missing primary inner proof fields
Pass example: Inputs `raw MIR blocks/terminators/source_info; renderer-input functionSource and node basicBlockRefs/lineRanges; verifier pin/relation/classification/certificate record; missing primary inner proof fields` with state `declaredRefs=["a1"]; observedRefs=["a1"]` -> accepted.
Fail example: Inputs `raw MIR blocks/terminators/source_info; renderer-input functionSource and node basicBlockRefs/lineRanges; verifier pin/relation/classification/certificate record; missing primary inner proof fields` with state `declaredRefs=["a1"]; observedRefs=[]` -> rejected.

### missing-retained-shell-prelude
Aliases: -
Enforced: scripts/async_shell_verifier.py:390
Condition: The enclosing failure condition is false: `if not isinstance(prelude, dict) or not prelude.get('nodes'): return [{'code': 'missing-retained-shell-prelude'}]`.
Stage: Stage 7
Required producer fields: raw MIR blocks/terminators/source_info; renderer-input functionSource and node basicBlockRefs/lineRanges; verifier pin/relation/classification/certificate record; record fields nodes
Pass example: Inputs `raw MIR blocks/terminators/source_info; renderer-input functionSource and node basicBlockRefs/lineRanges; verifier pin/relation/classification/certificate record; record fields nodes` with state `declaredRefs=["a1"]; observedRefs=["a1"]` -> accepted.
Fail example: Inputs `raw MIR blocks/terminators/source_info; renderer-input functionSource and node basicBlockRefs/lineRanges; verifier pin/relation/classification/certificate record; record fields nodes` with state `declaredRefs=["a1"]; observedRefs=[]` -> rejected.

### missing-shell-prelude-pin
Aliases: -
Enforced: scripts/async_shell_verifier.py:472
Condition: The enclosing failure condition is false: `if not isinstance(pin, dict): return {'status': 'needs-evidence', 'failures': [{'code': 'missing-shell-prelude-pin'}]}`.
Stage: Stage 7
Required producer fields: raw MIR blocks/terminators/source_info; renderer-input functionSource and node basicBlockRefs/lineRanges; verifier pin/relation/classification/certificate record; missing shell prelude pin proof fields
Pass example: Inputs `raw MIR blocks/terminators/source_info; renderer-input functionSource and node basicBlockRefs/lineRanges; verifier pin/relation/classification/certificate record; missing shell prelude pin proof fields` with state `declaredRefs=["a1"]; observedRefs=["a1"]` -> accepted.
Fail example: Inputs `raw MIR blocks/terminators/source_info; renderer-input functionSource and node basicBlockRefs/lineRanges; verifier pin/relation/classification/certificate record; missing shell prelude pin proof fields` with state `declaredRefs=["a1"]; observedRefs=[]` -> rejected.

### missing-source
Aliases: -
Enforced: scripts/verify_source_evidence.py:88
Condition: The enclosing failure condition is false: `if not source.get('lines'): return [dict(code='missing-source', node='functionSource')]`.
Stage: Stage 7
Required producer fields: raw MIR blocks/terminators/source_info; renderer-input functionSource and node basicBlockRefs/lineRanges; verifier pin/relation/classification/certificate record; record fields lines
Pass example: Inputs `raw MIR blocks/terminators/source_info; renderer-input functionSource and node basicBlockRefs/lineRanges; verifier pin/relation/classification/certificate record; record fields lines` with state `declaredRefs=["a1"]; observedRefs=["a1"]` -> accepted.
Fail example: Inputs `raw MIR blocks/terminators/source_info; renderer-input functionSource and node basicBlockRefs/lineRanges; verifier pin/relation/classification/certificate record; record fields lines` with state `declaredRefs=["a1"]; observedRefs=[]` -> rejected.

### output.archive.path.must.be.a.live.artifact.under.directory
Aliases: -
Enforced: scripts/output_paths.py:234
Condition: The enclosing failure condition is false: `if not path.resolve().is_relative_to(directory) or '.archive' in path.relative_to(directory).parts: raise ValueError('Archive path must be a live artifact under directory')`.
Stage: Prepare
Required producer fields: archive path; live directory path; resolved relative parts
Pass example: Inputs `archive path; live directory path; resolved relative parts` with state `directory=/out/body; archive=/out/body/report.json` -> accepted.
Fail example: Inputs `archive path; live directory path; resolved relative parts` with state `directory=/out/body; archive=/out/body/.archive/report.json` -> rejected.

### output.body.identity.changed.for.existing.def.path.hash
Aliases: -
Enforced: scripts/output_paths.py:129
Condition: The enclosing failure condition is false: `if key == body_hash and (entry['slug'] != slug or entry.get('canonical_path') != canonical): raise ValueError('Body identity changed for existing def_path_hash')`.
Stage: Prepare
Required producer fields: index.json bodies[key].slug/canonical_path; selected def_path_hash/slug/canonical_path
Pass example: Inputs `index.json bodies[key].slug/canonical_path; selected def_path_hash/slug/canonical_path` with state `existing h123 slug=s canonical=p; selected h123 slug=s canonical=p` -> accepted.
Fail example: Inputs `index.json bodies[key].slug/canonical_path; selected def_path_hash/slug/canonical_path` with state `existing h123 slug=s canonical=p; selected h123 slug=other canonical=p` -> rejected.

### output.body.output.directory.is.missing.run.prepare.first
Aliases: -
Enforced: scripts/output_paths.py:182
Condition: The enclosing failure condition is false: `elif not out.is_dir(): raise ValueError('Body output directory is missing; run prepare first')`.
Stage: Publish
Required producer fields: resolved body output directory path and is_dir result
Pass example: Inputs `resolved body output directory path and is_dir result` with state `body output /out/h123 is_dir=true` -> accepted.
Fail example: Inputs `resolved body output directory path and is_dir result` with state `body output /out/h123 is_dir=false` -> rejected.

### output.cannot.record.passed.published.site.is.missing.required.files
Aliases: -
Enforced: scripts/output_paths.py:186
Condition: The enclosing failure condition is false: `if any(not (out / 'deliverable' / name).is_file() for name in required): raise ValueError('Cannot record passed: published site is missing required files')`.
Stage: Publish
Required producer fields: record status; body deliverable path; required deliverable filenames and is_file results
Pass example: Inputs `record status; body deliverable path; required deliverable filenames and is_file results` with state `status=passed; every required deliverable file exists` -> accepted.
Fail example: Inputs `record status; body deliverable path; required deliverable filenames and is_file results` with state `status=passed; deliverable/roundtrip/index.html is missing` -> rejected.

### output.def.path.hash.must.contain.at.least.8.hex.characters
Aliases: -
Enforced: scripts/output_paths.py:37
Condition: The enclosing failure condition is false: `if not isinstance(body_hash, str) or not re.fullmatch(r'[0-9a-fA-F]{8,}', body_hash): raise ValueError('def_path_hash must contain at least 8 hex characters')`.
Stage: Prepare
Required producer fields: selected def_path_hash string
Pass example: Inputs `selected def_path_hash string` with state `def_path_hash="deadbeef"` -> accepted.
Fail example: Inputs `selected def_path_hash string` with state `def_path_hash="xyz"` -> rejected.

### output.definitions.is.required.with.a.hash.or.canonical.path.selector
Aliases: -
Enforced: scripts/output_paths.py:58
Condition: The enclosing failure condition is false: `if not args.definitions: raise ValueError('--definitions is required with a hash or canonical-path selector')`.
Stage: Prepare
Required producer fields: hash selector; canonical-path selector; --definitions argument
Pass example: Inputs `hash selector; canonical-path selector; --definitions argument` with state `hash="deadbeef"; definitions=/tmp/definitions.json` -> accepted.
Fail example: Inputs `hash selector; canonical-path selector; --definitions argument` with state `hash="deadbeef"; definitions is absent` -> rejected.

### output.dry.run.cannot.replace.an.actual.run.entry.use.resolve.dry.run
Aliases: -
Enforced: scripts/output_paths.py:180
Condition: The enclosing failure condition is false: `if existing and existing['status'] != 'dry-run': raise ValueError('Dry-run cannot replace an actual run entry; use resolve --dry-run')`.
Stage: Publish
Required producer fields: command dry-run flag; existing index.json body status
Pass example: Inputs `command dry-run flag; existing index.json body status` with state `dry-run=true; existing status="dry-run"` -> accepted.
Fail example: Inputs `command dry-run flag; existing index.json body status` with state `dry-run=true; existing status="passed"` -> rejected.

### output.identity.canonical.path.must.be.nonempty
Aliases: -
Enforced: scripts/output_paths.py:35
Condition: The enclosing failure condition is false: `if not isinstance(canonical, str) or not canonical.strip(): raise ValueError('identity.canonical_path must be nonempty')`.
Stage: Prepare
Required producer fields: definitions row identity.canonical_path
Pass example: Inputs `definitions row identity.canonical_path` with state `identity.canonical_path="crate::run"` -> accepted.
Fail example: Inputs `definitions row identity.canonical_path` with state `identity.canonical_path=""` -> rejected.

### output.input.lies.inside.body.output.move.the.input.before.preparing.a.rerun
Aliases: -
Enforced: scripts/output_paths.py:153
Condition: The enclosing failure condition is false: `if Path(source).resolve().is_relative_to(out): raise ValueError('Input lies inside body output; move the input before preparing a rerun')`.
Stage: Prepare
Required producer fields: input source resolved path; body output resolved path
Pass example: Inputs `input source resolved path; body output resolved path` with state `input=/tmp/body.json; output=/out/h123` -> accepted.
Fail example: Inputs `input source resolved path; body output resolved path` with state `input=/out/h123/source/body.json; output=/out/h123` -> rejected.

### output.invalid.body.entry.in.index.json
Aliases: -
Enforced: scripts/output_paths.py:103
Condition: The enclosing failure condition is false: `if not isinstance(entry, dict) or entry.get('def_path_hash') != key or not entry.get('slug'): raise ValueError('Invalid body entry in index.json')`.
Stage: Prepare
Required producer fields: index.json bodies key; entry.def_path_hash; entry.slug
Pass example: Inputs `index.json bodies key; entry.def_path_hash; entry.slug` with state `bodies.deadbeef={def_path_hash:"deadbeef",slug:"run-deadbeef"}` -> accepted.
Fail example: Inputs `index.json bodies key; entry.def_path_hash; entry.slug` with state `bodies.deadbeef={def_path_hash:"other",slug:""}` -> rejected.

### output.provided.definition.row.differs.from.definitions.record
Aliases: -
Enforced: scripts/output_paths.py:55
Condition: The enclosing failure condition is false: `if selected != row: raise ValueError('Provided definition row differs from definitions record')`.
Stage: Prepare
Required producer fields: provided definition row; row selected from definitions file
Pass example: Inputs `provided definition row; row selected from definitions file` with state `provided row deep-equals selected definitions row` -> accepted.
Fail example: Inputs `provided definition row; row selected from definitions file` with state `provided row canonical_path="a"; selected row canonical_path="b"` -> rejected.

### output.record.requires.acceptance.summary.or.acceptance.file
Aliases: -
Enforced: scripts/output_paths.py:157
Condition: The enclosing failure condition is false: `if command == 'record' and summary is None: raise ValueError('record requires --acceptance-summary or --acceptance-file')`.
Stage: Publish
Required producer fields: record command; --acceptance-summary; --acceptance-file
Pass example: Inputs `record command; --acceptance-summary; --acceptance-file` with state `command=record; acceptance-summary="passed smoke"` -> accepted.
Fail example: Inputs `record command; --acceptance-summary; --acceptance-file` with state `command=record; acceptance-summary and acceptance-file absent` -> rejected.

### output.record.requires.status.and.stage
Aliases: -
Enforced: scripts/output_paths.py:155
Condition: The enclosing failure condition is false: `if command == 'record' and (not stage or not status): raise ValueError('record requires --status and --stage')`.
Stage: Publish
Required producer fields: record command; --status; --stage
Pass example: Inputs `record command; --status; --stage` with state `command=record; status=passed; stage=8` -> accepted.
Fail example: Inputs `record command; --status; --stage` with state `command=record; status=""; stage=""` -> rejected.

### output.refusing.symlink.management.path.path
Aliases: -
Enforced: scripts/output_paths.py:74
Condition: The enclosing failure condition is false: `if path.is_symlink(): raise ValueError(f'Refusing symlink management path: {path}')`.
Stage: Prepare
Required producer fields: management path and Path.is_symlink result
Pass example: Inputs `management path and Path.is_symlink result` with state `/out/index.json is_symlink=false` -> accepted.
Fail example: Inputs `management path and Path.is_symlink result` with state `/out/index.json is_symlink=true` -> rejected.

### output.representations.mir.body.available.must.be.true
Aliases: -
Enforced: scripts/output_paths.py:31
Condition: The enclosing failure condition is false: `if row.get('representations', {}).get('mir', {}).get('body_available') is not True: raise ValueError('representations.mir.body_available must be true')`.
Stage: Prepare
Required producer fields: definitions row representations.mir.body_available
Pass example: Inputs `definitions row representations.mir.body_available` with state `body_available=true` -> accepted.
Fail example: Inputs `definitions row representations.mir.body_available` with state `body_available=false` -> rejected.

### output.slug.collision.different.bodies.share.the.8.hex.prefix.refusing.overwrite
Aliases: -
Enforced: scripts/output_paths.py:131
Condition: The enclosing failure condition is false: `if entry['slug'].casefold() == slug.casefold() and key != body_hash: raise ValueError('Slug collision: different bodies share the 8-hex prefix; refusing overwrite')`.
Stage: Prepare
Required producer fields: selected body hash/slug; every index.json body key/slug
Pass example: Inputs `selected body hash/slug; every index.json body key/slug` with state `selected deadbeef1 slug=run-deadbeef; existing key deadbeef1` -> accepted.
Fail example: Inputs `selected body hash/slug; every index.json body key/slug` with state `selected deadbeef2 slug=run-deadbeef; existing key deadbeef1` -> rejected.

### output.unexpected.management.path.type.path
Aliases: -
Enforced: scripts/output_paths.py:76
Condition: The enclosing failure condition is false: `if path.exists() and (not path.is_dir() if directory else not path.is_file()): raise ValueError(f'Unexpected management path type: {path}')`.
Stage: Prepare
Required producer fields: management path exists/is_dir/is_file; expected directory flag
Pass example: Inputs `management path exists/is_dir/is_file; expected directory flag` with state `path=/out exists=true is_dir=true; expected directory=true` -> accepted.
Fail example: Inputs `management path exists/is_dir/is_file; expected directory flag` with state `path=/out exists=true is_file=true; expected directory=true` -> rejected.

### output.unsupported.index.json.schema.refusing.to.overwrite.it
Aliases: -
Enforced: scripts/output_paths.py:100
Condition: The enclosing failure condition is false: `if data.get('version') not in (1, 2) or not isinstance(data.get('bodies'), dict): raise ValueError('Unsupported index.json schema; refusing to overwrite it')`.
Stage: Prepare
Required producer fields: index.json version; index.json bodies type
Pass example: Inputs `index.json version; index.json bodies type` with state `version=2; bodies={} object` -> accepted.
Fail example: Inputs `index.json version; index.json bodies type` with state `version=3; bodies=[]` -> rejected.

### page.action.labels.have.semantic.slots
Aliases: -
Enforced: tests/test_readability.cjs:23
Condition: The JavaScript assertion at Enforced evaluates true: `check('action labels have semantic slots',labels.every(r=>r.label?.trim()));`.
Stage: Stage 7
Required producer fields: DOM/assertion state for action labels have semantic slots
Pass example: Inputs `DOM/assertion state for action labels have semantic slots` with state `action.labels.have.semantic.slots: observed DOM value=2; expected=2` -> accepted.
Fail example: Inputs `DOM/assertion state for action labels have semantic slots` with state `action.labels.have.semantic.slots: observed DOM value=1; expected=2` -> rejected.

### page.bb.list.collapsed
Aliases: -
Enforced: tests/test_sidebar.cjs:54
Condition: The JavaScript assertion at Enforced evaluates true: `check('BB list collapsed',!await page.locator('.bb-blocks').evaluate(e=>e.open));`.
Stage: Stage 7
Required producer fields: DOM .bb-blocks; read operation: bb list collapsed
Pass example: Inputs `DOM .bb-blocks; read operation: bb list collapsed` with state `bb.list.collapsed: observed DOM value=2; expected=2` -> accepted.
Fail example: Inputs `DOM .bb-blocks; read operation: bb list collapsed` with state `bb.list.collapsed: observed DOM value=1; expected=2` -> rejected.

### page.bb.total
Aliases: -
Enforced: tests/test_sidebar.cjs:55
Condition: The JavaScript assertion at Enforced evaluates true: `check('BB total', (await page.locator('.bb-blocks summary').textContent()).includes(String(node.basicBlockRefs.length)));`.
Stage: Stage 7
Required producer fields: DOM .bb-blocks summary
Pass example: Inputs `DOM .bb-blocks summary` with state `bb.total: observed DOM value=2; expected=2` -> accepted.
Fail example: Inputs `DOM .bb-blocks summary` with state `bb.total: observed DOM value=1; expected=2` -> rejected.

### page.code.scrollport.stays.readable
Aliases: -
Enforced: tests/test_sidebar.cjs:61
Condition: The JavaScript assertion at Enforced evaluates true: `check('code scrollport stays readable',geometry.height>=140);`.
Stage: Stage 7
Required producer fields: DOM/assertion state for code scrollport stays readable
Pass example: Inputs `DOM/assertion state for code scrollport stays readable` with state `code.scrollport.stays.readable: observed DOM value=2; expected=2` -> accepted.
Fail example: Inputs `DOM/assertion state for code scrollport stays readable` with state `code.scrollport.stays.readable: observed DOM value=1; expected=2` -> rejected.

### page.compact.range.markers
Aliases: -
Enforced: tests/test_readability.cjs:38
Condition: The JavaScript assertion at Enforced evaluates true: `check('compact range markers',(await page.locator('.bb-range-label').allTextContents()).every(s=>/^片段 \d+ · L\d+(–\d+)?$/.test(s)));`.
Stage: Stage 7
Required producer fields: DOM .bb-range-label; read operation: compact range markers
Pass example: Inputs `DOM .bb-range-label; read operation: compact range markers` with state `functionSource L10-L12; lineRanges=[L10-L11]` -> accepted.
Fail example: Inputs `DOM .bb-range-label; read operation: compact range markers` with state `functionSource L10-L12; lineRanges=[L9-L11]` -> rejected.

### page.default.begins.at.signature
Aliases: -
Enforced: tests/test_sidebar.cjs:38
Condition: The JavaScript assertion at Enforced evaluates true: `check('default begins at signature',await page.locator('.bb-source-scroll').evaluate(e=>e.scrollTop)===0);`.
Stage: Stage 7
Required producer fields: DOM .bb-source-scroll; read operation: default begins at signature
Pass example: Inputs `DOM .bb-source-scroll; read operation: default begins at signature` with state `default.begins.at.signature: observed DOM value=2; expected=2` -> accepted.
Fail example: Inputs `DOM .bb-source-scroll; read operation: default begins at signature` with state `default.begins.at.signature: observed DOM value=1; expected=2` -> rejected.

### page.default.has.no.highlight
Aliases: -
Enforced: tests/test_sidebar.cjs:37
Condition: The JavaScript assertion at Enforced evaluates true: `check('default has no highlight',await page.locator('.source-highlight').count()===0);`.
Stage: Stage 7
Required producer fields: DOM .source-highlight; read operation: default has no highlight
Pass example: Inputs `DOM .source-highlight; read operation: default has no highlight` with state `default.has.no.highlight: observed DOM value=2; expected=2` -> accepted.
Fail example: Inputs `DOM .source-highlight; read operation: default has no highlight` with state `default.has.no.highlight: observed DOM value=1; expected=2` -> rejected.

### page.diagram.redraw.preserves.source.scroll
Aliases: -
Enforced: tests/test_sidebar.cjs:123
Condition: The JavaScript assertion at Enforced evaluates true: `check('diagram redraw preserves source scroll',Math.abs(await pre.evaluate(e=>e.scrollTop)-before)<2);`.
Stage: Stage 7
Required producer fields: DOM/assertion state for diagram redraw preserves source scroll
Pass example: Inputs `DOM/assertion state for diagram redraw preserves source scroll` with state `diagram.redraw.preserves.source.scroll: observed DOM value=2; expected=2` -> accepted.
Fail example: Inputs `DOM/assertion state for diagram redraw preserves source scroll` with state `diagram.redraw.preserves.source.scroll: observed DOM value=1; expected=2` -> rejected.

### page.diagram.redraw.preserves.source.selection
Aliases: -
Enforced: tests/test_sidebar.cjs:122
Condition: The JavaScript assertion at Enforced evaluates true: `check('diagram redraw preserves source selection',await page.locator('#selection').getAttribute('data-source-node')===group.id);`.
Stage: Stage 7
Required producer fields: DOM #selection; read operation: diagram redraw preserves source selection
Pass example: Inputs `DOM #selection; read operation: diagram redraw preserves source selection` with state `diagram.redraw.preserves.source.selection: observed DOM value=2; expected=2` -> accepted.
Fail example: Inputs `DOM #selection; read operation: diagram redraw preserves source selection` with state `diagram.redraw.preserves.source.selection: observed DOM value=1; expected=2` -> rejected.

### page.expanded.bb.list
Aliases: -
Enforced: tests/test_sidebar.cjs:74
Condition: The JavaScript assertion at Enforced evaluates true: `check('expanded BB list',await page.locator('.bb-blocks').evaluate(e=>e.open));`.
Stage: Stage 7
Required producer fields: DOM .bb-blocks; read operation: expanded bb list
Pass example: Inputs `DOM .bb-blocks; read operation: expanded bb list` with state `expanded.bb.list: observed DOM value=2; expected=2` -> accepted.
Fail example: Inputs `DOM .bb-blocks; read operation: expanded bb list` with state `expanded.bb.list: observed DOM value=1; expected=2` -> rejected.

### page.expanded.list.preserves.readable.code
Aliases: -
Enforced: tests/test_sidebar.cjs:75
Condition: The JavaScript assertion at Enforced evaluates true: `check('expanded list preserves readable code',await page.locator('.bb-source-scroll').evaluate(e=>e.clientHeight>=140));`.
Stage: Stage 7
Required producer fields: DOM .bb-source-scroll; read operation: expanded list preserves readable code
Pass example: Inputs `DOM .bb-source-scroll; read operation: expanded list preserves readable code` with state `expanded.list.preserves.readable.code: observed DOM value=2; expected=2` -> accepted.
Fail example: Inputs `DOM .bb-source-scroll; read operation: expanded list preserves readable code` with state `expanded.list.preserves.readable.code: observed DOM value=1; expected=2` -> rejected.

### page.first.highlighted.line.auto.scrolled.into.view
Aliases: -
Enforced: tests/test_sidebar.cjs:62
Condition: The JavaScript assertion at Enforced evaluates true: `check('first highlighted line auto-scrolled into view',geometry.top>=geometry.viewTop&&geometry.top<geometry.bottom);`.
Stage: Stage 7
Required producer fields: DOM/assertion state for first highlighted line auto scrolled into view
Pass example: Inputs `DOM/assertion state for first highlighted line auto scrolled into view` with state `first.highlighted.line.auto.scrolled.into.view: observed DOM value=2; expected=2` -> accepted.
Fail example: Inputs `DOM/assertion state for first highlighted line auto scrolled into view` with state `first.highlighted.line.auto.scrolled.into.view: observed DOM value=1; expected=2` -> rejected.

### page.footer.documentation.is.nonempty
Aliases: -
Enforced: tests/test_sidebar.cjs:170
Condition: The JavaScript assertion at Enforced evaluates true: `check('footer documentation is nonempty',(await response.text()).trim().length>0);`.
Stage: Stage 7
Required producer fields: DOM/assertion state for footer documentation is nonempty
Pass example: Inputs `DOM/assertion state for footer documentation is nonempty` with state `footer.documentation.is.nonempty: observed DOM value=2; expected=2` -> accepted.
Fail example: Inputs `DOM/assertion state for footer documentation is nonempty` with state `footer.documentation.is.nonempty: observed DOM value=1; expected=2` -> rejected.

### page.footer.documentation.returns.http.200
Aliases: -
Enforced: tests/test_sidebar.cjs:169
Condition: The JavaScript assertion at Enforced evaluates true: `check('footer documentation returns HTTP 200',response.status()===200);`.
Stage: Stage 7
Required producer fields: DOM/assertion state for footer documentation returns http 200
Pass example: Inputs `DOM/assertion state for footer documentation returns http 200` with state `footer.documentation.returns.http.200: observed DOM value=2; expected=2` -> accepted.
Fail example: Inputs `DOM/assertion state for footer documentation returns http 200` with state `footer.documentation.returns.http.200: observed DOM value=1; expected=2` -> rejected.

### page.footer.file.is.nonempty
Aliases: -
Enforced: tests/test_sidebar.cjs:167
Condition: The JavaScript assertion at Enforced evaluates true: `if(new URL(href).protocol==='file:'){check('footer file is nonempty',fs.readFileSync(fileURLToPath(href),'utf8').trim().length>0);continue;}`.
Stage: Stage 7
Required producer fields: DOM/assertion state for footer file is nonempty
Pass example: Inputs `DOM/assertion state for footer file is nonempty` with state `footer.file.is.nonempty: observed DOM value=2; expected=2` -> accepted.
Fail example: Inputs `DOM/assertion state for footer file is nonempty` with state `footer.file.is.nonempty: observed DOM value=1; expected=2` -> rejected.

### page.footer.has.documentation.link
Aliases: -
Enforced: tests/test_sidebar.cjs:164
Condition: The JavaScript assertion at Enforced evaluates true: `check('footer has documentation link',footerLinks.length>0);`.
Stage: Stage 7
Required producer fields: DOM/assertion state for footer has documentation link
Pass example: Inputs `DOM/assertion state for footer has documentation link` with state `footer.has.documentation.link: observed DOM value=2; expected=2` -> accepted.
Fail example: Inputs `DOM/assertion state for footer has documentation link` with state `footer.has.documentation.link: observed DOM value=1; expected=2` -> rejected.

### page.footer.link.stays.local
Aliases: -
Enforced: tests/test_sidebar.cjs:166
Condition: The JavaScript assertion at Enforced evaluates true: `check('footer link stays local',new URL(href).origin===new URL(url).origin);`.
Stage: Stage 7
Required producer fields: DOM/assertion state for footer link stays local
Pass example: Inputs `DOM/assertion state for footer link stays local` with state `footer.link.stays.local: observed DOM value=2; expected=2` -> accepted.
Fail example: Inputs `DOM/assertion state for footer link stays local` with state `footer.link.stays.local: observed DOM value=1; expected=2` -> rejected.

### page.fullSource
Aliases: page.full.function.preserved, page.full.function.rows
Enforced: tests/test_file_protocol.cjs:13, tests/test_readability.cjs:39, tests/test_sidebar.cjs:27
Condition: Rendered `.bb-code-line` count must equal both `functionSource.lines.length` and `endLine-startLine+1`, and `.bb-line-text` contents must deep-equal `functionSource.lines`.
Stage: Stage 8
Required producer fields: functionSource.startLine/endLine/lines and rendered `.bb-code-line`/`.bb-line-text`
Pass example: `startLine=10,endLine=10,lines=["fn f() {}"]` renders one identical row.
Fail example: The same source renders zero rows or text `fn g() {}`.

### page.marker.identifies.selected.node
Aliases: -
Enforced: tests/test_sidebar.cjs:53
Condition: The JavaScript assertion at Enforced evaluates true: `if(node.lineRanges.length)check('marker identifies selected node',await page.locator('.bb-range-label').first().getAttribute('title')===node.id);`.
Stage: Stage 7
Required producer fields: DOM .bb-range-label; read operation: marker identifies selected node
Pass example: Inputs `DOM .bb-range-label; read operation: marker identifies selected node` with state `functionSource L10-L12; lineRanges=[L10-L11]` -> accepted.
Fail example: Inputs `DOM .bb-range-label; read operation: marker identifies selected node` with state `functionSource L10-L12; lineRanges=[L9-L11]` -> rejected.

### page.message.rows.preserved
Aliases: -
Enforced: tests/test_readability.cjs:26
Condition: The JavaScript assertion at Enforced evaluates true: `check('message rows preserved',await page.locator('[data-message]').count()===d.messages.length);`.
Stage: Stage 7
Required producer fields: DOM [data-message]
Pass example: Inputs `DOM [data-message]` with state `message.rows.preserved: observed DOM value=2; expected=2` -> accepted.
Fail example: Inputs `DOM [data-message]` with state `message.rows.preserved: observed DOM value=1; expected=2` -> rejected.

### page.no.bare.local.alt.headings
Aliases: -
Enforced: tests/test_readability.cjs:21
Condition: The JavaScript assertion at Enforced evaluates true: `check('no bare local alt headings',!(await page.locator('.control-semantic.kind-alt').allTextContents()).some(s=>s.trim()==='alt'));`.
Stage: Stage 7
Required producer fields: DOM .control-semantic.kind-alt
Pass example: Inputs `DOM .control-semantic.kind-alt` with state `no.bare.local.alt.headings: observed DOM value=2; expected=2` -> accepted.
Fail example: Inputs `DOM .control-semantic.kind-alt` with state `no.bare.local.alt.headings: observed DOM value=1; expected=2` -> rejected.

### page.no.browser.exceptions
Aliases: -
Enforced: tests/test_readability.cjs:53, tests/test_sidebar.cjs:179
Condition: The JavaScript assertion at Enforced evaluates true: `check('no browser exceptions',report.errors.length===0);report.passed=true;`.
Stage: Stage 7
Required producer fields: DOM/assertion state for no browser exceptions
Pass example: Inputs `DOM/assertion state for no browser exceptions` with state `no.browser.exceptions: observed DOM value=2; expected=2` -> accepted.
Fail example: Inputs `DOM/assertion state for no browser exceptions` with state `no.browser.exceptions: observed DOM value=1; expected=2` -> rejected.

### page.one.named.marker.per.range
Aliases: -
Enforced: tests/test_sidebar.cjs:52
Condition: The JavaScript assertion at Enforced evaluates true: `check('one named marker per range',await page.locator('.bb-range-label').count()===node.lineRanges.length);`.
Stage: Stage 7
Required producer fields: DOM .bb-range-label; read operation: one named marker per range
Pass example: Inputs `DOM .bb-range-label; read operation: one named marker per range` with state `functionSource L10-L12; lineRanges=[L10-L11]` -> accepted.
Fail example: Inputs `DOM .bb-range-label; read operation: one named marker per range` with state `functionSource L10-L12; lineRanges=[L9-L11]` -> rejected.

### page.phase.clears.highlight
Aliases: -
Enforced: tests/test_sidebar.cjs:173
Condition: The JavaScript assertion at Enforced evaluates true: `await full();check('phase clears highlight',await page.locator('.source-highlight').count()===0);`.
Stage: Stage 7
Required producer fields: DOM .source-highlight; read operation: phase clears highlight
Pass example: Inputs `DOM .source-highlight; read operation: phase clears highlight` with state `click phase p1; DOM .source-highlight count=0` -> accepted.
Fail example: Inputs `DOM .source-highlight; read operation: phase clears highlight` with state `click phase p1; DOM .source-highlight count=1` -> rejected.

### page.phase.rails.use.ordinals
Aliases: -
Enforced: tests/test_readability.cjs:25
Condition: The JavaScript assertion at Enforced evaluates true: `check('phase rails use ordinals',(await page.locator('.frame-tag').allTextContents()).every(s=>/^阶段 \d+$/.test(s)));`.
Stage: Stage 7
Required producer fields: DOM .frame-tag
Pass example: Inputs `DOM .frame-tag` with state `phase.rails.use.ordinals: observed DOM value=2; expected=2` -> accepted.
Fail example: Inputs `DOM .frame-tag` with state `phase.rails.use.ordinals: observed DOM value=1; expected=2` -> rejected.

### page.prelude.bb.refs.stay.namespaced
Aliases: -
Enforced: tests/test_sidebar.cjs:33
Condition: The JavaScript assertion at Enforced evaluates true: `check('prelude BB refs stay namespaced',(await page.locator('.bb-list').textContent()).includes('shell:bb'));`.
Stage: Stage 7
Required producer fields: DOM .bb-list
Pass example: Inputs `DOM .bb-list` with state `basicBlockRefs=["shell:bb0"]` -> accepted.
Fail example: Inputs `DOM .bb-list` with state `basicBlockRefs=["bb0"]` -> rejected.

### page.prelude.selection.persists
Aliases: -
Enforced: tests/test_sidebar.cjs:32
Condition: The JavaScript assertion at Enforced evaluates true: `check('prelude selection persists',await page.locator('#selection').getAttribute('data-source-node')===node.id);`.
Stage: Stage 7
Required producer fields: DOM #selection; read operation: prelude selection persists
Pass example: Inputs `DOM #selection; read operation: prelude selection persists` with state `prelude.selection.persists: observed DOM value=2; expected=2` -> accepted.
Fail example: Inputs `DOM #selection; read operation: prelude selection persists` with state `prelude.selection.persists: observed DOM value=1; expected=2` -> rejected.

### page.prelude.source.highlight
Aliases: -
Enforced: tests/test_sidebar.cjs:34
Condition: The JavaScript assertion at Enforced evaluates true: `if(node.lineRanges.length)check('prelude source highlight',await page.locator('.source-highlight,.source-column-highlight').count()>0);`.
Stage: Stage 7
Required producer fields: DOM .source-highlight,.source-column-highlight
Pass example: Inputs `DOM .source-highlight,.source-column-highlight` with state `functionSource L10-L12; lineRanges=[L10-L11]` -> accepted.
Fail example: Inputs `DOM .source-highlight,.source-column-highlight` with state `functionSource L10-L12; lineRanges=[L9-L11]` -> rejected.

### page.resize.preserves.measured.row.heights
Aliases: -
Enforced: tests/test_readability.cjs:49
Condition: The JavaScript assertion at Enforced evaluates true: `check('resize preserves measured row heights',contained);`.
Stage: Stage 7
Required producer fields: DOM/assertion state for resize preserves measured row heights
Pass example: Inputs `DOM/assertion state for resize preserves measured row heights` with state `resize.preserves.measured.row.heights: observed DOM value=2; expected=2` -> accepted.
Fail example: Inputs `DOM/assertion state for resize preserves measured row heights` with state `resize.preserves.measured.row.heights: observed DOM value=1; expected=2` -> rejected.

### page.resize.recomputes.reading.width
Aliases: -
Enforced: tests/test_readability.cjs:47
Condition: The JavaScript assertion at Enforced evaluates true: `check('resize recomputes reading width',width===1440?afterWidth<beforeWidth:afterWidth>beforeWidth);`.
Stage: Stage 7
Required producer fields: DOM/assertion state for resize recomputes reading width
Pass example: Inputs `DOM/assertion state for resize recomputes reading width` with state `resize.recomputes.reading.width: observed DOM value=2; expected=2` -> accepted.
Fail example: Inputs `DOM/assertion state for resize recomputes reading width` with state `resize.recomputes.reading.width: observed DOM value=1; expected=2` -> rejected.

### page.smaller.viewport.expanded.list.keeps.scrollport
Aliases: -
Enforced: tests/test_sidebar.cjs:178
Condition: The JavaScript assertion at Enforced evaluates true: `check('smaller viewport expanded list keeps scrollport',await pre.evaluate(e=>e.clientHeight>=120));`.
Stage: Stage 7
Required producer fields: DOM/assertion state for smaller viewport expanded list keeps scrollport
Pass example: Inputs `DOM/assertion state for smaller viewport expanded list keeps scrollport` with state `smaller.viewport.expanded.list.keeps.scrollport: observed DOM value=2; expected=2` -> accepted.
Fail example: Inputs `DOM/assertion state for smaller viewport expanded list keeps scrollport` with state `smaller.viewport.expanded.list.keeps.scrollport: observed DOM value=1; expected=2` -> rejected.

### page.title.fits.viewport.width
Aliases: -
Enforced: tests/test_readability.cjs:41
Condition: The JavaScript assertion at Enforced evaluates true: `check('title fits viewport width',title);`.
Stage: Stage 7
Required producer fields: DOM/assertion state for title fits viewport width
Pass example: Inputs `DOM/assertion state for title fits viewport width` with state `title.fits.viewport.width: observed DOM value=2; expected=2` -> accepted.
Fail example: Inputs `DOM/assertion state for title fits viewport width` with state `title.fits.viewport.width: observed DOM value=1; expected=2` -> rejected.

### page.wheel.reaches.final.source.line
Aliases: -
Enforced: tests/test_sidebar.cjs:92
Condition: The JavaScript assertion at Enforced evaluates true: `check('wheel reaches final source line',last.y>=box.y&&last.y+last.height<=box.y+box.height);`.
Stage: Stage 7
Required producer fields: DOM/assertion state for wheel reaches final source line
Pass example: Inputs `DOM/assertion state for wheel reaches final source line` with state `functionSource L10-L12; lineRanges=[L10-L11]` -> accepted.
Fail example: Inputs `DOM/assertion state for wheel reaches final source line` with state `functionSource L10-L12; lineRanges=[L9-L11]` -> rejected.

### page.wheel.selection.redraw.preserves.every.frame.of.user.scroll
Aliases: -
Enforced: tests/test_sidebar.cjs:159
Condition: The JavaScript assertion at Enforced evaluates true: `check('wheel/selection/redraw preserves every frame of user scroll',report.scrollRedrawRace.samples.every(top=>Math.abs(top-report.scrollRedrawRace.before)<2));`.
Stage: Stage 7
Required producer fields: DOM/assertion state for wheel selection redraw preserves every frame of user scroll
Pass example: Inputs `DOM/assertion state for wheel selection redraw preserves every frame of user scroll` with state `wheel.selection.redraw.preserves.every.frame.of.user.scroll: observed DOM value=2; expected=2` -> accepted.
Fail example: Inputs `DOM/assertion state for wheel selection redraw preserves every frame of user scroll` with state `wheel.selection.redraw.preserves.every.frame.of.user.scroll: observed DOM value=1; expected=2` -> rejected.

### page.wheel.selection.redraw.preserves.selection
Aliases: -
Enforced: tests/test_sidebar.cjs:158
Condition: The JavaScript assertion at Enforced evaluates true: `check('wheel/selection/redraw preserves selection',report.scrollRedrawRace.node===group.id);`.
Stage: Stage 7
Required producer fields: DOM/assertion state for wheel selection redraw preserves selection
Pass example: Inputs `DOM/assertion state for wheel selection redraw preserves selection` with state `wheel.selection.redraw.preserves.selection: observed DOM value=2; expected=2` -> accepted.
Fail example: Inputs `DOM/assertion state for wheel selection redraw preserves selection` with state `wheel.selection.redraw.preserves.selection: observed DOM value=1; expected=2` -> rejected.

### page.wheel.selection.redraw.preserves.source.dom
Aliases: -
Enforced: tests/test_sidebar.cjs:157
Condition: The JavaScript assertion at Enforced evaluates true: `check('wheel/selection/redraw preserves source DOM',report.scrollRedrawRace.sameCode);`.
Stage: Stage 7
Required producer fields: DOM/assertion state for wheel selection redraw preserves source dom
Pass example: Inputs `DOM/assertion state for wheel selection redraw preserves source dom` with state `wheel.selection.redraw.preserves.source.dom: observed DOM value=2; expected=2` -> accepted.
Fail example: Inputs `DOM/assertion state for wheel selection redraw preserves source dom` with state `wheel.selection.redraw.preserves.source.dom: observed DOM value=1; expected=2` -> rejected.

### pair.integrity
Aliases: P6.invocation_pair_integrity, pair.cardinality, pair.closedState, pair.completionBranch, pair.endpoints, pair.identity, pair.incomplete, pair.invocationScope, pair.kinds, pair.orderAndGuard, pair.required
Enforced: assets/renderer/contract.mjs:27, assets/renderer/contract.mjs:28, assets/renderer/contract.mjs:81, scripts/check_principles.py:389
Condition: Fails exactly when the enforcing predicate reports: `pair and two distinct callable endpoints required`; `open unknown request required`; `one request + one conditional return`; `request/return required`; `reverse endpoints`; `pair must remain in one logical root invocation/control`; `request must precede return under same or outer branch conditions`; `closed pair marked open`; `normal/poll return cannot belong to unwind/termination/cancellation`.
Stage: Stage 7
Required producer fields: messages[].pair/kind/pairState/completion/fromActorId/toActorId/taskId/handleId/wrapperId/attemptId/taskEvent/invocationRef; messagePlacements root/control/ordinal/guardPath
Pass example: Inputs `messages[].pair/kind/pairState/completion/fromActorId/toActorId/taskId/handleId/wrapperId/attemptId/taskEvent/invocationRef; messagePlacements root/control/ordinal/guardPath` with state `declaredRefs=["a1"]; observedRefs=["a1"]` -> accepted.
Fail example: Inputs `messages[].pair/kind/pairState/completion/fromActorId/toActorId/taskId/handleId/wrapperId/attemptId/taskEvent/invocationRef; messagePlacements root/control/ordinal/guardPath` with state `declaredRefs=["a1"]; observedRefs=[]` -> rejected.

### prelude-extra-bb
Aliases: -
Enforced: scripts/async_shell_verifier.py:448
Condition: The enclosing failure condition is false: `if actual - expected: failures.append({'code': 'prelude-extra-bb',`.
Stage: Stage 7
Required producer fields: prelude.nodes[].basicBlockRefs; independently classified retained shell prelude BB set
Pass example: Inputs `prelude.nodes[].basicBlockRefs; independently classified retained shell prelude BB set` with state `prelude refs=["shell:bb0"] and classified refs=["shell:bb0"]` -> accepted.
Fail example: Inputs `prelude.nodes[].basicBlockRefs; independently classified retained shell prelude BB set` with state `prelude refs=["shell:bb0","shell:bb9"] but classified refs=["shell:bb0"]` -> rejected.

### prelude-missing-business-bb
Aliases: -
Enforced: scripts/async_shell_verifier.py:445
Condition: The enclosing failure condition is false: `if expected - actual: failures.append({'code': 'prelude-missing-business-bb',`.
Stage: Stage 7
Required producer fields: raw MIR blocks/terminators/source_info; renderer-input functionSource and node basicBlockRefs/lineRanges; verifier pin/relation/classification/certificate record; prelude missing business bb proof fields
Pass example: Inputs `raw MIR blocks/terminators/source_info; renderer-input functionSource and node basicBlockRefs/lineRanges; verifier pin/relation/classification/certificate record; prelude missing business bb proof fields` with state `declaredRefs=["a1"]; observedRefs=["a1"]` -> accepted.
Fail example: Inputs `raw MIR blocks/terminators/source_info; renderer-input functionSource and node basicBlockRefs/lineRanges; verifier pin/relation/classification/certificate record; prelude missing business bb proof fields` with state `declaredRefs=["a1"]; observedRefs=[]` -> rejected.

### prelude-relation-mismatch
Aliases: -
Enforced: scripts/async_shell_verifier.py:394
Condition: The enclosing failure condition is false: `if prelude.get('relation') != relation: failures.append({'code': 'prelude-relation-mismatch'})`.
Stage: Stage 7
Required producer fields: raw MIR blocks/terminators/source_info; renderer-input functionSource and node basicBlockRefs/lineRanges; verifier pin/relation/classification/certificate record; record fields relation
Pass example: Inputs `raw MIR blocks/terminators/source_info; renderer-input functionSource and node basicBlockRefs/lineRanges; verifier pin/relation/classification/certificate record; record fields relation` with state `declared="a1"; observed="a1"` -> accepted.
Fail example: Inputs `raw MIR blocks/terminators/source_info; renderer-input functionSource and node basicBlockRefs/lineRanges; verifier pin/relation/classification/certificate record; record fields relation` with state `declared="a1"; observed="missing"` -> rejected.

### prelude-shell-body-mismatch
Aliases: -
Enforced: scripts/async_shell_verifier.py:392
Condition: The enclosing failure condition is false: `if prelude.get('shellBodyId') != _body_id(shell): failures.append({'code': 'prelude-shell-body-mismatch'})`.
Stage: Stage 7
Required producer fields: raw MIR blocks/terminators/source_info; renderer-input functionSource and node basicBlockRefs/lineRanges; verifier pin/relation/classification/certificate record; record fields shellBodyId
Pass example: Inputs `raw MIR blocks/terminators/source_info; renderer-input functionSource and node basicBlockRefs/lineRanges; verifier pin/relation/classification/certificate record; record fields shellBodyId` with state `declared="a1"; observed="a1"` -> accepted.
Fail example: Inputs `raw MIR blocks/terminators/source_info; renderer-input functionSource and node basicBlockRefs/lineRanges; verifier pin/relation/classification/certificate record; record fields shellBodyId` with state `declared="a1"; observed="missing"` -> rejected.

### prelude.relation
Aliases: -
Enforced: assets/renderer/contract.mjs:104
Condition: The executable comparison is satisfied: `if(d.prelude){const r=d.prelude.relation,refs=[r.constructionBbRef,...r.instrumentBbRefs,...r.intoFutureBbRefs,...r.pollBbRefs,...r.technicalBlocks.flatMap(b=>[b.bbRef,...b.evidenceRefs])];for(const ref of refs)if(!/^shell:bb[0-9]+$/.test(ref))fail('prelude.relation',\`shell BB namespace required: ${ref}\`);}`.
Stage: Stage 7
Required producer fields: prelude.relation.shellBodyId/constructionBbRef/instrumentBbRefs/intoFutureBbRefs/pollBbRefs/technicalBbRefs; prelude.nodes[].basicBlockRefs
Pass example: Inputs `prelude.relation.shellBodyId/constructionBbRef/instrumentBbRefs/intoFutureBbRefs/pollBbRefs/technicalBbRefs; prelude.nodes[].basicBlockRefs` with state `basicBlockRefs=["shell:bb0"]` -> accepted.
Fail example: Inputs `prelude.relation.shellBodyId/constructionBbRef/instrumentBbRefs/intoFutureBbRefs/pollBbRefs/technicalBbRefs; prelude.nodes[].basicBlockRefs` with state `basicBlockRefs=["bb0"]` -> rejected.

### prelude.shellBodyId
Aliases: -
Enforced: assets/renderer/contract.mjs:103
Condition: Fails exactly when the enforcing predicate reports: `must equal relation.shellBodyId`.
Stage: Stage 7
Required producer fields: prelude.shellBodyId; prelude.relation.shellBodyId
Pass example: Inputs `prelude.shellBodyId; prelude.relation.shellBodyId` with state `declared="a1"; observed="a1"` -> accepted.
Fail example: Inputs `prelude.shellBodyId; prelude.relation.shellBodyId` with state `declared="a1"; observed="missing"` -> rejected.

### publish.candidate.must.be.under.body.work
Aliases: -
Enforced: scripts/publish_site.py:101
Condition: The enclosing failure condition is false: `if not candidate.is_relative_to(work) or candidate == work: raise ValueError('Candidate must be under body/work')`.
Stage: Publish
Required producer fields: candidate resolved path; body/work resolved path
Pass example: Inputs `candidate resolved path; body/work resolved path` with state `work=/out/body/work; candidate=/out/body/work/site` -> accepted.
Fail example: Inputs `candidate resolved path; body/work resolved path` with state `work=/out/body/work; candidate=/tmp/site` -> rejected.

### publish.expected.one.renderer.module.entry.in.candidate.html
Aliases: -
Enforced: scripts/publish_site.py:53
Condition: The enclosing failure condition is false: `if count != 1: raise ValueError('Expected one renderer module entry in candidate HTML')`.
Stage: Publish
Required producer fields: candidate index.html module-entry match count
Pass example: Inputs `candidate index.html module-entry match count` with state `renderer module entry count=1` -> accepted.
Fail example: Inputs `candidate index.html module-entry match count` with state `renderer module entry count=2` -> rejected.

### publish.missing.source.identity.key
Aliases: -
Enforced: scripts/publish_site.py:45
Condition: The enclosing failure condition is false: `if not match: raise ValueError(f'Missing source identity: {key}')`.
Stage: Publish
Required producer fields: candidate HTML source identity keys and values
Pass example: Inputs `candidate HTML source identity keys and values` with state `HTML contains data-symbol="crate::run"` -> accepted.
Fail example: Inputs `candidate HTML source identity keys and values` with state `HTML omits data-symbol` -> rejected.

### publish.publish.body.must.be.directly.under.output.root
Aliases: -
Enforced: scripts/publish_site.py:97
Condition: The enclosing failure condition is false: `if body.parent != root or body.name.startswith(('.', '_')): raise ValueError('Publish body must be directly under OUTPUT_ROOT')`.
Stage: Publish
Required producer fields: body resolved path; OUTPUT_ROOT resolved path; body basename
Pass example: Inputs `body resolved path; OUTPUT_ROOT resolved path; body basename` with state `root=/out; body=/out/run-deadbeef` -> accepted.
Fail example: Inputs `body resolved path; OUTPUT_ROOT resolved path; body basename` with state `root=/out; body=/out/nested/run-deadbeef` -> rejected.

### publish.stale.browser.bundle.run.scripts.build.browser.bundle.cjs
Aliases: -
Enforced: scripts/publish_site.py:18
Condition: The enclosing failure condition is false: `if hashlib.sha256((renderer / name).read_bytes()).hexdigest() != expected: raise ValueError('Stale browser bundle; run development-only build_browser_bundle.cjs (not shipped with skill)')`.
Stage: Publish
Required producer fields: renderer/bundle-sources.json expected hashes; current renderer source bytes hashes
Pass example: Inputs `renderer/bundle-sources.json expected hashes; current renderer source bytes hashes` with state `expected app.mjs hash=abc; current hash=abc` -> accepted.
Fail example: Inputs `renderer/bundle-sources.json expected hashes; current renderer source bytes hashes` with state `expected app.mjs hash=abc; current hash=def` -> rejected.

### publish.tokens
Aliases: publish.unresolved.presentation.placeholders, publish.unresolved.presentation.placeholders.in.path.relative.to.target
Enforced: SKILL.md:611, scripts/publish_site.py:56, scripts/publish_site.py:88
Condition: Candidate and assembled deliverable text must contain none of `__SYMBOL__`, `__SOURCE_FILE__`, `__MODULE__`, or `__CRATE__`.
Stage: Publish
Required producer fields: publish candidate/body/work/renderer fields: tokens
Pass example: Inputs `publish candidate/body/work/renderer fields: tokens` with state `tokens: path="/out/body/work/site"; exists=true` -> accepted.
Fail example: Inputs `publish candidate/body/work/renderer fields: tokens` with state `tokens: path="/tmp/missing"; exists=false` -> rejected.

### purpose.members
Aliases: -
Enforced: assets/renderer/contract.mjs:83
Condition: Concatenated invocationRefs and waitRefs must be unique, non-empty, and every value must equal one control invocationRef.
Stage: Stage 6
Required producer fields: purposeProjections[].invocationRefs/waitRefs; controls tree invocationRef
Pass example: Inputs `purposeProjections[].invocationRefs/waitRefs; controls tree invocationRef` with state `values=["a","b"]` -> accepted.
Fail example: Inputs `purposeProjections[].invocationRefs/waitRefs; controls tree invocationRef` with state `values=["a","a"]` -> rejected.

### purpose.owner
Aliases: -
Enforced: assets/renderer/contract.mjs:83
Condition: Fails exactly when the enforcing predicate reports: `visible goal anchor required`.
Stage: Stage 7
Required producer fields: purposeProjections[].goalRef/relatedGoalRefs; goals[].id
Pass example: Inputs `purposeProjections[].goalRef/relatedGoalRefs; goals[].id` with state `declaredRefs=["a1"]; observedRefs=["a1"]` -> accepted.
Fail example: Inputs `purposeProjections[].goalRef/relatedGoalRefs; goals[].id` with state `declaredRefs=["a1"]; observedRefs=[]` -> rejected.

### readability.goalMergeReason
Aliases: -
Enforced: scripts/hard_rules.py:52
Condition: A goal is a merge when actions.length > 1; its stated merge reason must be either non-whitespace goals[].mergeReason in renderer-input or non-whitespace cohesionReason in the matching stage2 goalContracts record. No other field satisfies this rule.
Stage: Stage 2
Required producer fields: phases[].goals[].actions; phases[].goals[].mergeReason; stage2/granularity.json goalContracts[].goalRef/cohesionReason
Pass example: Inputs `phases[].goals[].actions; phases[].goals[].mergeReason; stage2/granularity.json goalContracts[].goalRef/cohesionReason` with state `expected=["yes","no"]; observed=["yes","no"]` -> accepted.
Fail example: Inputs `phases[].goals[].actions; phases[].goals[].mergeReason; stage2/granularity.json goalContracts[].goalRef/cohesionReason` with state `expected=["yes","no"]; observed=["yes"]` -> rejected.

### readability.goalSplitReason
Aliases: -
Enforced: scripts/hard_rules.py:65
Condition: Adjacent goals in one phase are a split when their stage2 goalContracts records have equal non-empty contractRef and entryMode; every goal in that adjacent run requires non-whitespace splitReason.
Stage: Stage 2
Required producer fields: phases[].goals[].id/splitReason; stage2/granularity.json goalContracts[].goalRef/contractRef/entryMode
Pass example: Inputs `phases[].goals[].id/splitReason; stage2/granularity.json goalContracts[].goalRef/contractRef/entryMode` with state `expected=["yes","no"]; observed=["yes","no"]` -> accepted.
Fail example: Inputs `phases[].goals[].id/splitReason; stage2/granularity.json goalContracts[].goalRef/contractRef/entryMode` with state `expected=["yes","no"]; observed=["yes"]` -> rejected.

### readability.preludeDistinct
Aliases: -
Enforced: scripts/hard_rules.py:30
Condition: Two prelude nodes are identical when their field-name sets excluding id, label, and distinctionReason are equal, their lineRanges are deep-equal, and every other field except basicBlockRefs is deep-equal. Different basicBlockRefs values do not distinguish nodes; identical nodes must merge or every retained node must have a non-whitespace distinctionReason.
Stage: Stage 6
Required producer fields: prelude.nodes field-name set excluding id/label/distinctionReason; prelude.nodes[].lineRanges; all remaining field values except basicBlockRefs; prelude.nodes[].distinctionReason
Pass example: Inputs `prelude.nodes field-name set excluding id/label/distinctionReason; prelude.nodes[].lineRanges; all remaining field values except basicBlockRefs; prelude.nodes[].distinctionReason` with state `nodes p1/p2 have equal lineRanges L10 and BB refs shell:bb0/shell:bb7; both carry nonempty distinctionReason` -> accepted.
Fail example: Inputs `prelude.nodes field-name set excluding id/label/distinctionReason; prelude.nodes[].lineRanges; all remaining field values except basicBlockRefs; prelude.nodes[].distinctionReason` with state `nodes p1/p2 have equal lineRanges L10 and BB refs shell:bb0/shell:bb7; neither carries distinctionReason` -> rejected.

### reference.control
Aliases: -
Enforced: assets/renderer/contract.mjs:16
Condition: The executable comparison is satisfied: `function own(ref,scope){if(!roots.has(ref))fail('reference.control',scope,ref);if(ownership.has(ref))fail('control.multipleOwners',scope,ref);ownership.set(ref,scope);}`.
Stage: Stage 7
Required producer fields: rootControlRefs; phase boundaryControlRefs; action controlRefs; controls[].id
Pass example: Inputs `rootControlRefs; phase boundaryControlRefs; action controlRefs; controls[].id` with state `declared="a1"; observed="a1"` -> accepted.
Fail example: Inputs `rootControlRefs; phase boundaryControlRefs; action controlRefs; controls[].id` with state `declared="a1"; observed="missing"` -> rejected.

### reference.message
Aliases: -
Enforced: assets/renderer/contract.mjs:21
Condition: The executable comparison is satisfied: `for(const id of n.messages??[]){if(!mm.has(id))fail('reference.message',n.id,id);if(msgOwner.has(id))fail('message.multipleOwners',n.id,id);msgOwner.set(id,{root,node:n.id,ordinal:ordinal++,branchPath,guardPath,invocationControlRef});}`.
Stage: Stage 7
Required producer fields: controls tree messages[]; messages[].messageId; read operation: message
Pass example: Inputs `controls tree messages[]; messages[].messageId; read operation: message` with state `declared="a1"; observed="a1"` -> accepted.
Fail example: Inputs `controls tree messages[]; messages[].messageId; read operation: message` with state `declared="a1"; observed="missing"` -> rejected.

### return.branch
Aliases: -
Enforced: assets/renderer/contract.mjs:81
Condition: For each return message, returnContracts.branchRef must equal the last branchPath item in its derived message placement, or null when the path is empty.
Stage: Stage 6
Required producer fields: returnContracts[].messageRef/branchRef; messagePlacements[].messageRef/branchPath
Pass example: Inputs `returnContracts[].messageRef/branchRef; messagePlacements[].messageRef/branchPath` with state `declared="a1"; observed="a1"` -> accepted.
Fail example: Inputs `returnContracts[].messageRef/branchRef; messagePlacements[].messageRef/branchPath` with state `declared="a1"; observed="missing"` -> rejected.

### return.coverage
Aliases: -
Enforced: assets/renderer/contract.mjs:80
Condition: Fails exactly when the enforcing predicate reports: `every return requires one explicit completion meaning`.
Stage: Stage 7
Required producer fields: returnContracts[].messageRef; messages[].messageId/kind
Pass example: Inputs `returnContracts[].messageRef; messages[].messageId/kind` with state `declaredRefs=["a1"]; observedRefs=["a1"]` -> accepted.
Fail example: Inputs `returnContracts[].messageRef; messages[].messageId/kind` with state `declaredRefs=["a1"]; observedRefs=[]` -> rejected.

### return.handle
Aliases: -
Enforced: assets/renderer/contract.mjs:81
Condition: Fails exactly when the enforcing predicate reports: `handle return requires original task identity`.
Stage: Stage 7
Required producer fields: returnContracts[].meaning; messages[].taskId
Pass example: Inputs `returnContracts[].meaning; messages[].taskId` with state `declared="a1"; observed="a1"` -> accepted.
Fail example: Inputs `returnContracts[].meaning; messages[].taskId` with state `declared="a1"; observed="missing"` -> rejected.

### return.pending
Aliases: -
Enforced: assets/renderer/contract.mjs:81
Condition: Fails exactly when the enforcing predicate reports: `Pending poll response differs from task completion`.
Stage: Stage 7
Required producer fields: branchRoles[].role; returnContracts[].meaning; messages[].taskId; read operation: pending
Pass example: Inputs `branchRoles[].role; returnContracts[].meaning; messages[].taskId; read operation: pending` with state `declared="a1"; observed="a1"` -> accepted.
Fail example: Inputs `branchRoles[].role; returnContracts[].meaning; messages[].taskId; read operation: pending` with state `declared="a1"; observed="missing"` -> rejected.

### return.ready
Aliases: -
Enforced: assets/renderer/contract.mjs:81
Condition: Fails exactly when the enforcing predicate reports: `Ready result belongs to the task Ready branch`.
Stage: Stage 7
Required producer fields: branchRoles[].role; returnContracts[].meaning; messages[].taskId; read operation: ready
Pass example: Inputs `branchRoles[].role; returnContracts[].meaning; messages[].taskId; read operation: ready` with state `declared="a1"; observed="a1"` -> accepted.
Fail example: Inputs `branchRoles[].role; returnContracts[].meaning; messages[].taskId; read operation: ready` with state `declared="a1"; observed="missing"` -> rejected.

### root.anchor
Aliases: -
Enforced: assets/renderer/contract.mjs:33
Condition: Fails exactly when the enforcing predicate reports: `rootAnchors`.
Stage: Stage 7
Required producer fields: rootAnchors[].controlRef/beforePhaseRef; rootControlRefs; phases[].id
Pass example: Inputs `rootAnchors[].controlRef/beforePhaseRef; rootControlRefs; phases[].id` with state `declared="a1"; observed="a1"` -> accepted.
Fail example: Inputs `rootAnchors[].controlRef/beforePhaseRef; rootControlRefs; phases[].id` with state `declared="a1"; observed="missing"` -> rejected.

### root.anchorCoverage
Aliases: -
Enforced: assets/renderer/contract.mjs:33
Condition: Fails exactly when the enforcing predicate reports: `every root control requires exactly one reading boundary anchor`.
Stage: Stage 7
Required producer fields: rootAnchors[].controlRef; rootControlRefs
Pass example: Inputs `rootAnchors[].controlRef; rootControlRefs` with state `declaredRefs=["a1"]; observedRefs=["a1"]` -> accepted.
Fail example: Inputs `rootAnchors[].controlRef; rootControlRefs` with state `declaredRefs=["a1"]; observedRefs=[]` -> rejected.

### scope.action
Aliases: -
Enforced: assets/renderer/contract.mjs:34
Condition: Fails exactly when the enforcing predicate reports: `scopeAnnotations`.
Stage: Stage 7
Required producer fields: scopeAnnotations[].actionRefs; phases[].goals[].actions[].id
Pass example: Inputs `scopeAnnotations[].actionRefs; phases[].goals[].actions[].id` with state `declared="a1"; observed="a1"` -> accepted.
Fail example: Inputs `scopeAnnotations[].actionRefs; phases[].goals[].actions[].id` with state `declared="a1"; observed="missing"` -> rejected.

### scope.alt
Aliases: -
Enforced: assets/renderer/contract.mjs:50
Condition: Fails exactly when the enforcing predicate reports: `explicit alternative branches required`.
Stage: Stage 7
Required producer fields: readingScopes[].kind; readingScopes[].branches
Pass example: Inputs `readingScopes[].kind; readingScopes[].branches` with state `declaredRefs=["a1"]; observedRefs=["a1"]` -> accepted.
Fail example: Inputs `readingScopes[].kind; readingScopes[].branches` with state `declaredRefs=["a1"]; observedRefs=[]` -> rejected.

### scope.arrivals
Aliases: -
Enforced: assets/renderer/contract.mjs:58
Condition: commonAfter.arrivals paths, as a sorted multiset, must equal non-terminating branch IDs for alt, `taken,skipped` for opt, or `exit` for loop.
Stage: Stage 6
Required producer fields: readingScopes[].kind; readingScopes[].branches[].id/effect; readingScopes[].commonAfter.arrivals[].path
Pass example: Inputs `readingScopes[].kind; readingScopes[].branches[].id/effect; readingScopes[].commonAfter.arrivals[].path` with state `{"readingScopes":[{"id":"s","kind":"opt","commonAfter":{"arrivals":[{"path":"taken"},{"path":"skipped"}]}}]}` -> accepted.
Fail example: Inputs `readingScopes[].kind; readingScopes[].branches[].id/effect; readingScopes[].commonAfter.arrivals[].path` with state `{"readingScopes":[{"id":"s","kind":"opt","commonAfter":{"arrivals":[{"path":"taken"}]}}]}` -> rejected.

### scope.branchMembers
Aliases: -
Enforced: assets/renderer/contract.mjs:50
Condition: Fails exactly when the enforcing predicate reports: `branch union must exactly cover range`.
Stage: Stage 7
Required producer fields: readingScopes[].members; readingScopes[].branches[].members
Pass example: Inputs `readingScopes[].members; readingScopes[].branches[].members` with state `functionSource L10-L12; lineRanges=[L10-L11]` -> accepted.
Fail example: Inputs `readingScopes[].members; readingScopes[].branches[].members` with state `functionSource L10-L12; lineRanges=[L9-L11]` -> rejected.

### scope.crossing
Aliases: -
Enforced: assets/renderer/contract.mjs:61
Condition: Fails exactly when the enforcing predicate reports: `partially crossing ranges need a different expression; do not move or duplicate reading nodes`.
Stage: Stage 7
Required producer fields: readingScopes[].members; reading-tree action order; read operation: crossing
Pass example: Inputs `readingScopes[].members; reading-tree action order; read operation: crossing` with state `values=["a","b"]` -> accepted.
Fail example: Inputs `readingScopes[].members; reading-tree action order; read operation: crossing` with state `values=["a","a"]` -> rejected.

### scope.cycle
Aliases: -
Enforced: assets/renderer/contract.mjs:49
Condition: Fails exactly when the enforcing predicate reports: `parent cycle`.
Stage: Stage 7
Required producer fields: readingScopes[].id; readingScopes[].parentScopeRef
Pass example: Inputs `readingScopes[].id; readingScopes[].parentScopeRef` with state `declared="a1"; observed="a1"` -> accepted.
Fail example: Inputs `readingScopes[].id; readingScopes[].parentScopeRef` with state `declared="a1"; observed="missing"` -> rejected.

### scope.decision
Aliases: -
Enforced: assets/renderer/contract.mjs:44
Condition: Fails exactly when the enforcing predicate reports: `explicit alternatives required`.
Stage: Stage 7
Required producer fields: readingScopes[].decision.values
Pass example: Inputs `readingScopes[].decision.values` with state `declaredRefs=["a1"]; observedRefs=["a1"]` -> accepted.
Fail example: Inputs `readingScopes[].decision.values` with state `declaredRefs=["a1"]; observedRefs=[]` -> rejected.

### scope.duplicate
Aliases: -
Enforced: assets/renderer/contract.mjs:41, assets/renderer/contract.mjs:44
Condition: Fails exactly when the enforcing predicate reports: `duplicate reference/value`; `scope id`.
Stage: Stage 7
Required producer fields: readingScopes[].id; readingScopes[].members/branches refs and values
Pass example: Inputs `readingScopes[].id; readingScopes[].members/branches refs and values` with state `values=["a","b"]` -> accepted.
Fail example: Inputs `readingScopes[].id; readingScopes[].members/branches refs and values` with state `values=["a","a"]` -> rejected.

### scope.empty
Aliases: -
Enforced: assets/renderer/contract.mjs:46
Condition: Fails exactly when the enforcing predicate reports: `nonempty controlled range required`.
Stage: Stage 7
Required producer fields: readingScopes[].members
Pass example: Inputs `readingScopes[].members` with state `functionSource L10-L12; lineRanges=[L10-L11]` -> accepted.
Fail example: Inputs `readingScopes[].members` with state `functionSource L10-L12; lineRanges=[L9-L11]` -> rejected.

### scope.emptyBranch
Aliases: -
Enforced: assets/renderer/contract.mjs:50
Condition: Fails exactly when the enforcing predicate reports: `empty branch needs explicit whole-turn termination`.
Stage: Stage 7
Required producer fields: readingScopes[].branches[].members; readingScopes[].branches[].effect.kind/scopeRef
Pass example: Inputs `readingScopes[].branches[].members; readingScopes[].branches[].effect.kind/scopeRef` with state `declared="a1"; observed="a1"` -> accepted.
Fail example: Inputs `readingScopes[].branches[].members; readingScopes[].branches[].effect.kind/scopeRef` with state `declared="a1"; observed="missing"` -> rejected.

### scope.loop
Aliases: -
Enforced: assets/renderer/contract.mjs:57
Condition: Fails exactly when the enforcing predicate reports: `repeat semantics required`.
Stage: Stage 7
Required producer fields: readingScopes[].kind; readingScopes[].repeat
Pass example: Inputs `readingScopes[].kind; readingScopes[].repeat` with state `declaredRefs=["a1"]; observedRefs=["a1"]` -> accepted.
Fail example: Inputs `readingScopes[].kind; readingScopes[].repeat` with state `declaredRefs=["a1"]; observedRefs=[]` -> rejected.

### scope.loopEntry
Aliases: -
Enforced: assets/renderer/contract.mjs:57
Condition: Fails exactly when the enforcing predicate reports: `continue returns to range entry`.
Stage: Stage 7
Required producer fields: readingScopes[].members[0]; readingScopes[].repeat.entryActionRef
Pass example: Inputs `readingScopes[].members[0]; readingScopes[].repeat.entryActionRef` with state `functionSource L10-L12; lineRanges=[L10-L11]` -> accepted.
Fail example: Inputs `readingScopes[].members[0]; readingScopes[].repeat.entryActionRef` with state `functionSource L10-L12; lineRanges=[L9-L11]` -> rejected.

### scope.loopExit
Aliases: -
Enforced: assets/renderer/contract.mjs:57
Condition: Fails exactly when the enforcing predicate reports: `continue and exit differ`.
Stage: Stage 7
Required producer fields: readingScopes[].repeat.continue; readingScopes[].repeat.exit
Pass example: Inputs `readingScopes[].repeat.continue; readingScopes[].repeat.exit` with state `declared="a1"; observed="a1"` -> accepted.
Fail example: Inputs `readingScopes[].repeat.continue; readingScopes[].repeat.exit` with state `declared="a1"; observed="missing"` -> rejected.

### scope.loopSuccessor
Aliases: -
Enforced: assets/renderer/contract.mjs:57
Condition: Fails exactly when the enforcing predicate reports: `exactly one of outside successor or certified terminal-only exits required`.
Stage: Stage 7
Required producer fields: readingScopes[].commonAfter; readingScopes[].terminalOnly; read operation: loopSuccessor
Pass example: Inputs `readingScopes[].commonAfter; readingScopes[].terminalOnly; read operation: loopSuccessor` with state `declaredRefs=["a1"]; observedRefs=["a1"]` -> accepted.
Fail example: Inputs `readingScopes[].commonAfter; readingScopes[].terminalOnly; read operation: loopSuccessor` with state `declaredRefs=["a1"]; observedRefs=[]` -> rejected.

### scope.memberOrder
Aliases: -
Enforced: assets/renderer/contract.mjs:46
Condition: Fails exactly when the enforcing predicate reports: `references must preserve reading-tree order`.
Stage: Stage 7
Required producer fields: readingScopes[].members; reading-tree action order; read operation: memberOrder
Pass example: Inputs `readingScopes[].members; reading-tree action order; read operation: memberOrder` with state `declared="a1"; observed="a1"` -> accepted.
Fail example: Inputs `readingScopes[].members; reading-tree action order; read operation: memberOrder` with state `declared="a1"; observed="missing"` -> rejected.

### scope.nesting
Aliases: -
Enforced: assets/renderer/contract.mjs:61
Condition: Fails exactly when the enforcing predicate reports: `overlapping contained scopes require explicit parent relation`.
Stage: Stage 7
Required producer fields: readingScopes[].members; readingScopes[].parentScopeRef
Pass example: Inputs `readingScopes[].members; readingScopes[].parentScopeRef` with state `declared="a1"; observed="a1"` -> accepted.
Fail example: Inputs `readingScopes[].members; readingScopes[].parentScopeRef` with state `declared="a1"; observed="missing"` -> rejected.

### scope.noncontiguous
Aliases: -
Enforced: assets/renderer/contract.mjs:48
Condition: Fails exactly when the enforcing predicate reports: `range would enclose unrelated reading members; provide separate precise ranges`.
Stage: Stage 7
Required producer fields: readingScopes[].members; reading-tree action order; read operation: noncontiguous
Pass example: Inputs `readingScopes[].members; reading-tree action order; read operation: noncontiguous` with state `functionSource L10-L12; lineRanges=[L10-L11]` -> accepted.
Fail example: Inputs `readingScopes[].members; reading-tree action order; read operation: noncontiguous` with state `functionSource L10-L12; lineRanges=[L9-L11]` -> rejected.

### scope.opt
Aliases: -
Enforced: assets/renderer/contract.mjs:56
Condition: Fails exactly when the enforcing predicate reports: `take and bypass required`.
Stage: Stage 7
Required producer fields: readingScopes[].skip/takeValues/skipValues; readingScopes[].decision.values
Pass example: Inputs `readingScopes[].skip/takeValues/skipValues; readingScopes[].decision.values` with state `declaredRefs=["a1"]; observedRefs=["a1"]` -> accepted.
Fail example: Inputs `readingScopes[].skip/takeValues/skipValues; readingScopes[].decision.values` with state `declaredRefs=["a1"]; observedRefs=[]` -> rejected.

### scope.origin
Aliases: -
Enforced: assets/renderer/contract.mjs:50, assets/renderer/contract.mjs:53
Condition: Fails exactly when the enforcing predicate reports: `condition must match original control branch`; `opt origin must match its single projected range`.
Stage: Stage 7
Required producer fields: readingScopes[].originControlRef; readingScopes[].branches[].sourceBranchRef/condition; controls[].branches[].id/condition
Pass example: Inputs `readingScopes[].originControlRef; readingScopes[].branches[].sourceBranchRef/condition; controls[].branches[].id/condition` with state `functionSource L10-L12; lineRanges=[L10-L11]` -> accepted.
Fail example: Inputs `readingScopes[].originControlRef; readingScopes[].branches[].sourceBranchRef/condition; controls[].branches[].id/condition` with state `functionSource L10-L12; lineRanges=[L9-L11]` -> rejected.

### scope.originBody
Aliases: -
Enforced: assets/renderer/contract.mjs:54
Condition: Fails exactly when the enforcing predicate reports: `range origin is a body-free binding, not a second visible control`.
Stage: Stage 7
Required producer fields: readingScopes[].originControlRef; controls[].messages/children/branches/notes/after
Pass example: Inputs `readingScopes[].originControlRef; controls[].messages/children/branches/notes/after` with state `functionSource L10-L12; lineRanges=[L10-L11]` -> accepted.
Fail example: Inputs `readingScopes[].originControlRef; controls[].messages/children/branches/notes/after` with state `functionSource L10-L12; lineRanges=[L9-L11]` -> rejected.

### scope.outcome
Aliases: -
Enforced: assets/renderer/contract.mjs:9
Condition: Fails exactly when the enforcing predicate reports: `omitted outcome requires one action member and no effect`.
Stage: Stage 7
Required producer fields: readingScopes[].branches[].outcome/effect/members
Pass example: Inputs `readingScopes[].branches[].outcome/effect/members` with state `expected=["yes","no"]; observed=["yes","no"]` -> accepted.
Fail example: Inputs `readingScopes[].branches[].outcome/effect/members` with state `expected=["yes","no"]; observed=["yes"]` -> rejected.

### scope.parent
Aliases: -
Enforced: assets/renderer/contract.mjs:49
Condition: Fails exactly when the enforcing predicate reports: `parent must contain exact child members`.
Stage: Stage 7
Required producer fields: readingScopes[].parentScopeRef; readingScopes[].members
Pass example: Inputs `readingScopes[].parentScopeRef; readingScopes[].members` with state `declared="a1"; observed="a1"` -> accepted.
Fail example: Inputs `readingScopes[].parentScopeRef; readingScopes[].members` with state `declared="a1"; observed="missing"` -> rejected.

### scope.partition
Aliases: -
Enforced: assets/renderer/contract.mjs:43
Condition: Fails exactly when the enforcing predicate reports: `decision values must be complete, disjoint and exact`.
Stage: Stage 7
Required producer fields: readingScopes[].decision.values; branches[].when or takeValues/skipValues or repeat.continueValues/exitValues
Pass example: Inputs `readingScopes[].decision.values; branches[].when or takeValues/skipValues or repeat.continueValues/exitValues` with state `expected=["yes","no"]; observed=["yes","no"]` -> accepted.
Fail example: Inputs `readingScopes[].decision.values; branches[].when or takeValues/skipValues or repeat.continueValues/exitValues` with state `expected=["yes","no"]; observed=["yes"]` -> rejected.

### scope.phase
Aliases: -
Enforced: assets/renderer/contract.mjs:34
Condition: Fails exactly when the enforcing predicate reports: `scopeAnnotations`.
Stage: Stage 7
Required producer fields: scopeAnnotations[].phaseRef; phases[].id
Pass example: Inputs `scopeAnnotations[].phaseRef; phases[].id` with state `declared="a1"; observed="a1"` -> accepted.
Fail example: Inputs `scopeAnnotations[].phaseRef; phases[].id` with state `declared="a1"; observed="missing"` -> rejected.

### scope.phaseRefs
Aliases: -
Enforced: assets/renderer/contract.mjs:84
Condition: Fails exactly when the enforcing predicate reports: `unknown phase reference`.
Stage: Stage 7
Required producer fields: scopeAnnotations[].phaseRefs; phases[].id
Pass example: Inputs `scopeAnnotations[].phaseRefs; phases[].id` with state `declared="a1"; observed="a1"` -> accepted.
Fail example: Inputs `scopeAnnotations[].phaseRefs; phases[].id` with state `declared="a1"; observed="missing"` -> rejected.

### scope.reference
Aliases: -
Enforced: assets/renderer/contract.mjs:42
Condition: The executable comparison is satisfied: `function expand(refs,path){for(const r of refs)if(ix.nodes.get(r.ref)?.kind!==r.kind)fail('scope.reference',path,r.ref);const ids=expandRefs(refs,ix);unique(ids,path);return ids;}`.
Stage: Stage 7
Required producer fields: readingScopes[].members/branches[].members ref/kind; phases/goals/actions IDs
Pass example: Inputs `readingScopes[].members/branches[].members ref/kind; phases/goals/actions IDs` with state `values=["a","b"]` -> accepted.
Fail example: Inputs `readingScopes[].members/branches[].members ref/kind; phases/goals/actions IDs` with state `values=["a","a"]` -> rejected.

### scope.successor
Aliases: -
Enforced: assets/renderer/contract.mjs:58
Condition: Fails exactly when the enforcing predicate reports: `shared successor must be one later action outside scope`.
Stage: Stage 7
Required producer fields: readingScopes[].members; readingScopes[].commonAfter.actionRef; reading-tree action order
Pass example: Inputs `readingScopes[].members; readingScopes[].commonAfter.actionRef; reading-tree action order` with state `expected=["yes","no"]; observed=["yes","no"]` -> accepted.
Fail example: Inputs `readingScopes[].members; readingScopes[].commonAfter.actionRef; reading-tree action order` with state `expected=["yes","no"]; observed=["yes"]` -> rejected.

### scope.termination
Aliases: -
Enforced: assets/renderer/contract.mjs:50
Condition: Fails exactly when the enforcing predicate reports: `whole-turn termination has no subsequent members`.
Stage: Stage 7
Required producer fields: readingScopes[].branches[].effect.kind/scopeRef; branches[].members
Pass example: Inputs `readingScopes[].branches[].effect.kind/scopeRef; branches[].members` with state `declared="a1"; observed="a1"` -> accepted.
Fail example: Inputs `readingScopes[].branches[].effect.kind/scopeRef; branches[].members` with state `declared="a1"; observed="missing"` -> rejected.

### segment.coverage
Aliases: -
Enforced: assets/renderer/contract.mjs:30
Condition: Every messages[].messageId must occur in exactly one segments[].messages list.
Stage: Stage 6
Required producer fields: segments[].messages; messages[].messageId; read operation: coverage
Pass example: Inputs `segments[].messages; messages[].messageId; read operation: coverage` with state `declaredRefs=["a1"]; observedRefs=["a1"]` -> accepted.
Fail example: Inputs `segments[].messages; messages[].messageId; read operation: coverage` with state `declaredRefs=["a1"]; observedRefs=[]` -> rejected.

### segment.nonlinear
Aliases: -
Enforced: assets/renderer/contract.mjs:29
Condition: The executable comparison is satisfied: `const segmentUse=new Map();for(const s of d.segments){let previous;for(const id of s.messages??[]){const m=mm.get(id);if(!m){fail('segment.unknown',s.id,id);continue;}segmentUse.set(id,(segmentUse.get(id)??0)+1);if(previous&&previous.toActorId!==m.fromActorId)fail('segment.nonlinear',s.id,id);previous=m;}}`.
Stage: Stage 7
Required producer fields: segments[].messages order; messages[].fromActorId/toActorId
Pass example: Inputs `segments[].messages order; messages[].fromActorId/toActorId` with state `m1.toActorId="b" and following m2.fromActorId="b"` -> accepted.
Fail example: Inputs `segments[].messages order; messages[].fromActorId/toActorId` with state `m1.toActorId="b" but following m2.fromActorId="c"` -> rejected.

### segment.unknown
Aliases: -
Enforced: assets/renderer/contract.mjs:29
Condition: The executable comparison is satisfied: `const segmentUse=new Map();for(const s of d.segments){let previous;for(const id of s.messages??[]){const m=mm.get(id);if(!m){fail('segment.unknown',s.id,id);continue;}segmentUse.set(id,(segmentUse.get(id)??0)+1);if(previous&&previous.toActorId!==m.fromActorId)fail('segment.nonlinear',s.id,id);previous=m;}}`.
Stage: Stage 7
Required producer fields: segments[].messages; messages[].messageId
Pass example: Inputs `segments[].messages; messages[].messageId` with state `segments[0].messages=["m1"]; message IDs=["m1"]` -> accepted.
Fail example: Inputs `segments[].messages; messages[].messageId` with state `segments[0].messages=["missing"]; message IDs=["m1"]` -> rejected.

### semanticRoot.actor
Aliases: -
Enforced: assets/renderer/contract.mjs:68
Condition: Fails exactly when the enforcing predicate reports: `primary body must be an explicit root actor`.
Stage: Stage 7
Required producer fields: semanticRoot.actorRef; top-level actors[].actorId/kind
Pass example: Inputs `semanticRoot.actorRef; top-level actors[].actorId/kind` with state `declared="a1"; observed="a1"` -> accepted.
Fail example: Inputs `semanticRoot.actorRef; top-level actors[].actorId/kind` with state `declared="a1"; observed="missing"` -> rejected.

### shape.additionalProperties
Aliases: -
Enforced: assets/renderer/renderer-input.schema.json:1
Condition: At every schema occurrence, no undeclared property exists where false.
Stage: Stage 6
Required producer fields: object schema additionalProperties=false; object keys
Pass example: Inputs `object schema additionalProperties=false; object keys` with state `schema={additionalProperties:false,properties:{id:{}}}; value={"id":"a"}` -> accepted.
Fail example: Inputs `object schema additionalProperties=false; object keys` with state `schema={additionalProperties:false,properties:{id:{}}}; value={"id":"a","extra":1}` -> rejected.

### shape.allOf
Aliases: -
Enforced: assets/renderer/renderer-input.schema.json:1
Condition: At every schema occurrence, every branch validates.
Stage: Stage 6
Required producer fields: allOf subschemas; governed value
Pass example: Inputs `allOf subschemas; governed value` with state `allOf=[{type:"string"},{minLength:1}]; value="a"` -> accepted.
Fail example: Inputs `allOf subschemas; governed value` with state `allOf=[{type:"string"},{minLength:1}]; value=""` -> rejected.

### shape.anyOf
Aliases: -
Enforced: assets/renderer/renderer-input.schema.json:1
Condition: At every schema occurrence, at least one branch validates.
Stage: Stage 6
Required producer fields: anyOf subschemas; governed value
Pass example: Inputs `anyOf subschemas; governed value` with state `anyOf=[{type:"string"},{type:"number"}]; value="a"` -> accepted.
Fail example: Inputs `anyOf subschemas; governed value` with state `anyOf=[{type:"string"},{type:"number"}]; value=false` -> rejected.

### shape.const
Aliases: -
Enforced: assets/renderer/renderer-input.schema.json:1
Condition: At every schema occurrence, the value deep-equals the constant.
Stage: Stage 6
Required producer fields: const argument; governed value
Pass example: Inputs `const argument; governed value` with state `const="real-flow"; value="real-flow"` -> accepted.
Fail example: Inputs `const argument; governed value` with state `const="real-flow"; value="test-suite"` -> rejected.

### shape.dependentRequired
Aliases: -
Enforced: assets/renderer/renderer-input.schema.json:1
Condition: At every schema occurrence, a trigger property implies all listed dependent properties.
Stage: Stage 6
Required producer fields: dependentRequired trigger/dependent names; object keys
Pass example: Inputs `dependentRequired trigger/dependent names; object keys` with state `dependentRequired={a:["b"]}; value={"a":1,"b":2}` -> accepted.
Fail example: Inputs `dependentRequired trigger/dependent names; object keys` with state `dependentRequired={a:["b"]}; value={"a":1}` -> rejected.

### shape.enum
Aliases: -
Enforced: assets/renderer/renderer-input.schema.json:1
Condition: At every schema occurrence, the value deep-equals one listed value.
Stage: Stage 6
Required producer fields: enum values; governed value
Pass example: Inputs `enum values; governed value` with state `enum=["alt","opt"]; value="alt"` -> accepted.
Fail example: Inputs `enum values; governed value` with state `enum=["alt","opt"]; value="loop"` -> rejected.

### shape.maxItems
Aliases: -
Enforced: assets/renderer/renderer-input.schema.json:1
Condition: At every schema occurrence, array length is at most the bound.
Stage: Stage 6
Required producer fields: maxItems bound; governed array length
Pass example: Inputs `maxItems bound; governed array length` with state `maxItems=1; value=["a"]` -> accepted.
Fail example: Inputs `maxItems bound; governed array length` with state `maxItems=1; value=["a","b"]` -> rejected.

### shape.minItems
Aliases: -
Enforced: assets/renderer/renderer-input.schema.json:1
Condition: At every schema occurrence, array length is at least the bound.
Stage: Stage 6
Required producer fields: minItems bound; governed array length
Pass example: Inputs `minItems bound; governed array length` with state `minItems=1; value=["a"]` -> accepted.
Fail example: Inputs `minItems bound; governed array length` with state `minItems=1; value=[]` -> rejected.

### shape.minLength
Aliases: -
Enforced: assets/renderer/renderer-input.schema.json:1
Condition: At every schema occurrence, string length is at least the bound.
Stage: Stage 6
Required producer fields: minLength bound; governed string length
Pass example: Inputs `minLength bound; governed string length` with state `minLength=1; value="a"` -> accepted.
Fail example: Inputs `minLength bound; governed string length` with state `minLength=1; value=""` -> rejected.

### shape.minimum
Aliases: -
Enforced: assets/renderer/renderer-input.schema.json:1
Condition: At every schema occurrence, the number is at least the bound.
Stage: Stage 6
Required producer fields: minimum bound; governed number
Pass example: Inputs `minimum bound; governed number` with state `minimum=1; value=1` -> accepted.
Fail example: Inputs `minimum bound; governed number` with state `minimum=1; value=0` -> rejected.

### shape.not
Aliases: -
Enforced: assets/renderer/renderer-input.schema.json:1
Condition: At every schema occurrence, the nested schema does not validate.
Stage: Stage 6
Required producer fields: not subschema; governed value
Pass example: Inputs `not subschema; governed value` with state `not={type:"null"}; value="a"` -> accepted.
Fail example: Inputs `not subschema; governed value` with state `not={type:"null"}; value=null` -> rejected.

### shape.oneOf
Aliases: -
Enforced: assets/renderer/renderer-input.schema.json:1
Condition: At every schema occurrence, exactly one branch validates.
Stage: Stage 6
Required producer fields: oneOf subschemas; governed value
Pass example: Inputs `oneOf subschemas; governed value` with state `oneOf=[{type:"string"},{type:"number"}]; value="a"` -> accepted.
Fail example: Inputs `oneOf subschemas; governed value` with state `oneOf=[{minimum:0},{maximum:10}]; value=5` -> rejected.

### shape.pattern
Aliases: -
Enforced: assets/renderer/renderer-input.schema.json:1
Condition: At every schema occurrence, the string matches the regex.
Stage: Stage 6
Required producer fields: pattern regex; governed string
Pass example: Inputs `pattern regex; governed string` with state `pattern="^bb[0-9]+$"; value="bb0"` -> accepted.
Fail example: Inputs `pattern regex; governed string` with state `pattern="^bb[0-9]+$"; value="shell:bb0"` -> rejected.

### shape.required
Aliases: -
Enforced: assets/renderer/renderer-input.schema.json:1
Condition: At every schema occurrence, the object contains every listed property.
Stage: Stage 6
Required producer fields: required property names; governed object keys
Pass example: Inputs `required property names; governed object keys` with state `required=["id"]; value={"id":"a"}` -> accepted.
Fail example: Inputs `required property names; governed object keys` with state `required=["id"]; value={}` -> rejected.

### shape.type
Aliases: -
Enforced: assets/renderer/renderer-input.schema.json:1
Condition: At every schema occurrence, the value has the declared JSON type.
Stage: Stage 6
Required producer fields: type argument; governed value
Pass example: Inputs `type argument; governed value` with state `type="array"; value=[]` -> accepted.
Fail example: Inputs `type argument; governed value` with state `type="array"; value={}` -> rejected.

### shape.uniqueItems
Aliases: -
Enforced: assets/renderer/renderer-input.schema.json:1
Condition: At every schema occurrence, array elements are pairwise distinct.
Stage: Stage 6
Required producer fields: uniqueItems flag; governed array elements
Pass example: Inputs `uniqueItems flag; governed array elements` with state `uniqueItems=true; value=["a","b"]` -> accepted.
Fail example: Inputs `uniqueItems flag; governed array elements` with state `uniqueItems=true; value=["a","a"]` -> rejected.

### shell-pin-owner-mismatch
Aliases: -
Enforced: scripts/async_shell_verifier.py:358
Condition: The enclosing failure condition is false: `if shell.get('owner_def_path_hash') != pin.get('def_path_hash'): failures.append({'code': 'shell-pin-owner-mismatch',`.
Stage: Stage 7
Required producer fields: raw MIR blocks/terminators/source_info; renderer-input functionSource and node basicBlockRefs/lineRanges; verifier pin/relation/classification/certificate record; record fields owner_def_path_hash, def_path_hash; read operation: shell pin owner mismatch
Pass example: Inputs `raw MIR blocks/terminators/source_info; renderer-input functionSource and node basicBlockRefs/lineRanges; verifier pin/relation/classification/certificate record; record fields owner_def_path_hash, def_path_hash; read operation: shell pin owner mismatch` with state `declared="a1"; observed="a1"` -> accepted.
Fail example: Inputs `raw MIR blocks/terminators/source_info; renderer-input functionSource and node basicBlockRefs/lineRanges; verifier pin/relation/classification/certificate record; record fields owner_def_path_hash, def_path_hash; read operation: shell pin owner mismatch` with state `declared="a1"; observed="missing"` -> rejected.

### shell-pin-sha256-mismatch
Aliases: -
Enforced: scripts/async_shell_verifier.py:354
Condition: The enclosing failure condition is false: `if actual != expected: failures.append({'code': 'shell-pin-sha256-mismatch',`.
Stage: Stage 7
Required producer fields: raw MIR blocks/terminators/source_info; renderer-input functionSource and node basicBlockRefs/lineRanges; verifier pin/relation/classification/certificate record; shell pin sha256 mismatch proof fields
Pass example: Inputs `raw MIR blocks/terminators/source_info; renderer-input functionSource and node basicBlockRefs/lineRanges; verifier pin/relation/classification/certificate record; shell pin sha256 mismatch proof fields` with state `declared sha256="abc"; computed sha256="abc"` -> accepted.
Fail example: Inputs `raw MIR blocks/terminators/source_info; renderer-input functionSource and node basicBlockRefs/lineRanges; verifier pin/relation/classification/certificate record; shell pin sha256 mismatch proof fields` with state `declared sha256="abc"; computed sha256="def"` -> rejected.

### source.bbNamespace
Aliases: -
Enforced: scripts/source_ranges.py:654
Condition: The enclosing failure condition is false: `if not ranges: node['sourceRangeReason'] = ('No precise semantic operation span in the shell BBs; ' 'full source remains available.') node.update(basicBlockRefs=refs, lineRanges=ranges) data['functionSource'] = source return data   def check_source(data, out=None):`.
Stage: Stage 7
Required producer fields: functionSource.startLine/endLine/lines; node basicBlockRefs/lineRanges/sourceRangeReason; sourceGroups; regenerated bbNamespace value
Pass example: Inputs `functionSource.startLine/endLine/lines; node basicBlockRefs/lineRanges/sourceRangeReason; sourceGroups; regenerated bbNamespace value` with state `basicBlockRefs=["shell:bb0"]` -> accepted.
Fail example: Inputs `functionSource.startLine/endLine/lines; node basicBlockRefs/lineRanges/sourceRangeReason; sourceGroups; regenerated bbNamespace value` with state `basicBlockRefs=["bb0"]` -> rejected.

### source.broadRangeReason
Aliases: -
Enforced: scripts/source_ranges.py:654
Condition: A goal/action/execution/source-group whose ranges cover more than 25% of functionSource lines has nonblank broadRangeReason.
Stage: Stage 7
Required producer fields: functionSource.startLine/endLine; goals/actions/execution.nodes/sourceGroups lineRanges; broadRangeReason
Pass example: Inputs `functionSource.startLine/endLine; goals/actions/execution.nodes/sourceGroups lineRanges; broadRangeReason` with state `functionSource L1-L100; action.lineRanges=[L1-L30]; action.broadRangeReason="reviewed combined operation"` -> accepted.
Fail example: Inputs `functionSource.startLine/endLine; goals/actions/execution.nodes/sourceGroups lineRanges; broadRangeReason` with state `functionSource L1-L100; action.lineRanges=[L1-L30]; action.broadRangeReason=""` -> rejected.

### source.canonicalRanges
Aliases: -
Enforced: scripts/source_ranges.py:654
Condition: The enclosing failure condition is false: `if not ranges: node['sourceRangeReason'] = ('No precise semantic operation span in the shell BBs; ' 'full source remains available.') node.update(basicBlockRefs=refs, lineRanges=ranges) data['functionSource'] = source return data   def check_source(data, out=None):`.
Stage: Stage 7
Required producer fields: functionSource.startLine/endLine/lines; node basicBlockRefs/lineRanges/sourceRangeReason; sourceGroups; regenerated canonicalRanges value
Pass example: Inputs `functionSource.startLine/endLine/lines; node basicBlockRefs/lineRanges/sourceRangeReason; sourceGroups; regenerated canonicalRanges value` with state `functionSource L10-L12; lineRanges=[L10-L11]` -> accepted.
Fail example: Inputs `functionSource.startLine/endLine/lines; node basicBlockRefs/lineRanges/sourceRangeReason; sourceGroups; regenerated canonicalRanges value` with state `functionSource L10-L12; lineRanges=[L9-L11]` -> rejected.

### source.function
Aliases: -
Enforced: scripts/source_ranges.py:654
Condition: The enclosing failure condition is false: `if not ranges: node['sourceRangeReason'] = ('No precise semantic operation span in the shell BBs; ' 'full source remains available.') node.update(basicBlockRefs=refs, lineRanges=ranges) data['functionSource'] = source return data   def check_source(data, out=None):`.
Stage: Stage 7
Required producer fields: functionSource.startLine/endLine/lines; node basicBlockRefs/lineRanges/sourceRangeReason; sourceGroups; regenerated function value
Pass example: Inputs `functionSource.startLine/endLine/lines; node basicBlockRefs/lineRanges/sourceRangeReason; sourceGroups; regenerated function value` with state `functionSource L10-L12; lineRanges=[L10-L11]` -> accepted.
Fail example: Inputs `functionSource.startLine/endLine/lines; node basicBlockRefs/lineRanges/sourceRangeReason; sourceGroups; regenerated function value` with state `functionSource L10-L12; lineRanges=[L9-L11]` -> rejected.

### source.groupCoverage
Aliases: -
Enforced: scripts/source_ranges.py:654
Condition: The enclosing failure condition is false: `if not ranges: node['sourceRangeReason'] = ('No precise semantic operation span in the shell BBs; ' 'full source remains available.') node.update(basicBlockRefs=refs, lineRanges=ranges) data['functionSource'] = source return data   def check_source(data, out=None):`.
Stage: Stage 7
Required producer fields: functionSource.startLine/endLine/lines; node basicBlockRefs/lineRanges/sourceRangeReason; sourceGroups; regenerated groupCoverage value
Pass example: Inputs `functionSource.startLine/endLine/lines; node basicBlockRefs/lineRanges/sourceRangeReason; sourceGroups; regenerated groupCoverage value` with state `functionSource L10-L12; lineRanges=[L10-L11]` -> accepted.
Fail example: Inputs `functionSource.startLine/endLine/lines; node basicBlockRefs/lineRanges/sourceRangeReason; sourceGroups; regenerated groupCoverage value` with state `functionSource L10-L12; lineRanges=[L9-L11]` -> rejected.

### source.mappingPresence
Aliases: -
Enforced: scripts/source_ranges.py:654
Condition: The enclosing failure condition is false: `if not ranges: node['sourceRangeReason'] = ('No precise semantic operation span in the shell BBs; ' 'full source remains available.') node.update(basicBlockRefs=refs, lineRanges=ranges) data['functionSource'] = source return data   def check_source(data, out=None):`.
Stage: Stage 7
Required producer fields: functionSource.startLine/endLine/lines; node basicBlockRefs/lineRanges/sourceRangeReason; sourceGroups; regenerated mappingPresence value
Pass example: Inputs `functionSource.startLine/endLine/lines; node basicBlockRefs/lineRanges/sourceRangeReason; sourceGroups; regenerated mappingPresence value` with state `functionSource L10-L12; lineRanges=[L10-L11]` -> accepted.
Fail example: Inputs `functionSource.startLine/endLine/lines; node basicBlockRefs/lineRanges/sourceRangeReason; sourceGroups; regenerated mappingPresence value` with state `functionSource L10-L12; lineRanges=[L9-L11]` -> rejected.

### source.nodeRegeneration
Aliases: -
Enforced: scripts/source_ranges.py:654
Condition: The enclosing failure condition is false: `if not ranges: node['sourceRangeReason'] = ('No precise semantic operation span in the shell BBs; ' 'full source remains available.') node.update(basicBlockRefs=refs, lineRanges=ranges) data['functionSource'] = source return data   def check_source(data, out=None):`.
Stage: Stage 7
Required producer fields: functionSource.startLine/endLine/lines; node basicBlockRefs/lineRanges/sourceRangeReason; sourceGroups; regenerated nodeRegeneration value
Pass example: Inputs `functionSource.startLine/endLine/lines; node basicBlockRefs/lineRanges/sourceRangeReason; sourceGroups; regenerated nodeRegeneration value` with state `functionSource L10-L12; lineRanges=[L10-L11]` -> accepted.
Fail example: Inputs `functionSource.startLine/endLine/lines; node basicBlockRefs/lineRanges/sourceRangeReason; sourceGroups; regenerated nodeRegeneration value` with state `functionSource L10-L12; lineRanges=[L9-L11]` -> rejected.

### source.regeneration
Aliases: -
Enforced: scripts/source_ranges.py:654
Condition: The enclosing failure condition is false: `if not ranges: node['sourceRangeReason'] = ('No precise semantic operation span in the shell BBs; ' 'full source remains available.') node.update(basicBlockRefs=refs, lineRanges=ranges) data['functionSource'] = source return data   def check_source(data, out=None):`.
Stage: Stage 7
Required producer fields: functionSource.startLine/endLine/lines; node basicBlockRefs/lineRanges/sourceRangeReason; sourceGroups; regenerated regeneration value
Pass example: Inputs `functionSource.startLine/endLine/lines; node basicBlockRefs/lineRanges/sourceRangeReason; sourceGroups; regenerated regeneration value` with state `functionSource L10-L12; lineRanges=[L10-L11]` -> accepted.
Fail example: Inputs `functionSource.startLine/endLine/lines; node basicBlockRefs/lineRanges/sourceRangeReason; sourceGroups; regenerated regeneration value` with state `functionSource L10-L12; lineRanges=[L9-L11]` -> rejected.

### sourceGroups
Aliases: -
Enforced: assets/renderer/contract.mjs:99
Condition: Fails exactly when the enforcing predicate reports: `BB group source mappings required`.
Stage: Stage 7
Required producer fields: deliveryMode; sourceGroups[].id/basicBlockRefs/lineRanges; basic-block-details.blocks
Pass example: Inputs `deliveryMode; sourceGroups[].id/basicBlockRefs/lineRanges; basic-block-details.blocks` with state `declaredRefs=["a1"]; observedRefs=["a1"]` -> accepted.
Fail example: Inputs `deliveryMode; sourceGroups[].id/basicBlockRefs/lineRanges; basic-block-details.blocks` with state `declaredRefs=["a1"]; observedRefs=[]` -> rejected.

### stage.gates
Aliases: stage.0, stage.1, stage.2, stage.3, stage.4, stage.5, stage.6, stage.7, stage.8, stage.batchPreflight, stage.failStop, stage.prepare, stage.resolve
Enforced: SKILL.md:260
Condition: Every completed stage writes `OUT/stageN-check.json`; `passed` is true only after all listed stage checks pass and no review remains open. A false check, exception, interruption, unresolved identity, or open review stops before the next stage and records failed at the actual stage; no in-stage self-correction loop is authorized.
Stage: Resolve, Batch, Prepare, Stages 0–8, and Publish
Required producer fields: OUT/stageN-check.json.passed; OUT/stageN-check.json.reviews; index.json.status; index.json.stage
Pass example: Stage 3 has passed=true and zero open reviews before Stage 4.
Fail example: Stage 4 starts while Stage 3 has an open review.

### strict-forward-prelude-must-be-absent
Aliases: -
Enforced: scripts/async_shell_verifier.py:387, scripts/async_shell_verifier.py:522
Condition: The enclosing failure condition is false: `if prelude is not None: failures.append({'code': 'strict-forward-prelude-must-be-absent'})`.
Stage: Stage 7
Required producer fields: async-shell classification.kind; renderer-input.prelude
Pass example: Inputs `async-shell classification.kind; renderer-input.prelude` with state `classification.kind="strict-forward"; prelude is absent` -> accepted.
Fail example: Inputs `async-shell classification.kind; renderer-input.prelude` with state `classification.kind="strict-forward"; prelude.nodes contains p1` -> rejected.

### terminal-loop-bb-namespace
Aliases: -
Enforced: scripts/terminal_loop_verifier.py:193
Condition: The enclosing failure condition is false: `if any(not re.fullmatch(r'bb[0-9]+', ref) for ref in cited): return [{'code':'terminal-loop-bb-namespace','scope':scope.get('id')}]`.
Stage: Stage 7
Required producer fields: raw MIR blocks/terminators/source_info; renderer-input functionSource and node basicBlockRefs/lineRanges; verifier pin/relation/classification/certificate record; record fields id; read operation: terminal loop bb namespace
Pass example: Inputs `raw MIR blocks/terminators/source_info; renderer-input functionSource and node basicBlockRefs/lineRanges; verifier pin/relation/classification/certificate record; record fields id; read operation: terminal loop bb namespace` with state `basicBlockRefs=["bb0"]` -> accepted.
Fail example: Inputs `raw MIR blocks/terminators/source_info; renderer-input functionSource and node basicBlockRefs/lineRanges; verifier pin/relation/classification/certificate record; record fields id; read operation: terminal loop bb namespace` with state `basicBlockRefs=["shell:bb0"]` -> rejected.

### terminal-loop-certificate
Aliases: -
Enforced: scripts/terminal_loop_verifier.py:186
Condition: The enclosing failure condition is false: `if not cert: return [{'code':'terminal-loop-certificate','scope':scope.get('id'),'reason':'missing or invalid proof artifact'}]`.
Stage: Stage 7
Required producer fields: raw MIR blocks/terminators/source_info; renderer-input functionSource and node basicBlockRefs/lineRanges; verifier pin/relation/classification/certificate record; record fields id; read operation: terminal loop certificate
Pass example: Inputs `raw MIR blocks/terminators/source_info; renderer-input functionSource and node basicBlockRefs/lineRanges; verifier pin/relation/classification/certificate record; record fields id; read operation: terminal loop certificate` with state `declaredRefs=["a1"]; observedRefs=["a1"]` -> accepted.
Fail example: Inputs `raw MIR blocks/terminators/source_info; renderer-input functionSource and node basicBlockRefs/lineRanges; verifier pin/relation/classification/certificate record; record fields id; read operation: terminal loop certificate` with state `declaredRefs=["a1"]; observedRefs=[]` -> rejected.

### terminal-loop-exclusive
Aliases: -
Enforced: scripts/terminal_loop_verifier.py:278
Condition: terminalOnly and commonAfter are mutually exclusive.
Stage: Stage 7
Required producer fields: raw MIR blocks/terminators/source_info; renderer-input functionSource and node basicBlockRefs/lineRanges; verifier pin/relation/classification/certificate record; terminal loop exclusive proof fields
Pass example: Inputs `raw MIR blocks/terminators/source_info; renderer-input functionSource and node basicBlockRefs/lineRanges; verifier pin/relation/classification/certificate record; terminal loop exclusive proof fields` with state `readingScopes[0]={terminalOnly:{proofRef:"proof"}} with commonAfter absent` -> accepted.
Fail example: Inputs `raw MIR blocks/terminators/source_info; renderer-input functionSource and node basicBlockRefs/lineRanges; verifier pin/relation/classification/certificate record; terminal loop exclusive proof fields` with state `readingScopes[0] contains both terminalOnly and commonAfter` -> rejected.

### terminal-loop-execution-edge
Aliases: -
Enforced: scripts/terminal_loop_verifier.py:178
Condition: The enclosing failure condition is false: `if not source_ok or not target_ok: fail.append({'code':'terminal-loop-execution-edge','scope':scope.get('id'),'edge':edge.get('id')})`.
Stage: Stage 7
Required producer fields: execution.edges[].from/to; execution.nodes[].kind/actionRef/outcome; terminalOnly.terminalNodeRefs; scope member actions
Pass example: Inputs `execution.edges[].from/to; execution.nodes[].kind/actionRef/outcome; terminalOnly.terminalNodeRefs; scope member actions` with state `loop-exit edge goes from member action node n1 to declared terminal t1` -> accepted.
Fail example: Inputs `execution.edges[].from/to; execution.nodes[].kind/actionRef/outcome; terminalOnly.terminalNodeRefs; scope member actions` with state `loop-exit edge goes from unrelated action n9 to terminal t1` -> rejected.

### terminal-loop-exit-coverage
Aliases: -
Enforced: scripts/terminal_loop_verifier.py:172
Condition: terminalOnly.exitEdgeRefs equals exactly all execution loop-exit IDs for that scope.
Stage: Stage 7
Required producer fields: raw MIR blocks/terminators/source_info; renderer-input functionSource and node basicBlockRefs/lineRanges; verifier pin/relation/classification/certificate record; terminal loop exit coverage proof fields
Pass example: Inputs `raw MIR blocks/terminators/source_info; renderer-input functionSource and node basicBlockRefs/lineRanges; verifier pin/relation/classification/certificate record; terminal loop exit coverage proof fields` with state `declaredRefs=["a1"]; observedRefs=["a1"]` -> accepted.
Fail example: Inputs `raw MIR blocks/terminators/source_info; renderer-input functionSource and node basicBlockRefs/lineRanges; verifier pin/relation/classification/certificate record; terminal loop exit coverage proof fields` with state `declaredRefs=["a1"]; observedRefs=[]` -> rejected.

### terminal-loop-mismatch
Aliases: -
Enforced: scripts/terminal_loop_verifier.py:277
Condition: The enclosing failure condition is false: `if cert.get(key) != value: fail.append({'code':'terminal-loop-mismatch','scope':scope['id'],'field':key})`.
Stage: Stage 7
Required producer fields: raw MIR blocks/terminators/source_info; renderer-input functionSource and node basicBlockRefs/lineRanges; verifier pin/relation/classification/certificate record; record fields id; read operation: terminal loop mismatch
Pass example: Inputs `raw MIR blocks/terminators/source_info; renderer-input functionSource and node basicBlockRefs/lineRanges; verifier pin/relation/classification/certificate record; record fields id; read operation: terminal loop mismatch` with state `declared="a1"; observed="a1"` -> accepted.
Fail example: Inputs `raw MIR blocks/terminators/source_info; renderer-input functionSource and node basicBlockRefs/lineRanges; verifier pin/relation/classification/certificate record; record fields id; read operation: terminal loop mismatch` with state `declared="a1"; observed="missing"` -> rejected.

### terminal-loop-operation
Aliases: -
Enforced: scripts/terminal_loop_verifier.py:254
Condition: The enclosing failure condition is false: `if reason is None: fail.append({'code':'terminal-loop-operation','scope':scope['id'],'bb':'bb'+str(n),'operation':index,'kind':kind})`.
Stage: Stage 7
Required producer fields: raw MIR member/tail basic_blocks[].statements; allowed terminal-tail operations
Pass example: Inputs `raw MIR member/tail basic_blocks[].statements; allowed terminal-tail operations` with state `tail bb4 contains only StorageDead and deinit operations` -> accepted.
Fail example: Inputs `raw MIR member/tail basic_blocks[].statements; allowed terminal-tail operations` with state `tail bb4 contains a business Call operation` -> rejected.

### terminal-loop-tail
Aliases: -
Enforced: scripts/terminal_loop_verifier.py:275
Condition: The enclosing failure condition is false: `if cyclic or not terminals or leaves != set(terminals): fail.append({'code':'terminal-loop-tail','scope':scope['id'],'reason':'tail must be acyclic and end only in Return'})`.
Stage: Stage 7
Required producer fields: raw MIR CFG successors/terminators; certificate terminalBBs
Pass example: Inputs `raw MIR CFG successors/terminators; certificate terminalBBs` with state `tail bb4 is acyclic and its sole leaf bb5 terminates Return` -> accepted.
Fail example: Inputs `raw MIR CFG successors/terminators; certificate terminalBBs` with state `tail bb4 cycles to itself before Return` -> rejected.

### terminal-loop-terminal-node
Aliases: -
Enforced: scripts/terminal_loop_verifier.py:171
Condition: The enclosing failure condition is false: `if node.get('kind') != 'terminal' or node.get('outcome') not in ('return','error') or not set(node.get('basicBlockRefs', [])) & terminal_bbs: fail.append({'code':'terminal-loop-terminal-node','scope':scope.get('id'),'node':ref})`.
Stage: Stage 7
Required producer fields: raw MIR blocks/terminators/source_info; renderer-input functionSource and node basicBlockRefs/lineRanges; verifier pin/relation/classification/certificate record; record fields kind, outcome, basicBlockRefs, id
Pass example: Inputs `raw MIR blocks/terminators/source_info; renderer-input functionSource and node basicBlockRefs/lineRanges; verifier pin/relation/classification/certificate record; record fields kind, outcome, basicBlockRefs, id` with state `declared="a1"; observed="a1"` -> accepted.
Fail example: Inputs `raw MIR blocks/terminators/source_info; renderer-input functionSource and node basicBlockRefs/lineRanges; verifier pin/relation/classification/certificate record; record fields kind, outcome, basicBlockRefs, id` with state `declared="a1"; observed="missing"` -> rejected.

### terminal-loop-terminator
Aliases: -
Enforced: scripts/terminal_loop_verifier.py:262
Condition: The enclosing failure condition is false: `if reason is None: fail.append({'code':'terminal-loop-terminator','scope':scope['id'],'bb':'bb'+str(n),'kind':kind})`.
Stage: Stage 7
Required producer fields: raw MIR tail basic_blocks[].terminator.kind; allowed Return-only tail terminators
Pass example: Inputs `raw MIR tail basic_blocks[].terminator.kind; allowed Return-only tail terminators` with state `tail leaf bb5 terminator.kind="Return"` -> accepted.
Fail example: Inputs `raw MIR tail basic_blocks[].terminator.kind; allowed Return-only tail terminators` with state `tail leaf bb5 terminator.kind="Yield"` -> rejected.

### test.boundaryCoverage
Aliases: -
Enforced: assets/renderer/contract.mjs:85
Condition: Fails exactly when the enforcing predicate reports: `every action must belong to one declared independent test boundary`.
Stage: Stage 7
Required producer fields: deliveryMode; testBoundaries[].actionRefs; phases[].goals[].actions[].id
Pass example: Inputs `deliveryMode; testBoundaries[].actionRefs; phases[].goals[].actions[].id` with state `declaredRefs=["a1"]; observedRefs=["a1"]` -> accepted.
Fail example: Inputs `deliveryMode; testBoundaries[].actionRefs; phases[].goals[].actions[].id` with state `declaredRefs=["a1"]; observedRefs=[]` -> rejected.

### test.caseCoverage
Aliases: -
Enforced: assets/renderer/contract.mjs:85
Condition: Fails exactly when the enforcing predicate reports: `every case belongs to explicit test boundary`.
Stage: Stage 7
Required producer fields: testBoundaries[].caseRefs; caseIndex[][0]; read operation: caseCoverage
Pass example: Inputs `testBoundaries[].caseRefs; caseIndex[][0]; read operation: caseCoverage` with state `declaredRefs=["a1"]; observedRefs=["a1"]` -> accepted.
Fail example: Inputs `testBoundaries[].caseRefs; caseIndex[][0]; read operation: caseCoverage` with state `declaredRefs=["a1"]; observedRefs=[]` -> rejected.

### test.caseReference
Aliases: -
Enforced: assets/renderer/contract.mjs:85
Condition: Fails exactly when the enforcing predicate reports: `exact case references required`.
Stage: Stage 7
Required producer fields: testBoundaries[].caseRefs; caseIndex[][0]; read operation: caseReference
Pass example: Inputs `testBoundaries[].caseRefs; caseIndex[][0]; read operation: caseReference` with state `declaredRefs=["a1"]; observedRefs=["a1"]` -> accepted.
Fail example: Inputs `testBoundaries[].caseRefs; caseIndex[][0]; read operation: caseReference` with state `declaredRefs=["a1"]; observedRefs=[]` -> rejected.

### unproven-event-macro
Aliases: -
Enforced: scripts/event_macro_verifier.py:329
Condition: The enclosing failure condition is false: `if not block: errors.append({'code': 'unproven-event-macro', 'bbRef': ref})`.
Stage: Stage 7
Required producer fields: raw MIR blocks/terminators/source_info; renderer-input functionSource and node basicBlockRefs/lineRanges; verifier pin/relation/classification/certificate record; unproven event macro proof fields
Pass example: Inputs `raw MIR blocks/terminators/source_info; renderer-input functionSource and node basicBlockRefs/lineRanges; verifier pin/relation/classification/certificate record; unproven event macro proof fields` with state `declared="a1"; observed="a1"` -> accepted.
Fail example: Inputs `raw MIR blocks/terminators/source_info; renderer-input functionSource and node basicBlockRefs/lineRanges; verifier pin/relation/classification/certificate record; unproven event macro proof fields` with state `declared="a1"; observed="missing"` -> rejected.

### unproven-shell-instrumentation-base
Aliases: -
Enforced: scripts/async_shell_verifier.py:435
Condition: The enclosing failure condition is false: `if unproven_base: failures.append({'code': 'unproven-shell-instrumentation-base',`.
Stage: Stage 7
Required producer fields: shell MIR candidate BBs; instrumentation classification proof blocks
Pass example: Inputs `shell MIR candidate BBs; instrumentation classification proof blocks` with state `candidate base BBs=["shell:bb2"]; proof blocks=["shell:bb2"]` -> accepted.
Fail example: Inputs `shell MIR candidate BBs; instrumentation classification proof blocks` with state `candidate base BBs=["shell:bb2"]; proof blocks=[]` -> rejected.

### unproven-span-wrapper-extension
Aliases: -
Enforced: scripts/span_wrapper_extension_verifier.py:259
Condition: The enclosing failure condition is false: `if number in proof['candidates'] and number not in proof['blocks']: errors.append({'code': 'unproven-span-wrapper-extension', 'bbRef': ref})`.
Stage: Stage 7
Required producer fields: raw MIR blocks/terminators/source_info; renderer-input functionSource and node basicBlockRefs/lineRanges; verifier pin/relation/classification/certificate record; record fields candidates, blocks
Pass example: Inputs `raw MIR blocks/terminators/source_info; renderer-input functionSource and node basicBlockRefs/lineRanges; verifier pin/relation/classification/certificate record; record fields candidates, blocks` with state `functionSource L10-L12; lineRanges=[L10-L11]` -> accepted.
Fail example: Inputs `raw MIR blocks/terminators/source_info; renderer-input functionSource and node basicBlockRefs/lineRanges; verifier pin/relation/classification/certificate record; record fields candidates, blocks` with state `functionSource L10-L12; lineRanges=[L9-L11]` -> rejected.

### unsupported-attribute-range
Aliases: -
Enforced: scripts/attribute_source_verifier.py:255, scripts/attribute_source_verifier.py:271
Condition: The enclosing failure condition is false: `if exact is None: errors.append({'code': 'unsupported-attribute-range', 'node': node.get('id'),`.
Stage: Stage 7
Required producer fields: raw MIR blocks/terminators/source_info; renderer-input functionSource and node basicBlockRefs/lineRanges; verifier pin/relation/classification/certificate record; record fields id; read operation: unsupported attribute range
Pass example: Inputs `raw MIR blocks/terminators/source_info; renderer-input functionSource and node basicBlockRefs/lineRanges; verifier pin/relation/classification/certificate record; record fields id; read operation: unsupported attribute range` with state `functionSource L10-L12; lineRanges=[L10-L11]` -> accepted.
Fail example: Inputs `raw MIR blocks/terminators/source_info; renderer-input functionSource and node basicBlockRefs/lineRanges; verifier pin/relation/classification/certificate record; record fields id; read operation: unsupported attribute range` with state `functionSource L10-L12; lineRanges=[L9-L11]` -> rejected.


### publish.frozen.renderer.must.specify.all.three.static.assets
Aliases: -
Enforced: scripts/publish_site.py:37
Condition: The frozen asset mapping contains exactly the three required static filenames.
Stage: Stage 7
Required producer fields: keys of frozen_assets: index.html, style.css, app.bundle.js
Pass example: keys=[index.html,style.css,app.bundle.js], no extra entries -> accepted
Fail example: keys=[index.html,app.bundle.js], style.css absent -> rejected


### publish.frozen.renderer.changed
Aliases: -
Enforced: scripts/publish_site.py:35
Condition: Each frozen asset file content SHA256 equals its lock entry.
Stage: Stage 7
Required producer fields: frozen_assets[name].path; frozen_assets[name].sha256; SHA256 of the file bytes
Pass example: path=asset.js containing bytes abc; sha256=ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad -> accepted
Fail example: path=asset.js containing bytes abcd; sha256=ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad -> rejected



## Unified model diagnostics (S2 / S5 / S7) and lifecycle gates

These repair keys are emitted by the canonical stage gates. The frozen inventory retains its existing canonical stage entries.

| Error key | Enforced | Required repair |
| --- | --- | --- |
| `STOP-empty-action` | scripts/canonical_stages.py:503 | 核验pin或重做S3审阅/锁；空action必须停止并报告A/B选项。 |
| `event-macro-pins-missing` | scripts/stage_engine.py:217 | 核验pin或重做S3审阅/锁；空action必须停止并报告A/B选项。 |
| `model-bb-coverage` | scripts/check_model.py:29, scripts/check_model.py:33 | elements必须恰好覆盖原始MIR BB。 |
| `model-bb-destination` | scripts/check_model.py:74 | ROOT技术BB中的调用去向必须technical。 |
| `model-body-destination` | scripts/check_model.py:76 | 构造/消费BB均属技术时，执行体去向也必须technical。 |
| `model-body-endpoint` | scripts/check_model.py:184 | shown闭包/coroutine需真实endpoint及构造/消费调用绑定的消息。 |
| `model-call-interval` | scripts/check_model.py:68 | 混合BB中已证明的日志终止调用去向必须technical。 |
| `model-callee-pin` | scripts/check_model.py:202, scripts/stage_engine.py:287, scripts/stage_engine.py:432, scripts/stage_engine.py:434, scripts/stage_engine.py:436, scripts/stage_engine.py:455, scripts/stage_engine.py:458, scripts/stage_engine.py:464, scripts/stage_engine.py:472, scripts/stage_engine.py:474 | 核验pin或重做S3审阅/锁；空action必须停止并报告A/B选项。 |
| `model-destination` | scripts/canonical_stages.py:586 | 只允许shown、technical、folded。 |
| `model-duplicate-fold-rule` | scripts/canonical_stages.py:573 | 每个目标类别最多一条默认折叠规则。 |
| `model-duplicate-id` | scripts/canonical_stages.py:32, scripts/canonical_stages.py:569, scripts/check_model.py:14, scripts/check_model.py:27, scripts/check_model.py:87, scripts/check_model.py:89, scripts/check_model.py:138 | 同一元素只保留一个决定，事实id也必须唯一。 |
| `model-erased-future` | scripts/check_model.py:205, scripts/check_model.py:209 | 核验pin或重做S3审阅/锁；空action必须停止并报告A/B选项。 |
| `model-fold-reason` | scripts/canonical_stages.py:588 | folded必须提供按源码写的非空理由。 |
| `model-fold-rule` | scripts/canonical_stages.py:576 | 整类折叠只允许std/third_party且必须有理由。 |
| `model-folded-actor` | scripts/check_model.py:103 | folded不得同时成为已渲染actor。 |
| `model-group-order` | scripts/check_model.py:83 | 重建层级；组间边必须等于normal CFG投影。 |
| `model-instrumentation-proof` | scripts/check_model.py:222 | 核验pin或重做S3审阅/锁；空action必须停止并报告A/B选项。 |
| `model-local-business` | scripts/canonical_stages.py:617, scripts/check_model.py:78 | 函数体或执行coroutine含业务逻辑必须shown并连接真实endpoint。 |
| `model-local-source` | scripts/canonical_stages.py:615 | local_mir逐项记录business/adapter决定与源码引用。 |
| `model-log-business` | scripts/check_model.py:61 | 将已有完整日志证明的BB移出业务组归ROOT。 |
| `model-member-binding` | scripts/check_model.py:145 | 核验pin或重做S3审阅/锁；空action必须停止并报告A/B选项。 |
| `model-member-coverage` | scripts/check_model.py:173 | 核验pin或重做S3审阅/锁；空action必须停止并报告A/B选项。 |
| `model-member-endpoint` | scripts/check_model.py:155, scripts/check_model.py:166, scripts/check_model.py:170 | 核验pin或重做S3审阅/锁；空action必须停止并报告A/B选项。 |
| `model-member-invocation` | scripts/check_model.py:149 | 核验pin或重做S3审阅/锁；空action必须停止并报告A/B选项。 |
| `model-message-destination` | scripts/check_model.py:114 | S5消息只能指向S2 shown调用。 |
| `model-message-pair` | scripts/check_model.py:131 | 同一对消息的pair、invocation、binding和端点方向必须一致。 |
| `model-mir-witness` | scripts/check_model.py:38 | 元素中的操作/终结器形状及hash必须与MIR逐项一致。 |
| `model-missing-id` | scripts/canonical_stages.py:583 | 为列出的Call/body逐项补去向，或用合法std/third_party默认fold规则覆盖。 |
| `model-owner-mismatch` | scripts/canonical_stages.py:605, scripts/check_model.py:152, scripts/check_model.py:177 | 删除手写归属或使其与层级BB归属严格一致。 |
| `model-proof-reason` | scripts/canonical_stages.py:528, scripts/canonical_stages.py:530 | 逐操作与终结器理由必须为非空源码说明。 |
| `model-redundant-field` | scripts/check_model.py:95, scripts/check_model.py:142, scripts/blueprint.py:28, scripts/blueprint.py:30, scripts/blueprint.py:32, scripts/blueprint.py:50 | 移除手抄instrumentation、BB/group顺序、sourceInventory或innerBodies。 |
| `model-selection-drift` | scripts/check_model.py:230 | 核验pin或重做S3审阅/锁；空action必须停止并报告A/B选项。 |
| `model-shown-message` | scripts/check_model.py:128 | shown调用必须恰好一对request/return消息。 |
| `model-stale-witness` | scripts/canonical_stages.py:525 | BB事实hash与elements不一致，重新提取S1。 |
| `model-structural-proof` | scripts/check_model.py:56 | 核验pin或重做S3审阅/锁；空action必须停止并报告A/B选项。 |
| `model-switch-inventory` | scripts/check_model.py:92 | 在S2判断清单补足遗漏SwitchInt证据，S4只消费投影。 |
| `model-technical-intervals` | scripts/check_model.py:233 | 重建S2区间投影，必须与elements的安全日志操作证明相等。 |
| `model-technical-proof` | scripts/check_model.py:70, scripts/check_model.py:72 | technical需要完整BB证明，或混合BB日志终止调用的区间证明。 |
| `model-technical-witnesses` | scripts/check_model.py:227 | S2技术记录须等于elements事实及证明推导值，重新生成。 |
| `model-unknown-bb` | scripts/canonical_stages.py:522, scripts/check_model.py:20 | 调用/判断必须引用存在的BB元素。 |
| `model-unknown-id` | scripts/canonical_stages.py:567, scripts/check_model.py:109 | 删去未知引用或恢复对应S1元素；不允许虚构Call/body。 |
| `model-unknown-kind` | scripts/check_model.py:18 | 元素kind只允许bb、call、body、switch。 |
| `model-unknown-operation` | scripts/canonical_stages.py:532 | 逐操作理由只可引用该BB真实语句下标。 |
| `stage3-lock-missing` | scripts/gate_lifecycle.py:251 | 核验pin或重做S3审阅/锁；空action必须停止并报告A/B选项。 |
| `stage3-lock-stale` | scripts/gate_lifecycle.py:255 | 核验pin或重做S3审阅/锁；空action必须停止并报告A/B选项。 |
| `stage3-review-failed` | scripts/stage_engine.py:571 | 核验pin或重做S3审阅/锁；空action必须停止并报告A/B选项。 |

| `model-information-destination` | scripts/canonical_stages.py:595 | Recompute the MIR information proof, destination or body-message association; repair authored decisions and references to match the facts. |

| `model-body-message` | scripts/check_model.py:116 | Recompute the MIR information proof, destination or body-message association; repair authored decisions and references to match the facts. |

| `model-internal-operation` | scripts/check_model.py:161 | Recompute the MIR information proof, destination or body-message association; repair authored decisions and references to match the facts. |

| `model-information-proof` | scripts/check_model.py:213 | Recompute the MIR information proof, destination or body-message association; repair authored decisions and references to match the facts. |

| `model-internal-message` | scripts/check_model.py:125 | Recompute the MIR information proof, destination or body-message association; repair authored decisions and references to match the facts. |


## v22 按需 pin 说明

按需分析所需项目 body 在容器中存在但缺精确 pin，或 pin 的容器/owner/stage/body_id/SHA 不符，硬失败并列缺失身份。S0 自行生成；S1 补执行体；S2/S5/S7 验证，不以缺 pin 冒充缺 MIR。

## v22 trait 解析说明

trait 调用按具体接收者与 trait 实体解析到 definitions 中唯一 impl；多个匹配硬失败。dyn 保留声明身份，不假装其使用默认实现。

## v22 运行恢复说明

运行失败分类、环境未运行记录、证据支持的运行目录修正、偏离 SHA 与阶段使用记录见 [run-recovery.md](run-recovery.md)。原原则/源码/合同/回归检查全部保留；S3 自动锁定，S7 agent 以当前证据决定并直接完成验收。
### P6.full_source_identity_registry
Aliases: -
Enforced: scripts/check_principles.py:379
Condition: Every resolved source actor, including ancestors, has an unchanged source identity in identity_registry, with no duplicates or unknown actors.
Stage: Stage 5 and Stage 7
Required producer fields: stage5.external.identity_registry actorId/sourceNodeRef/bodyRef/declarationRef and renderer actors
Pass example: Source actor a with bodyRef h|stage|main appears unchanged once in identity_registry.
Fail example: Source actor a has bodyRef h|stage|main in actors but is absent from identity_registry.

### P7.async_mechanism
Aliases: -
Enforced: scripts/check_principles.py:423
Condition: Wording hint only: report the existing async_mechanism predicate as warning; it never blocks a stage or triggers repair.
Stage: Stage 2, Stage 4 and Stage 7
Required producer fields: Visible display fields scanned for async_mechanism patterns
Pass example: `处理本次请求` emits no wording hint.
Fail example: `poll Pending` emits a nonblocking warning with a display pointer.

### P7.code_condition
Aliases: -
Enforced: scripts/check_principles.py:423
Condition: Wording hint only: report the existing code_condition predicate as warning; it never blocks a stage or triggers repair.
Stage: Stage 2, Stage 4 and Stage 7
Required producer fields: Visible display fields scanned for code_condition patterns
Pass example: `核对当前结果` emits no wording hint.
Fail example: `discriminant(_12)` emits a nonblocking warning with a display pointer.

### P7.evidence_as_content
Aliases: -
Enforced: scripts/check_principles.py:423
Condition: Wording hint only: report the existing evidence_as_content predicate as warning; it never blocks a stage or triggers repair.
Stage: Stage 2, Stage 4 and Stage 7
Required producer fields: Visible display fields scanned for evidence_as_content patterns
Pass example: `进入后续步骤` emits no wording hint.
Fail example: `@canonical:origin` emits a nonblocking warning with a display pointer.

### P7.low_level_identifier
Aliases: -
Enforced: scripts/check_principles.py:423
Condition: Wording hint only: report the existing low_level_identifier predicate as warning; it never blocks a stage or triggers repair.
Stage: Stage 2, Stage 4 and Stage 7
Required producer fields: Visible display fields scanned for low_level_identifier patterns
Pass example: `准备输入` emits no wording hint.
Fail example: `bb419 call:3` emits a nonblocking warning with a display pointer.

### output.output.root.is.required.in.the.initial.request.no.default.finish.failed.if.missi
Aliases: -
Enforced: scripts/output_paths.py:68
Condition: The enclosing failure condition is false: `if not value or not value.strip(): raise ValueError('OUTPUT_ROOT is required; finish failed with the missing initial request parameter (no default)')`.
Stage: Prepare
Required producer fields: OUTPUT_ROOT argument/environment value
Pass example: Inputs `OUTPUT_ROOT argument/environment value` with state `OUTPUT_ROOT="/out"` -> accepted.
Fail example: Inputs `OUTPUT_ROOT argument/environment value` with state `OUTPUT_ROOT=""` -> rejected.

