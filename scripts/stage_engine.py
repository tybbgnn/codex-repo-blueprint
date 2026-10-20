"""Fixed stage implementation; no per-body code or baseline reads.
Mechanical lineage: historical stage1.py, convert.py; current partition,
source_ranges, derive_contract_fields and publish_site helpers.
"""
import copy,collections,hashlib,json,re,shutil,subprocess,sys,time,os
from pathlib import Path
from ledger_lib import PACKAGE,read,write,encode,digest,fingerprint
DEPTH={'root':0,'phase':1,'goal':1.5,'action':2,'bb_group':3,'bb':4}
KINDS={'goal_flow','scope_entry','scope_handoff','collaboration','wait_annotation','resume_annotation','result_annotation','runtime_annotation','internal_member_relation'}
TRIPLE=('renderer-input.json','reading-summaries.json','basic-block-details.json')

def stage0_input(c):
 request_path=c.inputs/'request.json'
 if not request_path.is_file():return 'prepared',None
 request=read(request_path)
 required=('identity','definitions','mir_bodies','source_workspace','renderer_version')
 missing=[name for name in required if name not in request]
 if missing:raise ValueError('request.json missing fields: '+', '.join(missing))
 identity=request['identity']
 if not isinstance(identity,(str,dict)):raise ValueError('request.identity must be a string or object')
 for name in required[1:4]:
  value=request[name]
  if not isinstance(value,str) or not value:raise ValueError('request.'+name+' must be a nonempty path')
  path=Path(value).expanduser()
  if not path.is_absolute():path=c.inputs/path
  path=path.resolve(strict=True)
  if name=='source_workspace' and not path.is_dir():raise ValueError('request.source_workspace must be a directory')
  if name!='source_workspace' and not path.is_file():raise ValueError('request.'+name+' must be a file')
  request[name]=path
 version=request['renderer_version']
 if not isinstance(version,str) or re.fullmatch(r'[0-9a-f]{64}',version) is None:
  raise ValueError('request.renderer_version must be a lowercase SHA-256')
 return 'request',request

def _definition_hashes(value):
 found=set();pending=[value]
 while pending:
  current=pending.pop()
  if isinstance(current,dict):pending.extend(current.values())
  elif isinstance(current,list):pending.extend(current)
  elif isinstance(current,str) and re.fullmatch(r'[0-9a-fA-F]{32}',current):found.add(current.lower())
 return found

def _build_definitions_index(definitions,row,raw):
 from resolve_bodies import scan_definitions
 wanted=_definition_hashes(raw)|_definition_hashes(row)
 found={row['def_path_hash'].lower():row}
 while wanted-set(found):
  rows=list(scan_definitions(definitions,'def_path_hash',wanted-set(found)))
  matched={item['def_path_hash'].lower():item for item,_ in rows}
  found.update(matched)
  for item in matched.values():wanted.update(_definition_hashes(item.get('ownership',{})))
  if not matched:break
 return {key:found[key] for key in sorted(found)}

def _renderer_lock(version):
 rows=read(PACKAGE/'assets/frozen-renderers/manifest.json')
 matches=[row for row in rows if row.get('assets',{}).get('app.bundle.js',{}).get('sha256')==version]
 if len(matches)!=1:raise ValueError('renderer_version matched '+str(len(matches))+' frozen renderer rows')
 row=copy.deepcopy(matches[0]);row.pop('body',None)
 for asset in row.get('assets',{}).values():asset.pop('accepted_source',None)
 return row

def _definitions_source(path):
 data=read(path)
 if (isinstance(data,dict) and set(data)=={'schema_version','definitions_path'}
     and data.get('schema_version')==1 and isinstance(data.get('definitions_path'),str)):
  target=Path(data['definitions_path']).expanduser().resolve(strict=True)
  if not target.is_file():raise ValueError('definitions reference must resolve to a file')
  return target
 return path

_EVENT_MACRO_SOURCE=re.compile(r'(?:^|/)tracing-[^/]+/src/macros\.rs$')

def _event_macro_closure_hash(term):
 """Return only the closure key accepted by classify._event_callee's Fn::call shape."""
 if term.get('kind')!='Call':return None
 constant=term.get('detail',{}).get('func',{}).get('detail',{}).get('constant',{})
 typ=constant.get('type',{});value=constant.get('value',{})
 identity=re.search(r'FnDef\(DefId\([^~]+~\s*([A-Za-z_]\w*)\[[^]]+\]::([^),]+)',
                    constant.get('value_debug',''))
 if (typ.get('kind')!='FnDef' or value.get('kind')!='FnDef'
     or not typ.get('def_path_hash')
     or value.get('detail',{}).get('definition',{}).get('def_path_hash')!=typ.get('def_path_hash')
     or not identity or identity.groups() not in (('core','ops::function::Fn::call'),('tracing_core','dispatcher::get_default'))):
  return None
 closures=[arg.get('type',{}) for arg in typ.get('generic_args',[])
           if arg.get('kind')=='Type' and arg.get('type',{}).get('kind')=='Closure']
 if len(closures)!=1:return None
 closure=closures[0]
 display=closure.get('display','').replace('\\','/').split('@',1)[-1].rsplit(':',4)[0]
 owner=closure.get('def_path_hash')
 return owner if re.fullmatch(r'[0-9a-f]{32}',owner or '') and _EVENT_MACRO_SOURCE.search(display) else None

def _event_macro_closure_hashes(raw):
 return sorted({owner for block in raw.get('basic_blocks',[])
                for owner in [_event_macro_closure_hash(block.get('terminator',{}))] if owner})

def validate_prepared_event_macro_pins(raw,pins):
 present={pin.get('def_path_hash') for pin in pins.get('event_macro_closures',[])}
 missing=[]
 for owner in _event_macro_closure_hashes(raw):
  if owner in present:continue
  refs=sorted({'call:'+str(block['basic_block']) for block in raw.get('basic_blocks',[])
               if _event_macro_closure_hash(block.get('terminator',{}))==owner},key=lambda x:int(x.split(':')[1]))
  missing.append('prepared inputs lack event-macro pin: '+owner+' (Fn::call at '+', '.join(refs)+')')
 if missing:raise ValueError('; '.join(missing))

