"""Meaningful host guard tests; runtime acceptance is a separate native suite."""
from pathlib import Path
from unittest.mock import patch
import sys,types,unittest,tempfile
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root/'src/scripts'))
sys.modules['scriptengine']=types.SimpleNamespace()
import invt_debugger as d
import invt_frames as f
import invt_trace as t
f.unicode=t.unicode=str

def native(guid='pou',state=3):
 frame=types.SimpleNamespace(LocationPOU=types.SimpleNamespace(Area=0,Offset=12),StackPointer=123,
                             LocationInformation=types.SimpleNamespace(CompiledPOU=types.SimpleNamespace(ObjectGuid=guid)))
 return types.SimpleNamespace(ApplicationState=state,ApplicationSessionId=1,CallStack=[frame])

class Guards(unittest.TestCase):
 def setUp(self):
  f.state_identity=lambda n:('stamp',getattr(n,'CurrentHitCount',0))
  f.invalidate();d._active={'debug_id':'debug'};self.n=native();self.stamp=f.synchronize(self.n,'debug')
  f._handles['frame']={'index':0,'stamp':self.stamp,'guid':'pou'};self.req={'frame_id':'frame'}
 def test_stable_current_halt_frame_can_be_checked(self):
  self.assertEqual(f.checked_frame(self.req,self.n)[1],self.stamp)
 def test_unknown_handle_is_rejected(self):
  with self.assertRaises(ValueError):f.checked_frame({'frame_id':'unknown'},self.n)
 def test_native_event_invalidates_same_address_and_source_frame(self):
  f.invalidate('event','args')
  with self.assertRaises(ValueError):f.checked_frame(self.req,self.n)
 def test_runtime_hit_change_invalidates_same_address_even_without_event(self):
  self.n.CurrentHitCount=2
  with self.assertRaises(ValueError):f.checked_frame(self.req,self.n)
 def test_run_and_stop_never_return_halted_values(self):
  for state in (1,2):
   with self.assertRaises(ValueError):f.checked_frame(self.req,native(state=state))
 def test_reconnect_invalidates_handle(self):
  self.n.ApplicationSessionId=2
  with self.assertRaises(ValueError):f.checked_frame(self.req,self.n)
 def test_repeated_pou_frames_are_not_silently_selected(self):
  self.n.CallStack.append(self.n.CallStack[0]);stamp=f.synchronize(self.n,'debug')
  f._handles['new']={'index':0,'stamp':stamp,'guid':'pou'}
  with self.assertRaises(ValueError):f.checked_frame({'frame_id':'new'},self.n)
 def test_trace_handles_cannot_adopt_foreign_records(self):
  with self.assertRaises(ValueError):t.selected(types.SimpleNamespace(path='p'),types.SimpleNamespace(guid='a'),'foreign')
 def test_lost_trace_connection_retains_packet_ledger(self):
  record={'packet_owned':True}
  with self.assertRaises(RuntimeError):t.release_packet(record,types.SimpleNamespace(is_logged_in=False),None)
  self.assertTrue(record['packet_owned'])
 def test_unconfirmed_trace_stop_is_not_automatically_replayed(self):
  record={'packet_owned':True,'packet_name':'owned','ids':('code',),'transition_pending':'stop'}
  editor=types.SimpleNamespace(is_running=True,stop=lambda:self.fail('STOP replayed'))
  with patch.object(d,'core',return_value=object()),patch.object(d,'code_ids',return_value=('code',)),patch.object(t,'editor_parts',return_value=(editor,object(),object(),'owned')),patch.object(t,'packet_online',return_value=True):
   with self.assertRaisesRegex(RuntimeError,'no automatic replay'):
    t.release_packet(record,types.SimpleNamespace(is_logged_in=True),None)
  self.assertTrue(record['packet_owned'])
 def csv(self,text,expected=['X']):
  folder=root/'.invt'/'guard-tmp';folder.mkdir(parents=True,exist_ok=True)
  with tempfile.NamedTemporaryFile(dir=folder,suffix='.csv',delete=False) as handle:p=Path(handle.name)
  try:
   p.write_text(text,encoding='utf-8');return t.parse_csv(str(p),expected)
  finally:p.unlink()
 def test_trace_parser_preserves_uint64_timestamps_and_locale_values(self):
  r=self.csv('BufferEntries; 100\n0.Variable; X\n0.Class; 8\n0.Data;\n; 9007199254740993; 1,5\n; 9007199254740994; 2,5\n')
  self.assertEqual(r['signals'][0]['samples'][0],{'timestamp':'9007199254740993','value':'1,5'})
 def test_empty_export_is_not_a_successful_capture(self):
  with self.assertRaises(RuntimeError):self.csv('0.Variable; X\n0.Data;\n')
 def test_trace_export_cannot_substitute_another_variable(self):
  with self.assertRaises(RuntimeError):self.csv('0.Variable; Other\n; 1; 3\n')
 def test_duplicate_or_out_of_order_timestamps_fail(self):
  for second in ('1','0'):
   with self.assertRaises(RuntimeError):self.csv('0.Variable; X\n; 1; 3\n; '+second+'; 4\n')

if __name__=='__main__':unittest.main()
