#!/usr/bin/env python3
"""Check the machine-readable rule index against every executable rule family."""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import re
import sys

SCHEMA_KEYS = {'type', 'required', 'additionalProperties', 'enum', 'const', 'pattern',
               'minLength', 'minItems', 'maxItems', 'uniqueItems', 'minimum',
               'anyOf', 'oneOf', 'not', 'allOf', 'dependentRequired'}
SOURCE_FAMILIES = {
    'source.function', 'source.idCollision', 'source.bbNamespace', 'source.mappingPresence',
    'source.canonicalRanges', 'source.broadRangeReason', 'source.regeneration',
    'source.groupCoverage', 'source.nodeRegeneration'}
STAGE_GATES = {'stage.resolve', 'stage.batchPreflight', 'stage.prepare'} | {f'stage.{n}' for n in range(9)} | {'stage.failStop'}
FILE_PROTOCOL_CHECKS = {
    'page.safeLocalPath', 'page.phaseRenders', 'page.fullSource', 'page.exactEmbeddedData',
    'page.selectableGoal', 'page.sourceHighlight', 'page.bbExpansion', 'page.sameProtocol',
    'page.localFilesExist', 'page.http200', 'page.noJsonFetch', 'page.noBrowserErrors'}
PLACEHOLDER_PHRASES = {
    'Condition': 'The named executable predicate at',
    'Stage': 'Stage 7 unless',
    'Required producer fields': 'The fields read by the enforcing predicate',
}
RULE_TRIGGERED_EXAMPLES = ({'ruleTriggered': False}, {'ruleTriggered': True})
CONCRETE_FIELDS = ('Required producer fields', 'Pass example', 'Fail example')
META_EXAMPLE_PHRASES = (
    'satisfies', 'violates', 'exactly as', 'described by',
    'the stated', 'the same assertion',
)


def slug(text):
    value = re.sub(r'[^a-zA-Z0-9]+', '.', text).strip('.').lower()
    return value[:80]


def add(found, rule, source):
    if rule:
        found[rule].add(source)


def at(path, text, offset, root):
    try:
        label = path.relative_to(root).as_posix()
    except ValueError:
        label = path.name
    return f'{label}:{text.count(chr(10), 0, offset) + 1}'


def inventory(root, contract_override=None):
    found = defaultdict(set)
    renderer = root / 'assets/renderer'
    scripts = root / 'scripts'
    for path in (Path(contract_override) if contract_override else renderer / 'contract.mjs', renderer / 'execution.mjs'):
        text = path.read_text()
        for match in re.finditer(r"\bfail\(\s*['\"]([^'\"]+)['\"]", text):
            add(found, match.group(1), at(path, text, match.start(), root))
    schema = json.loads((renderer / 'renderer-input.schema.json').read_text())
    def scan(value):
        if isinstance(value, dict):
            for key, child in value.items():
                if key in SCHEMA_KEYS:
                    add(found, 'shape.' + key, 'assets/renderer/renderer-input.schema.json:1')
                scan(child)
        elif isinstance(value, list):
            for child in value: scan(child)
    scan(schema)
    principles = (scripts / 'check_principles.py').read_text()
    principle_path = scripts / 'check_principles.py'
    for match in re.finditer(r"self\.result\(\s*['\"]([PG]\d+)['\"]\s*,\s*['\"]([^'\"]+)['\"]", principles):
        add(found, match.group(1) + '.' + match.group(2), at(principle_path, principles, match.start(), root))
    for name in ('async_mechanism','low_level_identifier','evidence_as_content','code_condition'):
        add(found,'P7.'+name,'scripts/check_principles.py:'+str(principles[:principles.index("self.result('P7', category")].count('\n')+1))
    for p in ('P6',):
        add(found, p + '.invocation_pair_integrity', 'scripts/check_principles.py:389')
    for category in ('C1', 'C2', 'C3', 'C4', 'C5', 'C6'):
        add(found, 'P7.duplicates_' + category, 'scripts/check_principles.py:394')
    duplicate_text = (scripts / 'audit_duplicates.py').read_text()
    duplicate_path = scripts / 'audit_duplicates.py'
    for match in re.finditer(r"add\(\s*['\"](C\d+)['\"]\s*,\s*['\"]([^'\"]+)['\"]", duplicate_text):
        add(found, match.group(1) + '.' + match.group(2), at(duplicate_path, duplicate_text, match.start(), root))
    for path in sorted(scripts.glob('*verifier.py')) + [scripts / 'verify_source_evidence.py', scripts / 'hard_rules.py']:
        text = path.read_text()
        for match in re.finditer(r"['\"]code['\"]\s*:\s*['\"]([^'\"]+)['\"]|\bcode\s*=\s*['\"]([^'\"]+)['\"]", text):
            add(found, match.group(1) or match.group(2), at(path, text, match.start(), root))
        if path.name == 'async_shell_verifier.py':
            add(found, 'invalid-inner-mir', 'scripts/async_shell_verifier.py:479')
            add(found, 'invalid-shell-mir', 'scripts/async_shell_verifier.py:479')
    for path in sorted((root / 'tests').glob('test_*.cjs')):
        page_text = path.read_text()
        for match in re.finditer(r"\bcheck\(\s*['\"]([^'\"]+)['\"]", page_text):
            add(found, 'page.' + slug(match.group(1)), at(path, page_text, match.start(), root))
    for name in FILE_PROTOCOL_CHECKS:
        add(found, name, 'tests/test_file_protocol.cjs:13')
    for name in SOURCE_FAMILIES:
        add(found, name, 'scripts/source_ranges.py:654')
    for path, prefix in ((scripts / 'publish_site.py', 'publish'), (scripts / 'output_paths.py', 'output')):
        precondition_text = path.read_text()
        for match in re.finditer(r"raise ValueError\((?:f)?['\"]([^'\"]+)", precondition_text):
            add(found, prefix + '.' + slug(match.group(1)), at(path, precondition_text, match.start(), root))
    for name in STAGE_GATES:
        add(found, name, 'SKILL.md:260')
    add(found, 'publish.tokens', 'SKILL.md:611')
    return {key: sorted(value) for key, value in sorted(found.items())}


