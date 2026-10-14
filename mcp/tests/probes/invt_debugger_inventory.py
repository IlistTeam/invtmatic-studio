# -*- coding: utf-8 -*-
"""Read-only developer probe of installed debugger metadata; never executes commands."""
import json
import re
import os
import scriptengine as se
import invt_operations as ops
import invt_runtime as rt
from System import AppDomain, Array, String, Object, Type, Enum, Int32, Int64
from System.Reflection import BindingFlags

FLAGS = BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance | BindingFlags.Static

def json_safe(value):
    if isinstance(value, basestring):
        try:
            normalized = unicode(value)
        except UnicodeError:
            try:
                normalized = value.decode('utf-8')
            except UnicodeError:
                normalized = value.decode('cp1251', 'replace')
        # Some private vendor metadata names are byte-valued CLR strings that
        # IronPython's JSON encoder misidentifies as UTF-8 bytes. Preserve their
        # escaped spelling instead of letting an irrelevant private name abort
        # the entire metadata inventory. Public ASCII API names are unchanged.
        if any(ord(c) > 127 for c in normalized):
            return normalized.encode('unicode_escape')
        return normalized
    if isinstance(value, dict):
        return {json_safe(k): json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(v) for v in value]
    return value

def shape(obj):
    typ = obj.GetType()
    return {'type': unicode(typ.FullName),
            'methods': [unicode(m.ToString()) for m in typ.GetMethods(FLAGS)
                        if m.DeclaringType == typ],
            'fields': [{'name': unicode(f.Name), 'type': unicode(f.FieldType.FullName)} for f in typ.GetFields(FLAGS)]}

def inventory(request):
    project = ops.owned()
    application = ops.choose_application(list(project.get_children(True)), request)
    info, device = rt.checked(project, application, request)
    result = {'target': info, 'commands': [], 'assemblies': [], 'scriptengine_names': dir(se),
              'system_members': dir(se.system), 'application_members': dir(application)}
    for command in se.system.commands:
        tokens = [unicode(t) for t in (command.tokens or [])]
        text = (unicode(command.name) + ' ' + ' '.join(tokens)).lower()
        if any(k in text for k in ('break', 'step', 'cycle', 'debug', 'callstack', 'trace', u'точк', u'шаг', u'курсор')):
            item = {'name': unicode(command.name), 'tokens': tokens, 'guid': str(command.guid),
                    'members': dir(command)}
            try:
                item['reflection'] = shape(command)
                fields = []
                for f in command.GetType().GetFields(FLAGS):
                    try:
                        value = f.GetValue(command)
                        if value is not None:
                            fields.append({'name': f.Name, 'value_type': unicode(value.GetType().FullName),
                                           'shape': shape(value) if 'command' in f.Name.lower() else None})
                    except Exception as e:
                        fields.append({'name': f.Name, 'error': unicode(e)})
                item['field_values'] = fields
            except Exception as e:
                item['reflection_error'] = unicode(e)
            result['commands'].append(item)
    def inspect_online(obj):
        result['online_shape'] = shape(obj)
        fields = []
        for f in obj.GetType().GetFields(FLAGS):
            try:
                value = f.GetValue(obj)
                fields.append({'name': f.Name, 'value_type': unicode(value.GetType().FullName) if value is not None else None,
                               'shape': shape(value) if value is not None and 'app' in f.Name.lower() else None})
            except Exception as e:
                fields.append({'name': f.Name, 'error': unicode(e)})
        result['online_fields'] = fields
    rt.with_executor(lambda: rt.use_online(application, inspect_online))
    for assembly in AppDomain.CurrentDomain.GetAssemblies():
        name = assembly.GetName().Name
        if name not in ('Online', 'OnlineCommands', 'Breakpoints', 'STEditor', 'Commands',
                        'ScriptEngine', 'ScriptDriverOnline', 'ScriptDriverOnline.plugin',
                        'OnlineManager.plugin', 'OnlineCommands.plugin', 'Breakpoints.plugin', 'STEditor.plugin'):
            continue
        entry = {'name': name, 'version': unicode(assembly.GetName().Version), 'types': []}
        try:
            types = assembly.GetTypes()
        except Exception as e:
            types = [t for t in getattr(e, 'Types', []) if t is not None]
            entry['load_error'] = unicode(e)
        for typ in types:
            if not re.search(r'(Application|Breakpoint|SingleStep|StepInto|StepOver|StepOut|CodePosition|SourcePosition|CommandManager|CommandContext|ICommand|CallStack)',typ.Name,re.I):
                continue
            entry['types'].append({'name': unicode(typ.FullName), 'public': typ.IsPublic,
                'methods': [unicode(m.ToString()) for m in typ.GetMethods(FLAGS)
                            if m.DeclaringType == typ and re.search(r'(break|step|cycle|start|stop|halt|position|context|execute|query|instance|application|stack)', m.Name, re.I)],
                'constructors': [unicode(c.ToString()) for c in typ.GetConstructors(FLAGS)],
                'properties': [{'name': p.Name, 'type': unicode(p.PropertyType.FullName)} for p in typ.GetProperties(FLAGS)]})
        result['assemblies'].append(entry)
    return result