def inner_body_inventory(raw,definitions,pins):
 """Inventory closure/coroutine identities referenced in this body, without ownership filtering."""
 owner=raw.get('owner_def_path_hash');found={}
 pinned={pin.get('def_path_hash') for pin in pins.get('event_macro_closures',[])}
 def nodes(value):
  if isinstance(value,dict):
   yield value
   for child in value.values():yield from nodes(child)
  elif isinstance(value,list):
   for child in value:yield from nodes(child)
 def entry(key):
  if key not in found:
   row=definitions.get(key);r=row or {};parent=r.get('ownership',{}).get('parent_def_path_hash')
   found[key]=dict(def_path_hash=key,definition=row,canonical_path=r.get('identity',{}).get('canonical_path'),
    closure_kind=r.get('detail',{}).get('closure_kind'),def_kind=r.get('rustc',{}).get('def_kind'),
    parent_def_path_hash=parent,owned=bool(parent and parent==owner),
    body_available=r.get('representations',{}).get('mir',{}).get('body_available'),
    source=r.get('source'),constructions=set(),callRefs=set(),otherRefs=set(),eventMacroPinned=key in pinned)
  return found[key]
 for block in raw.get('basic_blocks',[]):
  bb='bb'+str(block['basic_block'])
  for i,stmt in enumerate(block.get('statements',[])):
   for node in nodes(stmt):
    key=node.get('def_path_hash') if node.get('kind') in ('Closure','Coroutine') else None
    if key and key!=owner:entry(key)['otherRefs'].add(bb)
    if node.get('kind')=='Aggregate':
     agg=node.get('detail',{}).get('aggregate_kind',{})
     key=agg.get('detail',{}).get('definition',{}).get('def_path_hash')
     if agg.get('kind') in ('Closure','Coroutine') and key and key!=owner:
      item=entry(key);item['constructions'].add(bb+'['+str(stmt.get('statement_index',i))+']');item['otherRefs'].add(bb)
  term=block.get('terminator',{})
  if term.get('kind')=='Call':
   destination=term.get('detail',{}).get('destination')
   if isinstance(destination,dict) and destination.get('projection')==[]:
    local=next((item for item in raw.get('locals',[]) if item.get('local')==destination.get('local')),None)
    result_type=(local or {}).get('type',{})
    key=result_type.get('def_path_hash') if result_type.get('kind') in ('Closure','Coroutine') else None
    if key and key!=owner:entry(key)['callRefs'].add('call:'+str(block['basic_block']))
  for node in nodes(term):
   key=node.get('def_path_hash') if node.get('kind') in ('Closure','Coroutine') else None
   if key and key!=owner:
    entry(key)['callRefs' if term.get('kind')=='Call' else 'otherRefs'].add('call:'+str(block['basic_block']) if term.get('kind')=='Call' else bb)
 for item in found.values():
  for name in ('constructions','callRefs','otherRefs'):item[name]=sorted(item[name],key=lambda x:tuple(map(int,re.findall(r'\d+',x))))
 return [found[key] for key in sorted(found)]

def _closure_extract_inputs(c,request,resolved,scratch):
 """Keep frozen extraction usable when a macro definition points outside SOURCE_WORKSPACE."""
 row=resolved['definition_row'];source=row.get('source',{});workspace=request['source_workspace']
 source_file=source.get('file')
 candidate=(Path(source_file) if Path(source_file or '').is_absolute() else workspace/str(source_file)).resolve()
 if source_file and candidate.is_relative_to(workspace) and candidate.is_file():
  return request['definitions'],resolved
 call_site=source.get('call_site') or {};call_file=call_site.get('file')
 call_path=(workspace/str(call_file)).resolve() if call_file else None
 if (not source.get('from_expansion') or not call_path or not call_path.is_relative_to(workspace)
     or not call_path.is_file()):
  raise ValueError('closure source is outside workspace without an in-workspace macro call site')
 adapted=copy.deepcopy(resolved);adapted_row=adapted['definition_row']
 adapted_row['source']['file']=str(call_path.relative_to(workspace))
 if isinstance(call_site.get('span'),dict):adapted_row['source']['span']=copy.deepcopy(call_site['span'])
 definitions=scratch/'extract-definitions.json'
 write(definitions,{'meta':{'commit':c.load('input-pins.json')['commit']},
                    'targets':[{'definitions':[adapted_row]}]})
 return definitions,adapted

def _generate_event_macro_pins(c,request):
 """Resolve and extract exact closure MIR artifacts referenced by event-macro Fn::call sites."""
 from resolve_bodies import scan_definitions
 raw=c.load('raw-body.json');pins=[];missing=[]
 for owner in _event_macro_closure_hashes(raw):
  rows=list(scan_definitions(request['definitions'],'def_path_hash',{owner}))
  if len(rows)!=1:
   missing.append({'def_path_hash':owner,'reason':'definition count '+str(len(rows))});continue
  row=rows[0][0]
  if (row.get('rustc',{}).get('def_kind')!='Closure'
      and row.get('detail',{}).get('closure_kind')!='Closure'):
   missing.append({'def_path_hash':owner,'reason':'definition is not a closure'});continue
  scratch=c.out.parent/'.stage0-event-macro'/owner
  command=[sys.executable,'-B',str(PACKAGE/'scripts/resolve_bodies.py'),'--input',owner,
           '--definitions',str(request['definitions']),'--mir-bodies',str(request['mir_bodies']),
           '--output-root',str(scratch/'resolve')]
  result=subprocess.run(command,capture_output=True,text=True,timeout=1800)
  if result.returncode:
   missing.append({'def_path_hash':owner,'reason':'resolver failed'});continue
  items=read(scratch/'resolve/_inputs/bodies.json').get('items',[])
  if len(items)!=1 or items[0].get('status')!='resolved':
   reason=items[0].get('reason') if len(items)==1 else 'resolver did not return one item'
   missing.append({'def_path_hash':owner,'reason':reason or 'unresolved'});continue
  try:
   definitions,resolved=_closure_extract_inputs(c,request,items[0],scratch)
  except ValueError as exc:
   missing.append({'def_path_hash':owner,'reason':str(exc)});continue
  extract_out=scratch/'extract'
  command=[sys.executable,'-B',str(PACKAGE/'scripts/extract_body.py'),
           '--resolved-row',json.dumps(resolved,ensure_ascii=False,sort_keys=True),
           '--definitions',str(definitions),'--mir-bodies',str(request['mir_bodies']),
           '--workspace',str(request['source_workspace']),'--out',str(extract_out)]
  result=subprocess.run(command,capture_output=True,text=True,timeout=1800)
  if result.returncode:
   missing.append({'def_path_hash':owner,'reason':'extractor failed'});continue
  content=(extract_out/'raw-body.json').read_bytes()
  artifact=json.loads(content)
  if artifact.get('owner_def_path_hash')!=owner:
   missing.append({'def_path_hash':owner,'reason':'extracted owner mismatch'});continue
  relative='pins/event-macro/'+owner+'.json'
  c.save(relative,content)
  pins.append({'path':relative,'sha256':digest(content),'def_path_hash':owner})
 if missing:raise ValueError('event-macro-pins-missing: '+json.dumps(missing,ensure_ascii=False,sort_keys=True))
 return sorted(pins,key=lambda pin:pin['def_path_hash']),[]