def parse_index(path):
    entries, duplicates = {}, []
    current = None
    for line_no, line in enumerate(path.read_text().splitlines(), 1):
        match = re.match(r'^###\s+(\S+)\s*$', line)
        if match:
            current = match.group(1)
            if current in entries:
                duplicates.append(current)
            entries.setdefault(current, {'line': line_no})
        elif current and (field := re.match(r'^([A-Za-z ]+):\s*(.*)$', line)):
            entries[current][field.group(1).strip()] = field.group(2).strip()
    return entries, duplicates


def parsed_example(value):
    text = value.strip().strip('`').strip()
    try:
        return json.loads(text)
    except (TypeError, ValueError):
        return text


def normalized_entry_text(canonical, entry, field):
    """Remove an entry's IDs before comparing supposedly concrete prose."""
    aliases = [x.strip() for x in entry.get('Aliases', '').split(',')
               if x.strip() and x.strip() != '-']
    value = entry.get(field, '')
    for identity in sorted({canonical, *aliases}, key=len, reverse=True):
        value = re.sub(re.escape(identity), '<RULE_ID>', value, flags=re.IGNORECASE)
    return ' '.join(value.split()).casefold()


def merged_canonical(rule):
    if rule in {'P14.source_coverage_at_most_25_percent_or_reason'}:
        return 'source.broadRangeReason'
    if rule in {'P6.invocation_pair_integrity', 'P9.invocation_pair_integrity'} or rule.startswith('pair.'):
        return 'pair.integrity'
    if rule.startswith('P7.duplicates_C'):
        return rule.split('_')[-1] + '.duplicateAudit'
    if rule in {'C3.same_endpoint_label', 'C6.same_endpoint_label_edges'}:
        return 'C.endpointLabel'
    if rule in {'page.full.function.rows', 'page.full.function.preserved', 'page.fullSource'}:
        return 'page.fullSource'
    if rule in {'id.duplicate', 'source.idCollision'}:
        return 'id.unique'
    if rule.startswith('stage.'):
        return 'stage.gates'
    if rule.startswith('publish.unresolved.presentation.placeholders'):
        return 'publish.tokens'
    return rule


