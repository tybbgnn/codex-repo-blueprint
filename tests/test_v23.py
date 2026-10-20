"""Unattended lifecycle and evidence-bound decisions, using retained local scratch."""
import copy,json,sys,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from ledger_lib import write,read,digest,validate_inputs,validate_display_identifiers
import gate_lifecycle as gates
from agent_review import decide,question_digest
from body_labels import labels,apply

class Context:
    def __init__(self):
        self.out=Path(tempfile.mkdtemp(prefix='v23-test-'));self.work=self.out/'work';self.work.mkdir();self.inputs=self.out/'inputs';self.inputs.mkdir()
    def save(self,name,value):write(self.work/name,value)
    def load(self,name):return read(self.work/name)

class Decisions(unittest.TestCase):
    def setUp(self):self.c=Context();self.c.save('raw.json',{'bb':['call','return']});self.c.save('renderer-input.json',{'current':'subject'})
    def decision(self):return dict(subject_sha256=digest((self.c.work/'renderer-input.json').read_bytes()),decision='pass',rationale='call produces the returned result; no intervening state effect',question_sha256=question_digest('G2','boundary','question',{}),evidence=[dict(path='raw.json',sha256=digest((self.c.work/'raw.json').read_bytes()),pointer='/bb/0')])
    def test_current_evidence_closes(self):self.assertEqual(decide(self.c.work,self.decision(),'G2','boundary','question',{})['status'],'pass')
    def test_missing_decision_fails(self):self.assertEqual(decide(self.c.work,None,'G2','boundary','question',{})['status'],'fail')
    def test_stale_question_fails(self):self.assertEqual(decide(self.c.work,self.decision(),'G2','boundary','changed',{})['status'],'fail')
    def test_stale_evidence_fails(self):
        d=self.decision();self.c.save('raw.json',{'bb':[]});self.assertEqual(decide(self.c.work,d,'G2','boundary','question',{})['status'],'fail')
    def test_bad_pointer_fails(self):
        d=self.decision();d['evidence'][0]['pointer']='/missing';self.assertEqual(decide(self.c.work,d,'G2','boundary','question',{})['status'],'fail')
    def test_environment_warning_requires_real_not_run_receipt(self):
        evidence={'environment_gate':'browser'};d=self.decision();d['decision']='warning';d['question_sha256']=question_digest('P14','browser','question',evidence)
        self.assertEqual(decide(self.c.work,d,'P14','browser','question',evidence)['status'],'fail')
        self.c.save('stage7/browser-execution.json',{'passed':False,'status':'not-run','reason':'sandbox listener denied'})
        d['evidence'].append(dict(path='stage7/browser-execution.json',sha256=digest((self.c.work/'stage7/browser-execution.json').read_bytes())))
        self.assertEqual(decide(self.c.work,d,'P14','browser','question',evidence)['status'],'warning')
    def test_renderer_change_invalidates_decision(self):
        d=self.decision();self.c.save('renderer-input.json',{'changed':'subject'})
        self.assertEqual(decide(self.c.work,d,'G2','boundary','question',{})['status'],'fail')
    def test_warning_needs_no_gate(self):self.assertEqual(decide(self.c.work,None,'P7','locks_iterators','hint',{})['status'],'warning')
    def test_display_hint_nonblocking(self):self.assertTrue(validate_display_identifiers({'nodes':[{'kind':'action','name':'路径 bb419'}]},('nodes',)))

class Labels(unittest.TestCase):
    def row(self,path):return dict(identity=dict(canonical_path=path))
    def test_function_closure_and_method(self):
        got=labels({k:self.row(v) for k,v in dict(a='crate::m::go::{closure#0}',b='crate::m::<impl crate::T>::run::{closure#1}',c='crate::m::plain').items()})
        self.assertEqual(got,dict(a='go::{closure#0}',b='T::run::{closure#1}',c='plain'))
    def test_nested_closure(self):self.assertEqual(labels({'a':self.row('c::go::{closure#0}::{closure#2}')})['a'],'go::{closure#0}::{closure#2}')
    def test_root_identity_projection_keeps_unknown_references_rejectable(self):
        from body_labels import project_references
        row=self.row('crate::m::go::{closure#0}')
        value=[{'kind':'terminate-turn','scopeRef':'go'},{'kind':'terminate-turn','scopeRef':'wrong'}, {'kind':'entry','targets':['main','go']},{'kind':'inventory','subjectRef':'go'}]
        project_references(value,row,'go::{closure#0}','main')
        self.assertEqual(value[0]['scopeRef'],'go::{closure#0}');self.assertEqual(value[1]['scopeRef'],'wrong');self.assertEqual(value[2]['targets'],['main','go::{closure#0}']);self.assertEqual(value[3]['subjectRef'],'go::{closure#0}')
    def test_peer_collision(self):self.assertEqual(labels({'a':self.row('c::a::go'),'b':self.row('c::b::go')}),dict(a='a::go',b='b::go'))

