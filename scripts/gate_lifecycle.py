"""One unattended acceptance and publication lifecycle for both testing levels."""
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from ledger_lib import PACKAGE, read, write, digest


def environment(c, browser=True):
    playwright_path = os.environ.get('PLAYWRIGHT_PATH')
    if browser and not playwright_path:
        raise RuntimeError('PLAYWRIGHT_PATH is required for browser validation; set it to the Playwright module path')
    scratch = c.out.parent / 'scratch'
    scratch.mkdir(exist_ok=True)
    return dict(os.environ, PYTHONDONTWRITEBYTECODE='1', TMPDIR=str(scratch),
                BLUEPRINT_SCRATCH_ROOT=str(scratch), PYTHONPATH=os.pathsep.join([str(PACKAGE / 'tests/support'),str(PACKAGE/'scripts')]),
                NODE_OPTIONS='--require=' + str(PACKAGE / 'tests/support/retain.cjs'),
                PLAYWRIGHT_PATH=playwright_path or "",
                BROWSER_PATH=os.environ.get('BROWSER_PATH', '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'))


def execute(c, name, command):
    start = time.monotonic()
    try:
        process = subprocess.run(command, capture_output=True, text=True,
                                 env=environment(c, browser=name=='browser'), timeout=420)
        result = dict(passed=process.returncode == 0, exit_code=process.returncode,
                      stdout=process.stdout, stderr=process.stderr)
    except (OSError,RuntimeError) as exc:
        result = dict(passed=False,exit_code=None,status='not-run',reason=str(exc),error=str(exc))
    except subprocess.TimeoutExpired:
        result = dict(passed=False, exit_code=None, error='420s timeout')
    result.update(command=command, elapsed_seconds=time.monotonic() - start)
    result = environment_result(result)
    c.save('stage7/' + name + '-execution.json', result)
    return result


def environment_result(result):
    import re,shlex
    signature=str(result.get('error',''))+' '+result.get('stderr','')+' '+result.get('stdout','')
    if not result.get('passed') and (result.get('status')=='not-run' or re.search(r'PLAYWRIGHT_PATH is required|Cannot find (?:module|package).*playwright|browserType.launch.*(?:EPERM|EACCES|Target page, context or browser has been closed)|listen EPERM|Operation not permitted|Executable doesn.t exist|spawn.*ENOENT',signature,re.I)):
        result.update(status='not-run',reason=cause_line(signature),rerun_command=('PLAYWRIGHT_PATH="${PLAYWRIGHT_PATH:?set Playwright module path}" ' if any('test_file_protocol' in str(a) for a in result.get('command',[])) else '')+shlex.join(result.get('command',[])))
    # Batch executes independent children and saves their real logs. Classify
    # each child rather than hiding missing browsers behind a generic batch failure.
    try:children=json.loads(result.get('stdout','')).get('results',[])
    except (ValueError,AttributeError,TypeError):children=[]
    classified=[]
    for child in children:
        code=child.get('exit_code')
        if code==0:classified.append(dict(child,passed=True));continue
        try:log=Path(child['log']).read_text()
        except (KeyError,OSError):log=''
        classified.append(environment_result(dict(child,passed=False,stdout='',stderr=log)))
    if classified:
        result['subchecks']=classified
        failed=[x for x in classified if not x['passed']]
        if failed and all(x.get('status')=='not-run' for x in failed):
            result.update(status='not-run',reason='; '.join(x['reason'] for x in failed),rerun_command=shlex.join(result.get('command',[])))
    return result

def check_result(result):
    return {key:result[key] for key in ('passed','status','reason','rerun_command','subchecks') if key in result}


def counts(c):
    nodes = c.load('stage2/hierarchy.json')['nodes']
    data = c.load('renderer-input.json')
    return dict(bb_total=len(c.load('raw-body.json')['basic_blocks']),
                bb_covered=sum(n['kind'] == 'bb' for n in nodes.values()),
                phase_count=sum(n['kind'] == 'phase' for n in nodes.values()),
                goal_count=sum(n['kind'] == 'goal' for n in nodes.values()),
                action_count=sum(n['kind'] == 'action' for n in nodes.values()),
                message_count=len(data['messages']), execution_node_count=len(data['execution']['nodes']))


