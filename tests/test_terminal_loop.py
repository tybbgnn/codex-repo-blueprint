"""Terminal-only loop generator and independent-verifier proofs."""
import sys
from pathlib import Path as _PackagePath
sys.path.insert(0, str(_PackagePath(__file__).resolve().parents[1] / 'scripts'))

import copy
import hashlib
import json
import unittest

import classify
from check_principles import Audit
from verify_source_evidence import verify


def place(local): return {'local': local, 'projection': []}


def constant(bit='0'):
    return {'kind': 'Constant', 'detail': {'constant': {'type': {'kind': 'Bool'},
            'value': {'kind': 'ScalarInt', 'detail': {'bits': bit}}}}}


def assign(local, operand=None):
    return {'kind': 'Assign', 'detail': {'destination': place(local),
            'rvalue': {'kind': 'Use', 'detail': {'operand': operand or constant()}}}}


def terminator(kind, successors=(), **detail):
    return {'kind': kind, 'detail': detail, 'successors': list(successors)}


def raw_fixture():
    return {'arg_count': 0, 'is_coroutine': False, 'debug_variables': [],
            'locals': [
                {'local': 0, 'type': {'kind': 'Tuple', 'detail': {'elements': []}, 'display': '()'}},
                {'local': 1, 'type': {'kind': 'Bool', 'display': 'bool'}},
                {'local': 2, 'type': {'kind': 'Adt', 'display': 'std::string::String'}},
                {'local': 3, 'type': {'kind': 'Bool', 'display': 'bool'}},
            ], 'basic_blocks': [
                {'basic_block': 0, 'is_cleanup': False, 'statements': [],
                 'terminator': terminator('SwitchInt', [0, 1], discriminant={'kind': 'Constant'}, targets=[{'target': 0}], otherwise=1)},
                {'basic_block': 1, 'is_cleanup': False,
                 'statements': [assign(1, constant('0')), assign(1, constant('1')), assign(3)],
                 'terminator': terminator('Goto', [2], target=2)},
                {'basic_block': 2, 'is_cleanup': False, 'statements': [],
                 'terminator': terminator('SwitchInt', [3, 4], discriminant={'kind': 'Copy', 'detail': {'place': place(1)}}, targets=[{'target': 3}], otherwise=4)},
                {'basic_block': 3, 'is_cleanup': False, 'statements': [],
                 'terminator': terminator('Drop', [4], place=place(2), target=4)},
                {'basic_block': 4, 'is_cleanup': False, 'statements': [assign(0)],
                 'terminator': terminator('Return')},
            ]}


def base(raw=None):
    raw=raw or raw_fixture(); content=json.dumps(raw, sort_keys=True, separators=(',', ':'))
    mir={'id': 'mir', 'sourcePath': 'raw-body.json', 'format': 'mir',
         'sha256': hashlib.sha256(content.encode()).hexdigest(), 'content': content}
    scope={'id': 'loop', 'kind': 'loop', 'condition': 'more',
           'members': [{'kind': 'action', 'ref': 'a'}], 'parentScopeRef': None,
           'decision': {'variable': 'more', 'values': ['yes','no']},
           'repeat': {'entryActionRef': 'a', 'continueValues': ['yes'], 'exitValues': ['no'],
                      'continue': 'again', 'exit': 'done', 'limit': 'input'}}
    data={'functionSource': {'file': 'lib.rs', 'definitionRef': 'f', 'sourcePath': 'lib.rs',
                            'startLine': 1, 'endLine': 1, 'lines': ['fn f() {}']},
          'phases': [{'id': 'p', 'goals': [{'id': 'g', 'actions': [{'id': 'a', 'basicBlockRefs': ['bb0']}]}]}],
          'readingScopes': [scope], 'execution': {'artifacts': [mir], 'nodes': [], 'evidence': [], 'edges': []}}
    return data,scope


def attach(data, scope, certificate):
    content=json.dumps(certificate, sort_keys=True, separators=(',', ':'))
    data['execution']['artifacts'].append({'id': 'proof', 'sourcePath': 'terminal-loop-proof.json',
        'format': 'icfg', 'sha256': hashlib.sha256(content.encode()).hexdigest(), 'content': content})
    scope['terminalOnly']={'proofRef':'proof','terminalNodeRefs':['terminal'],'exitEdgeRefs':['exit']}
    data['execution']['nodes']=[{'id':'member','kind':'action','actionRef':'a'},
        {'id':'terminal','kind':'terminal','outcome':'return','basicBlockRefs':certificate['terminalBBs']}]
    data['execution']['edges']=[{'id':'exit','from':'member','to':'terminal','kind':'loop-exit','readingScopeRef':'loop'}]


def decision_exit(data, bb='bb0', listed=True, terminal=True):
    data['execution']['nodes'].insert(1, {'id':'choice','kind':'decision','decisionRef':'more','basicBlockRefs':[bb]})
    data['execution']['edges']=[
        {'id':'arrive','from':'member','to':'choice','kind':'flow','guards':[{'decisionRef':'more','value':'none'}]},
        {'id':'exit','from':'choice','to':'terminal','kind':'loop-exit','readingScopeRef':'loop','guards':[{'decisionRef':'more','value':'none'}]}]
    if not listed: data['readingScopes'][0]['terminalOnly']['exitEdgeRefs']=[]
    if not terminal: data['execution']['nodes'][-1]={'id':'terminal','kind':'action','actionRef':'a'}


