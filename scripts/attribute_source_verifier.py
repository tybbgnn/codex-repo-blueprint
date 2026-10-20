"""Independent stdlib-only verification of instrument fields source ranges.

This module intentionally does not import source_ranges, classify, or any other
generator module. It rebuilds attached attributes and field expressions from
the pinned source bytes.
"""
import bisect
import re


def _tokens(source_bytes):
    text = source_bytes.decode('utf-8')
    pattern = (r'/\*|//[^\n]*|(?<![\w])(?:br|r)(\#*)"[\s\S]*?"\1|'
               r'b?"(?:\\.|[^"\\])*"|b?\'(?:\\.|[^\'\\])\'|'
               r'::|\b\w+\b|[^\s]')
    starts = [0]
    starts.extend(match.end() for match in re.finditer('\n', text))

    def location(offset):
        line_index = bisect.bisect_right(starts, offset) - 1
        return line_index + 1, len(text[starts[line_index]:offset].encode('utf-8')) + 1

    result = []
    position = 0
    scanner = re.compile(pattern)
    while position < len(text):
        match = scanner.search(text, position)
        if not match:
            break
        value = match.group()
        begin, finish = match.start(), match.end()
        position = finish
        if value == '/*':
            depth = 1
            while depth:
                nested = re.search(r'/\*|\*/', text[position:])
                if not nested:
                    raise ValueError('unclosed source comment')
                depth += 1 if nested.group() == '/*' else -1
                position += nested.end()
            continue
        if value.startswith('//'):
            continue
        start_line, start_column = location(begin)
        end_line, end_column = location(finish)
        result.append({'text': value, 'startLine': start_line, 'startColumn': start_column,
                       'endLine': end_line, 'endColumn': end_column})
    return result


def _forward(tokens, index, opening, closing):
    depth = 0
    for current in range(index, len(tokens)):
        if tokens[current]['text'] == opening:
            depth += 1
        elif tokens[current]['text'] == closing:
            depth -= 1
            if depth == 0:
                return current + 1
    raise ValueError('unclosed source delimiter')


def _backward(tokens, index, opening, closing):
    depth = 0
    for current in range(index, -1, -1):
        if tokens[current]['text'] == closing:
            depth += 1
        elif tokens[current]['text'] == opening:
            depth -= 1
            if depth == 0:
                return current
    raise ValueError('unclosed source delimiter')


def _attached_attributes(source_bytes, source):
    lines = source_bytes.decode('utf-8').splitlines()
    claimed = source.get('attributeLines') or {}
    hint = claimed.get('endLine', source.get('startLine', 1))
    search_end = min(len(lines), source.get('endLine', hint) + 1)
    fn_line = next((line for line in range(max(1, hint), search_end + 1)
                    if re.search(r'\bfn\s+\w+', lines[line-1])), None)
    if fn_line is None:
        return [], None
    candidates = [line for line in range(1, fn_line + 1) if '#[' in lines[line-1]]
    window_start = candidates[-1] if candidates else fn_line
    fragment = ('\n' * (window_start - 1) +
                '\n'.join(lines[window_start-1:min(len(lines), fn_line+7)])).encode('utf-8')
    tokens = _tokens(fragment)
    fn_index = next((i for i, token in enumerate(tokens)
                     if token['text'] == 'fn' and token['startLine'] >= fn_line), None)
    if fn_index is None:
        return [], fn_line
    cursor = fn_index - 1
    while cursor >= 0:
        value = tokens[cursor]['text']
        if value in ('pub', 'async', 'unsafe', 'const', 'default', 'extern'):
            cursor -= 1
            continue
        if value.startswith('"') and cursor and tokens[cursor-1]['text'] == 'extern':
            cursor -= 2
            continue
        if value == ')':
            opening = _backward(tokens, cursor, '(', ')')
            if opening and tokens[opening-1]['text'] == 'pub':
                cursor = opening - 2
                continue
        break
    spans = []
    while cursor >= 0 and tokens[cursor]['text'] == ']':
        opening = _backward(tokens, cursor, '[', ']')
        if opening == 0 or tokens[opening-1]['text'] != '#':
            break
        spans.append((opening-1, cursor))
        cursor = opening - 2
    spans.reverse()
    attributes = []
    for start, end in spans:
        paren = next((i for i in range(start+2, end) if tokens[i]['text'] == '('), None)
        path_end = paren if paren is not None else end
        path = [tokens[i]['text'] for i in range(start+2, path_end)]
        if path not in (['instrument'], ['tracing', '::', 'instrument']):
            continue
        fields = []
        if paren is not None:
            outer_end = _forward(tokens, paren, '(', ')') - 1
            index = paren + 1
            while index < outer_end:
                if (tokens[index]['text'] == 'fields' and index+1 < outer_end
                        and tokens[index+1]['text'] == '('):
                    fields_end = _forward(tokens, index+1, '(', ')') - 1
                    first = index + 2
                    nesting = []
                    entries = []
                    for current in range(first, fields_end + 1):
                        value = tokens[current]['text'] if current < fields_end else ','
                        if value in ('(', '[', '{', '<'):
                            nesting.append(value)
                        elif value in (')', ']', '}', '>') and nesting:
                            nesting.pop()
                        if value == ',' and not nesting:
                            if first < current:
                                entries.append((first, current))
                            first = current + 1
                    for first, last in entries:
                        nesting = []
                        equals = None
                        for current in range(first, last):
                            value = tokens[current]['text']
                            if value in ('(', '[', '{', '<'):
                                nesting.append(value)
                            elif value in (')', ']', '}', '>') and nesting:
                                nesting.pop()
                            elif value == '=' and not nesting:
                                equals = current
                                break
                        expression = equals + 1 if equals is not None else first
                        if expression < last:
                            begin, finish = tokens[expression], tokens[last-1]
                            fields.append({'startLine': begin['startLine'],
                                           'startColumn': begin['startColumn'],
                                           'endLine': finish['endLine'],
                                           'endColumn': finish['endColumn']})
                    index = fields_end + 1
                    continue
                index += 1
        attributes.append({'startLine': tokens[start]['startLine'],
                           'endLine': tokens[end]['endLine'], 'fields': fields})
    return attributes, fn_line