def _run_stage0_request(c,request):
 identity=request['identity'] if isinstance(request['identity'],str) else json.dumps(request['identity'],ensure_ascii=False,sort_keys=True)
 request_sha=digest((c.inputs/'request.json').read_bytes())
 resolver_root=c.out.parent/'.stage0-resolve'/request_sha
 command=[sys.executable,'-B',str(PACKAGE/'scripts/resolve_bodies.py'),'--input',identity,
          '--definitions',str(request['definitions']),'--mir-bodies',str(request['mir_bodies']),
          '--output-root',str(resolver_root)]
 # Large definitions and MIR containers can require a full scan before a unique body is resolved.
 result=subprocess.run(command,capture_output=True,text=True,timeout=1800)
 if result.returncode:raise ValueError('Body resolver failed: '+(result.stderr.strip() or result.stdout.strip()))
 report=read(resolver_root/'_inputs/bodies.json');items=report.get('items',[])
 if len(items)!=1 or items[0].get('status')!='resolved':raise ValueError('Body resolver did not produce exactly one resolved item')
 resolved=copy.deepcopy(items[0])
 # Resolver output locations are execution metadata, not body identity or extraction evidence.
 resolved.pop('out',None)
 c.save('stage0/resolved-row.json',resolved)
 command=[sys.executable,'-B',str(PACKAGE/'scripts/extract_body.py'),
          '--resolved-row',json.dumps(resolved,ensure_ascii=False,sort_keys=True),
          '--definitions',str(request['definitions']),'--mir-bodies',str(request['mir_bodies']),
          '--workspace',str(request['source_workspace']),'--out',str(c.work)]
 # Extraction verifies pinned slices and source metadata, which can be slow on large workspaces.
 result=subprocess.run(command,capture_output=True,text=True,timeout=1800)
 if result.returncode:raise ValueError('Body extractor failed: '+(result.stderr.strip() or result.stdout.strip()))
 write(c.inputs/'definitions.json',{'schema_version':1,'definitions_path':str(request['definitions'])})
 write(c.inputs/'renderer-lock.json',_renderer_lock(request['renderer_version']))
 c.save('facts/definitions-index.json',_build_definitions_index(
        request['definitions'],c.load('input-pins.json')['definition_row'],c.load('raw-body.json')))
 rules=(PACKAGE/'resources/rules.json').read_bytes();c.save('rules.json',rules)
 pins=c.load('input-pins.json')
 if isinstance(pins.get('inputs',{}).get('mir_cache'),dict):
  pins['inputs']['mir_cache']['manifest']=None
 pins['rules']={'path':str(PACKAGE/'resources/rules.json'),'size_bytes':len(rules),
                'sha256':digest(rules),'hash_scope':'full-file'}
 pins['event_macro_closures'],missing=_generate_event_macro_pins(c,request)
 c.save('input-pins.json',pins)
 return missing

def information_mir_pins(raw,path,pins=None,elements=None):
 from check_model import InformationRule
 if pins is None:raise ValueError('information pin generation requires definitions and input provenance')
 rule=InformationRule(pins,generate=True)
 if elements is not None:rule.decisions(raw,elements)
 else:
  # Call-site-only inventory; S1 adds recovered erased futures and verifies completeness.
  items=[]
  for block in raw['basic_blocks']:
   term=block['terminator']
   if term['kind']=='Call':
    from check_model import fhash,fname
    h=fhash(term['detail']['func']);row=rule.access.definition(h) if h else None
    items.append(dict(id='call:'+str(block['basic_block']),kind='call',bb='bb'+str(block['basic_block']),
      source_info=term.get('source_info',{}),callee=dict(def_path_hash=h,canonical_path=(row or {}).get('identity',{}).get('canonical_path')),
      targetCategory='local_mir' if row else 'third_party'))
  rule.decisions(raw,dict(items=items))
 rule.access.finish()
 return pins['information_mir_slices']

def _validate_stage0_product(c):
 pins=c.load('input-pins.json');raw=c.load('raw-body.json');row=pins['definition_row']
 if raw['owner_def_path_hash']!=row['def_path_hash']:raise ValueError('Raw owner identity mismatch')
 if not isinstance(raw.get('basic_blocks'),list) or not raw['basic_blocks']:raise ValueError('Raw body is empty')
 mir_pin=pins.get('inputs',{}).get('mir_bodies',{}).get('slice',{})
 raw_bytes=(c.work/'raw-body.json').read_bytes()
 if mir_pin.get('sha256') and digest(raw_bytes)!=mir_pin['sha256']:raise ValueError('Raw body differs from MIR slice pin')
 rules=(c.work/'rules.json').read_bytes();rules_pin=pins.get('rules',{})
 if rules_pin and (rules_pin.get('sha256')!=digest(rules) or rules_pin.get('size_bytes')!=len(rules)):raise ValueError('Rules pin differs from copied rules')
 for pin in pins.get('event_macro_closures',[])+([pins['async_shell_prelude']] if pins.get('async_shell_prelude') else []):
  p=(c.work/pin['path']).resolve()
  if not p.is_relative_to(c.work):raise ValueError('Pinned path escapes work output')
  data=p.read_bytes()
  if digest(data)!=pin['sha256']:raise ValueError('Pinned raw bytes changed: '+pin['path'])
  if pin in pins.get('event_macro_closures',[]) and json.loads(data).get('owner_def_path_hash')!=pin.get('def_path_hash'):
   raise ValueError('Pinned closure owner changed: '+pin['path'])
 return raw_bytes

def stage0(c):
 mode,request=stage0_input(c)
 missing=[]
 if mode=='request':missing=_run_stage0_request(c,request)
 else:
  for name in ['raw-body.json','input-pins.json','rules.json','classification.json','facts/definitions-index.json']:
   p=c.inputs/name
   if p.exists():c.save(name,p.read_bytes())
  for p in sorted((c.inputs/'source').rglob('*')):
   if p.is_file():c.save(str(p.relative_to(c.inputs)),p.read_bytes())
  pins=read(c.inputs/'input-pins.json')
  validate_prepared_event_macro_pins(read(c.inputs/'raw-body.json'),pins)
  for pin in pins.get('event_macro_closures',[])+([pins['async_shell_prelude']] if pins.get('async_shell_prelude') else []):
   p=(c.inputs/pin['path']).resolve()
   if not p.is_relative_to(c.inputs):raise ValueError('Pinned path escapes inputs')
   data=p.read_bytes()
   if digest(data)!=pin['sha256']:raise ValueError('Pinned raw bytes changed: '+pin['path'])
   c.save(pin['path'],data)
 pins=c.load('input-pins.json')
 # Ignore developer-supplied information pins; both modes generate their own demand set.
 pins['information_mir_slices']=[];pins['callee_mir_slices']=[]
 pins['information_mir_aliases']=[];pins['missing_mir']=[]
 information_mir_pins(c.load('raw-body.json'),Path(pins['inputs']['mir_bodies']['path']),pins)
 c.save('input-pins.json',pins)
 raw_bytes=_validate_stage0_product(c)
 c.save('stage0/input-sha256.json',fingerprint(c.inputs))
 c.save('raw-body.slice-sha256.txt',f'{digest(raw_bytes)}  {len(raw_bytes)}\n'.encode())
 return {'mode':mode,'missing_event_macro_closures':missing}
def _mir_nodes(value):
 if isinstance(value,dict):
  yield value
  for child in value.values():yield from _mir_nodes(child)
 elif isinstance(value,list):
  for child in value:yield from _mir_nodes(child)

def _flow_place(place):
 return (place.get('local'),tuple((step.get('kind'),step.get('detail',{}).get('field_index'),
          step.get('detail',{}).get('variant_index'),step.get('detail',{}).get('index'))
          for step in place.get('projection',[])))

