"""Host tests for refusal and force ownership, independent of installed Studio."""
import importlib.util
import pathlib
import sys
import types
import unittest

root = pathlib.Path(__file__).resolve().parents[1]
sys.modules['scriptengine'] = types.SimpleNamespace()
sys.modules['invt_executor'] = types.SimpleNamespace(with_executor=lambda fn, *a: fn(*a))
spec = importlib.util.spec_from_file_location('invt_runtime', root / 'src/scripts/invt_runtime.py')
r = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r)
r.basestring, r.unicode = str, str

class Guards(unittest.TestCase):
    def setUp(self):
        r._binding, r._attached, r._forces, r._uncertain = None, False, {}, False
        self.mode = False
        self.calls = []
        self.device = types.SimpleNamespace(
            guid='device', parent=None, get_name=lambda: 'misleading device name',
            get_address=lambda: 'physical configured address',
            get_simulation_mode=lambda: self.mode,
            get_device_identification=lambda: types.SimpleNamespace(type=4102, id='1631 0050', version='3.5.15.20'))
        self.app = types.SimpleNamespace(guid='app', parent=self.device, get_name=lambda: 'Application')
        self.project = types.SimpleNamespace(path='owned.project')

    def test_physical_and_unknown_refused_before_native_call(self):
        for mode in (False, None):
            self.mode = mode
            info, _ = r.target(self.project, self.app)
            self.assertIn(info['mode'], ('physical', 'unknown'))
            with self.assertRaises(RuntimeError):
                r.checked(self.project, self.app, {'target_id': info['target_id']})

    def test_mode_change_invalidates_token(self):
        before, _ = r.target(self.project, self.app)
        self.mode = True
        after, _ = r.target(self.project, self.app)
        self.assertNotEqual(before['target_id'], after['target_id'])
        with self.assertRaises(ValueError):
            r.checked(self.project, self.app, {'target_id': before['target_id']})

    def test_attached_target_change_does_not_adopt_other_target(self):
        self.mode = True
        r.target(self.project, self.app)
        r._attached = True
        self.mode = False
        with self.assertRaises(RuntimeError):
            r.target(self.project, self.app)

    def test_selective_unforce_preserves_foreign_force(self):
        active = ['PLC_PRG.ours', 'PLC_PRG.foreign']
        r._forces = {'PLC_PRG.ours': '42'}
        prepared = []
        obj = types.SimpleNamespace(get_prepared_expressions=lambda: [], get_forced_expressions=lambda: active,
            set_unforce_value=lambda p, restore: prepared.append(p),
            force_prepared_values=lambda: active.remove(prepared[0]))
        with self.assertRaises(ValueError):
            r.unforce_owned(obj, 'PLC_PRG.foreign')
        r.unforce_owned(obj, 'PLC_PRG.ours')
        self.assertEqual(active, ['PLC_PRG.foreign'])
        self.assertEqual(r._forces, {})

    def test_foreign_preparation_refused_and_lost_connection_retains_force_ownership(self):
        with self.assertRaises(RuntimeError):
            r.prepared_empty(types.SimpleNamespace(get_prepared_expressions=lambda: ['foreign']))
        r._forces = {'PLC_PRG.ours': '1'}
        with self.assertRaises(RuntimeError):
            r.detach(types.SimpleNamespace(is_logged_in=False))
        self.assertEqual(r._forces, {'PLC_PRG.ours': '1'})

    def test_variable_paths_exclude_evaluation_and_controls(self):
        for path in ['PLC_PRG.x', 'PLC_PRG.st.x', 'PLC_PRG.a[2]']:
            self.assertEqual(r.variable_path(path), path)
        for path in ['PLC_PRG.x\n', 'f()', 'a := 1', 'a[1+2]', 'a[-1]', 'a;STOP']:
            with self.assertRaises(ValueError):
                r.variable_path(path)

    def test_online_object_disposed_even_when_native_action_fails(self):
        disposed = []
        original = r.online
        r.online = lambda application: types.SimpleNamespace(Dispose=lambda: disposed.append(True))
        try:
            def failing(obj):
                raise RuntimeError('native action failure')
            with self.assertRaises(RuntimeError):
                r.use_online(self.app, failing)
            self.assertEqual(disposed, [True])
        finally:
            r.online = original

if __name__ == '__main__':
    unittest.main()