class Lifecycle(unittest.TestCase):
    def setUp(self):self.c=Context()
    def report(self):return dict(checks={'agent-review':{'passed':True},'browser':{'passed':False,'status':'not-run'},'batch':{'passed':True},'batch-reference':{'passed':True}},warnings=[{'key':'wording'}],deviations=[],missing_mir=[],custom={'retain':1})
    def test_browser_nested_failure_beats_zero_exit(self):
        with patch.object(gates,'execute',return_value=dict(passed=True,exit_code=0,stdout=json.dumps(dict(passed=True,results=[{'passed':False}])))):
            self.assertFalse(gates.record_environment(self.c,'browser',['node','test'])['passed'])
    def test_browser_actual_success_aggregates(self):
        with patch.object(gates,'execute',return_value=dict(passed=True,exit_code=0,stdout=json.dumps(dict(passed=True,results=[{'passed':True}])))):
            self.assertTrue(gates.record_environment(self.c,'browser',['node','test'])['passed'])
    def test_rerun_only_not_run_preserves_report_and_review(self):
        report=self.report();self.c.save('stage7/acceptance.json',report);self.c.save('stage7/browser-execution.json',{'command':['node','browser']});self.c.save('stage7/agent-review.json',{'items':[{'retained':True}]});original=(self.c.work/'stage7/agent-review.json').read_bytes()
        with patch.object(gates,'record_environment',return_value={'passed':True}) as execute:
            result=gates.rerun_env(self.c.out)
        self.assertEqual(execute.call_count,1);self.assertEqual(execute.call_args.args[1],'browser');self.assertTrue(result['passed']);self.assertEqual(result['custom'],report['custom']);self.assertEqual(result['warnings'],report['warnings']);self.assertEqual((self.c.work/'stage7/agent-review.json').read_bytes(),original)
    def test_rerun_retains_not_run_batch_reference_dependency(self):
        r=self.report();r['checks']['browser']={'passed':True};r['checks']['batch']={'passed':False,'status':'not-run'};r['checks']['batch-reference']={'passed':False,'status':'not-run'}
        self.c.save('stage7/acceptance.json',r)
        for name in ('batch','batch-reference'):self.c.save('stage7/'+name+'-execution.json',{'command':[name]})
        def execute(c,name,command):return {'passed':False,'status':'not-run'} if name=='batch' else {'passed':False}
        with patch.object(gates,'record_environment',side_effect=execute),patch.object(gates,'blocked_report'):
            result=gates.rerun_env(self.c.out)
        self.assertEqual(result['checks']['batch-reference']['status'],'not-run');self.assertEqual(result['status'],'failed')
    def test_rerun_does_not_retry_failed_checks(self):
        r=self.report();r['checks']['browser']={'passed':False};self.c.save('stage7/acceptance.json',r)
        with patch.object(gates,'record_environment') as execute,patch.object(gates,'blocked_report'):
            result=gates.rerun_env(self.c.out)
        execute.assert_not_called();self.assertEqual(result['status'],'failed')
    def test_warning_report_does_not_block(self):
        r=self.report();r['checks']['browser']={'passed':True};self.assertTrue(gates.summarize(self.c,r)['passed']);self.assertIn('Warnings',(self.c.out/'e2e-summary.md').read_text())
    def test_environment_not_run_failed_terminal(self):
        with patch.object(gates,'blocked_report'):
            r=gates.summarize(self.c,self.report())
        self.assertEqual(r['status'],'failed');self.assertIn('rerun-env',r['environment_rerun_command'])
    def test_semantic_gate_absent(self):
        self.assertFalse(hasattr(gates,'semantic'));self.assertFalse((gates.PACKAGE/'scripts/semantic_gate.py').exists())
    def test_stage_required_references_ship_in_runtime(self):
        includes=read(gates.PACKAGE/'references/package-runtime.json')['include']
        for name in ('ENGLISH-TERMS','ledger-templates','display-principles','display-validation','granularity','source-ranges','stage-guide','s2-authoring'):
            self.assertIn('references/'+name+'.md',includes)
    def test_s3_lock_automatic(self):
        import stage_engine
        self.c.ledger=lambda n:{'passed':True};self.c.save('stage2/granularity.json',{});write(self.c.inputs/'ledgers/review-narrative.md',b'purposeGroups: none\n')
        with patch('reading_groups.review',return_value={'passed':True}),patch.object(gates,'stage3_fingerprints',return_value={'source':'sha'}):
            stage_engine.stage3(self.c)
        self.assertEqual(self.c.load('stage3/lock.json'),dict(passed=True,sha256={'source':'sha'}))
    def test_review_input_only_declared_path(self):
        from ledger_lib import PACKAGE
        manifest=read(PACKAGE/'references/input-manifest.json');self.assertIn('stage7-review.json',manifest['ledgers']);self.assertNotIn('semantic-approvals.json',manifest['ledgers'])
        for name in ('raw-body.json','input-pins.json','rules.json','renderer-lock.json'):write(self.c.inputs/name,{})
        write(self.c.inputs/'ledgers/stage7-review.json',{'items':[]});validate_inputs(self.c.inputs)
        write(self.c.inputs/'stage7-review.json',{})
        with self.assertRaisesRegex(ValueError,'Undeclared input'):validate_inputs(self.c.inputs)
    def test_candidate_replaced_and_archived(self):
        import stage_engine
        for name in stage_engine.TRIPLE:self.c.save(name,{})
        self.c.save('renderer-input.json',{'semanticRoot':{'symbol':'go'}})
        self.c.save('input-pins.json',{'definition_row':{'ownership':{},'source':{'file':'f.rs'}}});self.c.save('facts/definitions-index.json',{})
        write(self.c.inputs/'renderer-lock.json',{'assets':{}})
        def assemble(candidate,target,**kw):
            target.mkdir();write(target/'renderer-input.json',(candidate/'renderer-input.json').read_bytes())
        with patch('publish_site.assemble',side_effect=assemble):
            _,first,_=stage_engine.prepare_candidate(self.c);old=(first/'renderer-input.json').read_bytes()
            self.c.save('renderer-input.json',{'semanticRoot':{'symbol':'new'}})
            _,second,_=stage_engine.prepare_candidate(self.c)
        self.assertEqual(first,second);archives=list((self.c.out/'aside').glob('candidate-deliverable-*'));self.assertEqual(len(archives),1);self.assertEqual((archives[0]/'renderer-input.json').read_bytes(),old);self.assertIn('new',(second/'renderer-input.json').read_text())
    def test_stage5_emits_full_identity_registry(self):
        import stage_engine
        actor={'actorId':'main','kind':'body','bodyRef':'a'*32+'|stage|main','sourceNodeRef':'a'*32+'|stage|main'}
        ext=dict(actors=[actor],messages=[],business_members=[])
        self.c.ledger=lambda n:copy.deepcopy(ext)
        self.c.save('stage2/selection.json',{'items':[]});self.c.save('facts/call-bindings.json',[])
        self.c.save('facts/definitions-index.json',{'a'*32:dict(identity=dict(canonical_path='c::go::{closure#0}'))})
        with patch.object(stage_engine,'_endpoint_ledger',return_value={}),patch.object(stage_engine,'_resolve_stage5',return_value={}),patch.object(stage_engine,'_apply_endpoints'),patch('endpoint_identity.targets_from',return_value={}):
            stage_engine.stage5(self.c)
        external=self.c.load('stage5/external.json')
        self.assertEqual(external['identity_registry'],external['actors']);self.assertEqual(external['actors'][0]['label'],'go::{closure#0}')
    def test_identity_registry_missing_or_changed_fails_p6(self):
        from check_principles import Audit
        actor={'actorId':'main','kind':'body','label':'go','bodyRef':'a'*32+'|stage|main','sourceNodeRef':'a'*32+'|stage|main'}
        audit=Audit.__new__(Audit);audit.data=dict(actors=[actor],semanticRoot={'actorRef':'main'});audit.actors=[actor];audit.actor_by_id={'main':actor};audit.messages=[];audit.checks=[]
        audit.definitions={'a'*32:{'representations':{'mir':{'body_available':True}}}};audit.external={}
        audit.check_p6();self.assertEqual(audit.checks[-1]['status'],'fail')
        audit.external={'identity_registry':[copy.deepcopy(actor)]};audit.check_p6();self.assertEqual(audit.checks[-1]['status'],'pass')
        audit.external['identity_registry'][0]['sourceNodeRef']='changed';audit.check_p6();self.assertEqual(audit.checks[-1]['status'],'fail')
    def test_rerun_nested_environment_child_preserves_success(self):
        from batch_selftests import skill_fingerprint
        first=dict(passed=True,command=['success'],exit_code=0,log='preserved')
        missing=dict(passed=False,status='not-run',command=['missing'],exit_code=1)
        r=self.report();r['checks']['browser']={'passed':True};r['checks']['batch']={'passed':False,'subchecks':[first,missing]}
        self.c.save('stage7/acceptance.json',r)
        self.c.save('stage7/batch-execution.json',dict(subchecks=[first,missing],stdout=json.dumps(dict(batch_id='test',skill_fingerprint=skill_fingerprint(gates.PACKAGE),results=[first,missing]))))
        with patch.object(gates,'execute',return_value=dict(passed=True,exit_code=0,stdout='',stderr='')) as execute,patch('batch_selftests.publish_record'):
            result=gates.rerun_env(self.c.out)
        self.assertEqual(execute.call_count,1);self.assertEqual(execute.call_args.args[-1],['missing']);self.assertEqual(result['checks']['batch']['subchecks'][0],first);self.assertTrue(result['passed'])
    def test_s7_all_machine_gates_finish_without_signature(self):
        self.c.save('input-pins.json',{'missing_mir':[]});self.c.save('stage7/principles.json',{'warnings':[{'check':'hint'}]})
        with patch('stage_engine.prepare_candidate',return_value=(self.c.work,self.c.out/'candidate-deliverable',{})),patch.object(gates,'record_environment',return_value={'passed':True}),patch.object(gates,'counts',return_value={}),patch('run_fixes.records',return_value=[]):
            result=gates.finish_gates(self.c,{'principles':{'passed':True}})
        self.assertTrue(result['passed']);self.assertEqual(result['status'],'passed');self.assertNotIn('semantic',result['checks']);self.assertEqual(result['warnings'],[{'check':'hint'}])
    def test_s8_delivers_without_signature(self):
        # Exercise the publication state transition, retaining real byte equality checks.
        site=self.c.out/'candidate-deliverable';site.mkdir();write(site/'page',b'validated')
        self.c.save('stage7/acceptance.json',{'passed':True,'checks':{}});self.c.save('renderer-input.json',{'semanticRoot':{'symbol':'go'}})
        def publish(*args,**kwargs):
            target=self.c.out/'deliverable';target.mkdir();write(target/'page',b'validated');return {'deliverable':str(target)}
        with patch.object(gates,'validate_stage3_lock'),patch('stage_engine.prepare_candidate',return_value=(self.c.work,site,{})),patch('publish_site.publish',side_effect=publish),patch.object(gates,'counts',return_value={}):
            result=gates.deliver(self.c)
        self.assertTrue(Path(result['deliverable']).is_dir());self.assertTrue(self.c.load('stage8/candidate.json')['published'])
    def test_deleted_pair_check_still_rejects_bad_pair(self):
        from check_principles import Audit
        audit=Audit.__new__(Audit);audit.messages=[dict(invocationRef='i',kind='request',messageId='m')];audit.checks=[]
        audit.check_pairs('P6');self.assertEqual(audit.checks[0]['status'],'fail')
    def test_deleted_broad_range_still_called(self):
        from source_ranges import check_source
        with patch('source_ranges.broad_range_errors',return_value=['retained duplicate predicate']) as check:
            result=check_source({'phases':[]})
        self.assertIn('retained duplicate predicate',result);check.assert_called_once()

if __name__=='__main__':unittest.main()