def environment_commands(c, site):
    base = [sys.executable, '-B', str(PACKAGE/'scripts/batch_selftests.py'),
            '--output-root',str(c.out.parent),'--batch-id',c.out.parent.name]
    return {'browser':[sys.executable,'-B',str(PACKAGE/'scripts/browser_checks.py'),'--site',str(site),'--receipts',str(c.work/'stage7/browser-runs')],
            'batch':base+['--fixture',str(c.work/'renderer-input.json')],
            'batch-reference':base+['--reference',str(c.out)]}


def record_environment(c, name, command):
    result = execute(c,name,command)
    try: payload = json.loads(result.get('stdout',''))
    except (ValueError,TypeError): payload = {}
    # A zero process exit cannot override failed protocol/subcheck assertions.
    if payload.get('passed') is False: result['passed'] = False
    if name == 'browser':
        if result.get('passed') and payload.get('passed') is not True:result.update(passed=False,reason='browser receipt lacks an explicit passing assertion')
        children = payload.get('results',[])
        if children and not all(row.get('passed') is True for row in children): result['passed']=False
    c.save('stage7/'+name+'-execution.json',result)
    c.save('stage7/'+name+'.json',payload if payload else result)
    return check_result(result)


def summarize(c, report):
    checks = report['checks']
    report['passed'] = all(item.get('passed') is True for item in checks.values())
    report['browser_checked'] = checks.get('browser',{}).get('passed') is True
    deviations = report.get('deviations',[])
    gaps = [r for r in report.get('missing_mir',[]) if r['category']=='out-of-scope']
    report.update(status=('passed-with-deviations('+str(len(deviations))+')' if deviations else 'passed') if report['passed'] else 'failed',
                  missing_mir_count=len(gaps),clean_pass=report['passed'] and not gaps and not deviations,
                  mir_status=('通过，但有 '+str(len(gaps))+' 项缺 MIR') if gaps else 'clean',
                  checks_not_run=[dict(check=k,**v) for k,v in checks.items() if v.get('status')=='not-run']+
                    [dict(check=k,**child) for k,v in checks.items() for child in v.get('subchecks',[]) if child.get('status')=='not-run'])
    rerun = [sys.executable,'-B',str(PACKAGE/'scripts/blueprint.py'),'rerun-env','--out',str(c.out)]
    import shlex
    report['environment_rerun_command'] = shlex.join(rerun)
    c.save('stage7/acceptance.json',report)
    warning_text = '\n'.join('- '+json.dumps(w,ensure_ascii=False) for w in report.get('warnings',[])) or '无。'
    write(c.out/'e2e-summary.md', ('# 验收结果\n\n'+report['status']+'\n\nMIR：'+report['mir_status']+
        '\n\n## Warnings\n\n'+warning_text+'\n\n环境补跑：`'+report['environment_rerun_command']+'`\n\n```json\n'+json.dumps(report,ensure_ascii=False,indent=2)+'\n```\n').encode())
    if not report['passed']: blocked_report(c,report)
    return report


def defer_batch_reference(c, checks):
    """A missing batch credential remains rerunnable while an environment child is pending."""
    batch=checks.get('batch',{});reference=checks.get('batch-reference',{})
    pending=batch.get('status')=='not-run' or any(child.get('status')=='not-run' for child in batch.get('subchecks',[]))
    if reference.get('passed') is False and pending:
        reference.update(status='not-run',reason='passing batch reference unavailable until environment checks run')
        path=c.work/'stage7/batch-reference-execution.json'
        if path.exists():
            value=read(path);value.update(reference);c.save('stage7/batch-reference-execution.json',value)


