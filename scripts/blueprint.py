#!/usr/bin/env python3
"""Fixed stage interface. Semantic input is data; scripts and outputs are not model-editable."""
import argparse,json,os,re,sys,time
from pathlib import Path
sys.dont_write_bytecode=True
from ledger_lib import Context,PACKAGE,read,write,digest,fingerprint
from stage_engine import BUILD,TRIPLE,stage0_input,validate_prepared_event_macro_pins
from pipeline_reports import observe

def validate(c,n):
 errors=[]
 if n==0:
  try:
   mode,request=stage0_input(c)
   if mode=='prepared':
    raw=read(c.inputs/'raw-body.json');pins=read(c.inputs/'input-pins.json')
    validate_prepared_event_macro_pins(raw,pins)
    if raw.get('owner_def_path_hash')!=pins['definition_row']['def_path_hash']:errors.append('raw owner != definition')
    if not raw.get('basic_blocks'):errors.append('raw body is empty')
  except (ValueError,KeyError,FileNotFoundError) as e:errors.append(str(e))
 elif n==1:
  if not (c.work/'raw-body.json').is_file():errors.append('run S0 build first')
 elif n in (2,3,4,5):
  try:
   l=c.ledger(n)
   if n==2:
    if any('basic_block_order' in node or 'group_order_basis' in node for node in l.get('nodes',[])):
     raise ValueError('model-redundant-field: authored BB/group order')
    if any(row.get('category')=='instrumentation' for row in l.get('granularity',{}).get('technicalBlocks',[])):
     raise ValueError('model-redundant-field: authored instrumentation')
    if any(set(row)&{'factSha256','operationKinds','operationProofs','terminatorProof','purityWitnessRef','resumeState','resumeTarget'} for row in l.get('granularity',{}).get('technicalBlocks',[])):
     raise ValueError('model-redundant-field: authored MIR witness shape')
    from ledger_lib import validate_s2_purpose_groups,validate_display_identifiers,S2_DISPLAY_FIELDS
    from ledger_lib import validate_local_mechanism_items
    validate_local_mechanism_items(l.get('selection',{}),
                                   action_ids={node['id'] for node in l.get('nodes',[]) if node.get('kind')=='action'})
    display_warnings=validate_display_identifiers(l,S2_DISPLAY_FIELDS)
    c.save('display-warnings/S2.json',display_warnings)
    validate_s2_purpose_groups(l,c.load('facts/call-bindings.json'))
    from canonical_stages import ownership, prepare_instrumentation_ledger
    l, _ = prepare_instrumentation_ledger(l,c.load('facts/instrumentation-candidates.json'),c.load('facts/elements.json'))
    from classification_registry import load_event_macro_artifacts
    nodes,_=ownership(l,c.load('facts/blocks.json'),c.load('facts/edges.json'),
              c.load('raw-body.json'),load_event_macro_artifacts(c.work),c.work)
    from check_model import check_context
    check_context(c,2,l,dict(nodes=nodes))
   if n==3:
    from reading_groups import review
    review(c)
   if n==4:
    if 'sourceInventory' in l:raise ValueError('model-redundant-field: authored sourceInventory')
    from ledger_lib import validate_display_identifiers,S4_DISPLAY_FIELDS
    display_warnings=validate_display_identifiers(l,S4_DISPLAY_FIELDS)
    c.save('display-warnings/S4.json',display_warnings)
    for key in ['controls','executionNodes','executionEdges']: 
     if not isinstance(l.get(key),list):errors.append('missing presentation.'+key)
   if n==5:
    from check_model import check_context
    check_context(c,5)
    from ledger_lib import validate_purpose_projection_refs
    validate_purpose_projection_refs(l,c.load('stage2/granularity.json'))
    from ledger_lib import validate_local_mechanism_items
    validate_local_mechanism_items(c.ledger(2).get('selection',{}),actors=l.get('actors',[]))
    for key in ['actors','messages','business_members']:
     if not isinstance(l.get(key),list):errors.append('missing external.'+key)
  except (ValueError,KeyError,FileNotFoundError) as e:errors.append(str(e))
 elif n==6:
  for f in ['stage2/hierarchy.json','stage4/presentation.json','stage5/external.json']:
   if not (c.work/f).is_file():errors.append('missing prerequisite: '+f)
 elif n in (7,8):
  if n==7:
   from check_model import check_context
   try:check_context(c,7)
   except (ValueError,KeyError,FileNotFoundError) as e:errors.append(str(e))
  for f in TRIPLE:
   if not (c.work/f).is_file():errors.append('missing generated artifact: '+f)
 return {'passed':not errors,'scope':'input shape only; does not certify final acceptance','errors':errors}

