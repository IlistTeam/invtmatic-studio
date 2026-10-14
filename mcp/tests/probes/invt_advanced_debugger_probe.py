# -*- coding: utf-8 -*-
"""Fixed developer research on an owned simulation copy; not a public endpoint."""
import os
import time
import traceback
import re
import uuid
import scriptengine as se
import invt_operations as ops
import invt_runtime as rt
import invt_debugger as dbg
from System import AppDomain

if '_trace' not in globals():
    _trace = None
    _editor = None


def method_calls(method):
    """Read bounded method-call metadata; no method invocation or binary export."""
    from System.Reflection.Emit import OpCodes
    from System import BitConverter
    import clr
    body = method.GetMethodBody()
    if body is None:
        return []
    code = body.GetILAsByteArray()
    if len(code) > 12000:
        return ['Body exceeds probe limit']
    opcodes = {int(f.GetValue(None).Value) & 65535: f.GetValue(None) for f in clr.GetClrType(OpCodes).GetFields(dbg.flags())}
    result, i = [], 0
    while i < len(code):
        value = int(code[i]); i += 1
        if value == 254:
            value = 65024 | int(code[i]); i += 1
        if value not in opcodes:
            result.append({'decode_error':'Unknown metadata opcode at '+str(i)})
            return result
        op = opcodes[value]
        kind = str(op.OperandType)
        if kind == 'InlineSwitch':
            size = 4 + 4 * BitConverter.ToInt32(code,i)
        elif kind == 'InlineNone':
            size = 0
        elif kind in ('ShortInlineBrTarget','ShortInlineI','ShortInlineVar'):
            size = 1
        elif kind == 'InlineVar':
            size = 2
        elif kind in ('InlineI8','InlineR'):
            size = 8
        else:
            size = 4
        if kind in ('InlineMethod','InlineField','InlineType'):
            try:
                member = method.Module.ResolveMember(BitConverter.ToInt32(code,i))
                result.append({'op': op.Name, 'member': unicode(member.DeclaringType.FullName) + ':' + unicode(member)})
            except Exception as error:
                result.append({'op': op.Name, 'error': unicode(error)})
        i += size
    return result


def shape(value):
    typ = value if hasattr(value, 'GetMethods') else value.GetType()
    return {'type': unicode(typ.FullName), 'assembly': unicode(typ.Assembly.GetName().Name),
            'version': str(typ.Assembly.GetName().Version),
            'constructors': [unicode(c.ToString()) for c in typ.GetConstructors(dbg.flags())],
            'methods': [unicode(m.ToString()) for m in typ.GetMethods(dbg.flags()) if m.DeclaringType == typ],
            'properties': [{'name': p.Name, 'type': unicode(p.PropertyType.FullName)} for p in typ.GetProperties(dbg.flags())],
            'fields': [{'name': f.Name, 'type': unicode(f.FieldType.FullName)} for f in typ.GetFields(dbg.flags())]}


