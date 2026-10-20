"""Lazy exact MIR access. Index identities, open bodies only for a decision.

The index is metadata, never a pin. A read in verification mode must already
have an exact pin; generation mode creates it. Missing definitions are declarations.
"""
import json, mmap, re, shlex, bisect
from pathlib import Path
from collections import defaultdict
from ledger_lib import digest
from extract_body import object_slice, STAGE
from mir_cache import file_fingerprint

def object_start(stream,offset):
    # A key is normally near its opening brace. Avoid allocating a 1 MiB token
    # list for each tiny identity header; still handle arbitrary nesting/strings.
    depth=0;quoted=False;end=offset
    structural=re.compile(rb'[{}"]')
    while end:
        start=max(0,end-4096);stream.seek(start);data=stream.read(end-start)
        for match in reversed(list(structural.finditer(data))):
            pos=match.start();token=data[pos]
            if token==34:
                absolute=start+pos-1;slashes=0
                while absolute>=0:
                    if absolute>=start:ch=data[absolute-start]
                    else:
                        stream.seek(absolute);ch=stream.read(1)[0]
                    if ch!=92:break
                    slashes+=1;absolute-=1
                if slashes%2==0:quoted=not quoted
            elif not quoted:
                if token==125:depth+=1
                elif depth:depth-=1
                else:return start+pos
        end=start
    raise ValueError('No enclosing JSON object')

_INDEXES={}
def index_file(path,key):
    path=Path(path);fp=file_fingerprint(path);cache=(str(path),json.dumps(fp,sort_keys=True),key)
    if cache not in _INDEXES:
        rows=defaultdict(list)
        with path.open('rb') as f, mmap.mmap(f.fileno(),0,access=mmap.ACCESS_READ) as data:
            pattern=rb'"'+key.encode()+rb'"\s*:\s*"([^"\\]*)"'
            if key=='__body_starts':rows['starts']=[m.start() for m in re.finditer(rb'\{\s*"arg_count"\s*:',data)]
            else:
                for m in re.finditer(pattern,data):rows[m[1].decode()].append(m.start())
        _INDEXES[cache]=dict(rows)
    return _INDEXES[cache]