def main():
 if len(sys.argv)>1 and sys.argv[1]=='rerun-env':
  p=argparse.ArgumentParser(description='Rerun only recorded not-run environment checks')
  p.add_argument('--out',required=True,type=Path)
  a=p.parse_args(sys.argv[2:])
  from gate_lifecycle import rerun_env
  try:result=rerun_env(a.out)
  except (ValueError,KeyError,OSError,TypeError) as exc:result=dict(passed=False,status='failed',error=str(exc))
  print(json.dumps(result,ensure_ascii=False));return 0 if result['passed'] else 1
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('stage',choices=[str(i) for i in range(9)]+['S'+str(i) for i in range(9)]);p.add_argument('operation',choices=['extract','validate','build']);p.add_argument('--inputs',required=True,type=Path);p.add_argument('--out',required=True,type=Path)
 a=p.parse_args();n=int(a.stage.lstrip('S'));c=Context(a.inputs,a.out);start=time.monotonic()
 try:
  from run_fixes import apply
  apply(c,n)
  import stage_engine as engine
  globals().update({key:getattr(engine,key) for key in ('BUILD','TRIPLE','stage0_input','validate_prepared_event_macro_pins')})
  if a.operation=='extract':
   contract_ref=f'references/stage-io.json#/stages/S{n}'
   contract=read(PACKAGE/'references/stage-io.json')['stages'][f'S{n}']
   available={}
   for row in contract['inputs']:
    base=c.inputs if row['root']=='inputs' else c.work
    for source in sorted(base.glob(row['file'])) if '<' not in row['file'] else []:
     if source.is_file():available[row['root']+'/'+str(source.relative_to(base))]=digest(source.read_bytes())
   ledgers=[row['file'] for row in contract['inputs'] if row['root']=='inputs' and row['file']==f'ledgers/stage{n}.json']
   result={'stage':n,'available':available,'ledger_path':str(c.inputs/ledgers[0]) if ledgers else None,
           'schema':'references/ledger-schema.json' if n==2 else contract_ref,
           'contract':contract_ref,'inputs':contract['inputs'],'outputs':contract['outputs']}
   c.save(f'stage{n}/available.json',result)
  else:
   result=validate(c,n);c.save(f'stage{n}/validation.json',result)
   if not result['passed']:raise ValueError('; '.join(result['errors']))
   if a.operation=='build':
    build_result=BUILD[n](c)
    if n==6:
     first={f:digest((c.work/f).read_bytes()) for f in TRIPLE};BUILD[n](c);second={f:digest((c.work/f).read_bytes()) for f in TRIPLE}
     if first!=second:raise ValueError('Non-deterministic generation')
     c.save('stage6/determinism.json',dict(passed=True,runs=2,first=first,second=second,sha256=first,method='two consecutive builds from identical inputs'))
    from canonical_contract import stage as validate_output
    validate_output(c,n)
    closure=observe(c,n,start)
    result={'stage':n,'built':True,'output_closure':closure,'result':build_result if n in (7,8) else None}
    checkpoint=dict(stage=n,input_sha256=fingerprint(c.inputs),code_sha256=fingerprint(PACKAGE/'scripts'),elapsed_seconds=time.monotonic()-start)
    if n==0:
     checkpoint['mode']=build_result['mode']
     checkpoint['missing_event_macro_closures']=build_result.get('missing_event_macro_closures',[])
    c.save(f'stage{n}/checkpoint.json',checkpoint)
  print(json.dumps(result,ensure_ascii=False));return 0
 except Exception as e:
  if a.operation=='build':observe(c,n,start,error=e)
  result={'stage':n,'operation':a.operation,'passed':False,'error_type':type(e).__name__,'error':str(e),'repair':'Classify ledger/environment/skill-bug; see references/run-recovery.md. Evidence-backed mechanism fixes belong in OUTPUT/run-fixes, then rerun all output gates.'}
  payload=getattr(e,'payload',{})
  result.update(payload)
  signature=','.join(sorted(payload['blocking_classes'])) if 'blocking_classes' in payload else re.sub(r'\d','',str(e).split('\n',1)[0])
  failure_key=f'S{n}:{a.operation}:{type(e).__name__}:'+signature
  previous_path=c.work/f'stage{n}/failure.json'
  previous=read(previous_path) if previous_path.exists() else {}
  attempt=previous.get('attempt',0)+1 if previous.get('failure_key')==failure_key else 1
  result.update(failure_key=failure_key,attempt=attempt,max_attempts=3,stop=attempt>=3)
  result['repair']+=' 同一失败重复 3 次即以 failed 结束，保留原因与证据。'
  c.save(f'stage{n}/failure.json',result);print(json.dumps(result,ensure_ascii=False));return 1
if __name__=='__main__':raise SystemExit(main())
