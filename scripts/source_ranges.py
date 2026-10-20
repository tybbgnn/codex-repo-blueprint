"""Attach complete function source and BB-derived, inclusive line ranges (stage 6)."""
import json
import hashlib
import re
import bisect
from pathlib import Path
from classify import (ARTIFACT_KINDS, classify_block, classify_operation,
                      compiler_drop_flags, frame_aliases, frame_bool,
                      is_unit_assignment, place_key)


def read(out, name):
    return json.loads((Path(out) / name).read_text())


def async_shell_prelude_raw(out):
    root = Path(out).resolve(); pins = read(root, 'input-pins.json')
    pin = pins.get('async_shell_prelude')
    if not isinstance(pin, dict):
        return None
    path = (root / pin['path']).resolve()
    if (root not in path.parents or not re.fullmatch(r'[a-f0-9]{64}', pin.get('sha256', ''))
            or hashlib.sha256(path.read_bytes()).hexdigest() != pin['sha256']):
        raise ValueError('Invalid async_shell_prelude pin')
    raw = json.loads(path.read_bytes())
    if raw.get('owner_def_path_hash') != pin.get('def_path_hash'):
        raise ValueError('async_shell_prelude owner mismatch')
    return raw



def _source_tokens(lines):
    """Tokenize Rust source while retaining one-based UTF-8 byte positions."""
    text = '\n'.join(lines)
    pattern = (r'/\*|//[^\n]*|(?<![\w])(?:br|r)(\#*)"[\s\S]*?"\1|'
               r'b?"(?:\\.|[^"\\])*"|b?\'(?:\\.|[^\'\\])\'|'
               r'::|\b\w+\b|[^\s]')
    tokens = []
    line_starts = [0]
    line_starts.extend(m.end() for m in re.finditer('\n', text))

    def location(offset):
        line_index = bisect.bisect_right(line_starts, offset) - 1
        prefix = text[line_starts[line_index]:offset]
        return line_index + 1, len(prefix.encode('utf-8')) + 1

    pos = 0
    rx = re.compile(pattern)
    while pos < len(text):
        match = rx.search(text, pos)
        if not match:
            break
        token = match.group()
        start, end = match.start(), match.end()
        pos = end
        if token == '/*':
            depth = 1
            while depth:
                nested = re.search(r'/\*|\*/', text[pos:])
                if not nested:
                    raise ValueError('Unclosed source comment')
                depth += 1 if nested.group() == '/*' else -1
                pos += nested.end()
            continue
        if token.startswith('//'):
            continue
        start_line, start_column = location(start)
        end_line, end_column = location(end)
        tokens.append(dict(text=token, start=start, end=end,
                           startLine=start_line, startColumn=start_column,
                           endLine=end_line, endColumn=end_column))
    return text, tokens


def _balanced(tokens, index, opening, closing):
    depth = 0
    for current in range(index, len(tokens)):
        token = tokens[current]['text']
        if token == opening:
            depth += 1
        elif token == closing:
            depth -= 1
            if depth == 0:
                return current + 1
    raise ValueError('Unclosed source delimiter')


def _balanced_back(tokens, index, opening, closing):
    depth = 0
    for current in range(index, -1, -1):
        token = tokens[current]['text']
        if token == closing:
            depth += 1
        elif token == opening:
            depth -= 1
            if depth == 0:
                return current
    raise ValueError('Unclosed source delimiter')


