#!/usr/bin/env python3
"""Independent source bounds checks from raw MIR + source; no generator imports.

Verifies decision expression extent and header bookkeeping. This is not a Rust
parser or semantic certification of arbitrary action/group responsibilities.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
from event_macro_verifier import verify as verify_event_macro
from async_shell_verifier import verify_out as verify_async_shell
from span_wrapper_extension_verifier import verify as verify_span_wrapper_extensions
from terminal_loop_verifier import verify_terminal_loop
from attribute_source_verifier import verify as verify_attribute_source


def _tokens(text):
    # Independent lexical scan: comments/strings cannot open code delimiters.
    pattern = r'/\*[\s\S]*?\*/|//[^\n]*|r(?P<hash>\#+)?"[\s\S]*?"(?P=hash)|"(?:\\.|[^"\\])*"|\b\w+\b|&&|\|\||[^\s]'
    return [m.group() for m in re.finditer(pattern, text)
            if not m.group().startswith(('//', '/*', '"')) and not re.match(r'r\#*"', m.group())]


def _anchor_fragment(anchor, source, start, end):
    lines = source['lines'][start-source['startLine']:end-source['startLine']+1]
    if not lines:
        return ''
    start_column = anchor.get('start_column')
    end_column = anchor.get('end_column')
    valid = (isinstance(start_column, int) and isinstance(end_column, int)
             and (start != end or start_column <= end_column)
             and 1 <= start_column <= len(lines[0]) + 1
             and 1 <= end_column <= len(lines[-1]) + 1
             and lines[0][:start_column-1].isascii()
             and lines[-1][:end_column-1].isascii())
    if valid:
        lines = list(lines)
        if start == end:
            lines[0] = lines[0][start_column-1:end_column-1]
        else:
            lines[0] = lines[0][start_column-1:]
            lines[-1] = lines[-1][:end_column-1]
    return '\n'.join(lines)


def _allowed(term, source):
    span = term.get('source_info', {}).get('span') or {}
    candidates = [span]
    if span.get('call_site'):
        candidates.append(span['call_site'])
    spans = [s for s in candidates if s.get('file') == source['file']
             and source['startLine'] <= s.get('start_line', 0) <= s.get('end_line', -1) <= source['endLine']
             and not (s['start_line'] <= source['startLine'] and s['end_line'] >= source['endLine'])]
    if not spans:
        return set()
    # A narrower direct anchor cannot be widened by enclosing expansion context.
    anchor = min(spans, key=lambda s:s['end_line']-s['start_line'])
    start, end = anchor['start_line'], anchor['end_line']
    fragment = _anchor_fragment(anchor, source, start, end)
    tokens = _tokens(fragment)
    stack = []
    for t in tokens:
        if t in ('(', '['): stack.append(t)
        elif t in (')', ']') and stack: stack.pop()
    needs_rhs = bool(tokens and tokens[-1] == '=')
    originally_incomplete = bool(stack or needs_rhs)
    while end < source['endLine'] and (stack or needs_rhs):
        next_tokens = _tokens(source['lines'][end-source['startLine']+1])
        if next_tokens and next_tokens[0] in ('&&', '||', '{'):
            break
        end += 1
        for t in next_tokens:
            if t in ('(', '['): stack.append(t)
            elif t in (')', ']') and stack: stack.pop()
        needs_rhs = not next_tokens or next_tokens[-1] == '='
    if originally_incomplete and end < source['endLine']:
        ts = _tokens(source['lines'][end-source['startLine']+1])
        if ts in [['.', 'await'], ['.', 'await', '?'], ['.', 'await', ';'], ['.', 'await', '?', ';'], ['.', 'await', ',']]:
            end += 1
    return set(range(start, end+1))


def verify(data, raw, event_macro_context=None):
    source = data.get('functionSource') or {}
    if not source.get('lines'):
        return [dict(code='missing-source', node='functionSource')]
    blocks = {f"bb{b['basic_block']}": b for b in raw.get('basic_blocks', [])}
    shell_raw = (event_macro_context or {}).get('asyncShellPreludeRaw')
    shell_blocks = ({f"shell:bb{b['basic_block']}": b
                     for b in shell_raw.get('basic_blocks', [])}
                    if isinstance(shell_raw, dict) else {})
    errors = []
    errors.extend(verify_attribute_source(data, raw,
                  (event_macro_context or {}).get('sourceBytes'),
                  (event_macro_context or {}).get('asyncShellPreludeRaw')))
    if event_macro_context:
        errors.extend(verify_event_macro(raw, event_macro_context.get('records', []),
                                         event_macro_context.get('artifacts', [])))
        errors.extend(verify_span_wrapper_extensions(raw, event_macro_context.get('records', [])))
    for scope in data.get('readingScopes', []):
        if scope.get('kind') == 'loop' and scope.get('terminalOnly'):
            errors.extend(verify_terminal_loop(data, raw, scope))
    for node in data.get('execution', {}).get('nodes', []):
        if node.get('kind') != 'decision':
            continue
        allowed = set(); checked = []
        for ref in node.get('basicBlockRefs', []):
            if not re.fullmatch(r'bb[0-9]+', ref):
                errors.append(dict(code='inner-bb-namespace', node=node['id'], bbRef=ref))
                continue
            term = blocks.get(ref, {}).get('terminator', {})
            if term.get('kind') in ('SwitchInt', 'Call'):
                allowed.update(_allowed(term, source)); checked.append(ref)
                # Pattern-only SwitchInt spans omit the tested value. Its local
                # Discriminant definition is separate raw operation evidence.
                selector = term.get('detail', {}).get('discriminant', {}).get('detail', {}).get('place')
                if term.get('kind') == 'SwitchInt' and selector:
                    for statement in blocks[ref].get('statements', []):
                        detail = statement.get('detail', {})
                        if (statement.get('kind') == 'Assign' and detail.get('destination') == selector
                                and detail.get('rvalue', {}).get('kind') == 'Discriminant'):
                            allowed.update(_allowed(statement, source))
        claimed = {i for r in node.get('lineRanges', []) for i in range(r['startLine'], r['endLine']+1)}
        extra = sorted(claimed - allowed)
        if extra:
            errors.append(dict(code='decision-outside-operation', node=node['id'], bbRefs=checked,
                               operations=['terminator'], extraLines=extra))
    # Independently locate a multiline fn header; retain real inline body work.
    header = set(); found_fn = False
    for i, line in enumerate(source['lines'], source['startLine']):
        tokens = _tokens(line); found_fn |= 'fn' in tokens
        if not found_fn: continue
        if '{' in tokens:
            after = tokens[tokens.index('{')+1:]
            if not after or after == ['}']: header.add(i)
            break
        header.add(i)
    local_types = {l['local']:l.get('type', {}) for l in raw.get('locals', [])}
    shell_types = ({l['local']: l.get('type', {}) for l in shell_raw.get('locals', [])}
                   if isinstance(shell_raw, dict) else {})
    nodes = [n for p in data.get('phases', []) for n in [p,*p['goals'],*[a for g in p['goals'] for a in g['actions']]]]
    nodes += data.get('execution', {}).get('nodes', []) + data.get('sourceGroups', [])
    nodes += (data.get('prelude') or {}).get('nodes', [])
    for node in nodes:
        claimed = {i for r in node.get('lineRanges', []) for i in range(r['startLine'], r['endLine']+1)} & header
        if not claimed: continue
        real = set()
        for ref in node.get('basicBlockRefs', []):
            if re.fullmatch(r'bb[0-9]+', ref):
                table, types, body_raw = blocks, local_types, raw
            elif re.fullmatch(r'shell:bb[0-9]+', ref):
                table, types, body_raw = shell_blocks, shell_types, shell_raw or {}
            else:
                errors.append(dict(code='bb-namespace', node=node['id'], bbRef=ref))
                continue
            b = table.get(ref, {})
            for op in b.get('statements', []) + [b.get('terminator', {})]:
                if op.get('kind') not in ('Assign','Call','SwitchInt'): continue
                detail = op.get('detail', {}); typ = types.get(detail.get('destination', {}).get('local'), {})
                rv = detail.get('rvalue', {}).get('detail', {}).get('operand', {}).get('detail', {}).get('constant', {}).get('type', {})
                if op.get('kind') == 'Assign' and any(t.get('kind') == 'Tuple' and t.get('detail', {}).get('elements') == [] for t in [typ,rv]):
                    continue
                span = op.get('source_info', {}).get('span') or {}
                body = body_raw.get('span') or {}
                before_body = (span.get('end_line') == body.get('start_line')
                               and span.get('end_column', 0) and body.get('start_column', 0)
                               and span['end_column'] <= body['start_column'])
                if span.get('file') == source['file'] and not before_body:
                    real.update(range(span.get('start_line',0),span.get('end_line',-1)+1))
        if claimed-real:
            errors.append(dict(code='header-bookkeeping', node=node['id'], bbRefs=node.get('basicBlockRefs', []), extraLines=sorted(claimed-real)))
    return errors


def load_independent_context(out):
    """Load technical records and pinned event-macro closure bytes from OUT itself."""
    out = Path(out)
    context = {'records': [], 'artifacts': [], 'sourceBytes': None,
               'asyncShellPreludeRaw': None}
    try:
        granularity = json.loads((out/'stage2/granularity.json').read_text())
        context['records'] = granularity.get('technicalBlocks', [])
    except (OSError, TypeError, ValueError):
        pass
    try:
        pins = json.loads((out/'input-pins.json').read_text())
        root = out.resolve()
        for pin in pins.get('event_macro_closures', []):
            path = (root / pin['path']).resolve()
            if root not in path.parents or not re.fullmatch(r'[a-f0-9]{64}', pin.get('sha256', '')):
                context['artifacts'] = []; break
            context['artifacts'].append({'content': path.read_bytes(), 'sha256': pin['sha256']})
    except (OSError, KeyError, TypeError, ValueError):
        context['artifacts'] = []
    try:
        pins = json.loads((out/'input-pins.json').read_text())
        root = out.resolve(); pin = pins.get('async_shell_prelude')
        if isinstance(pin, dict):
            path = (root / pin['path']).resolve()
            if (root not in path.parents
                    or not re.fullmatch(r'[a-f0-9]{64}', pin.get('sha256', ''))):
                raise ValueError('invalid async shell prelude pin')
            content = path.read_bytes()
            if hashlib.sha256(content).hexdigest() != pin['sha256']:
                raise ValueError('async shell prelude sha mismatch')
            context['asyncShellPreludeRaw'] = json.loads(content)
    except (OSError, KeyError, TypeError, ValueError):
        context['asyncShellPreludeRaw'] = None
    try:
        data = json.loads((out/'renderer-input.json').read_text())
        relative = Path(data['functionSource']['sourcePath'])
        path = (out / relative).resolve()
        source_root = (out / 'source').resolve()
        if path.is_file() and (path == source_root or source_root in path.parents):
            context['sourceBytes'] = path.read_bytes()
    except (OSError, KeyError, TypeError, ValueError):
        context['sourceBytes'] = None
    return context


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True);p.add_argument('--report',type=Path)
    a=p.parse_args();data=json.loads((a.out/'renderer-input.json').read_text());raw=json.loads((a.out/'raw-body.json').read_text())
    context = load_independent_context(a.out)
    failures=verify(data,raw,context)
    failures.extend(verify_async_shell(a.out).get('failures', []))
    text=json.dumps(dict(passed=not failures,failures=failures),ensure_ascii=False,indent=2)+'\n'
    if a.report:
        if a.report.resolve() in {(a.out/'renderer-input.json').resolve(), (a.out/'raw-body.json').resolve()}: p.error('report would overwrite audited input')
        a.report.write_text(text)
    else: print(text,end='')
    return bool(failures)


if __name__ == '__main__': raise SystemExit(main())