def run(request, stage):
    project = ops.owned()
    app = ops.choose_application(list(project.get_children(True)), request)
    info, device = rt.checked(project, app, request)
    if info['mode'] != 'simulation':
        raise RuntimeError('Verified simulation required for advanced research')
    project.active_application = app
    result = {'stage': stage, 'target': info}
    global _trace, _editor
    if stage == 'trace_create':
        if _trace is not None or any(o.get_name() == 'Codex_Trace_Probe' for o in app.get_children(True)):
            raise RuntimeError('Probe will not adopt or replace an existing trace')
        _trace = se.trace.create(app, 'Codex_Trace_Probe', 'MainTask')
        result['shape'] = shape(_trace)
        _trace.auto_start = False
        _trace.trigger_enabled = False
        _trace.every_n_cycles = 1
        nodes = [o for o in app.get_children(True) if o.get_name() == 'Codex_Trace_Probe']
        if len(nodes) != 1:
            raise RuntimeError('Trace node identity is not unique')
        _trace.record_name = 'CodexTrace_' + uuid.uuid4().hex
        for expression in ('PLC_PRG.nCycle', 'PLC_PRG.nResult'):
            variable = _trace.variable_list.add()
            variable.variable_name = expression
            variable.enabled = True
        result.update(guid=str(nodes[0].guid), task=_trace.task_name, auto_start=_trace.auto_start,
                      variables=[v.variable_name for v in _trace.variable_list])
        project.save()
        return result
    if stage == 'trace_capture':
        if _trace is None:
            raise RuntimeError('Owned probe trace required')
        result['phases'] = []
        stop_requested = False
        def await_running(expected):
            until = time.time() + 5
            while time.time() < until:
                if bool(_editor.is_running) == expected:
                    return
                se.system.delay(100)
            raise RuntimeError('Trace status transition not confirmed; no automatic replay')
        try:
            _editor = _trace.open_editor()
            result['editor_shape'] = shape(_editor)
            result['phases'].append({'phase': 'editor', 'online': _editor.is_online, 'logged_in': _editor.is_logged_in})
            rt.checked(project, app, request)
            _editor.download()
            result['phases'].append({'phase': 'download', 'logged_in': _editor.is_logged_in})
            _editor.start()
            await_running(True)
            result['phases'].append({'phase': 'start', 'running': _editor.is_running})
            se.system.delay(1500)
            result['packet_state'] = unicode(_editor.get_packet_state())
            stop_requested = True
            _editor.stop()
            await_running(False)
            result['phases'].append({'phase': 'stop', 'running': _editor.is_running})
            output = os.path.join(os.path.dirname(__file__), 'trace-probe.csv')
            _editor.save(output)
            result.update(export_path=output, exported=os.path.exists(output),
                          export_size=os.path.getsize(output) if os.path.exists(output) else 0)
        except Exception:
            result['error'] = traceback.format_exc()
        finally:
            if _editor is not None and _editor.is_running and not stop_requested:
                _editor.stop()
        return result
    if stage == 'metadata':
        def inspect(obj):
            native, ctx = dbg.core(obj, app), dbg.context(app)
            if unicode(obj.application_state).lower() != 'halt_on_bp':
                raise RuntimeError('HALT required for frame research')
            dbg.validate_generation(request, app, ctx, native)
            result['snapshot'] = dbg.snapshot(app, obj, native, ctx)
            result['context_shape'] = shape(ctx)
            result['online_shape'] = shape(obj)
            result['get_online_var_ref_calls'] = method_calls(obj.GetType().GetMethod('GetOnlineVarRef',dbg.flags()))
            result['online_fields'] = []
            for field in obj.GetType().GetFields(dbg.flags()):
                if field.FieldType.FullName in ('System.String','System.Boolean','System.Int32'):
                    continue
                val = field.GetValue(obj)
                if val is not None:
                    result['online_fields'].append({'name': field.Name, 'shape': shape(val)})
            system_asm = [a for a in AppDomain.CurrentDomain.GetAssemblies() if a.GetName().Name == 'SystemInstances'][0]
            lm = system_asm.GetType('_3S.CoDeSys.Core.SystemInstances').GetProperty('LanguageModelMgr',dbg.flags()).GetValue(None,None)
            result['model_manager_shape'] = shape(lm)
            result['system_instances_properties'] = [p.Name for p in system_asm.GetType('_3S.CoDeSys.Core.SystemInstances').GetProperties(dbg.flags())]
            result['compiler_scopes'] = []
            for cp in ctx.GetAllCompiledPOUsEx():
                if unicode(cp.Name).upper() in ('F_INNER','F_OUTER'):
                    scope = ctx.CreateOnlineExpressionScope(cp.SignatureId)
                    result['compiler_scopes'].append({'name':unicode(cp.Name),'signature_id':int(cp.SignatureId),'scope_shape':shape(scope),
                        'get_var_reference_calls':[method_calls(m) for m in lm.GetType().GetMethods(dbg.flags()) if m.Name=='GetVarReference' and len(m.GetParameters())==5]})
            result['helper_shape'] = shape(native.GetType().GetField('_monitoringHelper', dbg.flags()).GetValue(native))
            result['core_monitor_methods'] = [unicode(m.ToString()) for m in native.GetType().GetMethods(dbg.flags())
                                              if re.search('stack|instance|monitor|expression',m.Name,re.I)]
            result['frame_shapes'] = [shape(f) for f in native.CallStack or []]
            result['pous'] = []
            for p in ctx.GetAllCompiledPOUsEx():
                if unicode(p.Name).upper() not in ('F_INNER','F_OUTER','PLC_PRG'):
                    continue
                entry = {'name': unicode(p.Name), 'shape': shape(p)}
                for prop in p.GetType().GetProperties(dbg.flags()):
                    if prop.Name not in ('Signature','Scope','LocalScope'):
                        continue
                    try:
                        value = prop.GetValue(p,None)
                        if value is not None:
                            entry[prop.Name] = shape(value)
                    except Exception as error:
                        entry[prop.Name] = {'error': unicode(error)}
                result['pous'].append(entry)
            result['types'] = []
            for asm in AppDomain.CurrentDomain.GetAssemblies():
                if asm.GetName().Name not in ('Online','OnlineManager.plugin','LanguageModel','LanguageModel2','LanguageModelInterface','ScriptDriverOnline','ScriptDriverOnline.plugin',ctx.GetType().Assembly.GetName().Name):
                    continue
                try:
                    types = asm.GetTypes()
                except Exception as error:
                    types = [t for t in getattr(error,'Types',[]) if t is not None]
                for typ in types:
                    if re.search('MonitoringExpression|StackEntry|StackFrame|OnlineVarRef|MonitoringContext|VarRefServices|DataLocationInformation|OnlineExpressionScope',typ.Name):
                        result['types'].append(shape(typ))
        rt.with_executor(lambda:rt.use_online(app,inspect))
        return result
    if stage == 'locals_read':
        def local_probe(obj):
            native,ctx = dbg.core(obj,app),dbg.context(app)
            dbg.validate_generation(request,app,ctx,native)
            if unicode(obj.application_state).lower() != 'halt_on_bp':
                raise RuntimeError('HALT required')
            asm=[a for a in AppDomain.CurrentDomain.GetAssemblies() if a.GetName().Name=='SystemInstances'][0]
            system=asm.GetType('_3S.CoDeSys.Core.SystemInstances')
            lm=system.GetProperty('LanguageModelMgr',dbg.flags()).GetValue(None,None)
            online=system.GetProperty('OnlineMgr',dbg.flags()).GetValue(None,None)
            result['online_manager']=shape(online)
            provider=lm.GetType().GetField('LMServiceProvider',dbg.flags()).GetValue(lm)
            monitoring=provider.MonitoringService
            result['monitoring_service']=shape(monitoring)
            result['varref_parameters']=[{'signature':unicode(m),'parameters':[{'name':p.Name,'type':unicode(p.ParameterType.FullName)} for p in m.GetParameters()]} for m in monitoring.GetType().GetMethods(dbg.flags()) if m.Name=='GetVarReference']
            result['frame_information']=[]
            result['resolved_variables']=[]
            result['set_stack_calls']=[method_calls(m) for m in online.GetType().GetMethods(dbg.flags()) if m.Name=='SetStackFrameInStackRelativeVarRef']
            for index,frame in enumerate(native.CallStack or []):
                value=frame.LocationInformation
                entry={'index':index,'stack_pointer':str(frame.StackPointer),'shape':shape(value),
                       'interfaces':[shape(t) for t in value.GetType().GetInterfaces()]}
                result['frame_information'].append(entry)
                if value.CompiledPOU is not None and unicode(value.CompiledPOU.Name).upper() in ('F_INNER','F_OUTER'):
                    from System import Int32
                    for expression in ('iValue','nInnerLocal' if unicode(value.CompiledPOU.Name).upper()=='F_INNER' else 'nOuterLocal'):
                        item={'frame_index':index,'expression':expression,'instance_path':unicode(value.EditorInstancePath),
                              'pou':unicode(value.CompiledPOU.Name)}
                        try:
                            ref=monitoring.GetVarReference(app.guid,value.EditorInstancePath,expression,Int32(value.SourcePosition.ProjectHandle),value.CompiledPOU.ObjectGuid)
                            item['shape']=shape(ref)
                            item['interfaces']=[shape(t) for t in ref.GetType().GetInterfaces()]
                            item['address_shape']=shape(ref.AddressInfo)
                            item['stack_relative']=bool(ref.AddressInfo.ContainsStackRelativeAddress)
                            watch=None
                            try:
                                watch=online.CreateWatch(ref)
                                until=time.time()+2
                                while time.time()<until:
                                    se.system.delay(100)
                                    item['state']=unicode(watch.State)
                                    if item['state']=='Good' and watch.Value is not None:
                                        item['value']=unicode(watch.Value)
                                        break
                                if 'value' not in item:
                                    item['state_message']=unicode(watch.GetStateMessage())
                            finally:
                                if watch is not None:
                                    watch.Release()
                        except Exception as error:
                            item['error']=unicode(error)
                        result['resolved_variables'].append(item)
        rt.with_executor(lambda:rt.use_online(app,local_probe))
        return result
    raise ValueError('Unknown fixed advanced research stage')
