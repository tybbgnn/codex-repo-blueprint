"""Stage artifact closure and real run observations.
Source: archived common.py.stage / pipeline.py.runstage / scripts.stage.py.
The historical stage-check path is retained; observations are never replayed.
"""
import time
from ledger_lib import PACKAGE,read,write,digest

IO=read(PACKAGE/'references/stage-io.json')
STAGE_OUTPUTS={int(key[1:]):[row['file'] for row in stage['outputs']
    if row['root']=='work' and not row.get('optional') and '<' not in row['file']]
    for key,stage in IO['stages'].items()}

def observe(c,n,start,error=None):
 required=list(STAGE_OUTPUTS[n])
 if n==4 and (c.inputs/'ledgers/execution-label-review.json').exists():required.append('stage4/execution-label-review.json')
 missing=[p for p in required if not any(path.is_file() for path in c.work.glob(p))]
 result=dict(passed=error is None and not missing,scope='stage construction and output closure; semantic acceptance is separate',outputs=required,missing=missing)
 if error:result['error']=str(error)
 if n in (7,8):
  receipt=c.work/'stage7/acceptance.json'
  result['acceptance_passed']=receipt.exists() and read(receipt).get('passed') is True
  result['passed']=result['passed'] and result['acceptance_passed']
 raw=c.work/'raw-body.json';counts={}
 if raw.exists():counts['bb_total']=len(read(raw)['basic_blocks'])
 hierarchy=c.work/'stage2/hierarchy.json'
 if hierarchy.exists():
  nodes=read(hierarchy)['nodes'];counts.update(bb_covered=sum(v['kind']=='bb' for v in nodes.values()),phase_count=sum(v['kind']=='phase' for v in nodes.values()),goal_count=sum(v['kind']=='goal' for v in nodes.values()),action_count=sum(v['kind']=='action' for v in nodes.values()))
 renderer=c.work/'renderer-input.json'
 if renderer.exists():
  data=read(renderer);counts.update(message_count=len(data['messages']),execution_node_count=len(data['execution']['nodes']))
 result['counts']=counts
 c.save(f'stage{n}-check.json',result)
 timings=c.work/'stage-timings.json';d=read(timings) if timings.exists() else {}
 d['stage'+str(n)]={'wall_seconds':time.monotonic()-start};c.save('stage-timings.json',d)
 return result
