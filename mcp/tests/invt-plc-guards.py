import importlib.util
import os
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import patch

class Online:
    def __init__(self):
        self.is_logged_in=False
        self.application_state='stop'
        self.operation_state=0
        self.calls=[]
        self.value='0'
        self.fail_login=False
    def login(self,option,delete):
        self.calls.append(('login',option,delete))
        if self.fail_login: raise RuntimeError('connection lost')
        self.is_logged_in=True
    def logout(self): self.calls.append(('logout',)); self.is_logged_in=False
    def start(self): self.calls.append(('start',)); self.application_state='run'
    def stop(self): self.calls.append(('stop',)); self.application_state='stop'
    def Dispose(self): pass
    def read_value(self,path): self.calls.append(('read',path)); return self.value
    def set_prepared_value(self,path,value): self.calls.append(('prepare',path,value))
    def write_prepared_values(self): self.calls.append(('write',))

obj=Online()
engine=NS(online=NS(create_online_application=lambda app:obj,gateways=[]),
          OnlineChangeOption=NS(Never='Never',Keep='Keep'))
device=NS(get_simulation_mode=lambda:False,get_device_identification=lambda:NS(type=4102,id='1631 0051',version='test'),
          get_address=lambda:'USB',set_gateway_and_address=lambda *a:None)
runtime=NS(ancestor_device=lambda app:device,assert_offline=lambda:None,
           variable_path=lambda value:value,prepared_empty=lambda online:None,forced_paths=lambda online:[])
hardware=NS(configured_address=lambda:'192.168.3.10')
with patch.dict(sys.modules,scriptengine=engine,invt_hardware=hardware,invt_runtime=runtime,
                invt_executor=NS(with_executor=lambda action:action())):
    spec=importlib.util.spec_from_file_location('plc',Path(__file__).resolve().parents[1]/'src/scripts/invt_plc.py')
    plc=importlib.util.module_from_spec(spec);spec.loader.exec_module(plc)
plc.unicode=str
project=NS(path='owned.project',save=lambda:None)
application=NS(guid='application')

class PhysicalGuards(unittest.TestCase):
    def setUp(self):
        global obj
        obj=Online()
        self.env=patch.dict(os.environ,INVT_MCP_PHYSICAL_RUNTIME='1'); self.env.start();self.addCleanup(self.env.stop)
        self.signature=patch.object(plc,'signature',return_value=('source','address'));self.addCleanup(self.signature.stop);self.signature=self.signature.start()
        self.identity=patch.object(plc,'read_identity',return_value={'type':4102,'id':'1631 0051','version':'test'});self.addCleanup(self.identity.stop);self.identity=self.identity.start()
        self.boot=patch.object(plc,'boot_settings',return_value={'after':{'CreateBootApplicationOnDownload':False}});self.addCleanup(self.boot.stop);self.boot=self.boot.start()
        plc._binding={'target_id':'fresh','signature':('source','address'),'application_guid':'application'}
        plc._attached=False;plc._uncertain=False
        device.get_simulation_mode=lambda:False
    def call(self,op,**args):
        return plc.perform(project,application,dict(operation=op,target_id=plc._binding['target_id'],**args))
    def attach(self): obj.is_logged_in=True;plc._attached=True
    def test_host_environment_opt_in_required(self):
        with patch.dict(os.environ,INVT_MCP_PHYSICAL_RUNTIME=''):
            with self.assertRaises(RuntimeError): self.call('plc_start')
        self.assertEqual(obj.calls,[])
    def test_stale_token_refused_before_online_access(self):
        with self.assertRaises(ValueError): plc.perform(project,application,{'operation':'plc_start','target_id':'stale'})
        self.assertEqual(obj.calls,[])
    def test_unknown_or_simulation_mode_refused(self):
        for mode in (None,True):
            device.get_simulation_mode=lambda:mode
            with self.assertRaises(RuntimeError): self.call('plc_connect')
        self.assertEqual(obj.calls,[])
    def test_project_source_or_address_change_refused(self):
        self.signature.return_value=('different source','address')
        with self.assertRaises(RuntimeError): self.call('plc_download')
        self.assertEqual(obj.calls,[])
    def test_unowned_login_is_not_adopted(self):
        obj.is_logged_in=True
        self.assertFalse(self.call('plc_stop')['ok'])
        self.assertEqual(obj.calls,[])
    def test_connect_keeps_existing_program_and_rotates_token(self):
        result=self.call('plc_connect')
        self.assertTrue(result['ok']);self.assertEqual(obj.calls,[('login','Keep',False)])
        self.assertNotEqual(result['target_id'],'fresh');self.boot.assert_not_called()
    def test_download_disables_boot_and_never_starts_or_deletes_foreign_apps(self):
        result=self.call('plc_download')
        self.assertTrue(result['ok']);self.boot.assert_called_once()
        self.assertEqual(obj.calls,[('login','Never',False)])
    def test_measured_identity_mismatch_prevents_download(self):
        self.identity.return_value={'type':4102,'id':'wrong','version':'test'}
        self.assertFalse(self.call('plc_download')['ok'])
        self.assertEqual(obj.calls,[]);self.assertFalse(plc._uncertain)
    def test_uncertain_login_blocks_replay(self):
        obj.fail_login=True
        self.assertFalse(self.call('plc_download')['ok']);self.assertTrue(plc._uncertain)
        with self.assertRaises(RuntimeError):self.call('plc_download')
        self.assertEqual(len(obj.calls),1)
    def test_disconnect_and_cleanup_leave_running_application_running(self):
        self.attach();obj.application_state='run'
        result=self.call('plc_disconnect')
        self.assertTrue(result['ok']);self.assertEqual(obj.application_state,'run')
        self.assertEqual(obj.calls,[('logout',)]);self.assertFalse(result['application_stop_requested'])
        self.assertNotEqual(result['target_id'],'fresh')
    def test_project_edits_blocked_while_attached_or_uncertain(self):
        self.attach()
        with self.assertRaises(RuntimeError):plc.assert_offline()
        plc._attached=False;plc._uncertain=True
        with self.assertRaises(RuntimeError):plc.assert_offline()
    def test_no_write_without_fresh_value(self):
        self.attach();obj.value=None
        self.assertFalse(self.call('plc_write',variable='PLC_PRG.TestInput',value='21')['ok'])
        self.assertEqual(obj.calls,[('read','PLC_PRG.TestInput')]);self.assertFalse(plc._uncertain)
    def test_foreign_forced_variable_cannot_be_written(self):
        self.attach()
        with patch.object(runtime,'forced_paths',return_value=['PLC_PRG.TestInput']):
            self.assertFalse(self.call('plc_write',variable='PLC_PRG.TestInput',value='21')['ok'])
        self.assertEqual(obj.calls,[])
    def test_halt_and_exception_do_not_implicitly_resume(self):
        self.attach();obj.application_state='halt_on_bp'
        self.assertFalse(self.call('plc_stop')['ok'])
        obj.application_state='stop';obj.operation_state=32
        self.assertFalse(self.call('plc_start')['ok'])
        self.assertEqual(obj.calls,[])
    def test_cleanup_ignores_other_applications(self):
        self.attach();plc.cleanup(project,NS(guid='other'))
        self.assertEqual(obj.calls,[]);self.assertTrue(plc._attached)

if __name__=='__main__':unittest.main()

