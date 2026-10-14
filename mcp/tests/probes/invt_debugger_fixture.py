# -*- coding: utf-8 -*-
"""Fixed test-fixture foreign point, manual-source and connection-loss probes."""
import json
import invt_operations as ops
import invt_runtime as rt
import invt_debugger as dbg
from System import Array, Object, String, Int32, Int64, Enum
_foreign = None
_original = None


def run(request, action):
    global _foreign, _original
    project = ops.owned()
    app = ops.choose_application(list(project.get_children(True)), request)
    rt.checked(project, app, request)
    def act(obj):
        global _foreign, _original
        rt.checked(project, app, request)
        native = dbg.core(obj, app) if action not in ('foreign_status','foreign_clear') else None
        ctx = dbg.context(app)
        if action == 'foreign_create':
            item, cp, bp = dbg.select_location(dbg.locations(app, ctx, request['object_guid']), request['line'], 1)
            pos = cp.GetSourcePositionOfBreakpoint(bp)
            manager = dbg.bp_manager()
            factory = [m for m in manager.GetType().GetMethods(dbg.flags()) if m.Name == 'CreateBreakpoint' and len(m.GetParameters()) == 8][0]
            enum = factory.GetParameters()[6].ParameterType
            names = [n for n in Enum.GetNames(enum) if str(n).lower() in ('always','none')]
            _foreign = factory.Invoke(manager, Array[Object]([app.guid, Int32(pos.ProjectHandle),cp.ObjectGuid,Int64(pos.PositionCombination),None,Array[String](['MainTask']),Enum.Parse(enum,names[0]),Int32(0)]))
            if not manager.SetBreakpoint(_foreign):raise RuntimeError('Foreign fixture point refused')
            if not manager.GetType().GetMethod('EnableBreakpoint',dbg.flags()).Invoke(manager,Array[Object]([_foreign])):raise RuntimeError('Foreign fixture activation refused')
        elif action == 'foreign_clear':
            if _foreign is not None:
                dbg.bp_manager().ClearBreakpoint(_foreign)
                _foreign = None
        elif action == 'logout':
            obj.logout()  # Deliberate loss, never alter the MCP ownership ledger.
        elif action == 'metadata':
            return {'executionpoints_remain_active':bool(native.ExecutionpointsRemainActive),
                'state':rt.state(obj), 'core_device_methods':[str(m.ToString()) for m in native.OnlineDevice.GetType().GetMethods(dbg.flags()) if 'log' in m.Name.lower() or 'exception' in m.Name.lower()],
                'bp_manager_methods':[str(m.ToString()) for m in dbg.bp_manager().GetType().GetMethods(dbg.flags()) if 'disable' in m.Name.lower()],
                'points':[dbg.point_info(p) for p in dbg.bp_manager().GetBreakpoints(app.guid)]}
        elif action in ('source_change', 'source_restore'):
            p = [o for o in app.get_children(True) if str(o.guid)==request['object_guid']][0]
            if action == 'source_change':
                _original = p.textual_implementation.text
                p.textual_implementation.replace(_original+'\n(* fixture manual source change *)')
            else:
                p.textual_implementation.replace(_original)
            project.save()
        elif action != 'foreign_status':
            raise ValueError('Unknown fixed fixture probe')
        return {'foreign_set':bool(_foreign.IsSet) if _foreign is not None else False,
                'foreign_enabled':bool(_foreign.IsEnabled) if _foreign is not None else False,
                'points':[dbg.point_info(p) for p in dbg.bp_manager().GetBreakpoints(app.guid)]}
    return rt.with_executor(lambda:rt.use_online(app,act))
