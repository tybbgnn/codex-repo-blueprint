import sys
from pathlib import Path as _PackagePath
sys.path.insert(0, str(_PackagePath(__file__).resolve().parents[1] / 'scripts'))

import copy
import tempfile
import unittest
from pathlib import Path

from canonical_stages import _execution_order, ownership, validate_goal_contracts
from classification_registry import fingerprint
from reading_groups import validate_reading_groups


def block(number, kind='Goto', successors=None, statements=None):
    successors = [number + 1] if successors is None else successors
    return {
        'basic_block': number,
        'is_cleanup': False,
        'statements': statements or [],
        'terminator': {'kind': kind, 'successors': successors, 'detail': {}},
    }


def edge(source, target, ordinal=0):
    return {'id': f'm{source}.{ordinal}', 'source': f'bb{source}', 'target': f'bb{target}'}


def node(identity, kind, members, name=None, evidence=None):
    return {'id': identity, 'kind': kind, 'name': name or identity,
            'members': members, 'evidence': evidence or ['bb0']}


def business_ledger(group_members=('bb0', 'bb1'), group_id='P01/A01.0/C0', group_name='片段工作'):
    nodes = [
        node('ROOT', 'root', ['P01']),
        node('P01', 'phase', ['sem:P01:g']),
        node('sem:P01:g', 'goal', ['P01/A01.0']),
        node('P01/A01.0', 'action', [group_id], name='完成业务动作'),
        node(group_id, 'bb_group', list(group_members), name=group_name, evidence=list(group_members)),
    ]
    return {'schema_version': 1, 'root': 'ROOT', 'phase_order': ['P01'], 'nodes': nodes,
            'technical': [], 'selection': {},
            'granularity': {'technicalBlocks': [], 'goalContracts': []}}


def contract(goal, action, contract_ref='contract:x', entry='normal'):
    return {'goalRef': goal, 'contractRef': contract_ref, 'entryMode': entry,
            'completion': '完成交付', 'cohesionReason': '共同履行合同', 'evidenceRefs': ['bb0'],
            'memberContracts': [{'actionRef': action, 'contractRef': contract_ref,
                                 'entryMode': entry, 'evidenceRefs': ['bb0']}]}


class TechnicalProofTests(unittest.TestCase):
    def root_technical_ledger(self, technical_record):
        ledger = business_ledger(('bb1',), 'P01/A01.0/C1')
        ledger['nodes'][0]['members'].append('ROOT/C0')
        ledger['nodes'].append(node('ROOT/C0', 'bb_group', ['bb0'], name='清理临时存储', evidence=['bb0']))
        ledger['granularity']['technicalBlocks'] = [technical_record]
        return ledger

    def test_drop_record_missing_operation_proofs_fails(self):
        assignment = {'kind': 'Assign', 'statement_index': 0,
                      'detail': {'destination': {'local': 1}, 'rvalue': {'kind': 'Use'}}}
        blocks = {'bb0': block(0, 'Goto', [1], [assignment]), 'bb1': block(1, 'Return', [])}
        record = {'bbRef': 'bb0', 'category': 'drop', 'reason': '伪造技术赋值',
                  'evidenceRefs': ['bb0'], 'factSha256': fingerprint(blocks['bb0']),
                  'terminatorProof': 'Goto 到下一块'}
        with self.assertRaisesRegex(ValueError, 'Incomplete operation proof'):
            ownership(self.root_technical_ledger(record), blocks, [edge(0, 1)],
                      {'basic_blocks': list(blocks.values())})

    def test_cleanup_record_with_invalid_anchor_fails(self):
        blocks = {'bb0': block(0), 'bb1': block(1, 'Return', [])}
        record = {'bbRef': 'bb0', 'category': 'cleanup', 'reason': '清理临时状态',
                  'evidenceRefs': ['invented-anchor'], 'factSha256': fingerprint(blocks['bb0'])}
        with self.assertRaisesRegex(ValueError, 'Invalid technical block proof'):
            ownership(self.root_technical_ledger(record), blocks, [edge(0, 1)],
                      {'basic_blocks': list(blocks.values())})

    def test_unregistered_category_fails(self):
        blocks = {'bb0': block(0), 'bb1': block(1, 'Return', [])}
        record = {'bbRef': 'bb0', 'category': 'routing', 'reason': '未知类别',
                  'evidenceRefs': ['bb0']}
        with self.assertRaises(ValueError):
            ownership(self.root_technical_ledger(record), blocks, [edge(0, 1)],
                      {'basic_blocks': list(blocks.values())})

    def test_root_bb_without_record_fails(self):
        blocks = {'bb0': block(0), 'bb1': block(1, 'Return', [])}
        ledger = self.root_technical_ledger(
            {'bbRef': 'bb0', 'category': 'cleanup', 'reason': '清理', 'evidenceRefs': ['bb0']})
        ledger['granularity']['technicalBlocks'] = []
        with self.assertRaisesRegex(ValueError, 'ROOT technical BB lacks a valid record'):
            ownership(ledger, blocks, [edge(0, 1)], {'basic_blocks': list(blocks.values())})

    def test_cleanup_record_with_valid_source_anchor_passes(self):
        blocks = {'bb0': block(0), 'bb1': block(1, 'Return', [])}
        record = {'bbRef': 'bb0', 'category': 'cleanup', 'reason': '清理临时状态',
                  'evidenceRefs': ['bb0', 'source/example.rs:1-2'],
                  'factSha256': fingerprint(blocks['bb0'])}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'source').mkdir()
            (root / 'source/example.rs').write_text('first\nsecond\n')
            nodes, _ = ownership(self.root_technical_ledger(record), blocks, [edge(0, 1)],
                                 {'basic_blocks': list(blocks.values())}, evidence_root=root)
        self.assertTrue(nodes['ROOT/C0']['technical'])
        self.assertEqual(nodes['ROOT/C0']['technical_reasons'][0]['type'], 'cleanup')

    def test_storage_dead_goto_record_passes(self):
        storage = {'kind': 'StorageDead', 'statement_index': 0, 'detail': {'local': 1}}
        blocks = {'bb0': block(0, 'Goto', [1], [storage]), 'bb1': block(1, 'Return', [])}
        record = {'bbRef': 'bb0', 'category': 'drop', 'reason': '只结束临时存储寿命并转交',
                  'evidenceRefs': ['bb0'], 'factSha256': fingerprint(blocks['bb0']),
                  'operationProofs': [],
                  'terminatorProof': 'Goto 到下一块'}
        nodes, _ = ownership(self.root_technical_ledger(record), blocks, [edge(0, 1)],
                             {'basic_blocks': list(blocks.values())})
        self.assertTrue(nodes['ROOT/C0']['technical'])
        self.assertEqual(nodes['ROOT/C0']['technical_reasons'][0]['type'], 'drop')


