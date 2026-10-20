"""Audited run-local mechanism repairs. Does not edit the installed package.

Register evidence and replacement scripts before running the affected stage.
S7 revalidates receipts and runs the normal output gates on repaired outputs.
"""
import argparse, importlib.util, sys
from pathlib import Path
from ledger_lib import PACKAGE,read,write,digest

def records(c):
    path=c.out/'run-fixes/deviations.json'
    if not path.exists():return []
    rows=read(path)['deviations']
    for r in rows:
        script=Path(r['script']);fixed=Path(r['fixed_script']).resolve()
        if script.name!=str(script) or script.suffix!='.py':raise ValueError('deviation script must be a package Python module name')
        if not fixed.is_relative_to((c.out/'run-fixes').resolve()):raise ValueError('deviation correction must be run-local')
        if digest(fixed.read_bytes())!=r['sha256']:raise ValueError('deviation correction SHA changed')
        if digest((PACKAGE/'scripts'/script).read_bytes())!=r['original_sha256']:raise ValueError('deviation original SHA changed')
        if not r['bug'] or not r['judgment'] or not r['change']:raise ValueError('deviation needs diagnosis and correction')
        for item in r['evidence']:
            if digest(Path(item['path']).read_bytes())!=item['sha256']:raise ValueError('deviation evidence SHA changed')
        if not r['evidence']:raise ValueError('deviation requires evidence')
    return rows

def used(c,stage,row):
    path=c.out/'run-fixes/used.json'
    rows=read(path) if path.exists() else []
    entry=dict(stage=stage,script=row['script'],sha256=row['sha256'],fixed_script=row['fixed_script'])
    if entry not in rows:write(path,rows+[entry])

def apply(c,stage):
    rows=records(c)
    for r in rows:
        if stage not in r['stages']:continue
        name=Path(r['script']).stem
        if name in ('blueprint','run_fixes','gate_lifecycle'):
            raise ValueError('repair runner and acceptance lifecycle cannot replace themselves')
        spec=importlib.util.spec_from_file_location(name,r['fixed_script']);module=importlib.util.module_from_spec(spec)
        sys.modules[name]=module;spec.loader.exec_module(module)
        used(c,stage,r)
    return rows

def command(c,stage,cmd):
    for r in records(c):
        if stage in r['stages']:
            if str(PACKAGE/'scripts'/r['script']) in cmd:used(c,stage,r)
            cmd=[r['fixed_script'] if arg==str(PACKAGE/'scripts'/r['script']) else arg for arg in cmd]
    return cmd

def register(out,script,fixed,stages,bug,judgment,change,evidence):
    class Run:pass
    c=Run();c.out=Path(out).resolve();fixed=Path(fixed).resolve()
    rows=records(c)
    row=dict(script=script,fixed_script=str(fixed),stages=stages,bug=bug,judgment=judgment,change=change,
             sha256=digest(fixed.read_bytes()),original_sha256=digest((PACKAGE/'scripts'/script).read_bytes()),
             evidence=[dict(path=str(Path(p).resolve()),sha256=digest(Path(p).read_bytes())) for p in evidence])
    path=c.out/'run-fixes/deviations.json';write(path,dict(schema='deviations/1',deviations=rows+[row]));records(c)
    write(c.out/'run-fixes/deviations.md', ('# 运行偏离\n\n'+'\n\n'.join('## '+r['script']+' / '+str(r['stages'])+'\n'+r['bug']+'\n判断：'+r['judgment']+'\n修正：'+r['change']+'\n证据：'+str(r['evidence'])+'\n脚本：'+r['fixed_script']+'\nSHA256：'+r['sha256'] for r in rows+[row])+'\n').encode())
    return row

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('out','script','fixed','bug','judgment','change'):p.add_argument('--'+name,required=True)
    p.add_argument('--stage',action='append',required=True,type=int);p.add_argument('--evidence',action='append',required=True)
    a=p.parse_args();register(a.out,a.script,a.fixed,a.stage,a.bug,a.judgment,a.change,a.evidence)