def finish_gates(c, checks):
    from stage_engine import prepare_candidate
    _, site, _ = prepare_candidate(c)
    for name, command in environment_commands(c,site).items():
        checks[name] = record_environment(c,name,command)
    defer_batch_reference(c,checks)
    report = dict(checks=checks,counts=counts(c))
    from run_fixes import records
    registered = records(c)
    used_path = c.out/'run-fixes/used.json'
    usage = read(used_path) if used_path.exists() else []
    deviations = [r for r in registered if any(u['sha256']==r['sha256'] and u['fixed_script']==r['fixed_script'] for u in usage)]
    warnings = []
    for path in sorted((c.work/'display-warnings').glob('*.json')): warnings.extend(read(path))
    principles = c.work/'stage7/principles.json'
    if principles.exists(): warnings.extend(read(principles).get('warnings',[]))
    report.update(deviations=deviations,registered_deviations=registered,repair_usage=usage,
                  missing_mir=c.load('input-pins.json').get('missing_mir',[]),warnings=warnings)
    return summarize(c,report)


def rerun_env(out):
    """Reuse all non-environment receipts, including agent decisions; never rebuild."""
    from types import SimpleNamespace
    out=Path(out).resolve();work=out/'work'
    c=SimpleNamespace(out=out,work=work,save=lambda name,value:write(work/name,value))
    report=read(work/'stage7/acceptance.json')
    for name in ('browser','batch','batch-reference'):
        prior=report['checks'].get(name,{})
        if prior.get('status')!='not-run' and not any(child.get('status')=='not-run' for child in prior.get('subchecks',[])): continue
        execution=read(work/('stage7/'+name+'-execution.json'))
        if name=='batch' and execution.get('subchecks'):
            # Keep successful children; execute only child commands classified not-run.
            children=[]
            for i, child in enumerate(execution['subchecks']):
                if child.get('status')=='not-run':
                    child=execute(c,'batch-child-'+str(i),child['command'])
                children.append(child)
            execution['subchecks']=children
            execution['passed']=all(child.get('passed') is True for child in children)
            execution['exit_code']=0 if execution['passed'] else 1
            execution.pop('status',None);execution.pop('reason',None)
            if any(child.get('status')=='not-run' for child in children):execution['status']='not-run'
            payload=json.loads(execution['stdout']);payload['results']=children;payload['passed']=execution['passed']
            if execution['passed']:
                from batch_selftests import publish_record,skill_fingerprint
                if payload['skill_fingerprint']!=skill_fingerprint(PACKAGE):raise ValueError('batch fingerprint changed; run S7 again')
                publish_record(out.parent,payload)
            execution['stdout']=json.dumps(payload)
            c.save('stage7/batch-execution.json',execution);c.save('stage7/batch.json',payload)
            report['checks'][name]=check_result(execution)
        else: report['checks'][name]=record_environment(c,name,execution['command'])
    defer_batch_reference(c,report['checks'])
    return summarize(c,report)


class BlockedRun(ValueError):
    """S8 refused publication; payload is preserved by the CLI failure receipt."""

    def __init__(self, payload):
        super().__init__('运行受阻：未通过 S7 验收')
        self.payload = payload


def cause_line(text):
    """Select the first cause-bearing line, ignoring Node stack boilerplate."""
    import re

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    for line in lines:
        if re.match(r'node:|at\s|throw\s+er;|\^$|Node\.js\s+v', line, re.I):
            continue
        if re.search(r'\bE[A-Z]{2,}\b|(?i:Error:|\berrno\b|operation not permitted|permission denied)', line):
            return line
    return lines[0] if lines else ''