def core_inventory(request):
    project = ops.owned()
    application = ops.choose_application(list(project.get_children(True)), request)
    info, device = rt.checked(project, application, request)
    result = {'target': info, 'application_shape': shape(application), 'model_types': []}
    if hasattr(se, 'trace'):
        result['trace_shape'] = shape(se.trace)
    def inspect(obj):
        prop = obj.GetType().GetProperty('Application', FLAGS)
        if prop is None:
            raise RuntimeError('Core Application getter not found')
        core = prop.GetValue(obj, None)
        if str(core.ApplicationGuid).lower() != str(application.guid).lower() or not core.IsLoggedIn:
            raise RuntimeError('Core application identity/login mismatch')
        result['core_shape'] = shape(core)
        result['core_interfaces'] = [unicode(t.FullName) for t in core.GetType().GetInterfaces()]
        result['core_state'] = unicode(core.ApplicationState)
        fields = []
        for f in core.GetType().GetFields(FLAGS):
            item = {'name': f.Name, 'type': unicode(f.FieldType.FullName)}
            try:
                value = f.GetValue(core)
                if value is not None and re.search(r'(compile|context|model|debug|object|manager)', f.Name, re.I):
                    item['shape'] = shape(value)
            except Exception as e:
                item['error'] = unicode(e)
            fields.append(item)
        result['core_field_values'] = fields
    rt.with_executor(lambda: rt.use_online(application, inspect))
    for assembly in AppDomain.CurrentDomain.GetAssemblies():
        if assembly.GetName().Name not in ('LanguageModel', 'Compiler', 'Breakpoints.plugin', 'ScriptDriverProjects.plugin', 'TextualObject', 'Database', 'MetaObject'):
            continue
        try:
            types = assembly.GetTypes()
        except Exception:
            continue
        for typ in types:
            if not re.search(r'^(ICompiled(Application|Project|POU).*|IBreakpoint.*|IDataLocation.*|I(Position|CodePosition).*|Breakpoints|BPManager|Breakpoint.*|.*CompilationContext.*|ScriptObject)$', typ.Name, re.I):
                continue
            result['model_types'].append({'assembly': assembly.GetName().Name, 'name': unicode(typ.FullName),
                'methods': [unicode(m.ToString()) for m in typ.GetMethods(FLAGS) if m.DeclaringType == typ],
                'properties': [{'name': p.Name, 'type': unicode(p.PropertyType.FullName)} for p in typ.GetProperties(FLAGS)],
                'constructors': [unicode(c.ToString()) for c in typ.GetConstructors(FLAGS)]})
    return result