def p11_failures(data, raw):
    data=copy.deepcopy(data)
    data['execution']['edges'].append({'id':'back','from':'member','to':'member','kind':'loop-continue',
        'readingScopeRef':'loop','evidenceRefs':['proof']})
    for edge in data['execution']['edges']: edge.setdefault('evidenceRefs',['proof'])
    audit=object.__new__(Audit); audit.data=data; audit.execution=data['execution']
    audit.exec_nodes={n['id']:n for n in data['execution']['nodes']}; audit.exec_edges={e['id']:e for e in data['execution']['edges']}
    audit.scopes={s['id']:s for s in data['readingScopes']}; audit.phases=data['phases']; audit.actions=[a for p in data['phases'] for g in p['goals'] for a in g['actions']]
    audit.units=[(p,'phase') for p in data['phases']]+[(g,'goal') for p in data['phases'] for g in p['goals']]+[(a,'action') for a in audit.actions]
    audit.checks=[]; audit.reviews=[]; audit.read=lambda name,required=False: raw if name == 'raw-body.json' else None
    audit.check_p11()
    return audit.checks[-1]['evidence']['failure_count']


class TerminalLoopTests(unittest.TestCase):
    def assert_both_reject_raw(self, mutate):
        raw=raw_fixture(); data,scope=base(raw); cert=classify.prove_terminal_loop(raw,scope,data); self.assertIsNotNone(cert)
        broken=copy.deepcopy(raw); mutate(broken)
        broken_data,broken_scope=base(broken)
        self.assertIsNone(classify.prove_terminal_loop(broken,broken_scope,broken_data))
        attach(broken_data,broken_scope,cert)
        self.assertTrue(any(x['code'].startswith('terminal-loop') for x in verify(broken_data,broken)))

    def test_positive_storage_drop_flag_dead_temp_and_drop(self):
        raw=raw_fixture(); data,scope=base(raw); cert=classify.prove_terminal_loop(raw,scope,data)
        self.assertIsNotNone(cert); attach(data,scope,cert)
        self.assertEqual(classify.classify_loop(scope,cert)['exitMode'],'terminalOnly')
        self.assertEqual([x for x in verify(data,raw) if x['code'].startswith('terminal-loop')],[])
        data['phases'][0]['goals'][0]['actions'][0]['basicBlockRefs']=['shell:bb0']
        self.assertTrue(any(x['code']=='terminal-loop-bb-namespace' for x in verify(data,raw)))

    def test_decision_sourced_exit_and_boundary_negatives(self):
        raw=raw_fixture(); data,scope=base(raw); cert=classify.prove_terminal_loop(raw,scope,data); attach(data,scope,cert)
        decision_exit(data)
        self.assertEqual([x for x in verify(data,raw) if x['code'].startswith('terminal-loop')],[])
        self.assertEqual(p11_failures(data,raw),0)
        for change,code in [
                (lambda d: d['execution']['nodes'][1].update(basicBlockRefs=['bb9']), 'terminal-loop-execution-edge'),
                (lambda d: d['readingScopes'][0]['terminalOnly'].update(exitEdgeRefs=[]), 'terminal-loop-exit-coverage'),
                (lambda d: d['execution']['nodes'][-1].update(kind='action', actionRef='a'), 'terminal-loop-execution-edge')]:
            broken=copy.deepcopy(data); change(broken)
            self.assertTrue(any(x['code'] == code for x in verify(broken,raw)), code)
            self.assertGreater(p11_failures(broken,raw),0,code)

    def test_rejects_yield_or_pending_suspension(self):
        self.assert_both_reject_raw(lambda raw: raw['basic_blocks'][4].update(terminator=terminator('Yield', [0], resume=0)))

    def test_rejects_non_allowlisted_drop(self):
        def mutate(raw): raw['locals'][2]['type']['display']='app::SideEffecting'
        self.assert_both_reject_raw(mutate)

    def test_rejects_business_call(self):
        self.assert_both_reject_raw(lambda raw: raw['basic_blocks'][4].update(terminator=terminator('Call', [5], target=5)))

    def test_scope_binding_and_forgery_are_rejected(self):
        raw=raw_fixture(); data,scope=base(raw); cert=classify.prove_terminal_loop(raw,scope,data)
        wrong={**cert,'scopeId':'another-loop'}
        self.assertIsNone(classify.classify_loop(scope,wrong)['exitMode'])
        attach(data,scope,wrong)
        self.assertTrue(any(x.get('field')=='scopeId' for x in verify(data,raw)))
        data,scope=base(raw); forged=copy.deepcopy(cert); forged['blocks'][0]['operations'][0]['reason']='invented'
        attach(data,scope,forged)
        self.assertTrue(any(x.get('field')=='blocks' for x in verify(data,raw)))


if __name__ == '__main__': unittest.main()