def blocked_report(c, report):
    """Classify existing S7 evidence without changing any checker receipt."""
    import re
    import shlex

    reports = {p.stem: read(p) for p in (c.work / 'stage7').glob('*.json')
               if p.name != 'blocked-report.json'}
    policy = read(PACKAGE / 'references/failure-classes.json')
    candidate = reports.get('candidate', {})
    # S8 records its exact preview; before S8 use the browser's checked site.
    pointer = c.work / 'stage8/candidate.json'
    if pointer.exists():
        candidate = read(pointer)
    browser_command = reports.get('browser-execution', {}).get('command', [])
    preview = candidate.get('path') or (browser_command[-1] if browser_command else str(c.out / 'candidate-deliverable'))
    entries = []

    def classify(check, source, principle=None, principle_check=None, execution=None):
        execution = execution or {}
        signature = json.dumps(source, ensure_ascii=False) + '\n' + json.dumps(execution, ensure_ascii=False)
        nested = []
        child_examples = []
        if check == 'batch':
            try:
                nested = json.loads(execution.get('stdout', '')).get('results', [])
            except (ValueError, TypeError, AttributeError):
                pass
            for child in nested:
                if child.get('exit_code') in (None, 0):
                    continue
                child_command = ' '.join(child.get('command', []))
                signature += '\n' + child_command + ' exit_code=' + str(child['exit_code'])
                example = dict(command=child.get('command', []), exit_code=child['exit_code'])
                log = child.get('log')
                if log:
                    try:
                        log_text = Path(log).read_text()
                        signature += '\n' + log_text
                        example['stderr'] = cause_line(log_text)
                    except OSError:
                        pass
                child_examples.append(example)
        rule = next(r for r in policy['rules']
                    if r['check'] in ('*', check)
                    and ('principle' not in r or r['principle'] == principle)
                    and ('principle_check' not in r or r['principle_check'] == principle_check)
                    and ('signature' not in r or re.search(r['signature'], signature, re.I)))
        if execution.get('status')=='not-run' or source.get('status')=='not-run':
            rule=dict(rule,**{'class':'environment','rule_index':'stage.gates'})
        evidence = source.get('evidence', source)
        failures = evidence.get('failures', evidence.get('errors', []))
        examples = evidence.get('examples', failures)
        if not isinstance(examples, list):
            examples = [examples]
        if not examples and child_examples:
            examples = child_examples
        if not examples:
            text = execution.get('stderr') or source.get('stderr') or execution.get('error', '')
            cause = cause_line(text)
            examples = [cause] if cause else []
        item = dict(check=check, **{'class': rule['class']},
                    **policy['classes'][rule['class']],
                    failure_count=evidence.get('failure_count', len(failures) or 1),
                    examples=examples[:5], rule_index=rule['rule_index'])
        if principle is not None:
            item.update(principle=principle, principle_check=principle_check)
            if rule['check'] == 'principles' and 'principle_check' not in rule:
                key = str(principle) + '.' + str(principle_check)
                if '### ' + key + '\n' in (PACKAGE / 'references/rule-index.md').read_text():
                    item['rule_index'] = key
        if item['class'] == 'environment':
            command = execution.get('command', [])
            # Preserve the recorded command and every argument; override only TMPDIR.
            playwright = execution.get('environment', {}).get('PLAYWRIGHT_PATH') or os.environ.get('PLAYWRIGHT_PATH')
            prefix = ''
            prefix += ('PLAYWRIGHT_PATH=' + shlex.quote(playwright) if playwright
                       else 'PLAYWRIGHT_PATH="${PLAYWRIGHT_PATH:?set PLAYWRIGHT_PATH to the Playwright module path}"')
            item['rerun_command'] = shlex.join([sys.executable,'-B',str(PACKAGE/'scripts/blueprint.py'),'rerun-env','--out',str(c.out)])
        entries.append(item)

    for check, status in report.get('checks', {}).items():
        if status.get('passed') is not False:
            continue
        if check == 'principles':
            failed = [row for row in reports.get('principles', {}).get('checks', []) if row.get('status') == 'fail']
            for row in failed:
                classify(check, row, row.get('principle'), row.get('check'))
            if failed:
                continue
        source = reports.get(check, status)
        execution = reports.get(check+'-execution',{})
        classify(check,source,execution=execution)
    if not report.get('checks') and not report.get('passed'):
        classify('acceptance',dict(errors=['S7 验收记录缺失或未通过']))
    result=dict(schema='blocked-report/1',status='failed',preview=str(preview),entries=entries,
                review_items=len(reports.get('principles',{}).get('review_items',[])))
    c.save('stage7/blocked-report.json',result)
    lines=['# 验收失败', '', '预览路径：`'+str(preview)+'`', '', '最终状态：failed。按 run-recovery.md 自行恢复；无法完成则记录原因与证据后结束。']
    for item in entries:
        lines += ['', '- '+item['check']+'：'+item['action']+'；规则：`'+item['rule_index']+'`；证据：'+json.dumps(item['examples'],ensure_ascii=False)]
        if item['class']=='environment':lines += ['  补跑：`'+report.get('environment_rerun_command','')+'`']
    write(c.work / 'stage7/blocked-report.md', ('\n'.join(lines) + '\n').encode())
    return result


