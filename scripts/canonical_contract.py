"""Validate the documented subset of canonical JSON Schema without dependencies."""
import json
from pathlib import Path
from ledger_lib import PACKAGE
SCHEMA=json.loads((PACKAGE/'references/canonical-schema.json').read_text())
def validate(value,schema,path='$'):
 errors=[];types={'object':lambda x:isinstance(x,dict),'array':lambda x:isinstance(x,list),'string':lambda x:isinstance(x,str),'integer':lambda x:type(x)==int,'number':lambda x:type(x) in (int,float),'boolean':lambda x:type(x)==bool,'null':lambda x:x is None}
 expected=schema.get('type');expected=[expected] if isinstance(expected,str) else expected
 if expected and not any(types[t](value) for t in expected):return [path+': expected '+str(expected)]
 if 'enum' in schema and value not in schema['enum']:errors.append(path+': invalid enum')
 if 'const' in schema and (isinstance(value,bool)!=isinstance(schema['const'],bool) or value!=schema['const']):errors.append(path+': invalid const')
 if isinstance(value,str) and len(value)<schema.get('minLength',0):errors.append(path+': minLength')
 if isinstance(value,dict):
  for key in schema.get('required',[]):
   if key not in value:errors.append(path+': missing '+key)
  props=schema.get('properties',{});extra=schema.get('additionalProperties',True)
  for key,item in value.items():
   if key in props:errors.extend(validate(item,props[key],path+'/'+key))
   elif extra is False:errors.append(path+': unexpected '+key)
   elif isinstance(extra,dict):errors.extend(validate(item,extra,path+'/'+key))
 if isinstance(value,list):
  if len(value)<schema.get('minItems',0):errors.append(path+': minItems')
  if schema.get('uniqueItems') and len({json.dumps(x,sort_keys=True) for x in value})!=len(value):errors.append(path+': uniqueItems')
  for i,item in enumerate(value):errors.extend(validate(item,schema.get('items',{}),path+'/'+str(i)))
 return errors

def stage(c,n):
 errors=[]
 for name,schema in SCHEMA['stages']['S'+str(n)].items():
  if not isinstance(schema,dict):continue
  path=c.work/name
  if not path.exists():continue # separate manifest closure reports absence
  if path.suffix=='.json':errors.extend(validate(json.loads(path.read_text()),schema,name))
  elif schema.get('format')=='tsv':
   rows=path.read_text().splitlines()
   if not rows or rows[0].split('\t')!=schema['columns']:errors.append(name+': canonical header mismatch')
   if any(len(row.split('\t'))!=len(schema['columns']) for row in rows[1:]):errors.append(name+': malformed row')
 if errors:raise ValueError('Canonical output schema: '+'; '.join(errors[:12]))
