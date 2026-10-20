"""Shared, isolated input contract for Level 1 and Level 2 builds."""
import hashlib
import json
import re
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]


def digest(data):
    return hashlib.sha256(data).hexdigest()


def encode(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + '\n').encode()


def read(path):
    return json.loads(Path(path).read_text())


def write(path, value):
    path = Path(path)
    data = value if isinstance(value, bytes) else encode(value)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        previous = path.read_bytes()
        if previous == data:
            return
        archive = path.parent / '.history' / digest(previous) / path.name
        archive.parent.mkdir(parents=True, exist_ok=True)
        if not archive.exists():
            archive.write_bytes(previous)
    path.write_bytes(data)


def contained(root, path):
    resolved = Path(path).resolve()
    if not resolved.is_relative_to(Path(root).resolve()):
        raise ValueError('Path escapes declared root: ' + str(path))
    return resolved


def fingerprint(root):
    root = Path(root)
    return {str(p.relative_to(root)): digest(p.read_bytes())
            for p in sorted(root.rglob('*')) if p.is_file()
            and '.history' not in p.parts and '__pycache__' not in p.parts}


def assert_isolated(inputs, output, package=PACKAGE):
    paths = [('INPUTS', Path(inputs).resolve()), ('OUTPUT', Path(output).resolve()),
             ('SKILL', Path(package).resolve())]
    for index, (left_name, left) in enumerate(paths):
        for right_name, right in paths[index + 1:]:
            if left.is_relative_to(right) or right.is_relative_to(left):
                raise ValueError(f'{left_name} and {right_name} must not contain each other')


def validate_inputs(inputs):
    inputs = Path(inputs).resolve()
    manifest = read(PACKAGE / 'references/input-manifest.json')
    modes = manifest.get('modes', {})
    request_mode = (inputs / 'request.json').is_file()
    mode = modes.get('request' if request_mode else 'prepared', {})
    required = manifest['required'] + mode.get('required', [])
    forbidden = mode.get('forbidden', [])
    allowed = set(manifest['required'] + manifest['optional'])
    for contract in modes.values():
        allowed.update(contract.get('required', []))
    allowed.update('ledgers/' + name for name in manifest['ledgers'])
    errors = ['Missing input: ' + name for name in required
              if not (inputs / name).is_file()]
    errors.extend('Input forbidden in selected mode: ' + name for name in forbidden
                  if (inputs / name).exists())
    for path in sorted(inputs.rglob('*')):
        rel = path.relative_to(inputs).as_posix()
        if path.is_symlink():
            errors.append('Input symlink forbidden: ' + rel)
        elif path.is_file() and rel not in allowed:
            if not any(rel.startswith(prefix) for prefix in manifest['trees']):
                errors.append('Undeclared input: ' + rel)
    if errors:
        raise ValueError('; '.join(errors))
    return manifest


class Context:
    def __init__(self, inputs, out):
        self.inputs = Path(inputs).resolve()
        self.out = Path(out).resolve()
        assert_isolated(self.inputs, self.out)
        validate_inputs(self.inputs)
        self.work = self.out / 'work'
        self.work.mkdir(parents=True, exist_ok=True)

    def load(self, name):
        return read(contained(self.work, self.work / name))

    def ledger(self, stage):
        return read(contained(self.inputs, self.inputs / 'ledgers' / f'stage{stage}.json'))

    def save(self, name, value):
        write(contained(self.work, self.work / name), value)


def validate_local_mechanism_items(selection, action_ids=None, actors=None):
    """Mirror P8: S2 checks ownership/truthiness; S5 checks rendered actor IDs.

    canonical_render.phases_from preserves S2 action IDs as action.id; renderId
    and semantic_action_ids aliases do not change the IDs consumed by P8.
    """
    items = selection.get('items', []) if isinstance(selection, dict) else selection
    actor_ids = set()
    def collect(rows):
        for actor in rows:
            actor_ids.add(actor['actorId'])
            collect(actor.get('children', []))
    if actors is not None:
        collect(actors)
    errors = []
    for item in items:
        if item.get('disposition') != 'local_mechanism':
            continue
        prefix = 'local_mechanism ' + str(item.get('id'))
        if action_ids is not None:
            if item.get('ownerActionRef') not in action_ids:
                detail = ' (found foldedInto)' if 'foldedInto' in item else ''
                errors.append(prefix + ' lacks ownerActionRef naming an S2 action' + detail)
            for field in ('businessMeaning', 'sourceRefs'):
                if not item.get(field):
                    errors.append(prefix + ' lacks ' + field)
        if actors is not None and item.get('actorRef') in actor_ids:
            errors.append(prefix + ' actorRef names an S5 actorId: ' + str(item['actorRef']))
    if errors:
        raise ValueError('; '.join(errors))


def validate_purpose_projection_refs(external, granularity):
    """Enforce S2/S5 identity agreement before endpoint resolution or generation."""
    groups = granularity.get('purposeGroups', [])
    projections = external.get('purposeProjections', [])
    def identities(rows, field, label):
        if not isinstance(rows, list):
            raise ValueError(label + ' must be an array')
        result = set()
        for row in rows:
            ref = row.get(field) if isinstance(row, dict) else None
            if not isinstance(ref, str) or not ref:
                raise ValueError(label + ' requires nonempty ' + field)
            if ref in result:
                raise ValueError('Duplicate ' + label + ': ' + ref)
            result.add(ref)
        return result
    group_refs = identities(groups, 'projectionRef', 'S2 purposeGroups.projectionRef')
    projection_ids = identities(projections, 'id', 'S5 purposeProjection id')
    errors = []
    if projection_ids - group_refs:
        errors.append('S5 purposeProjection has no S2 purposeGroup (projection id): '
                      + ', '.join(sorted(projection_ids - group_refs)))
    if group_refs - projection_ids:
        errors.append('S2 purposeGroup has no S5 purposeProjection (projectionRef): '
                      + ', '.join(sorted(group_refs - projection_ids)))
    if errors:
        raise ValueError('; '.join(errors))