def execution_probe(request):
    """Only known stepping commands on the already owned, verified simulation."""
    project = ops.owned()
    application = ops.choose_application(list(project.get_children(True)), request)
    info, device = rt.checked(project, application, request)
    project.active_application = application
    result = {'target': info, 'events': [], 'services': [], 'bp_static_fields': []}
    variables = ('PLC_PRG.nCycle', 'PLC_PRG.nAfter', 'PLC_PRG.fbProbe.nInside')
    def act(obj):
        rt.checked(project, application, request)
        if not obj.is_logged_in:
            raise RuntimeError('Owned simulation disconnected')
        core = obj.GetType().GetProperty('Application', FLAGS).GetValue(obj, None)
        if str(core.ApplicationGuid).lower() != str(application.guid).lower():
            raise RuntimeError('Core identity mismatch')
        def snapshot(label):
            rt.checked(project, application, request)
            item = {'label': label, 'state': unicode(obj.application_state), 'values': {}}
            for variable in variables:
                try:
                    item['values'][variable] = unicode(obj.read_value(variable))
                except Exception as e:
                    item['values'][variable] = {'error': unicode(e)}
            position = core.CurrentPosition
            item['position'] = None if position is None else {'shape': shape(position),
                'area': int(position.Area), 'offset': int(position.Offset)}
            item['instance_path'] = unicode(core.CurrentInstancePath)
            try:
                item['call_stack'] = [shape(entry) for entry in core.CallStack]
            except Exception as e:
                item['call_stack_error'] = unicode(e)
            result['events'].append(item)
        snapshot('initial')
        if unicode(obj.application_state).lower() != 'stop':
            raise RuntimeError('SingleCycle probe requires STOP')
        core.SingleCycle()
        se.system.delay(250)
        snapshot('core_single_cycle')
        for tokens in ('online singlecycleactiveapp', 'breakpoints stepinto',
                       'breakpoints stepover', 'breakpoints stepinto', 'breakpoints stepout'):
            rt.checked(project, application, request)
            command = se.system.commands[tokens]
            native = command.GetType().GetField('_command', FLAGS).GetValue(command)
            event = {'label': 'command', 'tokens': tokens, 'enabled': bool(native.Enabled)}
            result['events'].append(event)
            if not native.Enabled:
                continue
            try:
                command.execute(Array[String]([]))
                se.system.delay(250)
                event['executed'] = True
            except Exception as e:
                event['error'] = unicode(e)
            snapshot(tokens)
    rt.with_executor(lambda: rt.use_online(application, act))
    for assembly in AppDomain.CurrentDomain.GetAssemblies():
        try:
            types = assembly.GetTypes()
        except Exception:
            continue
        for typ in types:
            if typ.Name == 'BPManager':
                for f in typ.GetFields(FLAGS):
                    if f.IsStatic:
                        value = f.GetValue(None)
                        result['bp_static_fields'].append({'name': f.Name, 'type': unicode(f.FieldType.FullName),
                                                         'value': unicode(value) if value is not None else None})
            if typ.Name in ('SystemInstances', 'PluginManager', 'ComponentManager', 'ServiceManager'):
                result['services'].append({'name': unicode(typ.FullName), 'assembly': assembly.GetName().Name,
                    'methods': [unicode(m.ToString()) for m in typ.GetMethods(FLAGS) if m.DeclaringType == typ and re.search(r'(instance|service|component|system|global)',m.Name,re.I)],
                    'properties': [{'name': p.Name, 'type': unicode(p.PropertyType.FullName), 'static': bool(p.GetGetMethod(True) and p.GetGetMethod(True).IsStatic)} for p in typ.GetProperties(FLAGS)]})
    return result


def model_inventory(request):
    project = ops.owned()
    application = ops.choose_application(list(project.get_children(True)), request)
    info, device = rt.checked(project, application, request)
    result = {'target': info, 'project_shape': shape(project), 'services': {}, 'project_fields': []}
    for f in project.GetType().GetFields(FLAGS):
        try:
            value = f.GetValue(project)
            result['project_fields'].append({'name': f.Name, 'type': unicode(f.FieldType.FullName),
                'value': unicode(value) if value is not None else None,
                'shape': shape(value) if value is not None and not f.FieldType.IsPrimitive else None})
        except Exception as e:
            result['project_fields'].append({'name': f.Name, 'error': unicode(e)})
    for assembly in AppDomain.CurrentDomain.GetAssemblies():
        if assembly.GetName().Name == 'SystemInstances':
            typ = assembly.GetType('_3S.CoDeSys.Core.SystemInstances')
            for name in ('LanguageModelMgr', 'ObjectMgr', 'Engine'):
                prop = typ.GetProperty(name, FLAGS)
                value = prop.GetValue(None, None)
                result['services'][name] = shape(value)
                if name == 'LanguageModelMgr':
                    context = value.GetCompileContext(application.guid)
                    result['compile_context'] = {'found': context is not None}
                    if context is not None:
                        result['compile_context']['shape'] = shape(context)
                        result['compile_context']['properties'] = [{'name': unicode(p.Name), 'type': unicode(p.PropertyType.FullName)} for p in context.GetType().GetProperties(FLAGS)]
                        for attr in ('ApplicationGuid', 'ProjectHandle', 'Guid', 'Name'):
                            try:
                                result['compile_context'][attr] = unicode(getattr(context, attr))
                            except Exception:
                                pass
        if assembly.GetName().Name == 'Breakpoints.plugin':
            typ = assembly.GetType('_3S.CoDeSys.Breakpoints.BPManager')
            result['bp_manager_type'] = {'interfaces': [unicode(t.FullName) for t in typ.GetInterfaces()],
                                        'fields': [{'name': f.Name, 'type': unicode(f.FieldType.FullName)} for f in typ.GetFields(FLAGS)]}
    return result


