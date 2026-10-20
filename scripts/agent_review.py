"""Evidence-bound agent decisions; absent or stale correctness evidence fails."""
import json
from pathlib import Path
from ledger_lib import digest, encode


def question_digest(principle, check, reason, evidence):
    return digest(encode(dict(principle=principle,check=check,reason=reason,evidence=evidence)))


def decide(work, decision, principle, check, reason, evidence):
    result = dict(principle=principle,check=check,reason=reason,evidence=evidence,
                  question_sha256=question_digest(principle,check,reason,evidence))
    if principle == 'P7' and check in {'locks_iterators','debug_process','analyzer_notes','repeated_long_labels'}:
        return dict(result,status='warning',decision='wording hint',failure='Text heuristic requires no correctness gate')
    errors = []
    if not isinstance(decision,dict): errors.append('agent decision missing')
    else:
        subject=Path(work)/'renderer-input.json'
        if not subject.is_file() or decision.get('subject_sha256')!=digest(subject.read_bytes()): errors.append('stale reviewed renderer input')
        if decision.get('question_sha256') != result['question_sha256']: errors.append('stale or different review question')
        if decision.get('decision') not in ('pass','fail','warning'): errors.append('agent must decide pass/fail or an evidenced environment warning')
        if decision.get('decision')=='warning':
            gate=evidence.get('environment_gate')
            receipt=Path(work)/('stage7/'+str(gate)+'-execution.json')
            try: environment=json.loads(receipt.read_text())
            except (OSError,ValueError): environment={}
            refs=decision.get('evidence',[])
            relative='stage7/'+str(gate)+'-execution.json'
            if not gate or environment.get('status')!='not-run' or not any(isinstance(ref,dict) and ref.get('path')==relative for ref in refs):
                errors.append('warning requires a declared environment gate and its current not-run receipt')
        if not str(decision.get('rationale','')).strip(): errors.append('specific rationale missing')
        refs = decision.get('evidence',[])
        if not isinstance(refs,list) or not refs: errors.append('current evidence missing')
        for ref in refs if isinstance(refs,list) else []:
            try:
                path = (Path(work)/ref['path']).resolve()
                if not path.is_relative_to(Path(work).resolve()): raise ValueError('evidence escapes work')
                content = path.read_bytes()
                if digest(content) != ref['sha256']: raise ValueError('stale evidence SHA')
                if 'pointer' in ref:
                    value=json.loads(content)
                    for part in ref['pointer'].lstrip('/').split('/') if ref['pointer'] else []:
                        part=part.replace('~1','/').replace('~0','~')
                        value=value[int(part)] if isinstance(value,list) else value[part]
            except (KeyError,IndexError,TypeError,ValueError,OSError) as exc: errors.append(str(exc))
    if errors: return dict(result,status='fail',failure='; '.join(errors))
    return dict(result,status=decision['decision'],agent_decision=decision)