def validate_s2_purpose_groups(ledger, calls):
    """Check declared business calls now, without reading future S5 projections."""
    granularity = ledger.get('granularity', {})
    groups = granularity.get('purposeGroups', [])
    # Reuse identity checks without requiring any future projection data.
    validate_purpose_projection_refs(
        {'purposeProjections': [{'id': g.get('projectionRef')} for g in groups]}, granularity)
    by_call = {row['id']: row for row in calls}
    bb_calls = {row['bb']: row['id'] for row in calls}
    def anchors(row):
        refs = list(row.get('evidenceRefs', [])) + list(row.get('sourceRefs', []))
        refs += list(row.get('bindingRefs', []))
        if row.get('bindingRef'):
            refs.append(row['bindingRef'])
        return {bb_calls.get(ref, ref) for ref in refs if ref in by_call or ref in bb_calls}
    group_calls = set().union(*(anchors(g) for g in groups)) if groups else set()
    selection = ledger.get('selection', {})
    items = selection.get('items', []) if isinstance(selection, dict) else selection
    selected = {row.get('bindingRef', row.get('id')) for row in items
                if row.get('disposition') in ('business', 'shown') and row.get('bindingRef', row.get('id')) in by_call}
    missing = selected - group_calls
    def invocations(value):
        if isinstance(value, dict):
            if value.get('invocationRef'):
                yield value
            for child in value.values():
                yield from invocations(child)
        elif isinstance(value, list):
            for child in value:
                yield from invocations(child)
    covered_invocations = {ref for g in groups
                           for ref in g.get('invocationRefs', []) + g.get('members', [])}
    covered_invocations.update(g['invocationRef'] for g in groups if g.get('invocationRef'))
    for row in invocations([granularity.get('memberGuards', []), ledger.get('controls', [])]):
        if row['invocationRef'] not in covered_invocations and not (anchors(row) & group_calls):
            missing.add(row['invocationRef'])
    if missing:
        raise ValueError('S2 business invocation lacks purposeGroups basis: '
                         + ', '.join(sorted(str(ref) for ref in missing)))


def display_identifier_pattern():
    """Read the frozen P7 literal without importing its checker."""
    source = (PACKAGE / 'scripts/check_principles.py').read_text()
    matches = re.findall(r"^\s*'low_level_identifier': r'([^'\n]+)',\s*$", source, re.MULTILINE)
    if len(matches) != 1:
        raise ValueError('Cannot extract unique P7 low_level_identifier pattern')
    try:
        return re.compile(matches[0])
    except re.error as error:
        raise ValueError('Invalid P7 low_level_identifier pattern: ' + str(error)) from error


def validate_display_identifiers(obj, fields, label=''):
    """Check display text below selected JSON paths; evidence/identity stays opaque.

    Structural endpoints and member lists are references even in legacy fields
    whose names do not end in Ref/Refs. Never interpret those as display text.
    bb_annotations is unused legacy per-BB metadata, not a rendered node.
    """
    pattern = display_identifier_pattern()
    structural = {'id', 'ids', 'ref', 'refs', 'basis', 'evidence', 'members',
                  'children', 'parent', 'root', 'phase_order', 'basic_block_order',
                  'bb_annotations',
                  'source', 'target', 'from', 'to', 'entry', 'merge', 'back',
                  'backEdge', 'backEdges', 'exits', 'phase',
                  'semantic_key', 'kind', 'type', 'file', 'path', 'anchor'}
    errors = []
    def walk(value, pointer):
        if isinstance(value, dict):
            for key, child in value.items():
                if (key in structural or key.endswith(('Ref', 'Refs', '_ref', '_refs', 'Id', 'Ids', '_id', '_ids'))
                        or key.lower().endswith(('basis', 'evidence'))):
                    continue
                walk(child, pointer + '/' + key.replace('~', '~0').replace('/', '~1'))
        elif isinstance(value, list):
            for index, child in enumerate(value):
                walk(child, pointer + '/' + str(index))
        elif isinstance(value, str):
            for match in pattern.finditer(value):
                errors.append('display text contains low-level identifier ' + match.group()
                              + ' at ' + pointer + '; move ids to evidence fields')
    for path in fields:
        value = obj
        for part in path.split('/'):
            value = value.get(part, {}) if isinstance(value, dict) else {}
        if path == 'nodes':
            # Only these kinds project into rendered phases scanned by P7.
            for index, node in enumerate(value):
                if isinstance(node, dict) and node.get('kind') in {'phase', 'goal', 'action'}:
                    walk(node, '/nodes/' + str(index))
        else:
            walk(value, '/' + path)
    return [dict(key='P7.low_level_identifier',status='warning',message=(label + ': ' if label else '')+e) for e in errors]


S2_DISPLAY_FIELDS = ('nodes', 'granularity/memberGuards', 'granularity/ranges',
                     'granularity/purposeGroups')
S4_DISPLAY_FIELDS = ('controls', 'readingScopes')