def _inside(point, field):
    return ((field['startLine'], field['startColumn']) <= point
            < (field['endLine'], field['endColumn']))


def _operations(raw, refs=None, namespace=''):
    allowed = set(refs) if refs is not None else None
    for block in raw.get('basic_blocks', []):
        ref = f"{namespace}bb{block.get('basic_block')}"
        if allowed is not None and ref not in allowed:
            continue
        for operation in [*block.get('statements', []), block.get('terminator') or {}]:
            yield ref, operation


def _qualifying(operation, file, fields):
    span = (operation.get('source_info') or {}).get('span') or {}
    if (span.get('file') != file or span.get('from_expansion') is not False
            or not isinstance(span.get('start_line'), int)
            or not isinstance(span.get('start_column'), int)):
        return None
    point = (span['start_line'], span['start_column'])
    return next((field for field in fields if _inside(point, field)), None)


def verify(data, raw, source_bytes=None, prelude_raw=None):
    source = data.get('functionSource') or {}
    if source_bytes is None:
        source_bytes = (('\n' * max(0, source.get('startLine', 1)-1)) +
                        '\n'.join(source.get('lines', []))).encode('utf-8')
    errors = []
    try:
        attributes, signature_line = _attached_attributes(source_bytes, source)
    except (UnicodeDecodeError, ValueError) as error:
        return [{'code': 'attribute-source-tokenizer', 'detail': str(error)}]
    fields = [field for attribute in attributes for field in attribute['fields']]
    prelude_nodes = (data.get('prelude') or {}).get('nodes', [])
    prelude_refs = {ref for node in prelude_nodes for ref in node.get('basicBlockRefs', [])}
    async_inner = isinstance(prelude_raw, dict)
    support_raw = prelude_raw if async_inner else raw
    qualifying = ([] if async_inner and not prelude_nodes else
                  [(ref, field) for ref, operation in _operations(
                      support_raw, prelude_refs or None, 'shell:' if async_inner else '')
                   if (field := _qualifying(operation, source.get('file'), fields))])
    qualifying_fields = {tuple(field.items()) for _, field in qualifying}
    qualifying_attributes = [attribute for attribute in attributes
                             if any(tuple(field.items()) in qualifying_fields
                                    for field in attribute['fields'])]
    claimed_attribute = source.get('attributeLines')
    if qualifying_attributes:
        expected = {'startLine': min(a['startLine'] for a in qualifying_attributes),
                    'endLine': max(a['endLine'] for a in qualifying_attributes)}
        if claimed_attribute != expected:
            errors.append({'code': 'attribute-lines-mismatch', 'expected': expected,
                           'actual': claimed_attribute})
        if source.get('startLine') != expected['startLine']:
            errors.append({'code': 'function-source-start', 'expected': expected['startLine'],
                           'actual': source.get('startLine')})
    else:
        if claimed_attribute is not None:
            errors.append({'code': 'attribute-lines-without-operation',
                           'actual': claimed_attribute})
        if signature_line is not None and source.get('startLine') != signature_line:
            errors.append({'code': 'function-source-start', 'expected': signature_line,
                           'actual': source.get('startLine')})
    attribute_lines = {line for attribute in qualifying_attributes
                       for line in range(attribute['startLine'], attribute['endLine'] + 1)}
    nodes = [node for phase in data.get('phases', [])
             for node in [phase, *phase.get('goals', []),
                          *(action for goal in phase.get('goals', [])
                            for action in goal.get('actions', []))]]
    nodes += (data.get('execution') or {}).get('nodes', []) + data.get('sourceGroups', [])
    for node in nodes:
        supported = [field for _, operation in _operations(raw, node.get('basicBlockRefs', []))
                     if (field := _qualifying(operation, source.get('file'), fields))]
        for claimed_range in node.get('lineRanges', []):
            touched = attribute_lines.intersection(
                range(claimed_range.get('startLine', 0), claimed_range.get('endLine', -1)+1))
            if touched and async_inner:
                errors.append({'code': 'inner-node-attribute-range', 'node': node.get('id'),
                               'range': claimed_range})
            elif touched:
                exact = next((field for field in fields if claimed_range == field), None)
                if exact is None:
                    errors.append({'code': 'unsupported-attribute-range', 'node': node.get('id'),
                                   'range': claimed_range})
                elif exact not in supported:
                    errors.append({'code': 'attribute-range-without-node-operation',
                                   'node': node.get('id'), 'range': claimed_range})
    for node in prelude_nodes:
        supported = [field for _, operation in _operations(
                     support_raw, node.get('basicBlockRefs', []), 'shell:' if async_inner else '')
                     if (field := _qualifying(operation, source.get('file'), fields))]
        for claimed_range in node.get('lineRanges', []):
            touched = attribute_lines.intersection(
                range(claimed_range.get('startLine', 0), claimed_range.get('endLine', -1)+1))
            if not touched:
                continue
            exact = next((field for field in fields if claimed_range == field), None)
            if exact is None:
                errors.append({'code': 'unsupported-attribute-range', 'node': node.get('id'),
                               'range': claimed_range})
            elif exact not in supported:
                errors.append({'code': 'attribute-range-without-node-operation',
                               'node': node.get('id'), 'range': claimed_range})
    return errors