def prove_returned_coroutine(raw):
 """Prove returned value identity, not purity of the constructor's prelude."""
 from classify import _fn_identity
 blocks={b['basic_block']:b for b in raw.get('basic_blocks',[])}
 values={};sites={};path=[];pins=[];current=0
 def token(place):
  if place.get('projection'):return None
  return values.get(place.get('local'))
 try:
  while current not in path and current in blocks:
   path.append(current);block=blocks[current]
   if block.get('is_cleanup'):return None
   for index,statement in enumerate(block.get('statements',[])):
    if statement['kind'] in ('StorageLive','StorageDead','Nop'):continue
    if statement['kind']!='Assign':return None
    detail=statement['detail'];destination=detail['destination'];rv=detail['rvalue'];rd=rv.get('detail',{})
    if destination.get('projection'):return None
    result=None
    if rv['kind']=='Aggregate' and rd.get('aggregate_kind',{}).get('kind')=='Coroutine':
     owner=rd['aggregate_kind']['detail']['definition']['def_path_hash'];result=(owner,current,statement.get('statement_index',index));sites[result]=True
    elif rv['kind']=='Use':result=token(rd.get('operand',{}).get('detail',{}).get('place',{}))
    elif rv['kind']=='Cast' and re.fullmatch(r'PointerCoercion\(Unsize, (Implicit|AsCast)\)',rd.get('cast_kind','')):
     result=token(rd.get('operand',{}).get('detail',{}).get('place',{}))
    elif any(token(node) for node in _mir_nodes(rv) if 'local' in node and 'projection' in node):return None
    values[destination['local']]=result
   term=block['terminator'];detail=term.get('detail',{});kind=term['kind']
   if kind=='Return':
    result=values.get(0)
    if not result:return None
    return dict(coroutineDefPathHash=result[0],constructionBb=result[1],constructionStatement=result[2],returnBb=current,normalPath=path,pinCallBlocks=pins)
   if kind=='Call':
    identity=_fn_identity(term);args=detail.get('args',[]);tokens=[token(arg.get('detail',{}).get('place',{})) for arg in args]
    result=None
    if any(tokens):
     if not (identity and identity[0] in ('alloc','std') and identity[1].startswith('boxed::') and identity[1].endswith('::pin') and len(tokens)==1 and tokens[0]):return None
     result=tokens[0];pins.append(current)
    destination=detail.get('destination',{})
    if destination.get('projection'):return None
    values[destination['local']]=result;current=detail['target']
   elif kind=='Goto':current=detail['target']
   elif kind=='Drop' and not token(detail.get('place',{})):current=detail['target']
   else:return None
 except (KeyError,TypeError,ValueError):return None
 return None

def prove_caller_future_flow(raw,call):
 """Follow one returned erased future through exact moves/borrows/standard adapters to poll."""
 from classify import _fn_identity
 blocks={b['basic_block']:b for b in raw['basic_blocks']};aliases={_flow_place(call['destination'])};path=[call['bb']];calls=[call['id']]
 current=call['normal_successor'];seen=set()
 def contains(place):
  return (_flow_place(place) in aliases or all(step.get('kind')=='Deref' for step in place.get('projection',[])) and (place.get('local'),()) in aliases)
 while current and current not in seen:
  seen.add(current);path.append(current);block=blocks[int(current[2:])]
  for statement in block.get('statements',[]):
   if statement['kind']=='StorageDead':
    local=statement.get('detail',{}).get('local');aliases={key for key in aliases if key[0]!=local};continue
   if statement['kind']!='Assign':continue
   detail=statement['detail'];rv=detail['rvalue'];rd=rv.get('detail',{});place=rd.get('place',{}) if rv['kind']=='Ref' else rd.get('operand',{}).get('detail',{}).get('place',{})
   destination=_flow_place(detail['destination'])
   if rv['kind'] in ('Use','Ref','Cast') and contains(place):aliases.add(destination)
   else:aliases.discard(destination)
  term=block['terminator'];detail=term.get('detail',{});kind=term['kind']
  if kind=='Call':
   used=any(contains(arg.get('detail',{}).get('place',{})) for arg in detail.get('args',[]))
   destination=_flow_place(detail.get('destination',{}))
   if used:
    identity=_fn_identity(term)
    if not identity:return None
    crate,target=identity[:2];ref='call:'+current[2:];calls.append(ref)
    if crate=='core' and target=='future::future::Future::poll':return dict(bbRefs=path,callRefs=calls,pollRef=ref)
    adapter=(crate=='core' and (target=='future::into_future::IntoFuture::into_future' or re.fullmatch(r'pin::\{impl#\d+\}::(?:new|new_unchecked|as_mut|get_mut|get_unchecked_mut)',target)))
    if not adapter:return None
    aliases.add(destination)
   else:aliases.discard(destination)
   target=detail.get('target');current='bb'+str(target) if target is not None else None
  elif kind=='Goto':current='bb'+str(detail['target'])
  else:return None
 return None

def read_callee_slice(pin,pins):
 from extract_body import object_slice
 from resolve_bodies import STAGE
 path=Path(pins.get('inputs',{}).get('mir_bodies',{}).get('path',''))
 if not path.is_file() or Path(pin['path']).resolve()!=path.resolve():raise ValueError('model-callee-pin: wrong MIR container')
 with path.open('rb') as stream:content=object_slice(stream,pin['offset_bytes'])
 if len(content)!=pin['size_bytes'] or digest(content)!=pin['sha256']:raise ValueError('model-callee-pin: changed exact MIR slice')
 raw=json.loads(content)
 if raw.get('owner_def_path_hash')!=pin['def_path_hash'] or raw.get('body_id')!='main' or raw.get('capture_stage')!=STAGE:raise ValueError('model-callee-pin: wrong body identity')
 return raw

def erased_future_bindings(raw,calls,definitions,pins):
 """Recover only MIR-proven returned coroutine identities hidden by trait erasure."""
 from resolve_bodies import scan_mir,scan_definitions
 from extract_body import object_slice
 locals_by={item['local']:item.get('type',{}) for item in raw['locals']};candidates={}
 for call in calls:
  owner=call['callee'].get('def_path_hash');definition=definitions.get(owner,{})
  destination=call.get('destination') or {};typ=locals_by.get(destination.get('local'),{})
  if destination.get('projection'):
   typ=destination['projection'][-1].get('detail',{}).get('field_type',{})
  if (definition.get('representations',{}).get('mir',{}).get('body_available')
      and typ.get('kind') not in ('Closure','Coroutine') and any(node.get('kind')=='Dynamic' for node in _mir_nodes(typ))):candidates[call['id']]=(owner,call)
 if not candidates:return {}
 from mir_access import MirAccess
 access=MirAccess(pins,generate=True)
 locators={pin['def_path_hash']:pin for pin in pins.get('callee_mir_slices',[])}
 loaded={}
 for owner,call in candidates.values():
  if owner in loaded:continue
  body=access.body(owner,line=str(call.get('source_info')))
  if body is not None:
   loaded[owner]=body;locators[owner]=access.locators[owner]
 access.finish()
 result={}
 for ref,(owner,call) in candidates.items():
  if owner not in locators:continue
  if owner not in loaded:loaded[owner]=read_callee_slice(locators[owner],pins)
  returned=prove_returned_coroutine(loaded[owner]);flow=prove_caller_future_flow(raw,call)
  if not returned or not flow:continue
  child=returned['coroutineDefPathHash']
  if child not in definitions:
   source=Path(pins.get('inputs',{}).get('definitions',{}).get('path',''))
   matches=list(scan_definitions(source,'def_path_hash',{child})) if source.is_file() else []
   if len(matches)!=1:raise ValueError('model-callee-pin: returned body definition absent')
   definitions[child]=matches[0][0]
  if definitions[child].get('ownership',{}).get('parent_def_path_hash')!=owner:raise ValueError('model-callee-pin: returned body ownership mismatch')
  result[ref]=dict(constructorMirPin=locators[owner],returned=returned,callerFlow=flow)
 return result


