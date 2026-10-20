import sys
from pathlib import Path as _PackagePath
sys.path.insert(0, str(_PackagePath(__file__).resolve().parents[1] / 'scripts'))

import unittest

from hard_rules import validate


def goal(identity, actions, **extra):
    return dict(id=identity, actions=[{'id': x} for x in actions], **extra)


class HardRulesTest(unittest.TestCase):
    def test_prelude_same_source_with_different_bbs_requires_distinction(self):
        first = {'id': 'p1', 'label': '一',
                 'lineRanges': [{'startLine': 1, 'endLine': 1}],
                 'basicBlockRefs': ['shell:bb0']}
        second = dict(first, id='p2', label='二', basicBlockRefs=['shell:bb7'])
        data = {'prelude': {'nodes': [first, second]}, 'phases': []}
        self.assertEqual(validate(data)['errors'][0]['code'], 'readability.preludeDistinct')
        data['prelude']['nodes'][0]['distinctionReason'] = '负责装配'
        data['prelude']['nodes'][1]['distinctionReason'] = '负责调用'
        self.assertTrue(validate(data)['valid'])

    def test_prelude_different_source_ranges_are_distinct(self):
        first = {'id': 'p1', 'label': '一',
                 'lineRanges': [{'startLine': 1, 'endLine': 1}],
                 'basicBlockRefs': ['shell:bb0']}
        second = {'id': 'p2', 'label': '二',
                  'lineRanges': [{'startLine': 2, 'endLine': 2}],
                  'basicBlockRefs': ['shell:bb0']}
        data = {'prelude': {'nodes': [first, second]}, 'phases': []}
        self.assertTrue(validate(data)['valid'])

    def test_goal_merge_reason_accepts_renderer_or_contract_statement(self):
        renderer_reason = {'phases': [{'goals': [
            goal('g1', ['a', 'b'], mergeReason='共同完成提交')]}]}
        self.assertTrue(validate(renderer_reason)['valid'])

        contract_reason = {'phases': [{'goals': [goal('g1', ['a', 'b'])]}]}
        ledger = {'goalContracts': [{'goalRef': 'g1', 'cohesionReason': '共同完成提交'}]}
        self.assertTrue(validate(contract_reason, ledger)['valid'])

    def test_goal_merge_reason_fails_when_both_stated_fields_are_missing(self):
        data = {'phases': [{'goals': [goal('g1', ['a', 'b'], splitReason='不是合组理由')]}]}
        ledger = {'goalContracts': [{'goalRef': 'g1', 'completion': '提交完成'}]}
        self.assertEqual([e['code'] for e in validate(data, ledger)['errors']],
                         ['readability.goalMergeReason'])

    def test_goal_split_reason_is_renderer_field_only(self):
        data = {'phases': [{'id': 'phase', 'goals': [goal('g1', ['a']), goal('g2', ['b'])]}]}
        ledger = {'goalContracts': [
            {'goalRef': 'g1', 'contractRef': 'done', 'entryMode': 'normal',
             'cohesionReason': '先准备'},
            {'goalRef': 'g2', 'contractRef': 'done', 'entryMode': 'normal',
             'cohesionReason': '后确认'}]}
        self.assertEqual({e['code'] for e in validate(data, ledger)['errors']},
                         {'readability.goalSplitReason'})
        data['phases'][0]['goals'][0]['splitReason'] = '先准备'
        data['phases'][0]['goals'][1]['splitReason'] = '后确认'
        self.assertTrue(validate(data, ledger)['valid'])

    def test_singletons_without_shared_contract_do_not_trigger(self):
        data = {'phases': [{'goals': [goal('g1', ['a']), goal('g2', ['b'])]}]}
        ledger = {'goalContracts': [
            {'goalRef': 'g1', 'contractRef': 'x', 'entryMode': 'normal'},
            {'goalRef': 'g2', 'contractRef': 'y', 'entryMode': 'normal'}]}
        self.assertTrue(validate(data, ledger)['valid'])


if __name__ == '__main__':
    unittest.main()