def expanded_function_bounds(lines, lo, hi, name):
    """Recover an attribute-only macro span, anchored to the next named fn.

    Token offsets preserve original line positions. Comments and Rust literals
    cannot contribute delimiters; mismatches fail closed, never select a later fn.
    """
    text, tokens = _source_tokens(lines[lo-1:])
    i = 0
    while i + 1 < len(tokens) and tokens[i]['text'] == '#' and tokens[i+1]['text'] == '[':
        i = _balanced(tokens, i+1, '[', ']')
    start = i
    # Accept only Rust function modifiers between the attribute and exact name.
    while i < len(tokens) and tokens[i]['text'] in ('pub', 'async', 'unsafe', 'const', 'extern', 'default'):
        modifier = tokens[i]['text']; i += 1
        if modifier == 'pub' and i < len(tokens) and tokens[i]['text'] == '(':
            i = _balanced(tokens, i, '(', ')')
        if modifier == 'extern' and i < len(tokens) and tokens[i]['text'].startswith('"'): i += 1
    if i+1 >= len(tokens) or tokens[i]['text'] != 'fn' or tokens[i+1]['text'] != name:
        raise ValueError('Expanded attribute does not precede the owning function')
    i += 2
    angles = 0
    while i < len(tokens):
        t = tokens[i]['text']
        if t == '<': angles += 1
        elif t == '>' and angles: angles -= 1
        if t in ('(', '['):
            i = _balanced(tokens, i, t, ')' if t == '(' else ']'); continue
        if t == ';': raise ValueError('Owning function has no source body')
        if t == '{' and angles:
            i = _balanced(tokens, i, '{', '}'); continue
        if t == '{':
            end = _balanced(tokens, i, '{', '}') - 1
            return (lo + tokens[start]['startLine'] - 1,
                    lo + tokens[end]['endLine'] - 1)
        i += 1
    raise ValueError('Missing owning function body')


def instrument_attribute_fields(lines, signature_line, name):
    """Return attached instrument attribute blocks and fields expression ranges."""
    candidates = [line for line in range(1, signature_line + 1) if '#[' in lines[line-1]]
    if not candidates:
        return []
    window_start = candidates[-1]
    window_end = min(len(lines), signature_line + 8)
    # Attribute discovery is deliberately local. Tokenizing the whole module can
    # let an unrelated malformed/conditional literal obscure the owning item.
    _, tokens = _source_tokens([''] * (window_start - 1) + lines[window_start-1:window_end])
    fn_index = next((i for i, token in enumerate(tokens[:-1])
                     if token['text'] == 'fn' and tokens[i+1]['text'] == name
                     and token['startLine'] >= signature_line), None)
    if fn_index is None:
        raise ValueError('Owning function token not found')
    cursor = fn_index - 1
    while cursor >= 0:
        token = tokens[cursor]['text']
        if token in ('pub', 'async', 'unsafe', 'const', 'default', 'extern'):
            cursor -= 1
            continue
        if token.startswith('"') and cursor and tokens[cursor-1]['text'] == 'extern':
            cursor -= 2
            continue
        if token == ')':
            opening = _balanced_back(tokens, cursor, '(', ')')
            if opening and tokens[opening-1]['text'] == 'pub':
                cursor = opening - 2
                continue
        break
    attributes = []
    while cursor >= 0 and tokens[cursor]['text'] == ']':
        opening = _balanced_back(tokens, cursor, '[', ']')
        if opening == 0 or tokens[opening-1]['text'] != '#':
            break
        attributes.append((opening-1, cursor))
        cursor = opening - 2
    attributes.reverse()
    results = []
    for start, end in attributes:
        opening_paren = next((i for i in range(start+2, end)
                              if tokens[i]['text'] == '('), None)
        path_end = opening_paren if opening_paren is not None else end
        path = [tokens[i]['text'] for i in range(start+2, path_end)]
        if path not in (['instrument'], ['tracing', '::', 'instrument']):
            continue
        fields = []
        if opening_paren is not None:
            outer_end = _balanced(tokens, opening_paren, '(', ')') - 1
            index = opening_paren + 1
            while index < outer_end:
                if (tokens[index]['text'] == 'fields' and index+1 < outer_end
                        and tokens[index+1]['text'] == '('):
                    fields_end = _balanced(tokens, index+1, '(', ')') - 1
                    entry_start = index + 2
                    depth = []
                    entry_ranges = []
                    for current in range(entry_start, fields_end + 1):
                        value = tokens[current]['text'] if current < fields_end else ','
                        if value in ('(', '[', '{', '<'):
                            depth.append(value)
                        elif value in (')', ']', '}', '>') and depth:
                            depth.pop()
                        if value == ',' and not depth:
                            if entry_start < current:
                                entry_ranges.append((entry_start, current))
                            entry_start = current + 1
                    for first, last in entry_ranges:
                        inner_depth = []
                        equals = None
                        for current in range(first, last):
                            value = tokens[current]['text']
                            if value in ('(', '[', '{', '<'):
                                inner_depth.append(value)
                            elif value in (')', ']', '}', '>') and inner_depth:
                                inner_depth.pop()
                            elif value == '=' and not inner_depth:
                                equals = current
                                break
                        expression = (equals + 1) if equals is not None else first
                        if expression < last:
                            begin, finish = tokens[expression], tokens[last-1]
                            fields.append(dict(startLine=begin['startLine'], startColumn=begin['startColumn'],
                                               endLine=finish['endLine'], endColumn=finish['endColumn']))
                    index = fields_end + 1
                    continue
                index += 1
        results.append(dict(startLine=tokens[start]['startLine'], endLine=tokens[end]['endLine'],
                            fields=fields))
    return results


