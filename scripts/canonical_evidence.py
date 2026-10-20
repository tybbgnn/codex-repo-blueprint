"""Preserve authored evidence contracts; derive new evidence from pinned Rust source."""
from copy import deepcopy
import hashlib
import json
import re
from ledger_lib import contained,digest
from source_ranges import function_source,block_ranges,compiler_drop_flags


class Evidence:
    def __init__(self,context,blocks,edges,calls):
        self.context=context;self.blocks=blocks;self.edges={e['id']:e for e in edges};self.calls={v['id']:v for v in calls}
        self.raw=context.load('raw-body.json');self.source=function_source(context.work)
        self.locals={v['local']:v for v in self.raw['locals']}
        self.drop_flags=compiler_drop_flags(self.raw)
        self.ranges={}
        p=context.load('stage4/presentation.json')
        self.artifacts=deepcopy(p.get('artifacts',[]));self.evidence=deepcopy(p.get('evidence',[]))
        self.registry={a['id']:a for a in self.artifacts}
        if len(self.registry)!=len(self.artifacts):raise ValueError('Duplicate artifact identity')
        for artifact in self.artifacts:self.verify_artifact(artifact)
        self.evidence_by_id={e['id']:e for e in self.evidence}
        if len(self.evidence_by_id)!=len(self.evidence):raise ValueError('Duplicate evidence identity')
        for record in self.evidence:
            artifact=self.registry.get(record['artifactRef'])
            if artifact is None or not record['quote'] or record['quote'] not in artifact['content']:raise ValueError('Evidence quote is not an exact artifact substring: '+record['id'])
        if not self.artifacts:
            content='\n'.join(self.source['lines'])
            artifact=dict(id='source-function',sourcePath=self.source['sourcePath'],format='rust',content=content,sha256=digest(content.encode()))
            self.artifacts.append(artifact);self.registry[artifact['id']]=artifact

    def verify_artifact(self,artifact):
        content=artifact['content']
        if digest(content.encode())!=artifact['sha256']:raise ValueError('Artifact content hash mismatch: '+artifact['id'])
        rel=artifact['sourcePath']
        if artifact['format']=='rust':
            file=contained(self.context.work/'source',self.context.work/rel)
            if not content or content not in file.read_text():raise ValueError('Rust artifact differs from pinned source: '+artifact['id'])
        elif rel=='facts/edges.json':
            records=json.loads(content)
            if isinstance(records,dict):records=records['edges']
            if {e['id'] for e in records}!=set(self.edges):raise ValueError('Evidence edge coverage differs from current MIR')
            for row in records:
                actual=self.edges[row['id']]
                for key in ['source','target','source_info']:
                    if row.get(key)!=actual.get(key):raise ValueError('Evidence edge changed: '+row['id']+'/'+key)
                if row.get('terminator',row.get('terminator_kind'))!=actual['terminator_kind']:raise ValueError('Evidence terminator changed')
                old=row.get('condition');new=actual['condition']
                aliases={'return':'normal_return','assert_success':'success','assert_failure':'failure'}
                if aliases.get(old,old)!=new and not (actual['terminator_kind']=='Drop' and old=='normal_return' and new=='normal'):raise ValueError('Evidence branch condition changed: '+row['id'])
        else:
            raise ValueError('Artifact requires an explicit verified source adapter: '+rel)

    def validate_refs(self,refs):
        for ref in refs:
            if ref in self.blocks or ref in self.edges or ref in self.calls:continue
            if re.fullmatch(r't\d+\.\d+',ref):
                if ref not in {v['id'] for v in self.context.load('facts/terminal-events.json')}:raise ValueError('Unknown terminal selector: '+ref)
                continue
            match=re.fullmatch(r'(source/[^:]+):(\d+)(?:-(\d+))?',ref)
            if not match:raise ValueError('Unresolved evidence selector: '+ref)
            path=contained(self.context.work/'source',self.context.work/match.group(1));lines=path.read_text().splitlines()
            start,end=int(match.group(2)),int(match.group(3) or match.group(2))
            if not 1<=start<=end<=len(lines):raise ValueError('Source selector outside pinned file: '+ref)

    def quote(self,refs):
        source_art=next((a for a in self.artifacts if a['format']=='rust'),None)
        if source_art is None:raise ValueError('Rust evidence source required for new claims')
        for ref in refs:
            match=re.fullmatch(r'(source/[^:]+):(\d+)(?:-(\d+))?',ref)
            if match:
                lines=(self.context.work/match.group(1)).read_text().splitlines();start,end=int(match.group(2)),int(match.group(3) or match.group(2));quote='\n'.join(lines[start-1:end])
                if quote and quote in source_art['content']:return source_art,quote
            bb=ref if ref in self.blocks else self.edges[ref]['source'] if ref in self.edges else self.calls[ref]['bb'] if ref in self.calls else None
            if bb:
                if bb not in self.ranges:
                    self.ranges[bb]=block_ranges(self.blocks[bb],self.source,self.raw['span'],self.raw.get('source_scopes',[]),locals_by_id=self.locals,drop_flags=self.drop_flags)
                ranges=self.ranges[bb]
                for row in ranges:
                    quote='\n'.join(self.source['lines'][row['startLine']-self.source['startLine']:row['endLine']-self.source['startLine']+1])
                    if quote and quote in source_art['content']:return source_art,quote
        # Explicit enclosing function context; factual selectors still resolve independently.
        return source_art,source_art['content'].splitlines()[0]

    def claim(self,kind,subject,targets,refs,conditions=None):
        existing=[e for e in self.evidence if e['claim']['kind']==kind and e['claim']['subjectRef']==subject]
        if existing:
            for row in existing:
                if row['claim']['targets']!=targets or row['claim'].get('conditions',[])!=(conditions or []):raise ValueError('Authored claim contract changed: '+row['id'])
            return [e['id'] for e in existing]
        if not refs:raise ValueError('Missing authored evidence selector: '+subject)
        self.validate_refs(refs);artifact,quote=self.quote(refs)
        identity='evidence-'+hashlib.sha256(json.dumps([kind,subject,targets,refs,conditions or []],ensure_ascii=False,separators=(',',':')).encode()).hexdigest()[:24]
        row=dict(id=identity,artifactRef=artifact['id'],locator=','.join(refs),quote=quote,claim=dict(kind=kind,subjectRef=subject,targets=targets,conditions=conditions or []))
        self.evidence.append(row);self.evidence_by_id[identity]=row
        return [identity]