def breakpoint_inventory(request):
    project = ops.owned()
    application = ops.choose_application(list(project.get_children(True)), request)
    info, device = rt.checked(project, application, request)
    assembly = [a for a in AppDomain.CurrentDomain.GetAssemblies() if a.GetName().Name == 'SystemInstances'][0]
    service_type = assembly.GetType('_3S.CoDeSys.Core.SystemInstances')
    model = service_type.GetProperty('LanguageModelMgr', FLAGS).GetValue(None, None)
    context = model.GetCompileContext(application.guid)
    if context is None or str(context.ApplicationGuid).lower() != str(application.guid).lower():
        raise RuntimeError('Compiled context identity mismatch')
    result = {'target': info, 'pous': []}
    for compiled in context.GetAllCompiledPOUsEx():
        if unicode(compiled.Name).lower() not in ('plc_prg', 'fb_debugprobe'):
            continue
        item = {'name': unicode(compiled.Name), 'signature_id': compiled.SignatureId,
                'shape': shape(compiled), 'breakpoint_list_shape': shape(compiled.BreakpointList), 'breakpoints': []}
        for bp in compiled.BreakpointList:
            position = compiled.GetSourcePositionOfBreakpoint(bp)
            props = {}
            for prop in position.GetType().GetProperties(FLAGS):
                if prop.GetIndexParameters().Length:
                    continue
                try:
                    props[unicode(prop.Name)] = unicode(prop.GetValue(position, None))
                except Exception as e:
                    props[unicode(prop.Name)] = {'error': unicode(e)}
            item['breakpoints'].append({'offset': bp.Offset, 'successors': list(bp.Successors or []),
                'position_shape': shape(position), 'position': props})
        result['pous'].append(item)
    return result