def stage3_fingerprints(c):
    paths = {'ledgers/stage2.json':c.inputs/'ledgers/stage2.json',
             'ledgers/stage3.json':c.inputs/'ledgers/stage3.json',
             'stage2/hierarchy.json':c.work/'stage2/hierarchy.json',
             'stage3/review.json':c.work/'stage3/review.json',
             'stage3/review.md':c.work/'stage3/review.md'}
    for name in ('ledgers/summaries.json', 'ledgers/review-narrative.md', 'ledgers/stage4.json'):
        if (c.inputs/name).is_file():paths[name]=c.inputs/name
    if (c.work/'stage2/granularity.json').is_file():paths['stage2/granularity.json']=c.work/'stage2/granularity.json'
    return {name:digest(path.read_bytes()) for name,path in sorted(paths.items())}


def validate_stage3_lock(c):
    path=c.work/'stage3/lock.json'
    if not path.is_file():raise ValueError('stage3-lock-missing: run S3 build')
    lock=read(path)
    if (lock.get('passed') is not True or c.load('stage3/review.json').get('passed') is not True
            or lock.get('sha256')!=stage3_fingerprints(c)):
        raise ValueError('stage3-lock-stale: ledger or hierarchy changed after review')
    return lock


def deliver(c):
    validate_stage3_lock(c)
    from stage_engine import prepare_candidate
    from publish_site import publish
    candidate, site, assets = prepare_candidate(c)
    acceptance = c.load('stage7/acceptance.json') if (c.work / 'stage7/acceptance.json').exists() else {'passed': False}
    if not acceptance['passed']:
        report_path = c.work / 'stage7/blocked-report.md'
        c.save('stage8/candidate.json', dict(path=str(site), published=False, reason='S7 gates not passed',
                                           preview=True, blocked_report=str(report_path)))
        if not report_path.exists() or not (c.work / 'stage7/blocked-report.json').exists():
            blocked_report(c, acceptance)
        blocked = read(c.work / 'stage7/blocked-report.json')
        if blocked.get('preview') != str(site):
            blocked = blocked_report(c, acceptance)
        notice = site / '未验收预览.md'
        if not notice.exists():
            write(notice, ('本目录是未通过 S7 验收的预览，不是交付物。\n\n阻塞报告：['
                           'work/stage7/blocked-report.md](' + str(report_path) + ')\n').encode())
        raise BlockedRun({'class': 'blocked', 'preview': str(site), 'blocked_report': str(report_path),
                          'blocking_classes': sorted({row['class'] for row in blocked['entries']})})
    result = publish(c.out.parent, c.out, candidate, frozen_assets=assets)
    delivered = Path(result['deliverable'])
    hashes = {str(p.relative_to(site)): digest(p.read_bytes()) for p in site.rglob('*') if p.is_file()}
    actual = {str(p.relative_to(delivered)): digest(p.read_bytes()) for p in delivered.rglob('*') if p.is_file()}
    if actual != hashes:
        raise ValueError('Publication changed browser-validated bytes')
    c.save('stage8/candidate.json', dict(path=str(site), published=True,
                                       deliverable=str(delivered), validated_hashes=actual))
    report = ('# ' + c.load('renderer-input.json')['semanticRoot']['symbol'] +
              '\n\n[交付页面](deliverable/roundtrip/index.html) · [实际验收记录](work/stage7/acceptance.json)\n\n' +
              '实际计数：' + json.dumps(counts(c), ensure_ascii=False) + '\n\n实际验收：\n```json\n' +
              json.dumps(acceptance, ensure_ascii=False, indent=2) + '\n```\n')
    write(c.out / 'REPORT.md', report.encode())
    return result