def element_facts(raw,definitions,pins,blocks,calls,proof):
 """One stable row per MIR element; destinations are deliberately absent."""
 from classify import fingerprint,tracing_intervals
 intervals={row['bbRef']:row for row in tracing_intervals(raw,proof)}
 rows=[]
 proven=set((proof or {}).get('technical_blocks',{}))-set((proof or {}).get('conflicts',[]))
 for ref,block in blocks.items():
  operations=[dict(statementIndex=statement.get('statement_index',index),kind=statement['kind'])
              for index,statement in enumerate(block.get('statements',[]))
              if statement['kind'] not in ('StorageLive','StorageDead')]
  evidence={'mirWitness':dict(factSha256=fingerprint(block),operations=operations,
              terminator=dict(kind=block['terminator']['kind'],successors=block['terminator']['successors']))}
  if block.get('is_cleanup'):evidence['cleanup']=dict(isCleanup=True)
  if block['terminator']['kind'] in ('UnwindResume','UnwindTerminate'):
   evidence['unwind']=dict(terminatorKind=block['terminator']['kind'])
  if ref=='bb0' and raw.get('is_coroutine') and block['terminator']['kind']=='SwitchInt':
   evidence['stateDispatch']=dict(terminatorKind='SwitchInt',isCoroutine=True)
  if block['terminator']['kind'] in ('Drop','Goto','SwitchInt'):
   safe=True
   for statement in block.get('statements',[]):
    if statement['kind'] in ('StorageLive','StorageDead'):continue
    value=statement.get('detail',{}).get('rvalue',{});operand=value.get('detail',{}).get('operand',{})
    flag=value.get('kind')=='Use' and operand.get('kind')=='Constant' and operand.get('detail',{}).get('constant',{}).get('type',{}).get('kind')=='Bool'
    selector=value.get('kind')=='Discriminant' and block['terminator']['kind']=='SwitchInt'
    if statement['kind']!='Assign' or not (flag or selector):safe=False;break
   if safe:evidence['drop']=dict(operations=operations,terminatorKind=block['terminator']['kind'])
  if ref in proven:
   evidence['instrumentation']={'factSha256':proof['technical_blocks'][ref],
     'blockRole':proof.get('block_roles',{}).get(ref),
     'eventMacroProof':proof.get('block_proofs',{}).get(ref)}
  if ref in intervals:evidence['technicalIntervals']=intervals[ref]
  rows.append(dict(id=ref,kind='bb',bb=ref,proofs=evidence))
  if block['terminator']['kind']=='SwitchInt':
   rows.append(dict(id='switch:'+ref[2:],kind='switch',bb=ref,
                    source_info=block['terminator'].get('source_info')))
 def category(call):
  definition=definitions.get(call['callee'].get('def_path_hash'))
  canonical=(definition or {}).get('identity',{}).get('canonical_path','')
  debug=call['func'].get('detail',{}).get('constant',{}).get('value_debug','')
  crate=canonical.split('::')[0] if canonical else ''
  match=re.search(r'~\s*([A-Za-z_]\w*)\[',debug)
  crate=crate or (match.group(1) if match else '')
  if crate in ('std','core','alloc','proc_macro'):return 'std'
  if definition:
   source=(definition.get('source') or {}).get('file','') or ''
   external=bool(re.search(r'(?:^|/)[^/]+-\d[^/]*/src/|/rustlib/|^/rustc/|\.cargo/registry',source))
   if not external:
    return 'local_mir' if definition.get('representations',{}).get('mir',{}).get('body_available') else 'local_no_mir'
  return 'third_party'
 erased=erased_future_bindings(raw,[call for call in calls if category(call)=='local_mir'],definitions,pins)
 for call in calls:
  row=dict(call,kind='call',targetCategory=category(call))
  if call['id'] in erased:row['proofs']={'erasedFuture':erased[call['id']]}
  rows.append(row)
 inventory={body['def_path_hash']:body for body in inner_body_inventory(raw,definitions,pins)}
 for ref,binding in erased.items():
  key=binding['returned']['coroutineDefPathHash'];definition=definitions[key]
  body=inventory.setdefault(key,dict(def_path_hash=key,definition=definition,canonical_path=definition['identity']['canonical_path'],
       def_kind=definition.get('rustc',{}).get('def_kind'),closure_kind=definition.get('detail',{}).get('closure_kind'),
       parent_def_path_hash=definition.get('ownership',{}).get('parent_def_path_hash'),owned=False,
       body_available=definition.get('representations',{}).get('mir',{}).get('body_available'),source=definition.get('source'),
       constructions=[],callRefs=[],otherRefs=[],eventMacroPinned=False))
  body['callRefs']=sorted(set(body['callRefs'])|set(binding['callerFlow']['callRefs']),key=lambda value:int(value.split(':')[1]))
  body['otherRefs']=sorted(set(body['otherRefs'])|set(binding['callerFlow']['bbRefs']),key=lambda value:int(value[2:]))
  body.setdefault('erasedFutureBindings',[]).append(ref)
 for body in [inventory[key] for key in sorted(inventory)]:
  refs=sorted(set(body['otherRefs'])|{ref.split('[')[0] for ref in body['constructions']}|
              {'bb'+ref.split(':')[1] for ref in body['callRefs']},key=lambda ref:int(ref[2:]))
  rows.append(dict(body,id='body:'+body['def_path_hash'],kind='body',bbRefs=refs,
                   constructionRefs=body['constructions']))
 from check_model import InformationRule
 rule=InformationRule(pins,generate=True)
 effects=rule.decisions(raw,{'items':rows})
 rule.access.finish()
 from check_model import fname
 for row in rows:
  if row['kind']!='call' or effects[row['id']]['new']!='shown':continue
  original=row['callee'].get('def_path_hash');actual=rule.access.resolve(original,fname(row['func'])) if original else original
  if actual==original:continue
  definition=rule.access.definition(actual)
  row['resolvedCallee']=dict(def_path_hash=actual,canonical_path=definition['identity']['canonical_path'])
  pending=[definition]
  while pending:
   definition=pending.pop();key=definition['def_path_hash']
   if key in definitions:continue
   definitions[key]=definition
   for parent in definition.get('ownership',{}).values():
    if parent and parent not in definitions:
     ancestor=rule.access.definition(parent)
     if ancestor:pending.append(ancestor)
 for row in rows:
  if row['id'] in effects:row.setdefault('proofs',{})['informationEffect']={key:value for key,value in effects[row['id']].items() if key!='new'}
 return {'schemaVersion':1,'ownerDefPathHash':raw.get('owner_def_path_hash'),'items':rows}

def stage1(c):
 from canonical_stages import stage1 as build
 from classification_registry import load_event_macro_artifacts,prove_instrumentation
 raw=c.load('raw-body.json');pins=c.load('input-pins.json')
 validate_prepared_event_macro_pins(raw,pins)
 proof=prove_instrumentation(raw,load_event_macro_artifacts(c.work))
 result=build(c,proof)
 c.save('facts/instrumentation-candidates.json',proof)
 return result
def stage2(c):
 from canonical_stages import stage2 as build
 return build(c)
def stage3(c):
 from reading_groups import review as check_reading_groups
 check_reading_groups(c)
 review=c.ledger(3)
 if review.get('passed') is not True:raise ValueError('stage3-review-failed: passed must be true')
 c.save('stage3/review.json',review)
 narrative=c.inputs/'ledgers/review-narrative.md'
 if not narrative.exists():raise ValueError('Missing authored review narrative ledger: review-narrative.md')
 c.save('stage3/review.md',narrative.read_bytes())
 from gate_lifecycle import stage3_fingerprints
 c.save('stage3/lock.json',dict(passed=True,sha256=stage3_fingerprints(c)))