def function_source(out):
    row = read(out, 'input-pins.json')['definition_row']
    definitions = read(out, 'facts/definitions-index.json')
    # Async MIR belongs to a synthetic coroutine: follow ownership to the real fn.
    seen = set()
    while row['rustc']['def_kind'] not in ('Fn', 'AssocFn'):
        key = row.get('ownership', {}).get('parent_def_path_hash')
        if key in seen or key not in definitions:
            raise ValueError('Complete owning function definition is required for source view')
        seen.add(key)
        row = definitions[key]
    source = row['source']
    span = source['span']
    file = source['file']
    candidates = [Path(out) / 'source' / file, Path(out) / 'source' / Path(file).name]
    path = next((p for p in candidates if p.is_file()), None)
    if path is None:
        raise ValueError('Missing source snapshot: ' + file)
    lines = path.read_text().splitlines()
    lo, hi = span['start_line'], span['end_line']
    if not 1 <= lo <= hi <= len(lines):
        raise ValueError('Function definition span exceeds source snapshot')
    if source.get('from_expansion') and '\n'.join(lines[lo-1:hi]).lstrip().startswith('#['):
        lo, hi = expanded_function_bounds(lines, lo, hi, row.get('identity', {}).get('name'))
    return dict(file=file, startLine=lo, endLine=hi, lines=lines[lo-1:hi],
                definitionRef=row['def_path_hash'], sourcePath=str(path.relative_to(out)))


def _range_dict(value):
    if isinstance(value, dict):
        return dict(value)
    return dict(startLine=value[0], endLine=value[1])


def _range_position(value, end=False):
    line = value['endLine'] if end else value['startLine']
    column = value.get('endColumn' if end else 'startColumn')
    return line, column if column is not None else (10**12 if end else 0)


def merge_ranges(ranges):
    merged = []
    normalized = sorted((_range_dict(value) for value in ranges),
                        key=lambda value: _range_position(value))
    for current in normalized:
        previous = merged[-1] if merged else None
        column_range = 'startColumn' in current or (previous and 'startColumn' in previous)
        line_merge = (previous and not column_range
                      and current['startLine'] <= previous['endLine'] + 1)
        column_merge = (previous and column_range
                        and current['startLine'] == previous['endLine']
                        and current.get('startColumn', 0) <= previous.get('endColumn', 10**12))
        if line_merge:
            previous['endLine'] = max(previous['endLine'], current['endLine'])
        elif column_merge and _range_position(current, True) > _range_position(previous, True):
            previous['endLine'] = current['endLine']
            previous['endColumn'] = current.get('endColumn', previous.get('endColumn'))
        elif column_merge:
            continue
        else:
            merged.append(current)
    return merged


def _point_in_range(line, column, source_range):
    point = (line, column)
    return ((source_range['startLine'], source_range['startColumn']) <= point
            < (source_range['endLine'], source_range['endColumn']))


def _attribute_operation_range(op, source_file, attribute_fields):
    span = (op.get('source_info') or {}).get('span') or {}
    if (span.get('file') != source_file or span.get('from_expansion') is not False
            or not isinstance(span.get('start_line'), int)
            or not isinstance(span.get('start_column'), int)):
        return None
    return next((field for field in attribute_fields
                 if _point_in_range(span['start_line'], span['start_column'], field)), None)


# Fractions use the union of inclusive lines, never the bounding envelope.
MAX_SOURCE_FRACTION = .25


