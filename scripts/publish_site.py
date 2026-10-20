"""Assemble a minimal, offline-capable site; keep candidates and replaced sites."""
import hashlib
import json
from pathlib import Path
import re
import shutil

JSON_FILES = ('renderer-input.json', 'reading-summaries.json', 'basic-block-details.json')
PRESENTATION_TOKENS = dict(zip(
    ('__SYMBOL__', '__SOURCE_FILE__', '__MODULE__', '__CRATE__'),
    ('symbol', 'file', 'module', 'crate'),
))


def verify_bundle(renderer):
    for name, expected in json.loads((renderer / 'bundle-sources.json').read_text()).items():
        if hashlib.sha256((renderer / name).read_bytes()).hexdigest() != expected:
            raise ValueError('Stale browser bundle; run scripts/build_browser_bundle.cjs')


def normalize_footer(html):
    """Legacy candidates sometimes put README beside the nested entrypoint."""
    def footer(match):
        return re.sub(r'(href=[\'"])(?:\./|\.\./)?README\.md([\'"])', r'\1../README.md\2', match[0])
    return re.sub(r'<footer\b[^>]*>[\s\S]*?</footer>', footer, html, flags=re.IGNORECASE)


def assemble(candidate, target, renderer=None, transfer=shutil.copy2, frozen_assets=None):
    """Read a machine-validated renderer candidate, write a new directory exclusively."""
    renderer = renderer or Path(__file__).resolve().parents[1] / 'assets/renderer'
    verify_bundle(renderer)
    if frozen_assets:
        for name, item in frozen_assets.items():
            if hashlib.sha256(Path(item['path']).read_bytes()).hexdigest() != item['sha256']:
                raise ValueError('Frozen renderer changed: ' + name)
        if set(frozen_assets) != {'index.html', 'style.css', 'app.bundle.js'}:
            raise ValueError('Frozen renderer must specify all three static assets')
    data = {name: json.loads((candidate / name).read_text()) for name in JSON_FILES}
    config = (candidate / 'roundtrip/render-config.js').read_text()
    # Read the existing presentation metadata without executing arbitrary site code.
    identity = {}
    for key in ('symbol', 'file', 'module', 'crate'):
        match = re.search(r'\b' + key + r'''\s*:\s*("(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*')''', config)
        if not match:
            raise ValueError(f'Missing source identity: {key}')
        import ast
        identity[key] = ast.literal_eval(match[1])
    data['sourceIdentity'] = identity
    html = normalize_footer((candidate / 'roundtrip/index.html').read_text())
    html, count = re.subn(r'<script\s+type="module"\s+src="app\.js[^"\n]*"></script>',
                         '<script src="../data.js"></script><script src="app.bundle.js"></script>', html)
    if count != 1:
        raise ValueError('Expected one renderer module entry in candidate HTML')
    html = html.replace('<meta charset="utf-8">', '<meta charset="utf-8"><link rel="icon" href="data:,">')
    if any(token in html + json.dumps(identity) for token in PRESENTATION_TOKENS):
        raise ValueError('Unresolved presentation placeholders')
    target.mkdir(exist_ok=False)
    (target / 'roundtrip').mkdir()
    for name in JSON_FILES:
        transfer(candidate / name, target / name)
    if not frozen_assets:
        for name in ('style.css',):
            transfer(candidate / 'roundtrip' / name, target / 'roundtrip' / name)
        shutil.copy2(renderer / 'roundtrip/app.bundle.js', target / 'roundtrip/app.bundle.js')
    if frozen_assets:
        for name, item in frozen_assets.items():
            transfer(Path(item['path']), target / 'roundtrip' / name)
    else:
        (target / 'roundtrip/index.html').write_text(html, encoding='utf-8')
    # ensure_ascii escapes Unicode separators; JSON serialization also safely quotes
    # arbitrary Rust source. External JS cannot be closed by an HTML script tag.
    (target / 'data.js').write_text('window.__BLUEPRINT_DATA__ = ' + json.dumps(data, ensure_ascii=True, sort_keys=True) + ';\n', encoding='utf-8')
    (target / 'README.md').write_text('# ' + identity['symbol'] + '\n\n双击 [打开页面](roundtrip/index.html)，支持 file://。\n\n也可在此目录运行 `python3 -m http.server 8000 --bind 127.0.0.1`，访问 http://127.0.0.1:8000/roundtrip/ 。\n\n基于 SeqDia 的层级布局与消息样式，条件分段、重复范围与纵向折叠为本地扩展；静态投影不是执行轨迹。\n', encoding='utf-8')
    # Finalize the copied bundle only after every deliverable has been assembled.
    # Replace whole JS string literals so quotes/backslashes in identity stay safe.
    bundle = target / 'roundtrip/app.bundle.js'
    pattern = r'''(['"])(%s)\1''' % '|'.join(map(re.escape, PRESENTATION_TOKENS))
    if not frozen_assets:
        bundle.write_text(re.sub(pattern, lambda match: json.dumps(identity[PRESENTATION_TOKENS[match[2]]]),
                                 bundle.read_text(encoding='utf-8')), encoding='utf-8')
    # All deliverables are UTF-8 text. Scan the final bytes before publish() can
    # archive an existing delivery or rename staging into place.
    for path in sorted(target.rglob('*')):
        if path.is_file():
            content = path.read_text(encoding='utf-8')
            remaining = [token for token in PRESENTATION_TOKENS if token in content]
            if remaining:
                raise ValueError(f'Unresolved presentation placeholders in {path.relative_to(target)}: '
                                 + ', '.join(remaining))
    return target


def publish(root, body, candidate, *, dry_run=False, frozen_assets=None):
    from output_paths import locked, safe_child, utc_now
    root, body, candidate = Path(root).resolve(), Path(body).resolve(), Path(candidate).resolve()
    if body.parent != root or body.name.startswith(('.', '_')):
        raise ValueError('Publish body must be directly under OUTPUT_ROOT')
    work = body / 'work'
    safe_child(work, directory=True)
    if not candidate.is_relative_to(work) or candidate == work:
        raise ValueError('Candidate must be under body/work')
    result = dict(deliverable=str(body / 'deliverable'), entry_html='roundtrip/index.html', candidate=str(candidate))
    if dry_run:
        return result
    with locked(root):
        safe_child(body / 'deliverable', directory=True)
        staging = work / ('.publish-' + utc_now().replace(':', ''))
        assemble(candidate, staging, frozen_assets=frozen_assets)
        delivery = body / 'deliverable'
        if delivery.exists():
            archive = work / '.archive' / utc_now().replace(':', '')
            archive.mkdir(parents=True, exist_ok=False)
            delivery.rename(archive / 'deliverable')
        staging.rename(delivery)
    return result