class MirAccess:
    def __init__(self,pins,generate=False):
        self.pins=pins;self.generate=generate;self.cache={};self.defs={};self.aliases={(r['requested'],r['display']):r['resolved'] for r in pins.get('information_mir_aliases',[])};self.missing={(r['def_path_hash'],r['callee'],str(r.get('source_line'))):r for r in pins.get('missing_mir',[])}
        self.locators={p['def_path_hash']:p for p in pins.get('information_mir_slices',[])}
        self.path=Path(pins.get('inputs',{}).get('mir_bodies',{}).get('path',''))
        self.defpath=Path(pins.get('inputs',{}).get('definitions',{}).get('path',''))
        self.index=None;self.starts=None
    def owner_index(self):
        if self.index is None:
            saved=self.pins.get('information_mir_index',{})
            fp=file_fingerprint(self.path)
            if saved.get('fingerprint')==fp:
                self.index=saved['owners'];self.starts=saved.get('body_starts')
            else:self.index=index_file(self.path,'owner_def_path_hash')
            if self.starts is None:self.starts=index_file(self.path,'__body_starts').get('starts',[])
            if self.generate:self.pins['information_mir_index']=dict(fingerprint=fp,owners=self.index,body_starts=self.starts)
        return self.index
    def definition(self,h):
        if h not in self.defs:
            found=[]
            if self.defpath.is_file():
                with self.defpath.open('rb') as f:
                    for pos in index_file(self.defpath,'def_path_hash').get(h,[]):
                        row=json.loads(object_slice(f,object_start(f,pos)))
                        if row.get('def_path_hash')==h and 'identity' in row and 'representations' in row:found.append(row)
            if len(found)>1:raise ValueError('model-definition: nonunique '+h)
            self.defs[h]=found[0] if found else None
        return self.defs[h]
    def resolve(self,h,display=''):
        # One trait item can dispatch to several concrete impls: never cache by item alone.
        token=(h,display)
        if token in self.aliases:return self.aliases[token]
        if re.search(r'<dyn\s|\bdyn\s',display):return h
        row=self.definition(h)
        if ' as ' in display:
            # Concrete receiver + fully qualified trait identity, verified against definitions.
            m=re.match(r'^<(.*) as (.*)>::([^:]+)$',display)
            if m and self.defpath.is_file():
                receiver,trait,method=m.groups();wanted='<'+receiver+' as '+trait+'>::'+method
                candidates=[]
                for path,positions in index_file(self.defpath,'canonical_path').items():
                    exact=path==wanted
                    receiver_match=path.startswith('<'+receiver+' as ') and path.endswith('>::'+method)
                    if not exact and not (row and receiver_match):continue
                    with self.defpath.open('rb') as f:
                        for pos in positions:
                            d=json.loads(object_slice(f,object_start(f,object_start(f,pos))))
                            if d.get('rustc',{}).get('def_kind')!='AssocFn':continue
                            if not exact:
                                parent=self.definition(d.get('ownership',{}).get('parent_def_path_hash')) or {}
                                if parent.get('detail',{}).get('trait_def_path_hash')!=row.get('ownership',{}).get('parent_def_path_hash'):continue
                            candidates.append(d)
                if len(candidates)==1:
                    h=candidates[0]['def_path_hash'];self.defs[h]=candidates[0]
                elif len(candidates)>1:raise ValueError('model-trait-impl: ambiguous '+display)
        self.aliases[token]=h
        return h
    def body(self,h,display='',line=None):
        requested=h;h=self.resolve(h,display)
        if re.search(r'<dyn\s|\bdyn\s',display):
            self.note(requested,display,line,'declaration','dynamic dispatch has no concrete body');return None
        if h in self.cache:return self.cache[h]
        matches=[]
        if self.path.is_file():
            self.owner_index()
            with self.path.open('rb') as f:
                seen=set()
                for pos in self.index.get(h,[]):
                    index=bisect.bisect_right(self.starts,pos)-1
                    offset=self.starts[index] if index>=0 else object_start(f,pos)
                    if offset in seen:continue
                    seen.add(offset)
                    content=object_slice(f,offset);b=json.loads(content)
                    if b.get('owner_def_path_hash')!=h:
                        offset=object_start(f,pos);content=object_slice(f,offset);b=json.loads(content)
                    if b.get('capture_stage')==STAGE and b.get('body_id')=='main' and b.get('owner_def_path_hash')==h and 'basic_blocks' in b:
                        matches.append((offset,content,b))
        if len(matches)>1:raise ValueError('model-callee-pin: nonunique MIR '+h)
        if matches:
            offset,content,b=matches[0]
            pin=dict(def_path_hash=h,path=str(self.path),offset_bytes=offset,size_bytes=len(content),sha256=digest(content))
            if self.generate:self.locators[h]=pin
            elif h not in self.locators:raise ValueError('model-callee-pin: container has MIR but pin missing: '+h+' ('+display+')')
            elif self.locators[h]!=pin:raise ValueError('model-callee-pin: changed exact MIR slice '+h)
            self.cache[h]=b;return b
        row=self.definition(h)
        if row:
            if line is None:
                source=row.get('source') or {};line=str(source.get('file'))+':'+str((source.get('span') or {}).get('start_line'))
            self.note(requested,display or row['identity']['canonical_path'],line,'out-of-scope',
                      'definition exists but extraction container has no body (body_available='+str(row.get('representations',{}).get('mir',{}).get('body_available'))+')')
        else:self.note(requested,display,line,'declaration','std/third-party declaration absent from definitions')
        self.cache[h]=None;return None
    def note(self,h,display,line,category,reason):
        key=(h,display,str(line));row=dict(callee=display or h,def_path_hash=h,source_line=line,category=category,reason=reason)
        if category=='out-of-scope':
            row['rerun_command']='python3 "$MIRLOADER_ROOT/mirloader.py" --definitions '+shlex.quote(str(self.defpath))+' --scope "$MIR_SCOPE_WITH_MISSING_DEFINITIONS" --workspace '+shlex.quote(str(self.pins.get('workspace','SOURCE_WORKSPACE')))+' --output-dir "$MIR_REEXTRACT_OUTPUT" --result-file "$MIR_REEXTRACT_OUTPUT/mir-bodies.json" --offline --jobs 8'
            row['scope_requirement']='Generate a scope-definitions JSON including '+(display or h)+' ('+h+'); --scope accepts a scope file, not a callee name.'
            row['tool_reference']='/Users/jessie/ai/codex拆解/v3/v3-1-2-claude/02scrpits/03-mir-extraction/mirloader/README.md' 
        self.missing[key]=row
    def finish(self):
        self.pins['information_mir_slices']=[self.locators[h] for h in sorted(self.locators)]
        self.pins['information_mir_aliases']=[dict(requested=h,display=d,resolved=a) for (h,d),a in sorted(self.aliases.items()) if h!=a]
        self.pins['missing_mir']=[self.missing[k] for k in sorted(self.missing)]
        return self.pins