class GoalContractTests(unittest.TestCase):
    def goal_nodes(self, count=1):
        nodes = {'P01': {'id': 'P01', 'kind': 'phase',
                         'children': [f'g{i}' for i in range(count)]}}
        for i in range(count):
            nodes[f'g{i}'] = {'id': f'g{i}', 'kind': 'goal', 'children': [f'a{i}']}
            nodes[f'a{i}'] = {'id': f'a{i}', 'kind': 'action', 'children': []}
        return nodes

    def test_missing_goal_member_fails(self):
        nodes = self.goal_nodes()
        record = contract('g0', 'a0')
        record['memberContracts'] = []
        ledger = {'phase_order': ['P01'], 'granularity': {'goalContracts': [record]}}
        with self.assertRaisesRegex(ValueError, 'member coverage'):
            validate_goal_contracts(nodes, ledger)

    def test_mixed_contract_fails(self):
        nodes = self.goal_nodes()
        record = contract('g0', 'a0')
        record['memberContracts'][0]['contractRef'] = 'contract:other'
        ledger = {'phase_order': ['P01'], 'granularity': {'goalContracts': [record]}}
        with self.assertRaisesRegex(ValueError, 'mixed completion'):
            validate_goal_contracts(nodes, ledger)

    def test_three_fragmented_single_action_goals_fail(self):
        nodes = self.goal_nodes(3)
        records = [contract(f'g{i}', f'a{i}') for i in range(3)]
        ledger = {'phase_order': ['P01'], 'granularity': {'goalContracts': records}}
        with self.assertRaisesRegex(ValueError, 'adjacent singleton goals'):
            validate_goal_contracts(nodes, ledger)

    def test_three_singleton_goals_with_distinct_contracts_pass(self):
        nodes = self.goal_nodes(3)
        records = [dict(contract(f'g{i}', f'a{i}', contract_ref=f'contract:{i}'),
                        targetRef='target:shared') for i in range(3)]
        ledger = {'phase_order': ['P01'], 'granularity': {'goalContracts': records}}
        validate_goal_contracts(nodes, ledger)