def breakpoint_proof(request):
    project = ops.owned()
    application = ops.choose_application(list(project.get_children(True)), request)
    info, device = rt.checked(project, application, request)
    project.active_application = application
    program = [o for o in application.get_children(True) if o.get_name() == 'PLC_PRG' and hasattr(o, 'textual_implementation')][0]
    result = {'target': info, 'events': [], 'document_shape': shape(program.textual_implementation),
              'document_fields': []}
    def checkpoint(stage):
        result['checkpoint_stage'] = stage
        path = os.path.join(os.environ['INVT_IPC_SESSION'], 'debugger_checkpoint.json')
        payload = json.dumps(json_safe(result), ensure_ascii=True).encode('utf-8')
        with open(path, 'wb') as stream:
            stream.write(payload)
    doc = program.textual_implementation
    for f in doc.GetType().GetFields(FLAGS):
        try:
            value = f.GetValue(doc)
            result['document_fields'].append({'name': unicode(f.Name), 'shape': shape(value) if value is not None else None})
        except Exception as e:
            result['document_fields'].append({'name': unicode(f.Name), 'error': unicode(e)})
    assembly = [a for a in AppDomain.CurrentDomain.GetAssemblies() if a.GetName().Name == 'SystemInstances'][0]
    model = assembly.GetType('_3S.CoDeSys.Core.SystemInstances').GetProperty('LanguageModelMgr', FLAGS).GetValue(None, None)
    context = model.GetCompileContext(application.guid)
    compiled = [p for p in context.GetAllCompiledPOUsEx() if unicode(p.Name).lower() == 'plc_prg'][0]
    candidates = [bp for bp in compiled.BreakpointList if compiled.GetSourcePositionOfBreakpoint(bp).Length > 0]
    bp = min(candidates, key=lambda candidate: candidate.Offset)
    source = compiled.GetSourcePositionOfBreakpoint(bp)
    if str(source.ObjectGuid).lower() != str(program.guid).lower():
        raise RuntimeError('Compiler breakpoint does not belong to the chosen source POU')
    result['chosen_breakpoint'] = {'code_offset': bp.Offset, 'source_guid': str(source.ObjectGuid),
        'editor_position_id': long(source.Position), 'length': int(source.Length), 'implementation': doc.text}
    def act(obj):
        rt.checked(project, application, request)
        core = obj.GetType().GetProperty('Application', FLAGS).GetValue(obj, None)
        if not core.IsLoggedIn or str(core.ApplicationGuid).lower() != str(application.guid).lower():
            raise RuntimeError('Core application mismatch/disconnected')
        methods = [m for m in core.GetType().GetMethods(FLAGS) if m.Name == 'SetPermanentBreakpoint' and len(m.GetParameters()) == 6]
        method = methods[0]
        condition_type = method.GetParameters()[4].ParameterType
        names = list(Enum.GetNames(condition_type))
        result['hit_conditions'] = names
        condition_names = [name for name in names if unicode(name).lower() in ('none', 'always')]
        if len(condition_names) != 1:
            raise RuntimeError('Unconditional breakpoint enum not verified')
        condition = Enum.Parse(condition_type, condition_names[0])
        def snapshot(label):
            rt.checked(project, application, request)
            event = {'label': label, 'state': unicode(obj.application_state),
                'values': {name: unicode(obj.read_value(name)) for name in ('PLC_PRG.nCycle', 'PLC_PRG.nAfter', 'PLC_PRG.fbProbe.nInside')},
                'instance': unicode(core.CurrentInstancePath), 'call_stack_count': len(core.CallStack or [])}
            position = core.CurrentPosition
            if position is not None:
                event['code_location'] = {'area': int(position.Area), 'offset': int(position.Offset)}
            for field_name in ('_cpouCurrent', '_bpCurrent'):
                field = core.GetType().GetField(field_name, FLAGS)
                value = field.GetValue(core)
                if value is not None and field_name == '_cpouCurrent':
                    event['current_pou'] = unicode(value.Name)
                elif value is not None:
                    current_pou = core.GetType().GetField('_cpouCurrent', FLAGS).GetValue(core)
                    position = current_pou.GetSourcePositionOfBreakpoint(value)
                    event['source'] = {'guid': str(position.ObjectGuid), 'position_id': long(position.Position), 'length': int(position.Length)}
            if label == 'breakpoint_hit':
                result['frame_properties'] = [[{'name':p.Name,'type':unicode(p.PropertyType.FullName)} for p in e.GetType().GetProperties(FLAGS)] for e in (core.CallStack or [])]
            result['events'].append(event)
            checkpoint(label)
        installed = False
        manager = None
        definition = None
        try:
            if unicode(obj.application_state).lower() != 'stop':
                raise RuntimeError('Initial STOP required')
            checkpoint('before_set_breakpoint')
            if request.get('_use_manager'):
                manager = get_bp_manager()
                factory = [m for m in manager.GetType().GetMethods(FLAGS) if m.Name == 'CreateBreakpoint' and len(m.GetParameters()) == 8][0]
                definition = factory.Invoke(manager, Array[Object]([application.guid, Int32(source.ProjectHandle), program.guid,
                    Int64(source.PositionCombination), None, Array[String](['MainTask']), condition, Int32(0)]))
                result['definition_shape'] = shape(definition)
                result['definition_properties'] = {p.Name:unicode(p.GetValue(definition,None)) for p in definition.GetType().GetProperties(FLAGS) if not p.GetIndexParameters().Length}
                installed = True
                if not manager.SetBreakpoint(definition):
                    raise RuntimeError('BPManager refused SetBreakpoint')
                enable = manager.GetType().GetMethod('EnableBreakpoint', FLAGS)
                if not enable.Invoke(manager, Array[Object]([definition])):
                    raise RuntimeError('BPManager refused runtime activation')
                result['manager_enabled'] = bool(definition.IsEnabled)
                result['manager_is_set'] = bool(definition.IsSet)
                result['manager_count'] = len(manager.GetBreakpoints(application.guid))
            else:
                method.Invoke(core, Array[Object]([compiled, bp, None, Array[String](['MainTask']), condition, Int32(0)]))
            installed = True
            checkpoint('before_start')
            # ScriptOnline.start waits for RUN and times out when a breakpoint
            # is hit immediately. Core Start sends the action without that wait.
            core.Start()
            for i in range(100):
                se.system.delay(50)
                if unicode(obj.application_state).lower() == 'halt_on_bp':
                    break
            snapshot('breakpoint_hit')
            if unicode(obj.application_state).lower() != 'halt_on_bp':
                raise RuntimeError('Breakpoint did not halt the simulation')
            for tokens in ('breakpoints stepover', 'breakpoints stepinto', 'breakpoints stepover', 'breakpoints stepout'):
                rt.checked(project, application, request)
                command = se.system.commands[tokens]
                native = command.GetType().GetField('_command', FLAGS).GetValue(command)
                event = {'label': 'command', 'tokens': tokens, 'enabled': bool(native.Enabled)}
                result['events'].append(event)
                if not native.Enabled:
                    continue
                checkpoint('before_' + tokens)
                command.execute(Array[String]([]))
                se.system.delay(250)
                event['executed'] = True
                snapshot(tokens)
        except Exception as e:
            result['error'] = unicode(e)
            checkpoint('exception')
        finally:
            if installed:
                checkpoint('before_clear_breakpoint')
                rt.checked(project, application, request)
                if manager is not None:
                    manager.ClearBreakpoint(definition)
                    result['manager_count_after_clear'] = len(manager.GetBreakpoints(application.guid))
                else:
                    core.ClearPermanentBreakpoint(compiled, bp)
                result['owned_breakpoint_cleared'] = True
            if unicode(obj.application_state).lower() != 'stop':
                checkpoint('before_cleanup_stop')
                # The ScriptOnline wrapper also refuses STOP from HALT.
                # Test the actual core transition rather than silently resuming.
                core.Stop()
                se.system.delay(250)
            result['final_state'] = unicode(obj.application_state)
            checkpoint('cleaned')
    rt.with_executor(lambda: rt.use_online(application, act))
    return result


