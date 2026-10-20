#!/usr/bin/env python3
"""Run skill unit suites once per fingerprint; body checks remain per body."""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from output_paths import locked, safe_child


def skill_fingerprint(skill):
    h=hashlib.sha256();files=0
    manifest=skill/'references/package-runtime.json'
    roots=[skill/name for name in json.loads(manifest.read_text())['include']] if manifest.exists() else [skill]
    paths=set()
    for root in roots:
        paths.update(root.rglob('*') if root.is_dir() else [root])
    for p in sorted(paths):
        if not p.is_file() or '__pycache__' in p.parts or '.history' in p.parts or p.suffix=='.pyc':continue
        relative=p.relative_to(skill).as_posix().encode();raw=p.read_bytes()
        h.update(len(relative).to_bytes(8,'big'));h.update(relative)
        h.update(len(raw).to_bytes(8,'big'));h.update(raw);files+=1
    return dict(algorithm='sha256-relative-paths-and-content',sha256=h.hexdigest(),files=files)


def manifest_directory(root, batch_id):
    # Hash arbitrary batch IDs so even IDs containing slashes remain local.
    return root / '_inputs' / 'batch-manifests' / hashlib.sha256(batch_id.encode()).hexdigest()


def current_record(root, skill, batch_id=None):
    candidates = sorted(manifest_directory(root, batch_id).glob('*.json'), reverse=True) if batch_id else []
    candidates.append(root / '_inputs/batch-selftests.json')  # legacy read compatibility
    fingerprint = skill_fingerprint(skill)
    for path in candidates:
        try: record = json.loads(path.read_text())
        except (OSError, ValueError): continue
        if (record.get('passed') and record.get('skill_fingerprint') == fingerprint
                and (batch_id is None or record.get('batch_id') == batch_id)):
            return dict(record, manifest_path=str(path))
    return None


def publish_immutable(path, content):
    """Expose complete bytes with an exclusive link; never overwrite a pin."""
    import uuid
    path.parent.mkdir(parents=True, exist_ok=True)
    safe_child(path)
    staging = path.parent / ('.pending-' + uuid.uuid4().hex)
    with staging.open('x') as f:
        f.write(content); f.flush(); os.fsync(f.fileno())
    try: os.link(staging, path)
    except FileExistsError:
        if path.read_text() != content:
            raise ValueError(f'Reference already pinned to different content: {path}')
    # Retain staging artifacts; publishing does not delete existing files.
    return path


def publish_record(root, record):
    """Append an immutable manifest; concurrent batches never replace references."""
    directory = manifest_directory(root, record['batch_id'])
    # manifest_path describes the lookup location, not the original test result.
    content = json.dumps({k:v for k,v in record.items() if k != 'manifest_path'}, indent=2) + '\n'
    return publish_immutable(directory / (hashlib.sha256(content.encode()).hexdigest() + '.json'), content)


def write_reference(root, body, record):
    """Pin the passing result in one body, including when migrating a legacy read."""
    root = Path(root).resolve()
    body = Path(body)
    safe_child(body, directory=True)
    body = body.resolve()
    if body.parent != root or body.name.startswith(('_', '.')):
        raise ValueError('--reference must be a body folder directly under OUTPUT_ROOT, not a shared folder')
    if not record.get('batch_id') or not record.get('passed'):
        raise ValueError('A passing record with an explicit batch ID is required')
    # The legacy shared file is read-compatible, but never a durable reference.
    manifest = publish_record(root, record)
    content = json.dumps(dict(record=str(manifest), batch_id=record['batch_id'],
                              skill_fingerprint=record['skill_fingerprint'], passed=True), indent=2) + '\n'
    # Reuse the stable root lock used by output_paths' shared index. Different
    # bodies cannot clobber each other; a second batch for the same body must
    # archive the previous reference explicitly through the normal prepare flow.
    with locked(root):
        safe_child(body, directory=True)
        body.mkdir(parents=True, exist_ok=True)
        return publish_immutable(body / 'work' / 'batch-selftests.json', content)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output-root',type=Path,default=os.environ.get('OUTPUT_ROOT'));p.add_argument('--batch-id',default=os.environ.get('BLUEPRINT_BATCH_ID'));p.add_argument('--fixture',type=Path);p.add_argument('--reference',type=Path,help='Write reference only; requires current passing batch record');p.add_argument('--force',action='store_true');a=p.parse_args()
    if a.output_root is None:p.error('OUTPUT_ROOT required')
    if not a.batch_id:p.error('--batch-id (or BLUEPRINT_BATCH_ID) is required, including --reference')
    skill=Path(__file__).resolve().parents[1];root=a.output_root.resolve();record=current_record(root,skill,a.batch_id)
    if a.reference:
        if record is None:raise ValueError('Run batch self-tests for the current skill before body checks')
        reference=write_reference(root,a.reference,record)
        print(json.dumps(dict(passed=True,reused=True,reference=str(reference))));return
    if record and not a.force:
        print(json.dumps(dict(passed=True,reused=True,skill_fingerprint=record['skill_fingerprint'],manifest_path=record['manifest_path'])));return
    if not a.fixture:p.error('--fixture is required to run renderer integration regressions')
    started=time.perf_counter();fingerprint=skill_fingerprint(skill)
    commands=[[sys.executable,'-B',str(skill/'scripts/check_rule_index.py')],
              [sys.executable,'-B','-m','unittest','discover','-s',str(skill/'tests'),'-p','test_*.py']]
    for test in sorted((skill/'assets/renderer').glob('test-*.mjs')):
        cmd=['node',str(test)]
        if test.name in ('test-source-contract.mjs','test-declaration-contract.mjs','test-file-protocol.mjs','test-terminal-loop.mjs'):cmd.append(str(a.fixture.resolve()))
        commands.append(cmd)
    directory=root/'_inputs'/('selftests-'+datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'));directory.mkdir(parents=True)
    results=[]
    for i,cmd in enumerate(commands):
        start=time.perf_counter();r=subprocess.run(cmd,capture_output=True,text=True,env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1'))
        log=directory/f'{i+1}.log';log.write_text(r.stdout+r.stderr)
        results.append(dict(command=cmd,exit_code=r.returncode,wall_seconds=time.perf_counter()-start,log=str(log)))
    record=dict(batch_id=a.batch_id,passed=all(r['exit_code']==0 for r in results) and fingerprint==skill_fingerprint(skill),skill_fingerprint=fingerprint,fixture=str(a.fixture.resolve()),fixture_sha256=hashlib.sha256(a.fixture.read_bytes()).hexdigest(),results=results,wall_seconds=time.perf_counter()-started)
    dest=publish_record(root,record)
    print(json.dumps(dict(record,manifest_path=str(dest))));sys.exit(0 if record['passed'] else 1)

if __name__=='__main__':main()
