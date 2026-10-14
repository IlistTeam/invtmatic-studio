"""Host refusal tests for the debugger; native behavior is verified by stdio tests."""
import importlib.util
from pathlib import Path
import sys,types,unittest
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root/'src/scripts'))
sys.modules['scriptengine']=types.SimpleNamespace()
spec=importlib.util.spec_from_file_location('debugger',root/'src/scripts/invt_debugger.py')
d=importlib.util.module_from_spec(spec);spec.loader.exec_module(d)
d.unicode,d.long=str,int
original_core=d.core

class Guards(unittest.TestCase):
 def setUp(self):
  d.core=original_core;d.flags=lambda:None
  self.items=[({'line':3,'column':3},'cp1','bp1'),({'line':3,'column':25},'cp2','bp2'),({'line':4,'column':1},'cp3','bp3')]
  d._active={'debug_id':'generation','app':'app','ids':('code','data'),'source_hash':'unchanged','session_id':1,'target_id':None}
  d.verify_ids=lambda ctx,core:('code','data')
  d.source_hash=lambda app:'unchanged'
  self.app=types.SimpleNamespace(guid='app');self.core=types.SimpleNamespace(ApplicationSessionId=1)
 def test_no_snapping_from_comment_or_blank(self):
  for line in (1,2,5):
   with self.assertRaises(ValueError):d.select_location(self.items,line)
 def test_two_statements_require_column(self):
  with self.assertRaises(ValueError):d.select_location(self.items,3)
  self.assertEqual(d.select_location(self.items,3,25)[2],'bp2')
 def test_column_must_match_executable_position(self):
  with self.assertRaises(ValueError):d.select_location(self.items,3,4)
 def test_bool_and_zero_are_not_line_numbers(self):
  for line in (True,0,-1,'3'):
   with self.assertRaises(ValueError):d.select_location(self.items,line)
 def test_old_generation_and_wrong_app_are_rejected(self):
  with self.assertRaises(ValueError):d.validate_generation({'debug_id':'old'},self.app,None,self.core)
  with self.assertRaises(ValueError):d.validate_generation({'debug_id':'generation'},types.SimpleNamespace(guid='other'),None,self.core)
 def test_source_drift_is_rejected(self):
  d.source_hash=lambda app:'changed'
  with self.assertRaises(RuntimeError):d.validate_generation({'debug_id':'generation'},self.app,None,self.core)
 def test_download_drift_is_rejected(self):
  d.verify_ids=lambda ctx,core:('newcode','data')
  with self.assertRaises(RuntimeError):d.validate_generation({'debug_id':'generation'},self.app,None,self.core)
 def test_reconnect_and_lost_connection_invalidate_generation(self):
  with self.assertRaises(RuntimeError):d.validate_generation({'debug_id':'generation'},self.app,None,types.SimpleNamespace(ApplicationSessionId=2))
  d._owned={'owned':{'evidence':'retained'}};d.disconnected();self.assertIsNone(d._active);self.assertIn('owned',d._owned)
 def test_different_target_cannot_reuse_a_debugger_generation(self):
  d._active['target_id']='target1'
  with self.assertRaises(ValueError):d.validate_generation({'debug_id':'generation','target_id':'target2'},self.app,None,self.core)
 def test_exception_stop_is_not_a_successful_continue(self):
  obj=types.SimpleNamespace(application_state='stop',operation_state=33)
  with self.assertRaises(RuntimeError):d.execution_precondition(obj,'debug_continue')
 def test_step_cannot_be_issued_while_running(self):
  obj=types.SimpleNamespace(application_state='run',operation_state=0)
  with self.assertRaises(ValueError):d.execution_precondition(obj,'debug_step')
 def test_halt_stop_requires_explicit_cycle_choice_before_native_action(self):
  calls=[];d.core=lambda *args:calls.append('native')
  for behavior in (None,'resume','unknown'):
   with self.assertRaises(d.HaltRequiresExplicitStop):d.stop_with_behavior(self.app,None,behavior)
  self.assertEqual(calls,[])
 def test_cleanup_does_not_clear_against_other_download(self):
  calls=[]
  d.core=lambda obj,app:types.SimpleNamespace(CodeId='other',DataId='data')
  d.bp_manager=lambda:types.SimpleNamespace(ClearBreakpoint=lambda point:calls.append(point))
  d._owned={'owned':{'point':'point','app':'app','ids':('code','data')}}
  with self.assertRaises(RuntimeError):d.cleanup(self.app,None)
  self.assertEqual(calls,[]);self.assertIn('owned',d._owned)
 def test_unverified_component_is_rejected_before_execution(self):
  assembly=types.SimpleNamespace(GetName=lambda:types.SimpleNamespace(Version='3.5.20.62'))
  native=types.SimpleNamespace(GetType=lambda:types.SimpleNamespace(FullName='_3S.CoDeSys.OnlineManager.OnlineApplication',Assembly=assembly))
  prop=types.SimpleNamespace(GetValue=lambda obj,args:native)
  obj=types.SimpleNamespace(GetType=lambda:types.SimpleNamespace(GetProperty=lambda name,flags:prop))
  with self.assertRaises(RuntimeError):d.core(obj,self.app)

if __name__=='__main__':unittest.main()