def _validate_loop_members_return_to_entry(presentation,hierarchy,fact_edges,blocks=None):
 from canonical_stages import derive_loop_ranges
 return derive_loop_ranges(presentation,{'nodes':hierarchy},fact_edges,blocks or {})
def stage4(c):
 presentation=c.ledger(4);edges=read(c.inputs/'ledgers/edges.json');h=c.load('stage2/hierarchy.json')['nodes'];fact_edges=c.load('facts/edges.json');facts={e['id'] for e in fact_edges}
 if not isinstance(edges,list) and not (isinstance(edges,dict) and isinstance(edges.get('edges'),list)):raise ValueError('semantic edges must be an array or an authored object containing edges')
 rows=edges if isinstance(edges,list) else edges['edges']
 for e in rows:
  if e.get('kind') not in KINDS:raise ValueError('Invalid semantic edge kind: '+str(e.get('kind')))
  if any(m not in facts for m in e.get('members',[])):raise ValueError('Unknown edge member: '+e['id'])
 if isinstance(edges,dict):
  for transition in edges.get('transitions',[]):
   if any(member not in facts for member in transition.get('members',[])):raise ValueError('Unknown transition member: '+transition['id'])
   for path in transition.get('paths',[]):
    if any(member not in facts for member in path):raise ValueError('Unknown transition path: '+transition['id'])
 from canonicalize_controls import canonicalize
 hierarchy=c.load('stage2/hierarchy.json')
 action_ids={key:key for key,node in hierarchy['nodes'].items() if node.get('kind')=='action'}
 action_ids.update(hierarchy.get('semantic_action_ids',{}))
 granularity=c.load('stage2/granularity.json')
 presentation['sourceInventory']=copy.deepcopy(granularity.get('decisions',[]))
 summaries=c.load('stage2/reading-summaries.json')
 canonicalize(presentation,granularity.get('memberGuards',[]),action_ids,summaries)
 from canonical_stages import derive_loop_ranges
 blocks=c.load('facts/blocks.json')
 loops=derive_loop_ranges(presentation,hierarchy,fact_edges,blocks)
 execution={row['id']:row for row in presentation.get('executionNodes',[])}
 for edge in presentation.get('executionEdges',[]):
  if edge.get('kind')!='loop-exit':continue
  scope=next((row for row in presentation.get('readingScopes',[]) if row['id']==edge.get('readingScopeRef')),None)
  if scope is None:raise ValueError('Loop exit references unknown scope: '+edge['id'])
  target=execution.get(edge.get('to'),{})
  if target.get('actionRef') in loops[scope['id']]:
   edge['kind']='branch'
  elif target.get('actionRef') and target['actionRef']==scope.get('commonAfter',{}).get('actionRef'):
   continue
  elif target.get('kind')=='terminal' and any(blocks.get(ref,{}).get('terminator',{}).get('kind') in ('Return','UnwindResume','UnwindTerminate','CoroutineDrop','Unreachable') for ref in target.get('sourceEvidenceRefs',[])):
   continue
  else:raise ValueError('Loop exit target must be commonAfter or certified terminal: '+edge['id'])
 c.save('stage4/edges.json',edges);c.save('stage4/presentation.json',presentation)
 label_review=c.inputs/'ledgers/execution-label-review.json'
 if label_review.exists():c.save('stage4/execution-label-review.json',label_review.read_bytes())
HEX_RE=re.compile(r'^[0-9a-fA-F]{32}(?:[0-9a-fA-F]{32})?$')
def _endpoint_ledger(c):
 ledger=read(c.inputs/'ledgers/endpoint-ledger.json')
 def reject_hash(value,path='$'):
  if isinstance(value,dict):
   for key,item in value.items():
    if 'hash' in key.lower():raise ValueError('Endpoint ledger forbids hash fields: '+path+'/'+key)
    reject_hash(item,path+'/'+key)
  elif isinstance(value,list):
   for index,item in enumerate(value):reject_hash(item,path+'/'+str(index))
  elif isinstance(value,str) and HEX_RE.fullmatch(value):
   raise ValueError('Endpoint ledger forbids handwritten hash values: '+path)
 reject_hash(ledger)
 endpoints=ledger.get('endpoints')
 if not isinstance(endpoints,list) or not endpoints:raise ValueError('Endpoint ledger requires endpoints')
 ids=[row.get('id') for row in endpoints];actors=[row.get('actorRef') for row in endpoints]
 for row in endpoints:
  kind=row.get('kind','body')
  if kind not in ('body','declaration'):raise ValueError('Invalid endpoint kind: '+str(kind))
  row['kind']=kind
 if any(not isinstance(row.get('canonical_path'),str) or not row['canonical_path'] for row in endpoints):
  raise ValueError('Endpoint ledger requires canonical_path selectors')
 if len(ids)!=len(set(ids)) or None in ids:raise ValueError('Duplicate or missing endpoint id')
 if len(actors)!=len(set(actors)) or None in actors:raise ValueError('Duplicate or missing endpoint actorRef')
 return ledger
def _resolve_declarations(ledger,definitions,targets=None):
 from resolve_bodies import scan_definitions
 wanted={row['canonical_path'] for row in ledger['endpoints']}
 matches=collections.defaultdict(list)
 for definition,_ in scan_definitions(definitions,'canonical_path',wanted):
  path=definition.get('canonical_path') or definition.get('identity',{}).get('canonical_path')
  matches[path].append(definition)
 resolved=[]
 for request in ledger['endpoints']:
  rows=matches.get(request['canonical_path'],[])
  from endpoint_identity import select
  definition=select(request,rows,targets);identity=definition.get('def_path_hash') or definition.get('identity',{}).get('def_path_hash')
  if not identity:raise ValueError('endpoint '+request['id']+' definition has no def_path_hash')
  if definition.get('rustc',{}).get('def_kind') not in ('Fn','AssocFn'):
   raise ValueError('endpoint '+request['id']+' definition is not callable')
  resolved.append({'id':request['id'],'kind':'declaration','def_path_hash':identity,
                   'canonical_path':request['canonical_path'],'declarationRef':identity,
                   'sourceNodeRef':identity,'implementationStatus':'unresolved',
                   'ownership':definition.get('ownership',{}),'definition':definition})
 return {'endpoints':resolved}