def get_bp_manager():
    asm=[a for a in AppDomain.CurrentDomain.GetAssemblies() if a.GetName().Name=='ComponentModel'][0]
    typ=asm.GetType('_3S.CoDeSys.Core.Components.ComponentManager')
    manager=typ.GetProperty('Singleton',FLAGS).GetValue(None,None)
    bpasm=[a for a in AppDomain.CurrentDomain.GetAssemblies() if a.GetName().Name=='Breakpoints.plugin'][0]
    contract=[t for t in bpasm.GetType('_3S.CoDeSys.Breakpoints.BPManager').GetInterfaces() if t.Name=='IBPManager8'][0]
    getter=[m for m in typ.GetMethods(FLAGS) if m.Name=='GetSystemInstance' and m.IsGenericMethod and not m.GetParameters().Length][0]
    return getter.MakeGenericMethod(Array[Type]([contract])).Invoke(manager,None)


def manager_proof(request):
    request=dict(request)
    request['_use_manager']=True
    return breakpoint_proof(request)


def document_inventory(request):
    from System.Diagnostics import FileVersionInfo
    project = ops.owned()
    application = ops.choose_application(list(project.get_children(True)), request)
    rt.checked(project, application, request)
    result = {'documents': []}
    for o in application.get_children(True):
        if not hasattr(o, 'textual_implementation') or o.get_name() not in ('PLC_PRG', 'FB_DebugProbe'):
            continue
        scriptdoc = o.textual_implementation
        readable = scriptdoc.GetType().GetMethod('Readable', FLAGS).Invoke(scriptdoc, None)
        result['documents'].append({'name':o.get_name(), 'guid':str(o.guid), 'text':scriptdoc.text,
            'shape':shape(readable), 'all_methods':[unicode(m.ToString()) for m in readable.GetType().GetMethods(FLAGS)],
            'properties':[unicode(p.ToString()) for p in readable.GetType().GetProperties(FLAGS)]})
    def inspect(obj):
        core = obj.GetType().GetProperty('Application', FLAGS).GetValue(obj, None)
        result['core_version'] = FileVersionInfo.GetVersionInfo(core.GetType().Assembly.Location).FileVersion
        result['core_assembly'] = unicode(core.GetType().Assembly.GetName().Version)
        result['ids'] = {'code':str(core.CodeId), 'data':str(core.DataId), 'session':int(core.ApplicationSessionId)}
        result['execution_methods'] = [unicode(m.ToString()) for m in core.GetType().GetMethods(FLAGS) if re.search('executionpoint|breakpoint|callstack',m.Name,re.I)]
        result['execution_fields'] = [{'name':f.Name, 'type':unicode(f.FieldType.FullName)} for f in core.GetType().GetFields(FLAGS) if re.search('executionpoint|breakpoint|callstack|bpoint',f.Name,re.I)]
        result['stack'] = [shape(e) for e in (core.CallStack or [])]
    rt.with_executor(lambda:rt.use_online(application,inspect))
    return result


