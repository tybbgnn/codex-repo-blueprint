"""Run the unchanged protocol and detailed sidebar checks against one candidate."""
import argparse,json,subprocess,sys,time,uuid
from pathlib import Path
from ledger_lib import PACKAGE,write
from gate_lifecycle import environment_result

def run(site, receipts):
    commands=[('protocol',['node',str(PACKAGE/'tests/test_file_protocol.cjs'),str(site)]),
              ('sidebar',['node',str(PACKAGE/'tests/test_sidebar.cjs'),(site/'roundtrip/index.html').as_uri()])]
    results=[]
    for name,command in commands:
        try:
            p=subprocess.run(command,capture_output=True,text=True,timeout=180)
            result=dict(passed=p.returncode==0,exit_code=p.returncode,stdout=p.stdout,stderr=p.stderr,command=command)
        except (OSError,subprocess.TimeoutExpired) as exc:
            result=dict(passed=False,exit_code=None,stdout='',stderr=str(exc),command=command)
        result=environment_result(result)
        log=receipts/(name+'-'+str(time.time_ns())+'-'+uuid.uuid4().hex+'.log')
        write(log,(result['stdout']+result['stderr']).encode());result['log']=str(log)
        results.append(result)
    report=dict(passed=all(r['passed'] for r in results),results=results)
    return report

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--site',required=True,type=Path);p.add_argument('--receipts',required=True,type=Path);a=p.parse_args()
    result=run(a.site.resolve(),a.receipts.resolve());print(json.dumps(result));return 0 if result['passed'] else 1
if __name__=='__main__':raise SystemExit(main())