def _resolve_stage5(c,ledger,targets=None):
 from resolve_stage5_endpoints import resolve
 from endpoint_identity import select
 targets=targets or {}
 pins=c.load('input-pins.json');input_definitions=c.inputs/'definitions.json';input_mir=c.inputs/'mir-bodies.json'
 definitions=_definitions_source(input_definitions) if input_definitions.is_file() else c.work/'facts/definitions-index.json'
 if not definitions.is_file():raise ValueError('Missing definitions or facts/definitions-index.json')
 # Kind follows pinned MIR existence, independent of definitions.body_available.
 pinned={pin['def_path_hash'] for pin in pins.get('information_mir_slices',[])+pins.get('callee_mir_slices',[])+pins.get('event_macro_closures',[])}
 if pins.get('definition_row'):pinned.add(pins['definition_row']['def_path_hash'])
 from resolve_bodies import scan_definitions
 wanted={row['canonical_path'] for row in ledger['endpoints']};matches=collections.defaultdict(list)
 for definition,_ in scan_definitions(definitions,'canonical_path',wanted):
  matches[definition.get('canonical_path') or definition.get('identity',{}).get('canonical_path')].append(definition)
 for request in ledger['endpoints']:
  found=matches[request['canonical_path']]
  definition=select(request,found,targets)
  if definition['def_path_hash'] in pinned:
   request['kind']='body'
  elif definition.get('rustc',{}).get('def_kind') in ('Fn','AssocFn'):
   request['kind']='declaration'
  else:raise ValueError('endpoint '+request['id']+' requires executable MIR; add S0 pin')
 body_ledger={'endpoints':[row for row in ledger['endpoints'] if row['kind']=='body']}
 declaration_ledger={'endpoints':[row for row in ledger['endpoints'] if row['kind']=='declaration']}
 body_resolved={'endpoints':[]}
 if body_ledger['endpoints'] and input_definitions.is_file() and input_mir.is_file():
  pending=c.work/'stage5/resolved-endpoints.pending.json';pending.parent.mkdir(parents=True,exist_ok=True)
  body_ledger_path=c.work/'stage5/body-endpoint-ledger.pending.json'
  write(body_ledger_path,encode(body_ledger))
  targets_path=c.work/'stage5/endpoint-targets.json'
  write(targets_path,targets)
  if pending.exists():
   previous=pending.read_bytes();archive=pending.parent/'.history'/digest(previous)/pending.name
   archive.parent.mkdir(parents=True,exist_ok=True)
   if not archive.exists():shutil.move(pending,archive)
  command=[sys.executable,'-B',str(PACKAGE/'scripts/resolve_stage5_endpoints.py'),'--ledger',str(body_ledger_path),'--definitions',str(definitions),'--mir-bodies',str(input_mir),'--output-root',str(c.out),'--output',str(pending),'--targets',str(targets_path),'--pins',str(c.work/'input-pins.json')]
  # Endpoint resolution may stream large definitions and MIR inputs before all selectors close.
  result=subprocess.run(command,capture_output=True,text=True,timeout=600)
  if result.returncode:raise ValueError('Endpoint resolver failed: '+result.stderr.strip())
  body_resolved=read(pending)
 elif body_ledger['endpoints']:
  try:mir=Path(pins['inputs']['mir_bodies']['path'])
  except (KeyError,TypeError):raise ValueError('Missing MIR bodies input locator')
  if not mir.is_file():raise ValueError('MIR bodies input is unavailable: '+str(mir))
  manifest=pins.get('inputs',{}).get('mir_cache',{}).get('manifest')
  cache=Path(manifest).parent if manifest and Path(manifest).is_file() else c.out/'_inputs/mir-cache'
  body_resolved=resolve(body_ledger,definitions,mir,cache,targets,pins)
 for row in body_resolved['endpoints']:row['kind']='body'
 declaration_resolved=_resolve_declarations(declaration_ledger,definitions,targets) if declaration_ledger['endpoints'] else {'endpoints':[]}
 by_id={row['id']:row for row in body_resolved['endpoints']+declaration_resolved['endpoints']}
 resolved={'endpoints':[by_id[row['id']] for row in ledger['endpoints']]}
 c.save('stage5/resolved-endpoints.json',resolved)
 return resolved
def _actors(rows):
 for actor in rows:
  yield actor
  yield from _actors(actor.get('children',[]))
def _endpoint_hash(value):
 if not isinstance(value,str):return None
 value=value.removeprefix('definition:').split('|',1)[0]
 return value.lower() if HEX_RE.fullmatch(value) else None
def _apply_endpoints(ext,ledger,resolved):
 actors={};parents={}
 def index(rows,parent=None):
  for actor in rows:
   actors[actor.get('actorId')]=actor;parents[actor.get('actorId')]=parent
   index(actor.get('children',[]),actor)
 index(ext['actors'])
 requests={row['id']:row for row in ledger['endpoints']}
 rows={row['id']:row for row in resolved.get('endpoints',[])}
 if set(rows)!=set(requests):raise ValueError('Resolved endpoint set differs from endpoint ledger')
 callable_ids={actor_id for actor_id,actor in actors.items() if actor.get('kind') in ('body','declaration')}
 if {row['actorRef'] for row in requests.values()}!=callable_ids:
  raise ValueError('Endpoint ledger must cover every callable actor exactly once')
 main_ref=ext.get('rootActorRef') or ext.get('mainActorRef')
 if not main_ref:
  roots=[actor['actorId'] for actor in ext['actors'] if actor.get('kind')=='body']
  if len(roots)!=1:raise ValueError('Stage5 requires exactly one top-level main body actor')
  main_ref=roots[0]
 main_request=next((row for row in requests.values() if row['actorRef']==main_ref),None)
 if not main_request or main_request.get('kind','body')!='body':raise ValueError('Main body endpoint must have kind=body')
 for endpoint_id,request in requests.items():
  actor=actors.get(request['actorRef']);row=rows[endpoint_id];actual=row['def_path_hash'].lower();kind=request.get('kind','body')
  if actor is None or actor.get('kind') not in ('body','declaration'):raise ValueError('Unknown callable actor: '+str(request['actorRef']))
  if row.get('kind','body')!=kind:raise ValueError('Resolved endpoint kind differs: '+endpoint_id)
  if request['canonical_path']!=row['canonical_path']:raise ValueError('Resolved canonical path differs: '+endpoint_id)
  identity_fields=('sourceNodeRef','bodyRef') if kind=='body' else ('sourceNodeRef','bodyRef','declarationRef')
  for field in identity_fields:
   authored=actor.get(field)
   if authored is not None and _endpoint_hash(authored)!=actual:
    raise ValueError('Authored '+field+' differs from resolved endpoint: '+actor['actorId'])
  if kind=='body':
   body_ref=row['def_path_hash']+'|mir_drops_elaborated_and_const_checked|main'
   actor['kind']='body';actor['sourceNodeRef']=body_ref;actor['bodyRef']=body_ref
   actor.pop('declarationRef',None);actor.pop('implementationStatus',None)
  else:
   owner=row.get('ownership',{});module=parents.get(actor['actorId']);crate=parents.get(module.get('actorId')) if module else None
   if not module or module.get('kind')!='module' or not crate or crate.get('kind')!='crate':
    raise ValueError('Declaration actor must have crate→module ancestors: '+actor['actorId'])
   for ancestor,field in ((module,'module_def_path_hash'),(crate,'crate_root_def_path_hash')):
    expected=owner.get(field);observed=_endpoint_hash(ancestor.get('sourceNodeRef'))
    if not expected:raise ValueError('Declaration ownership lacks '+field+': '+actor['actorId'])
    if ancestor.get('sourceNodeRef') is not None and observed!=expected.lower():raise ValueError('Declaration ownership differs: '+actor['actorId'])
    ancestor['sourceNodeRef']=expected
   actor['kind']='declaration';actor['declarationRef']=row['def_path_hash'];actor['sourceNodeRef']=row['def_path_hash']
   actor['implementationStatus']='unresolved';actor.pop('bodyRef',None)
 return ext