def _operation_span_choice(op, source, body_span, scopes=()):
    info = op.get('source_info') or {}
    span = info.get('span') or {}
    def bounds(s):
        if s.get('file') != source['file']:
            return None
        lo, hi = s.get('start_line', 0), s.get('end_line', 0)
        # Reject, do not clip foreign/enclosing locations into plausible claims.
        if not max(source['startLine'], body_span['start_line']) <= lo <= hi <= source['endLine']:
            return None
        if (hi == body_span['start_line'] and s.get('end_column', 0)
                and body_span.get('start_column', 0)
                and s['end_column'] <= body_span['start_column']):
            return None
        if lo <= body_span['start_line'] and hi >= body_span['end_line']:
            return None
        return lo, hi
    call_span = span.get('call_site') or {}
    direct, call = bounds(span), bounds(call_span)
    # Expansions may retain a synthetic location even in the same file.
    # A callsite is usable only if it is not enclosing the body/parent scope.
    if call and span.get('from_expansion', bool(span.get('call_site'))):
        chosen, chosen_span = call, call_span
    else:
        chosen, chosen_span = direct, span
    if direct and call and call[0] <= direct[0] <= direct[1] <= call[1]:
        chosen, chosen_span = direct, span
    if chosen is None:
        chosen, chosen_span = direct, span
    if chosen and op.get('kind') in ARTIFACT_KINDS | {'Goto', 'SwitchInt'}:
        parents = {s.get('source_scope'): s for s in scopes}
        scope = parents.get(info.get('scope'))
        seen = set()
        while scope and scope.get('source_scope') not in seen:
            seen.add(scope.get('source_scope'))
            s = scope.get('span') or {}
            if (s.get('file') == source['file'] and chosen[0] < chosen[1]
                    and chosen[0] <= s.get('start_line', 0)
                    and chosen[1] >= s.get('end_line', 0)):
                return None, None
            scope = parents.get(scope.get('parent_scope'))
    return chosen, chosen_span if chosen else None


def operation_span(op, source, body_span, scopes=()):
    """Resolve only operation spans; expansion context must not widen source claims."""
    return _operation_span_choice(op, source, body_span, scopes)[0]


def condition_extent(span, source, *, span_info=None):
    """Complete only an unfinished anchored expression, never its next operand.

    A complete MIR span is authoritative. Short-circuit operands and subsequent
    method calls have their own operation evidence; union those records instead.
    """
    if not span or not source.get('lines'):
        return span
    import re
    lines = source['lines']; lo, hi = span
    def code(text):
        return re.sub(r'r(#+)?"[\s\S]*?"\1|"(?:\\.|[^"\\])*"|/\*[\s\S]*?\*/|//[^\n]*', '', text)
    def unfinished(text):
        text = code(text)
        return any(text.count(a) > text.count(b) for a, b in [('(', ')'), ('[', ']')]) or text.rstrip().endswith('=')
    selected = lines[lo-source['startLine']:hi-source['startLine']+1]
    if span_info:
        start_column = span_info.get('start_column')
        end_column = span_info.get('end_column')
        valid = (span_info.get('start_line') == lo and span_info.get('end_line') == hi
                 and isinstance(start_column, int) and isinstance(end_column, int)
                 and (lo != hi or start_column <= end_column)
                 and 1 <= start_column <= len(selected[0]) + 1
                 and 1 <= end_column <= len(selected[-1]) + 1
                 and selected[0][:start_column-1].isascii()
                 and selected[-1][:end_column-1].isascii())
        if valid:
            selected = list(selected)
            if lo == hi:
                selected[0] = selected[0][start_column-1:end_column-1]
            else:
                selected[0] = selected[0][start_column-1:]
                selected[-1] = selected[-1][:end_column-1]
    text = '\n'.join(selected)
    completed = False
    while hi < source['endLine'] and unfinished(text):
        following = lines[hi-source['startLine']+1]
        if following.lstrip().startswith(('&&', '||', '{')):
            break
        hi += 1; text += '\n' + following; completed = True
    # Await belongs to the unfinished call we just completed, not a new call.
    if completed and hi < source['endLine'] and re.fullmatch(r'\s*\.await\??[,;]?\s*', lines[hi-source['startLine']+1]):
        hi += 1
    return lo, hi


