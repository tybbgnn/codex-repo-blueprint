"""One detail protocol using the existing operation-source range algorithm."""
from source_ranges import block_ranges, compiler_drop_flags


def build(c, data, nodes, blocks, raw):
    source = data['functionSource']
    details = dict(nodes={}, blocks={}, node_sources={})
    lines, offset = source['lines'], source['startLine']

    def snippets(ranges):
        return [dict(file=source['file'], start_line=row['startLine'], end_line=row['endLine'],
                     code='\n'.join(lines[row['startLine']-offset:row['endLine']-offset+1])) for row in ranges]

    for phase in data['phases']:
        for unit in [*phase['goals'], *(action for goal in phase['goals'] for action in goal['actions'])]:
            depth = 1.5 if 'actions' in unit else 2
            details['nodes'][unit['id']] = dict(depth=depth, basic_block_refs=unit['basicBlockRefs'], name=unit['label'])
            details['node_sources'][unit['id']] = dict(rust_snippets=snippets(unit['lineRanges']))
    locals_by_id = {local['local']: local for local in raw['locals']}
    flags = compiler_drop_flags(raw)
    for identity, block in blocks.items():
        ranges = block_ranges(block, source, raw['span'], raw.get('source_scopes', []),
                              locals_by_id=locals_by_id, drop_flags=flags)
        rows = snippets(ranges)
        details['blocks'][identity] = dict(block, reading_parent=nodes[identity]['reading_parent'],
                                           rust_snippets=rows, source_context_only=not bool(ranges))
        if not ranges:
            details['blocks'][identity]['sourceRangeReason'] = 'No precise semantic span; original MIR source_info retained.'
    return details