def mapping_inventory(request):
    project=ops.owned()
    application=ops.choose_application(list(project.get_children(True)), request)
    rt.checked(project,application,request)
    result={'pous':[]}
    assembly=[a for a in AppDomain.CurrentDomain.GetAssemblies() if a.GetName().Name=='SystemInstances'][0]
    model=assembly.GetType('_3S.CoDeSys.Core.SystemInstances').GetProperty('LanguageModelMgr',FLAGS).GetValue(None,None)
    context=model.GetCompileContext(application.guid)
    result['context_shape']=shape(context)
    for o in application.get_children(True):
        if not hasattr(o,'textual_implementation') or o.get_name() not in ('PLC_PRG','FB_DebugProbe'):
            continue
        doc=o.textual_implementation.GetType().GetMethod('Readable',FLAGS).Invoke(o.textual_implementation,None)
        item={'guid':str(o.guid),'name':o.get_name(),'linecount':doc.LineCount,
            'lines':[{'index':i,'id':long(doc.GetLineId(i)),'text':unicode(doc.GetLineText(i))} for i in range(doc.LineCount)],'positions':[]}
        cp=[p for p in context.GetAllCompiledPOUsEx() if str(p.ObjectGuid)==str(o.guid)][0]
        for bp in cp.BreakpointList:
            sp=cp.GetSourcePositionOfBreakpoint(bp)
            item['positions'].append({'offset':int(bp.Offset),'position':long(sp.Position),'length':int(sp.Length),
                'props':{p.Name:unicode(p.GetValue(sp,None)) for p in sp.GetType().GetProperties(FLAGS) if not p.GetIndexParameters().Length},
                'methods':[unicode(m.ToString()) for m in sp.GetType().GetMethods(FLAGS)]})
        result['pous'].append(item)
    def inspect(obj):
        core=obj.GetType().GetProperty('Application',FLAGS).GetValue(obj,None)
        result['sorter']=shape(core.BreakpointSorter)
        result['sorter_properties']=[unicode(p.ToString()) for p in core.BreakpointSorter.GetType().GetProperties(FLAGS)]
    rt.with_executor(lambda:rt.use_online(application,inspect))
    return result


def manager_inventory(request):
    project=ops.owned()
    application=ops.choose_application(list(project.get_children(True)),request)
    rt.checked(project,application,request)
    asm=[a for a in AppDomain.CurrentDomain.GetAssemblies() if a.GetName().Name=='ComponentModel'][0]
    typ=asm.GetType('_3S.CoDeSys.Core.Components.ComponentManager')
    manager=typ.GetProperty('Singleton',FLAGS).GetValue(None,None)
    bpasm=[a for a in AppDomain.CurrentDomain.GetAssemblies() if a.GetName().Name=='Breakpoints.plugin'][0]
    contract=[t for t in bpasm.GetType('_3S.CoDeSys.Breakpoints.BPManager').GetInterfaces() if t.Name=='IBPManager8'][0]
    getter=[m for m in typ.GetMethods(FLAGS) if m.Name=='GetSystemInstance' and m.IsGenericMethod and not m.GetParameters().Length][0]
    bpm=getter.MakeGenericMethod(Array[Type]([contract])).Invoke(manager,None)
    points=bpm.GetType().GetField('_breakpoints',FLAGS).GetValue(bpm)
    result={'shape':shape(bpm),'project_handle':None,'points':[shape(p) for p in points],
        'contracts':[{ 'name':i.FullName,'methods':[unicode(m.ToString()) for m in i.GetMethods()]} for i in bpm.GetType().GetInterfaces()]}
    return result