def _function_header_lines(source):
    """Locate the header independently, using the checker's line boundary rule."""
    pattern = (r'/\*[\s\S]*?\*/|//[^\n]*|r(?P<hash>\#+)?"[\s\S]*?"(?P=hash)|'
               r'"(?:\\.|[^"\\])*"|\b\w+\b|&&|\|\||[^\s]')

    def tokens(text):
        return [match.group() for match in re.finditer(pattern, text)
                if not match.group().startswith(('//', '/*', '"'))
                and not re.match(r'r\#*"', match.group())]

    header = set()
    found_fn = False
    for number, text in enumerate(source.get('lines', []), source['startLine']):
        line_tokens = tokens(text)
        found_fn |= 'fn' in line_tokens
        if not found_fn:
            continue
        if '{' in line_tokens:
            after = line_tokens[line_tokens.index('{') + 1:]
            if not after or after == ['}']:
                header.add(number)
            break
        header.add(number)
    return header


def block_evidence(block, source, body_span, scopes=(), condition=False, locals_by_id=None,
                   drop_flags=frozenset(), attribute_fields=()):
    """One record per operation: identity, role, original span and disposition.

    All node projections consume this model. Rejected evidence stays inspectable
    without becoming a highlight or changing MIR ownership.
    """
    term = block.get('terminator') or {}
    block_classification = classify_block('cleanup' if block.get('is_cleanup') else None)
    header_lines = _function_header_lines(source) if source.get('lines') else set()
    records = []
    for index, op in enumerate([*block.get('statements', []), term]):
        kind = op.get('kind')
        attribute_range = _attribute_operation_range(op, source['file'], attribute_fields)
        span, span_info = _operation_span_choice(op, source, body_span, scopes)
        if attribute_range:
            span = attribute_range
            span_info = dict(start_line=attribute_range['startLine'],
                             start_column=attribute_range['startColumn'],
                             end_line=attribute_range['endLine'],
                             end_column=attribute_range['endColumn'])
        reason = None
        discr = term.get('detail', {}).get('discriminant', {}).get('detail', {}).get('place')
        producer = (term.get('kind') == 'SwitchInt' and kind == 'Assign' and discr is not None
                    and op.get('detail', {}).get('destination') == discr
                    and op.get('detail', {}).get('rvalue', {}).get('kind') == 'Discriminant')
        classification_span = ((span['startLine'], span['endLine'])
                               if isinstance(span, dict) else span)
        operation_classification = classify_operation(op, locals_by_id, drop_flags,
                                                       classification_span, source)
        if attribute_range:
            reason = None
        elif block_classification['technicalCategory'] == 'cleanup':
            reason = 'cleanup'
        elif condition and not producer and (op is not term or kind not in ('SwitchInt', 'Call')):
            reason = 'not-condition-terminator'
        elif 'proven_drop_flag' in operation_classification['roles']:
            reason = 'proven-drop-flag'
        elif 'compiler_bookkeeping' in operation_classification['roles']:
            reason = 'compiler-bookkeeping'
        elif span is None:
            reason = 'no-local-operation-span'
        if span and source.get('lines') and not attribute_range:
            text = '\n'.join(source['lines'][span[0]-source['startLine']:span[1]-source['startLine']+1]).strip()
            if not text.strip('{};, '):
                reason = 'punctuation-only'
            elif 'unit_context_or_signature' in operation_classification['roles']:
                reason = 'unit-context-or-signature'
        if (not reason and span and not attribute_range
                and is_unit_assignment(op, locals_by_id)
                and header_lines.intersection(range(span[0], span[1] + 1))):
            reason = 'unit-header-bookkeeping'
        accepted = (attribute_range if attribute_range else
                    condition_extent(span, source, span_info=span_info) if condition and not reason else span)
        records.append(dict(operation='terminator' if op is term else op.get('statement_index', index),
                            kind=kind, role='condition-discriminant' if condition and producer else 'condition' if condition else 'operation',
                            originalSpan=(op.get('source_info') or {}).get('span'),
                            range=accepted if not reason else None, rejection=reason))
    # Preserve an explicit source break/continue only when no business operation
    # supplies a range. An enclosing Goto context never becomes a fallback.
    if not condition and not block.get('is_cleanup') and not any(r['range'] for r in records) and term.get('kind') == 'Goto':
        span = operation_span(term, source, body_span, scopes)
        if (span and span[0] == span[1]
                and not header_lines.intersection(range(span[0], span[1] + 1))):
            text = source.get('lines', [''])[span[0]-source['startLine']] if source.get('lines') else 'goto'
            if text.strip().strip('{};, '):
                records[-1].update(range=span, rejection=None, role='explicit-handoff')
    return records


