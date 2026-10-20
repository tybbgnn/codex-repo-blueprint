"""Validate explicit, source-reviewed mechanism witnesses before BB reassignment.

A fingerprint and complete operation proof prevent stale or partial exemptions.
This checks evidence integrity, not whether destructors have business effects.
"""
from classification_registry import fingerprint, instrumentation_record_valid


def apply_review(blocks, owners, technical, records, raw=None, event_macro_artifacts=None):
    for record in records:
        bid = record['bbRef']
        block = blocks[bid]
        if fingerprint(block) != record['factSha256']:
            raise ValueError('Stale technical witness: ' + bid)
        if record.get('category') == 'instrumentation':
            if not instrumentation_record_valid(raw or {}, block, record, event_macro_artifacts):
                raise ValueError('Unproven instrumentation: ' + bid)
            technical[bid] = dict(record)
            owners.pop(bid, None)
            continue
        if not record.get('reason') or not record.get('evidenceRefs') or record.get('category') != 'drop':
            raise ValueError('Missing technical boundary evidence: ' + bid)
        operations = {s['statement_index'] for s in block['statements'] if s['kind'] not in ('StorageLive', 'StorageDead')}
        proofs = record.get('operationProofs', [])
        if {p['statementIndex'] for p in proofs} != operations or len(proofs) != len(operations) or any(not p.get('reason') for p in proofs):
            raise ValueError('Incomplete operation proof: ' + bid)
        if block['terminator']['kind'] not in ('Drop', 'Goto', 'SwitchInt') or not record.get('terminatorProof'):
            raise ValueError('Unproven routing/destruction: ' + bid)
        for statement in block['statements']:
            if statement['kind'] in ('StorageLive', 'StorageDead'):
                continue
            rv = statement.get('detail', {}).get('rvalue', {})
            operand = rv.get('detail', {}).get('operand', {})
            constant = operand.get('detail', {}).get('constant', {})
            flag = rv.get('kind') == 'Use' and operand.get('kind') == 'Constant' and constant.get('type', {}).get('kind') == 'Bool'
            selector = rv.get('kind') == 'Discriminant' and block['terminator']['kind'] == 'SwitchInt'
            if statement['kind'] != 'Assign' or not (flag or selector):
                raise ValueError('Potential business effect needs a stronger proof: ' + bid)
        technical[bid] = dict(record)
        owners.pop(bid, None)