def stage5(c):
 from endpoint_identity import targets_from
 ext=c.ledger(5);endpoint_ledger=_endpoint_ledger(c);resolved=_resolve_stage5(c,endpoint_ledger,targets_from(c,endpoint_ledger));_apply_endpoints(ext,endpoint_ledger,resolved)
 selection={row['id']:row for row in c.load('stage2/selection.json')['items']}
 owners={}
 for member in ext['business_members']:
  owner=selection[member['bindingRef']].get('ownerActionRef');member['ownerActionRef']=owner;owners[member['invocationRef']]=owner
 for clause in ext.get('clauses',[]):
  if clause.get('invocationRef') in owners:clause['ownerActionRef']=owners[clause['invocationRef']]
 calls={x['id'] for x in c.load('facts/call-bindings.json')};ids=[m['messageId'] for m in ext['messages']]
 if len(ids)!=len(set(ids)):raise ValueError('Duplicate message ID')
 for m in ext['messages']:
  if m.get('bindingRef') not in calls:raise ValueError('Unknown call anchor: '+str(m.get('bindingRef')))
  if m['kind']=='self':
   if m['fromActorId']!=m['toActorId'] or m.get('pair') is not None:raise ValueError('Invalid internal self message: '+m['messageId'])
   continue
  pair=[x for x in ext['messages'] if x.get('pair')==m.get('pair')]
  if not m.get('pair') or len(pair)!=2 or {x['kind'] for x in pair}!={'request','return'}:raise ValueError('Invalid request/return pair: '+m['messageId'])
  a,b=pair
  if a['invocationRef']!=b['invocationRef'] or a['bindingRef']!=b['bindingRef'] or (a['fromActorId'],a['toActorId'])!=(b['toActorId'],b['fromActorId']):raise ValueError('Inconsistent paired identity: '+m['messageId'])
 from body_labels import apply as label_bodies
 label_bodies(ext['actors'],c.load('facts/definitions-index.json'))
 # Preserve all resolved source actors before renderer projection, including ancestors.
 ext['identity_registry']=[copy.deepcopy(actor) for actor in _actors(ext['actors'])]
 c.save('stage5/external.json',ext)
def stage6(c):
 from canonical_render import build
 return build(c)

def stage7(c):
 checks={};stage=c.work/'stage7';stage.mkdir(exist_ok=True)
 review=c.inputs/'ledgers/stage7-review.json'
 c.save('stage7/agent-review.json',read(review) if review.exists() else {'items':[]})
 commands={
  'principles':[sys.executable,'-B',str(PACKAGE/'scripts/check_principles.py'),'--out',str(c.work),'--report',str(stage/'principles.json')],
  'regressions':[sys.executable,'-B',str(PACKAGE/'scripts/check_regressions.py'),'--out',str(c.work),'--report',str(stage/'regressions.json')],
  'hard-rules':[sys.executable,'-B',str(PACKAGE/'scripts/hard_rules.py'),'--out',str(c.work),'--report',str(stage/'hard-rules.json')],
  'independent-source':[sys.executable,'-B',str(PACKAGE/'scripts/verify_source_evidence.py'),'--out',str(c.work),'--report',str(stage/'independent-source.json')],
  'duplicates':[sys.executable,'-B',str(PACKAGE/'scripts/audit_duplicates.py'),'--out',str(c.work),'--report',str(stage/'duplicates.json'),'--replace-report'],
  'contract':['node','--input-type=module','-e',"import fs from 'node:fs';const m=await import(process.argv[1]);const r=await m.validateInput(JSON.parse(fs.readFileSync(process.argv[2])));console.log(JSON.stringify(r));process.exit(r.valid?0:1)",str(PACKAGE/'assets/renderer/contract.mjs'),str(c.work/'renderer-input.json')]
 }
 for name,cmd in commands.items():
  from run_fixes import command
  cmd=command(c,7,cmd)
  start=time.monotonic()
  # Each independent S7 checker receives a bounded window so one stalled gate cannot block the batch.
  try:r=subprocess.run(cmd,capture_output=True,text=True,timeout=180,env=dict(os.environ,PYTHONPATH=os.pathsep.join([str(PACKAGE/'scripts'),os.environ.get('PYTHONPATH','')])));result=dict(exit_code=r.returncode,stdout=r.stdout,stderr=r.stderr,elapsed_seconds=time.monotonic()-start)
  except subprocess.TimeoutExpired as e:result=dict(exit_code=None,error='timeout',elapsed_seconds=time.monotonic()-start)
  except OSError as e:result=dict(exit_code=None,error=str(e),status='not-run',reason=str(e),elapsed_seconds=time.monotonic()-start)
  from gate_lifecycle import environment_result,check_result
  result.update(passed=result['exit_code']==0,command=cmd)
  result=environment_result(result)
  c.save('stage7/'+name+'-execution.json',result);checks[name]=check_result(result)
  if name=='contract' and result.get('stdout'):
   try:c.save('stage7/contract.json',json.loads(result['stdout']))
   except ValueError:pass
 from gate_lifecycle import finish_gates
 return finish_gates(c,checks)

def prepare_candidate(c):
 from publish_site import assemble
 candidate=c.work/'.candidate-site';candidate.mkdir(exist_ok=True)
 for name in TRIPLE:write(candidate/name,(c.work/name).read_bytes())
 row=c.load('input-pins.json')['definition_row'];defs=c.load('facts/definitions-index.json');own=row.get('ownership',{});data=c.load('renderer-input.json')
 module=defs.get(own.get('module_def_path_hash'),{}).get('identity',{}).get('canonical_path','')
 crate=defs.get(own.get('crate_root_def_path_hash'),{}).get('identity',{}).get('name','')
 identity=dict(symbol=data['semanticRoot']['symbol'],file=row['source']['file'],module=module,crate=crate)
 rt=candidate/'roundtrip';rt.mkdir(exist_ok=True)
 config='export const sourceIdentity = '+json.dumps(identity,ensure_ascii=False)+';\n'
 # Publisher consumes JS object keys, not JSON quoted keys.
 config='export const sourceIdentity = {'+', '.join(k+': '+json.dumps(v,ensure_ascii=False) for k,v in identity.items())+'};\n'
 write(rt/'render-config.js',config.encode())
 for name in ['index.html','style.css']:
  text=(PACKAGE/'assets/renderer/roundtrip'/name).read_text()
  for token,k in [('__SYMBOL__','symbol'),('__SOURCE_FILE__','file'),('__MODULE__','module'),('__CRATE__','crate')]:text=text.replace(token,identity[k])
  write(rt/name,text.encode())
 # Build the full next candidate before rotating the last valid output.
 from datetime import datetime,timezone
 import uuid
 target=c.out/'candidate-deliverable'
 stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
 pending=c.work/('.candidate-build-'+stamp+'-'+uuid.uuid4().hex)
 lock=read(c.inputs/'renderer-lock.json');assets={}
 for name,item in lock['assets'].items():
  relative=Path(item['path'])
  if relative.parts[:2]==('reference','frozen-renderers'):
   relative=Path('assets/frozen-renderers').joinpath(*relative.parts[2:])
  asset=(PACKAGE/relative).resolve()
  if not asset.is_relative_to(PACKAGE/'assets/frozen-renderers'):raise ValueError('Renderer asset escapes frozen store')
  assets[name]=dict(path=asset,sha256=item['sha256'])
 assemble(candidate,pending,frozen_assets=assets)
 if target.exists():
  previous=digest(encode(fingerprint(target)))[:12]
  archive=c.out/'aside'/('candidate-deliverable-'+stamp+'-'+previous)
  archive.parent.mkdir(parents=True,exist_ok=True)
  target.rename(archive)
 pending.rename(target)
 return candidate,target,assets

def stage8(c):
 from gate_lifecycle import deliver
 return deliver(c)

BUILD={0:stage0,1:stage1,2:stage2,3:stage3,4:stage4,5:stage5,6:stage6,7:stage7,8:stage8}