class GroupSchemeATests(unittest.TestCase):
    def blocks(self, count):
        result = {f'bb{i}': block(i, 'Goto' if i + 1 < count else 'Return',
                                  [i + 1] if i + 1 < count else []) for i in range(count)}
        return result

    def test_disconnected_group_fails(self):
        blocks = self.blocks(2)
        with self.assertRaisesRegex(ValueError, 'exactly one entry'):
            ownership(business_ledger(), blocks, [], {'basic_blocks': list(blocks.values())})

    def test_switch_fork_inside_group_fails(self):
        blocks = self.blocks(3)
        blocks['bb0'] = block(0, 'SwitchInt', [1, 2])
        edges = [edge(0, 1), edge(0, 2, 1)]
        with self.assertRaisesRegex(ValueError, 'internal branch'):
            ownership(business_ledger(('bb0', 'bb1', 'bb2')), blocks, edges,
                      {'basic_blocks': list(blocks.values())})

    def test_multiple_entries_fail(self):
        blocks = self.blocks(3)
        group = {'id': 'A/C1', 'basic_block_refs': ['bb1', 'bb2']}
        with self.assertRaisesRegex(ValueError, 'exactly one entry'):
            _execution_order(group, [edge(0, 1), edge(0, 2, 1)], blocks)

    def test_group_id_must_use_execution_first_bb(self):
        blocks = self.blocks(2)
        with self.assertRaisesRegex(ValueError, 'execution-first C0'):
            ownership(business_ledger(group_id='P01/A01.0/C1'), blocks, [edge(0, 1)],
                      {'basic_blocks': list(blocks.values())})

    def test_non_entry_cycle_fails(self):
        blocks = self.blocks(4)
        edges = [edge(0, 1), edge(1, 2), edge(2, 1, 1), edge(2, 3)]
        with self.assertRaisesRegex(ValueError, 'internal branch'):
            ownership(business_ledger(('bb0', 'bb1', 'bb2', 'bb3')), blocks, edges,
                      {'basic_blocks': list(blocks.values())})

    def test_group_name_must_not_copy_parent(self):
        blocks = self.blocks(2)
        with self.assertRaisesRegex(ValueError, 'repeats parent label'):
            ownership(business_ledger(group_name='完成业务动作'), blocks, [edge(0, 1)],
                      {'basic_blocks': list(blocks.values())})

    def test_group_name_must_not_contain_parent(self):
        blocks = self.blocks(2)
        with self.assertRaisesRegex(ValueError, 'repeats parent label'):
            ownership(business_ledger(group_name='完成业务动作的 MIR 片段'), blocks, [edge(0, 1)],
                      {'basic_blocks': list(blocks.values())})

    def test_sibling_group_names_must_be_unique_after_normalization(self):
        blocks = {'bb0': block(0), 'bb1': block(1, 'Return', [])}
        nodes = {
            'A': node('A', 'action', ['A/C0', 'A/C1'], name='执行业务动作'),
            'A/C0': node('A/C0', 'bb_group', ['bb0'], name='读取 状态！', evidence=['bb0']),
            'A/C1': node('A/C1', 'bb_group', ['bb1'], name='读取状态', evidence=['bb1']),
        }
        nodes['A/C0']['children'] = ['bb0']
        nodes['A/C1']['children'] = ['bb1']
        with self.assertRaisesRegex(ValueError, 'Sibling reading groups repeat normalized label'):
            validate_reading_groups(nodes, {'A/C0': 'A', 'A/C1': 'A'}, blocks)

    def test_numbered_copy_forms_normalize_to_the_same_group_name(self):
        from reading_groups import normalized_label
        pairs = [
            ('评估日志输出条件并组装诊断记录 2', '评估日志输出条件并组装诊断记录 3'),
            ('汇合前置路径 1', '汇合前置路径 2'),
            ('X (2)', 'X (3)'),
            ('X（2）', 'X（3）'),
            ('X [2]', 'X [3]'),
            ('X #2', 'X #3'),
            ('X 2号', 'X 3号'),
        ]
        for left, right in pairs:
            with self.subTest(left=left, right=right):
                self.assertEqual(normalized_label(left), normalized_label(right))

    def test_meaningful_ordinals_and_distinct_names_remain_distinct(self):
        from reading_groups import normalized_label
        pairs = [
            ('接续参数错误事件的第二字段槽位', '接续参数错误事件的第三字段槽位'),
            ('第2段X', '第3段X'),
            ('X 1st 字段', 'X 2nd 字段'),
            ('X 1st', 'X 2nd'),
            ('阶段第 2', '阶段第 3'),
            ('读取库存', '读取库存上限'),
        ]
        for left, right in pairs:
            with self.subTest(left=left, right=right):
                self.assertNotEqual(normalized_label(left), normalized_label(right))

    def test_group_name_may_appear_at_most_three_times_per_body(self):
        blocks = {f'bb{i}': block(i, 'Return', []) for i in range(4)}
        nodes = {}
        parents = {}
        for i in range(4):
            action_id = f'A{i}'
            group_id = f'{action_id}/C{i}'
            nodes[action_id] = node(action_id, 'action', [group_id], name=f'动作{i}')
            nodes[group_id] = node(group_id, 'bb_group', [f'bb{i}'],
                                   name='提交结果', evidence=[f'bb{i}'])
            nodes[group_id]['children'] = [f'bb{i}']
            parents[group_id] = action_id
        with self.assertRaisesRegex(ValueError, 'more than three times in body'):
            validate_reading_groups(nodes, parents, blocks)

    def test_basic_block_order_is_generated_from_edges(self):
        blocks = self.blocks(3)
        ledger = business_ledger(('bb0', 'bb2', 'bb1'))
        ledger['nodes'][-1]['basic_block_order'] = ['bb2', 'bb1', 'bb0']
        nodes, _ = ownership(ledger, blocks, [edge(0, 1), edge(1, 2)],
                             {'basic_blocks': list(blocks.values())})
        self.assertEqual(nodes['P01/A01.0/C0']['basic_block_order'], ['bb0', 'bb1', 'bb2'])


if __name__ == '__main__':
    unittest.main()
