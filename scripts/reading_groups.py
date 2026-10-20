"""Mechanical floor for authored reading increments; never infer group boundaries."""
from collections import Counter
import unicodedata
import re


def normalized_label(value):
    text = unicodedata.normalize('NFKC', value).casefold()
    text = re.sub(r'\s*(?:\(\s*\d+\s*\)|\[\s*\d+\s*\]|#\s*\d+)\s*$', '', text)
    suffix = re.search(r'(?P<base>.*?)(?P<separator>[^\w]|_)(?:\d+\s*号|\d+)\s*$', text)
    if suffix and not suffix.group('base').rstrip().endswith('第'):
        text = suffix.group('base')
    return ''.join(c for c in text if not c.isspace() and not unicodedata.category(c).startswith('P'))


def validate_reading_groups(nodes, parents, blocks):
    body_name_counts = Counter(
        normalized_label(node['name'])
        for node in nodes.values()
        if node['kind'] == 'bb_group'
    )
    overused = sorted(label for label, count in body_name_counts.items() if count > 3)
    if overused:
        raise ValueError('Reading group label appears more than three times in body: ' + overused[0])

    sibling_names = {}
    for key, node in nodes.items():
        if node['kind'] != 'bb_group':
            continue
        parent = nodes.get(parents.get(key), {})
        group_label = normalized_label(node['name'])
        if parent.get('kind') == 'action':
            siblings = sibling_names.setdefault(parent['id'], set())
            if group_label in siblings:
                raise ValueError('Sibling reading groups repeat normalized label: ' + key)
            siblings.add(group_label)
        if parent.get('kind') == 'root':
            continue  # ROOT technical policy remains independent of reading semantics.
        parent_label = normalized_label(parent.get('name', ''))
        if parent_label and parent_label in group_label:
            raise ValueError('Reading group repeats parent label: ' + key)
        evidence = node.get('evidence')
        members = set(node.get('basic_block_refs', node.get('children', [])))
        if (not isinstance(evidence, list) or not evidence
                or any(not isinstance(ref, str) or ref not in blocks or ref not in members for ref in evidence)):
            raise ValueError('Reading group evidence must identify real member BB facts: ' + key)


def review(c):
    hierarchy = c.load('stage2/hierarchy.json')
    nodes = hierarchy['nodes']
    parents = {key: node.get('reading_parent') for key, node in nodes.items()}
    validate_reading_groups(nodes, parents, c.load('facts/blocks.json'))
