import sys
from pathlib import Path as _PackagePath
sys.path.insert(0, str(_PackagePath(__file__).resolve().parents[1] / 'scripts'))

import unittest
from check_principles import Audit


class AlternativeGuardTests(unittest.TestCase):
    def fixture(self):
        a = object.__new__(Audit)
        a.controls = []; a.attached = set(); a.control_by_id = {}; a.messages = []
        a.actions = [{'id': 'v1'}, {'id': 'v2'}]; a.goals = []; a.phases = []
        a.units = [(n, 'action') for n in a.actions]
        a.execution = {'decisions': [{'id': 'version', 'values': ['v1', 'v2'], 'readingScopeRef': 'versions'}]}
        members = lambda ref: [{'kind': 'action', 'ref': ref}]
        a.scopes = {'versions': {'id': 'versions', 'kind': 'alt', 'condition': '版本选择', 'members': members('v1') + members('v2'), 'branches': [{'id': 'branch-v1', 'when': ['v1'], 'condition': '版本一', 'members': members('v1')}, {'id': 'branch-v2', 'when': ['v2'], 'condition': '版本二', 'members': members('v2')}]}}
        a.granularity = {'memberGuards': [{'memberActionRefs': ['v1'], 'decisionRef': 'version', 'takeValues': ['v1'], 'skipValues': ['v2'], 'condition': '版本一', 'skip': '选择版本二', 'readingScopeRef': 'versions', 'alternativeBranchRef': 'branch-v1', 'evidenceRefs': ['bb0'], 'bypassEvidenceRefs': ['bb1']}]}
        a.details = {'blocks': {'bb0': {}, 'bb1': {}}}; a.exec_edges = {}; a.fact_edges = []; a.calls = []
        a.checks = []; a.reviews = []
        # This fixture tests mechanical guard coverage; agent decisions are tested separately.
        a.review = lambda *args, **kwargs: None
        return a

    def failures(self, a):
        a.check_g5()
        return [c for c in a.checks if c['status'] == 'fail']

    def test_exhaustive_alternatives_need_no_duplicate_opt(self):
        self.assertEqual(self.failures(self.fixture()), [])

    def test_missing_or_overlapping_domain_rejects_exemption(self):
        for values in ([], ['v1'], ['unknown']):
            a = self.fixture(); a.scopes['versions']['branches'][1]['when'] = values
            self.assertTrue(self.failures(a))

    def test_empty_bypass_is_still_optional_and_needs_opt(self):
        a = self.fixture(); a.scopes['versions']['branches'][1]['members'] = []
        self.assertTrue(self.failures(a))

    def test_wrong_member_or_duplicate_member_rejects_exemption(self):
        a = self.fixture(); a.granularity['memberGuards'][0]['memberActionRefs'] = ['v2']
        self.assertTrue(self.failures(a))
        a = self.fixture(); a.scopes['versions']['branches'][1]['members'] = [{'kind': 'action', 'ref': 'v1'}]
        self.assertTrue(self.failures(a))

    def test_plain_alt_cannot_silently_exempt_optional_guard(self):
        a = self.fixture(); del a.granularity['memberGuards'][0]['alternativeBranchRef']
        self.assertTrue(self.failures(a))

    def test_canonicalization_retains_alternative_without_inventing_opt(self):
        import copy
        from canonicalize_controls import canonicalize
        a = self.fixture()
        presentation = {'controls': [], 'ownerControls': {}, 'controlEvidence': {}, 'readingScopes': list(a.scopes.values()), 'decisions': a.execution['decisions']}
        before = copy.deepcopy(presentation)
        self.assertEqual(canonicalize(presentation, a.granularity['memberGuards'], {}), before)
