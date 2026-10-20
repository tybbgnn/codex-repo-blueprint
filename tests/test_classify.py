"""Classification-stage contracts with synthetic MIR only."""
import sys
from pathlib import Path as _PackagePath
sys.path.insert(0, str(_PackagePath(__file__).resolve().parents[1] / 'scripts'))

import copy
import unittest

import classify
from instrumentation_wrapper import prove_async


def async_span_fixture():
    generated = {'file': 'lib.rs', 'start_line': 1, 'end_line': 1,
                 'start_column': 1, 'end_column': 20, 'from_expansion': True}
    direct = {'file': 'lib.rs', 'start_line': 3, 'end_line': 3}

    def call(item, destination, target, span):
        return {'kind': 'Call', 'source_info': {'span': span}, 'successors': [target],
                'detail': {'func': {'kind': 'Constant', 'detail': {'constant': {
                    'type': {'kind': 'FnDef', 'display': 'fn() {' + item + '}'}}}},
                    'destination': {'local': destination, 'projection': []},
                    'args': [], 'target': target}}

    return {'arg_count': 0, 'is_coroutine': True, 'debug_variables': [],
            'locals': [{'local': 0, 'type': {'display': 'usize'}},
                       {'local': 1, 'type': {'display': 'tracing::Span'}}],
            'basic_blocks': [
                {'basic_block': 0, 'statements': [],
                 'terminator': call('tracing::Span::new', 1, 1, generated)},
                {'basic_block': 1, 'statements': [],
                 'terminator': call('example::compute', 0, 2, direct)},
                {'basic_block': 2, 'statements': [],
                 'terminator': {'kind': 'Return', 'detail': {}, 'successors': []}}]}


class ClassifyTests(unittest.TestCase):
    def test_async_span_proof_positive_and_negative(self):
        raw = async_span_fixture()
        proof = prove_async(raw)
        self.assertEqual(proof['kind'], 'async_instrumentation')
        self.assertIn('bb0', proof['technical_blocks'])
        broken = copy.deepcopy(raw)
        broken['basic_blocks'][0]['terminator']['detail']['func']['detail']['constant']['type']['display'] = 'fn() {example::side_effect}'
        self.assertIsNone(prove_async(broken))

    def test_body_and_block_roles(self):
        self.assertEqual(classify.classify_body(), {'kind': 'direct', 'executionForm': 'sync',
                         'mappingMode': None, 'status': 'verified', 'relation': None})
        for mode in classify.POLICY['roles']['body']['mappingModes']:
            self.assertEqual(classify.classify_body(mode)['kind'], 'async-shell')
        self.assertEqual(classify.POLICY['roles']['body']['mappingModes'],
                         ['strict-forward', 'retained-relation'])
        expected = {
            None: 'business', 'cleanup': 'compiler_artifact', 'unwind': 'compiler_artifact',
            'drop': 'compiler_artifact', 'state_dispatch': 'compiler_artifact',
            'async_mechanism': 'async_protocol', 'instrumentation': 'span_wrapper'}
        for category, role in expected.items():
            with self.subTest(category=category):
                self.assertEqual(classify.classify_block(category)['kind'], role)
        self.assertEqual(classify.prove_instrumentation(async_span_fixture())['kind'], 'async_instrumentation')

    def test_registered_loop_exit_modes(self):
        roles = classify.POLICY['roles']
        self.assertIn('event_macro', roles['block']['kinds'])
        self.assertIn('routing', roles['block']['kinds'])
        self.assertEqual(roles['attributes']['loop.exitMode']['consumers']['terminalOnly'], ['P11', 'renderer_contract'])
        self.assertEqual(classify.classify_loop({'commonAfter': {'actionRef': 'a'}})['exitMode'], 'commonAfter')
        self.assertIsNone(classify.classify_loop({})['exitMode'])
        scope={'id':'loop','terminalOnly':{'proofRef':'proof','terminalNodeRefs':['done'],'exitEdgeRefs':['exit']}}
        cert={'certificateKind':'terminal-loop','version':1,'scopeId':'loop','rawSha256':'a'*64,
              'memberBBs':['bb0'],'exitEdges':[{'from':'bb0','to':'bb1'}],
              'terminalBBs':['bb1'],'blocks':[{'bb':1}]}
        self.assertEqual(classify.classify_loop(scope, cert)['exitMode'], 'terminalOnly')
        self.assertIsNone(classify.classify_loop({**scope,'id':'other'}, cert)['exitMode'])


if __name__ == '__main__':
    unittest.main()
