"""Source paths retain the nearest named item and impl receiver; peers disambiguate."""
import re


def parts(path):
    # rustc impl identities contain :: inside angle brackets.
    result, start, depth = [], 0, 0
    for i, char in enumerate(path):
        if char == '<': depth += 1
        elif char == '>': depth -= 1
        elif path[i:i+2] == '::' and depth == 0:
            if i >= start:
                result.append(path[start:i]); start = i+2
    result.append(path[start:])
    return [p for p in result if p]


def source_parts(row):
    path = row.get('identity', {}).get('canonical_path', '')
    result = parts(path)
    normalized = []
    for part in result:
        if part.startswith('<impl ') and part.endswith('>'):
            receiver = part[6:-1].split(' for ')[-1]
            normalized.append(parts(receiver)[-1])
        else: normalized.append(part)
    return normalized


def minimum(row):
    values = source_parts(row)
    if not values: raise ValueError('body label requires canonical source path')
    i = len(values)-1
    while i > 0 and values[i].startswith('{'): i -= 1
    # Methods retain receiver type, including trait methods and named impls.
    if i > 0 and (values[i-1][:1].isupper() or '<impl ' in row['identity']['canonical_path']): i -= 1
    return len(values)-i


def labels(rows):
    values = {key:source_parts(row) for key,row in rows.items()}
    sizes = {key:minimum(row) for key,row in rows.items()}
    while True:
        groups = {}
        for key, path in values.items(): groups.setdefault('::'.join(path[-sizes[key]:]), []).append(key)
        changed = False
        for keys in groups.values():
            if len({tuple(values[k]) for k in keys}) < 2: continue
            for key in keys:
                if sizes[key] < len(values[key]): sizes[key] += 1; changed = True
        if not changed: return {k:'::'.join(v[-sizes[k]:]) for k,v in values.items()}


def actor_definitions(actors, definitions):
    result = {}
    def walk(items):
        for actor in items:
            if actor.get('kind') in ('body','declaration'):
                ref = actor.get('declarationRef') or actor.get('bodyRef','')
                match = re.search(r'([0-9a-f]{32,64})\|[^|]+\|[^|]+$', ref)
                key = match.group(1) if match else ref
                if key in definitions: result[actor['actorId']] = definitions[key]
            walk(actor.get('children', []))
    walk(actors)
    return result


def apply(actors, definitions):
    expected = labels(actor_definitions(actors, definitions))
    def walk(items):
        for actor in items:
            if actor['actorId'] in expected: actor['label'] = expected[actor['actorId']]
            walk(actor.get('children', []))
    walk(actors)
    return expected


def source_aliases(row):
    """Only spellings derived from the exact pinned source identity may migrate."""
    values=source_parts(row)
    result={'::'.join(values[i:]) for i in range(len(values))}
    named=[part for part in values if not part.startswith('{')]
    if named:result.add(named[-1])
    if row['identity'].get('name'):result.add(row['identity']['name'])
    return result


def project_references(value, row, symbol, root):
    """Project root identity references together; unknown references stay rejectable."""
    aliases=source_aliases(row)
    def walk(item):
        if isinstance(item,dict):
            if item.get('kind')=='terminate-turn' and item.get('scopeRef') in aliases:
                item['scopeRef']=symbol
            if item.get('kind')=='inventory' and item.get('subjectRef') in aliases:
                item['subjectRef']=symbol
            if item.get('kind')=='entry' and len(item.get('targets',[]))==2 and item['targets'][0]==root and item['targets'][1] in aliases:
                item['targets'][1]=symbol
            for child in item.values():walk(child)
        elif isinstance(item,list):
            for child in item:walk(child)
    walk(value)
    return value