def check(root, index_path, contract_override=None):
    raw = inventory(root, contract_override)
    expected = defaultdict(set)
    for rule, sources in raw.items():
        expected[merged_canonical(rule)].add(rule)
    entries, duplicates = parse_index(index_path)
    alias_owner = {}
    errors = [f'duplicate entry: {x}' for x in sorted(set(duplicates))]
    normalized_fields = {field: defaultdict(list) for field in CONCRETE_FIELDS}
    for canonical, entry in entries.items():
        for alias in [x.strip() for x in entry.get('Aliases', '').split(',') if x.strip() and x.strip() != '-']:
            if alias in alias_owner:
                errors.append(f'duplicate alias: {alias}')
            alias_owner[alias] = canonical
        for field in ('Enforced', 'Condition', 'Stage', 'Required producer fields', 'Pass example', 'Fail example'):
            if not entry.get(field):
                errors.append(f'{canonical}: missing {field}')
        for field, phrase in PLACEHOLDER_PHRASES.items():
            if phrase in entry.get(field, ''):
                errors.append(f'{canonical}: placeholder {field}')
        passed = parsed_example(entry.get('Pass example', ''))
        failed = parsed_example(entry.get('Fail example', ''))
        if passed == failed:
            errors.append(f'{canonical}: pass and fail examples are identical')
        if passed in RULE_TRIGGERED_EXAMPLES or failed in RULE_TRIGGERED_EXAMPLES:
            errors.append(f'{canonical}: ruleTriggered placeholder example')
        for field in CONCRETE_FIELDS:
            value = entry.get(field, '')
            folded = value.casefold()
            for phrase in META_EXAMPLE_PHRASES:
                if phrase in folded:
                    errors.append(f'{canonical}: meta phrase {phrase!r} in {field}')
            if 'Condition' in value:
                errors.append(f"{canonical}: meta phrase 'Condition' in {field}")
            normalized = normalized_entry_text(canonical, entry, field)
            if normalized:
                normalized_fields[field][normalized].append(canonical)
    for field, groups in normalized_fields.items():
        for canonicals in groups.values():
            if len(canonicals) >= 2:
                errors.append(f'{field}: duplicate concrete text across ' + ', '.join(canonicals))
    for canonical, rules in expected.items():
        if canonical not in entries:
            errors.append('missing entry: ' + canonical)
        else:
            declared = entries[canonical].get('Enforced', '')
            locations = {location for rule in rules for location in raw[rule]}
            for location in locations:
                if location not in declared:
                    errors.append(f'{canonical}: missing enforcement location {location}')
        for rule in rules:
            if rule != canonical and alias_owner.get(rule) != canonical:
                errors.append(f'missing alias: {rule} -> {canonical}')
    expected_names = set(expected)
    for canonical in entries:
        if canonical not in expected_names:
            errors.append('stale entry: ' + canonical)
    manifest = {'valid': not errors, 'entries': len(entries), 'aliases': len(alias_owner),
                'extracted': len(raw), 'canonical': len(expected),
                'bySource': dict(sorted(Counter(s.split(':', 1)[0] for sources in raw.values() for s in sources).items())),
                'errors': sorted(set(errors))}
    return manifest, raw, expected


def bootstrap(root, contract_override=None):
    raw = inventory(root, contract_override)
    expected = defaultdict(set)
    sources = defaultdict(set)
    for rule, locations in raw.items():
        canonical = merged_canonical(rule)
        expected[canonical].add(rule)
        sources[canonical].update(locations)
    lines = ['# Rule index', '', 'Each entry is normative. Aliases preserve executable report IDs while the eight safe merge groups share one index entry.', '']
    for canonical in sorted(expected):
        aliases = sorted(expected[canonical] - {canonical})
        location = ', '.join(sorted(sources[canonical]))
        lines += [f'### {canonical}', f"Aliases: {', '.join(aliases) if aliases else '-'}",
                  f'Enforced: {location}',
                  f'Condition: Rule `{canonical}` has no violation at its enforcing predicate.',
                  'Stage: Stage 7',
                  f'Required producer fields: The producer value identified by `{canonical}`.',
                  f'Pass example: `{{"rule":"{canonical}","violations":[]}}`',
                  f'Fail example: `{{"rule":"{canonical}","violations":["invalid"]}}`', '']
    return '\n'.join(lines) + '\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--index', type=Path)
    parser.add_argument('--contract', type=Path)
    parser.add_argument('--manifest', type=Path)
    parser.add_argument('--bootstrap', action='store_true')
    args = parser.parse_args()
    if args.bootstrap:
        sys.stdout.write(bootstrap(args.root, args.contract)); return 0
    index = args.index or args.root / 'references/rule-index.md'
    manifest, _, _ = check(args.root, index, args.contract)
    payload = json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(',', ':')) + '\n'
    if args.manifest:
        args.manifest.write_text(payload)
    sys.stdout.write(payload)
    return 0 if manifest['valid'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
