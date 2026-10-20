import sys
from pathlib import Path as _PackagePath
sys.path.insert(0, str(_PackagePath(__file__).resolve().parents[1] / 'scripts'))

import unittest
from copy import deepcopy
from goal_contracts import partition_actions, contract_violations
from technical_boundary import apply_review, fingerprint

class GoalContractsTest(unittest.TestCase):
    def test_recovery_boundary_and_cohesive_members(self):
        actions=[dict(key='a',phase='p'),dict(key='b',phase='p')]
        contracts={'verify':dict(entryMode='normal'),'retry':dict(entryMode='recovery')}
        assignments={'a':dict(contractRef='verify'),'b':dict(contractRef='retry')}
        self.assertEqual(len(partition_actions(actions,contracts,assignments)),2)
        assignments['b']['contractRef']='verify'
        self.assertEqual(len(partition_actions(actions,contracts,assignments)),1)

    def test_nonadjacent_reuse_rejected(self):
        with self.assertRaises(ValueError):
            partition_actions([dict(key=k,phase='p') for k in 'abc'], {'x':dict(entryMode='normal'),'y':dict(entryMode='normal')}, {k:dict(contractRef=v) for k,v in zip('abc','xyx')})

    def test_mixed_contract_and_incomplete_members_rejected(self):
        r=dict(contractRef='x',entryMode='normal',completion='accepted',cohesionReason='one request',evidenceRefs=['bb1'],memberContracts=[dict(actionRef='a',contractRef='x',entryMode='normal',evidenceRefs=['bb1'])])
        self.assertEqual(contract_violations(r,['a']),[])
        self.assertTrue(contract_violations(r,['a','b']))
        r['memberContracts'][0]['entryMode']='recovery'
        self.assertTrue(contract_violations(r,['a']))

    def test_technical_witness_is_complete_and_pinned(self):
        b=dict(statements=[],terminator=dict(kind='Drop'))
        r=dict(bbRef='bb1',factSha256=fingerprint(b),category='drop',reason='reviewed temporary destruction',evidenceRefs=['bb1'],operationProofs=[],terminatorProof='no business effect')
        owner={'bb1':'a'};technical={}
        apply_review({'bb1':b},owner,technical,[r])
        self.assertEqual(owner,{})
        self.assertIn('bb1',technical)
        stale=deepcopy(b);stale['terminator']['kind']='Call'
        with self.assertRaises(ValueError):apply_review({'bb1':stale},{},{},[r])

    def test_return_value_assignment_is_never_exempted(self):
        b=dict(statements=[dict(statement_index=0,kind='Assign',detail=dict(rvalue=dict(kind='Aggregate')))],terminator=dict(kind='Drop'))
        r=dict(bbRef='bb1',factSha256=fingerprint(b),category='drop',reason='invalid exemption',evidenceRefs=['bb1'],operationProofs=[dict(statementIndex=0,reason='invalid')],terminatorProof='drop')
        with self.assertRaises(ValueError):apply_review({'bb1':b},{},{},[r])

if __name__=='__main__':unittest.main()