def block_ranges(block, source, body_span, scopes=(), condition=False, locals_by_id=None,
                 drop_flags=frozenset(), attribute_fields=()):
    return merge_ranges(r['range'] for r in block_evidence(block, source, body_span, scopes,
                        condition, locals_by_id, drop_flags, attribute_fields) if r['range'])


def broad_range_errors(data):
    source = data.get('functionSource') or {}
    size = source.get('endLine', -1) - source.get('startLine', 0) + 1
    nodes = [n for p in data['phases'] for g in p['goals'] for n in [g, *g['actions']]]
    nodes += (data.get('execution') or {}).get('nodes', [])
    nodes += (data.get('prelude') or {}).get('nodes', [])
    return [n['id'] + ': source coverage exceeds 25% without broadRangeReason'
            for n in nodes if size > 0
            and sum(r['endLine']-r['startLine']+1 for r in n.get('lineRanges', [])) > size * MAX_SOURCE_FRACTION
            and not str(n.get('broadRangeReason', '')).strip()]


def attach_source(data, out):
    out = Path(out)
    source = function_source(out)
    facts = read(out, 'facts/blocks.json')
    hierarchy = read(out, 'stage2/hierarchy.json')['nodes']
    presentation = read(out, 'stage4/presentation.json')
    body_span = read(out, 'input-pins.json')['definition_row']['source']['span']
    raw = read(out, 'raw-body.json')
    prelude_raw = async_shell_prelude_raw(out) if data.get('prelude') else None
    scopes = raw.get('source_scopes', [])
    locals_by_id = {l['local']: l for l in raw.get('locals', [])}
    drop_flags = compiler_drop_flags(raw)
    definitions = read(out, 'facts/definitions-index.json')
    owner = definitions[source['definitionRef']]
    source_path = out / source['sourcePath']
    complete_lines = source_path.read_text().splitlines()
    attributes = instrument_attribute_fields(complete_lines, source['startLine'], owner['identity']['name'])
    qualifying_attributes = []
    prelude_refs = {ref for node in (data.get('prelude') or {}).get('nodes', [])
                    for ref in node.get('basicBlockRefs', [])}
    attribute_blocks = ({f"shell:bb{b['basic_block']}": b for b in prelude_raw.get('basic_blocks', [])}
                        if prelude_raw else facts)
    for attribute in attributes:
        if any(_attribute_operation_range(op, source['file'], attribute['fields'])
               for ref, block in attribute_blocks.items() if not prelude_raw or ref in prelude_refs
               for op in [*block.get('statements', []), block.get('terminator') or {}]):
            qualifying_attributes.append(attribute)
    attribute_fields = [field for attribute in qualifying_attributes for field in attribute['fields']]
    if qualifying_attributes:
        start = min(attribute['startLine'] for attribute in qualifying_attributes)
        end = max(attribute['endLine'] for attribute in qualifying_attributes)
        source['attributeLines'] = dict(startLine=start, endLine=end)
        source['startLine'] = start
        source['lines'] = complete_lines[start-1:source['endLine']]
    by_bb = {bid: block_ranges(b, source, body_span, scopes, locals_by_id=locals_by_id,
                               drop_flags=drop_flags,
                               attribute_fields=attribute_fields if not prelude_raw else ())
             for bid, b in facts.items()}

    attribute_line_set = set(range(source.get('attributeLines', {}).get('startLine', 1),
                                   source.get('attributeLines', {}).get('endLine', 0) + 1))
    if prelude_raw:
        by_bb = {ref: [value for value in ranges
                       if not attribute_line_set.intersection(
                           range(value['startLine'], value['endLine'] + 1))]
                 for ref, ranges in by_bb.items()}

    def attach(node, refs, condition=False):
        if any(not re.fullmatch(r'bb[0-9]+', ref) for ref in refs):
            raise ValueError('Invalid inner BB namespace: ' + node['id'])
        refs = sorted(set(refs), key=lambda b: int(b[2:]))
        if not refs or any(b not in by_bb for b in refs):
            raise ValueError('Missing BB evidence: ' + node['id'])
        mapping = ({b: block_ranges(facts[b], source, body_span, scopes, condition=True,
                                    locals_by_id=locals_by_id, drop_flags=drop_flags,
                                    attribute_fields=attribute_fields) for b in refs}
                   if condition else by_bb)
        ranges = merge_ranges(r for b in refs for r in mapping[b])
        node.pop('sourceRangeReason', None)
        if not ranges:
            node['sourceRangeReason'] = 'No precise semantic operation span in the recorded BBs; only compiler state, storage, drop, cleanup or enclosing-scope context. Full source remains available.'
        node.update(basicBlockRefs=refs, lineRanges=ranges)

    for p in data['phases']:
        for node in [p, *p['goals'], *(a for g in p['goals'] for a in g['actions'])]:
            attach(node, hierarchy[node['id']]['basic_block_refs'])
    original = {n['id']: n for n in presentation['executionNodes']}
    edge_sources = {e['id']: e['source'] for e in read(out, 'facts/edges.json')}
    for node in data['execution']['nodes']:
        if node.get('actionRef'):
            refs = hierarchy[node['actionRef']]['basic_block_refs']
        else:
            refs = [r if r in facts else edge_sources[r] for r in original[node['id']]['sourceEvidenceRefs'] if r in facts or r in edge_sources]
        if node.get('kind') == 'decision':
            # Outcome path edges often point at epilogues, not the deciding expression.
            # The stage4 inventory explicitly binds business SwitchInt BBs to decisions.
            inventory_refs = [r for item in presentation.get('sourceInventory', [])
                              if item.get('disposition') == 'business'
                              and item.get('decisionRef') == node.get('decisionRef')
                              for r in item.get('evidenceRefs', []) if r in facts]
            decision = next((q for q in presentation.get('decisions', []) if q['id'] == node.get('decisionRef')), {})
            if decision.get('type') == 'outcome':
                # Outcome summaries include compound guards in their owning action.
                owners = [a for p in data['phases'] for g in p['goals'] for a in g['actions']
                          if decision.get('controlRef') in a.get('controlRefs', [])]
                owner_bbs = {b for a in owners for b in hierarchy[a['id']]['basic_block_refs']}
                inventory_refs += [r for item in presentation.get('sourceInventory', [])
                                   if item.get('disposition') == 'business'
                                   for r in item.get('evidenceRefs', []) if r in owner_bbs]
            refs = sorted(set(inventory_refs + refs), key=lambda b: int(b[2:]))
            precise = [b for b in refs if block_ranges(facts[b], source, body_span, scopes,
                       condition=True, locals_by_id=locals_by_id, drop_flags=drop_flags,
                       attribute_fields=attribute_fields)]
            switches = [b for b in precise if facts[b]['terminator']['kind'] == 'SwitchInt']
            refs = switches or precise or refs
            attach(node, refs, condition=True)
        else:
            attach(node, refs)
    data['sourceGroups'] = []
    for n in hierarchy.values():
        # SourceGroup is the verification index, including ROOT technical groups.
        # Business rendering is determined by phases/goals/actions, not this index.
        if n['kind'] == 'bb_group':
            group = dict(id=n['id'], label=n['name'])
            attach(group, n['basic_block_refs'])
            data['sourceGroups'].append(group)
    if prelude_raw:
        shell_blocks = {f"shell:bb{b['basic_block']}": b for b in prelude_raw['basic_blocks']}
        shell_span = prelude_raw.get('span') or body_span
        shell_scopes = prelude_raw.get('source_scopes', [])
        shell_locals = {l['local']: l for l in prelude_raw.get('locals', [])}
        shell_flags = compiler_drop_flags(prelude_raw)
        for node in data['prelude']['nodes']:
            raw_refs = node.get('basicBlockRefs', [])
            if any(not re.fullmatch(r'shell:bb[0-9]+', ref) for ref in raw_refs):
                raise ValueError('Invalid shell BB namespace: ' + node['id'])
            refs = sorted(set(raw_refs), key=lambda b: int(b[8:]))
            if not refs or any(ref not in shell_blocks for ref in refs):
                raise ValueError('Missing shell BB evidence: ' + node['id'])
            ranges = merge_ranges(value for ref in refs for value in block_ranges(
                shell_blocks[ref], source, shell_span, shell_scopes,
                locals_by_id=shell_locals, drop_flags=shell_flags,
                attribute_fields=attribute_fields))
            node.pop('sourceRangeReason', None)
            if not ranges:
                node['sourceRangeReason'] = ('No precise semantic operation span in the shell BBs; '
                                             'full source remains available.')
            node.update(basicBlockRefs=refs, lineRanges=ranges)
    data['functionSource'] = source
    return data


def check_source(data, out=None):
    """Check shape and generator provenance/determinism; not independent semantics."""
    from classification_registry import source_less
    errors = []
    source = data.get('functionSource') or {}
    lo, hi, lines = source.get('startLine', 0), source.get('endLine', -1), source.get('lines', [])
    if not source.get('file') or lo < 1 or hi < lo or len(lines) != hi-lo+1 or not any(lines):
        errors.append('functionSource: missing source or line count differs from function span')
    inner_nodes = [n for p in data['phases'] for n in [p, *p['goals'], *(a for g in p['goals'] for a in g['actions'])]]
    inner_nodes += (data.get('execution') or {}).get('nodes', []) + data.get('sourceGroups', [])
    prelude_nodes = (data.get('prelude') or {}).get('nodes', [])
    nodes = inner_nodes + prelude_nodes
    prelude_ids = [n.get('id') for n in prelude_nodes]
    if (len(prelude_ids) != len(set(prelude_ids))
            or set(prelude_ids) & {n.get('id') for n in inner_nodes}):
        errors.append('source node IDs collide across prelude/reading/execution/sourceGroups')
    prelude_node_objects = {id(n) for n in prelude_nodes}
    for n in nodes:
        pattern = r'shell:bb[0-9]+' if id(n) in prelude_node_objects else r'bb[0-9]+'
        if any(not re.fullmatch(pattern, ref) for ref in n.get('basicBlockRefs', [])):
            errors.append(n['id'] + ': invalid BB namespace')
        previous = None
        ranges = n.get('lineRanges', [])
        if (not ranges and not source_less(n)) or not n.get('basicBlockRefs'):
            errors.append(n['id'] + ': missing ranges/BB refs')
        for r in ranges:
            a, b = r.get('startLine', 0), r.get('endLine', -1)
            columns = ('startColumn' in r, 'endColumn' in r)
            valid_columns = (columns == (False, False) or
                             columns == (True, True) and r['startColumn'] >= 1
                             and r['endColumn'] >= 1
                             and (a < b or r['startColumn'] < r['endColumn']))
            adjacent_lines = (previous and 'startColumn' not in previous
                              and 'startColumn' not in r and a <= previous['endLine'] + 1)
            overlaps = previous and _range_position(r) < _range_position(previous, True)
            if not lo <= a <= b <= hi or not valid_columns or adjacent_lines or overlaps:
                errors.append(n['id'] + ': invalid/noncanonical lineRanges')
            previous = r
    errors.extend(broad_range_errors(data))
    if out is not None:
        try:
            expected = attach_source(json.loads(json.dumps(data)), out)
            if source != expected['functionSource']:
                errors.append('functionSource differs from owning definition/source snapshot')
            expected_nodes = {n['id']: n for p in expected['phases'] for n in [p, *p['goals'], *(a for g in p['goals'] for a in g['actions'])]}
            expected_nodes.update({n['id']: n for n in expected['execution']['nodes'] + expected['sourceGroups']})
            expected_nodes.update({n['id']: n for n in (expected.get('prelude') or {}).get('nodes', [])})
            if {n['id'] for n in data.get('sourceGroups', [])} != {n['id'] for n in expected['sourceGroups']}:
                errors.append('sourceGroups must cover hierarchy BB groups')
            for n in nodes:
                e = expected_nodes.get(n['id'], {})
                if any(n.get(k) != e.get(k) for k in ('basicBlockRefs', 'lineRanges', 'sourceRangeReason')):
                    errors.append(n['id'] + ': ranges differ from BB span evidence')
        except (KeyError, ValueError, OSError, TypeError) as e:
            errors.append('source provenance: ' + str(e))
    return errors
