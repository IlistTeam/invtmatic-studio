# -*- coding: utf-8 -*-
"""Fixed, version-gated simulator debugger. No arbitrary commands or physical API."""
import hashlib
import json
import time
import uuid
import traceback
import scriptengine as se
import invt_frames

OPS = ('prepare_debug', 'debug_locations', 'debug_state', 'set_breakpoint',
       'list_breakpoints', 'remove_breakpoint', 'debug_continue', 'debug_step', 'read_frame_variables')
CORE_VERSION = '3.5.20.61'
STEP_COMMANDS = {
    'into': ('breakpoints stepinto', '12289edb-4f13-400c-9e9d-35aa46946c51'),
    'over': ('breakpoints stepover', '0e79e9b0-7516-456f-b201-c056a02c4876'),
    'out': ('breakpoints stepout', '417b5c5c-2bb4-4eb6-b19d-4513281bacb0')}
_download = None
_active = None
_owned = {}
_unavailable = 'A full download by this session is required before preparing debugging'


class HaltRequiresExplicitStop(RuntimeError):
    pass


def flags():
    from System.Reflection import BindingFlags
    return BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance | BindingFlags.Static


def core(obj, application):
    prop = obj.GetType().GetProperty('Application', flags())
    if prop is None:
        raise RuntimeError('Verified core getter unavailable')
    value = prop.GetValue(obj, None)
    typ = value.GetType()
    if typ.FullName != '_3S.CoDeSys.OnlineManager.OnlineApplication' or str(typ.Assembly.GetName().Version) != CORE_VERSION:
        raise RuntimeError('Debugger component version not verified; expected OnlineManager ' + CORE_VERSION)
    if not value.IsLoggedIn or str(value.ApplicationGuid).lower() != str(application.guid).lower():
        raise RuntimeError('Core application identity/login mismatch')
    return value


def context(application):
    from System import AppDomain
    asm = [a for a in AppDomain.CurrentDomain.GetAssemblies() if a.GetName().Name == 'SystemInstances'][0]
    model = asm.GetType('_3S.CoDeSys.Core.SystemInstances').GetProperty('LanguageModelMgr', flags()).GetValue(None, None)
    value = model.GetCompileContext(application.guid)
    if value is None or str(value.ApplicationGuid).lower() != str(application.guid).lower():
        raise RuntimeError('Compiled application identity mismatch')
    return value


def bp_manager():
    from System import AppDomain, Array, Type
    asm = [a for a in AppDomain.CurrentDomain.GetAssemblies() if a.GetName().Name == 'ComponentModel'][0]
    typ = asm.GetType('_3S.CoDeSys.Core.Components.ComponentManager')
    manager = typ.GetProperty('Singleton', flags()).GetValue(None, None)
    asm = [a for a in AppDomain.CurrentDomain.GetAssemblies() if a.GetName().Name == 'Breakpoints.plugin'][0]
    if str(asm.GetName().Version) != '3.5.20.60':
        raise RuntimeError('Breakpoint manager version not verified')
    contract = [t for t in asm.GetType('_3S.CoDeSys.Breakpoints.BPManager').GetInterfaces() if t.Name == 'IBPManager8'][0]
    getter = [m for m in typ.GetMethods(flags()) if m.Name == 'GetSystemInstance' and m.IsGenericMethod and not m.GetParameters().Length][0]
    return getter.MakeGenericMethod(Array[Type]([contract])).Invoke(manager, None)


def source_hash(application):
    from invt_project import describe, library_inventory
    import invt_tasks
    objects = list(application.get_children(True))
    sources = []
    for obj in objects:
        if hasattr(obj, 'textual_declaration'):
            item = describe(obj, True)
            if hasattr(obj, 'textual_implementation'):
                doc = document(obj)
                item['implementation_line_ids'] = [str(doc.GetLineId(i)) for i in range(doc.LineCount)]
            sources.append(item)
    data = {'objects': sorted(sources, key=lambda o:o['guid']),
            'tasks': invt_tasks.inspect(application), 'libraries': library_inventory(objects)}
    return hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=True).encode('utf-8')).hexdigest()


def code_ids(value):
    return (str(value.CodeId), str(value.DataId))


def verify_ids(ctx, native):
    ids = code_ids(native)
    if ids != code_ids(ctx) or any(i == '00000000-0000-0000-0000-000000000000' for i in ids):
        raise RuntimeError('Compiled and downloaded CodeId/DataId differ; explicit full download required')
    return ids


def downloaded(application, obj, target_info):
    global _download, _active, _unavailable
    _download, _active = None, None
    try:
        native = core(obj, application)
        _download = {'app': str(application.guid), 'target_id': target_info['target_id'],
                     'project': target_info['project'], 'ids': verify_ids(context(application), native),
                     'source_hash': source_hash(application)}
        _unavailable = None
    except Exception as e:
        # Optional debugger support must not turn a successful ordinary download
        # into an ambiguous runtime mutation. Its failure is exposed by prepare.
        _unavailable = unicode(e)


def validate_generation(request, application, ctx, native):
    if _active is None or request.get('debug_id') != _active['debug_id'] or str(application.guid) != _active['app']:
        raise ValueError('Stale or missing debug_id; prepare debugging explicitly')
    if request.get('target_id') != _active['target_id']:
        raise ValueError('Debugger generation belongs to a different target/project')
    if verify_ids(ctx, native) != _active['ids'] or source_hash(application) != _active['source_hash']:
        raise RuntimeError('Source/tasks/libraries or downloaded code changed; debugger handles are stale')
    if int(native.ApplicationSessionId) != _active['session_id']:
        raise RuntimeError('Runtime connection session changed; old debugger handles are stale')


def disconnected():
    global _active
    _active = None  # Retain breakpoint ownership independently for explicit recovery.
    invt_frames.invalidate()


def document(obj):
    if not hasattr(obj, 'textual_implementation'):
        raise ValueError('Choose an ST implementation object')
    wrapper = obj.textual_implementation
    return wrapper.GetType().GetMethod('Readable', flags()).Invoke(wrapper, None)


def source_location(application, cp, bp):
    pos = cp.GetSourcePositionOfBreakpoint(bp)
    objects = [o for o in application.get_children(True) if str(o.guid) == str(pos.ObjectGuid)]
    result = {'object_guid': str(pos.ObjectGuid), 'pou': unicode(cp.Name), 'position_id': str(pos.Position),
              'position_combination': str(pos.PositionCombination), 'length': int(pos.Length),
              'line': None, 'column': None, 'section': 'implementation', 'mapped': False}
    if len(objects) == 1 and hasattr(objects[0], 'textual_implementation'):
        doc = document(objects[0])
        index = int(doc.FindLineById(pos.Position))
        if 0 <= index < doc.LineCount and pos.Length > 0:
            result.update(line=index + 1, column=int(pos.PositionOffset) + 1,
                          text=unicode(doc.GetLineText(index)), mapped=True)
    return result


def locations(application, ctx, object_guid):
    found = [p for p in ctx.GetAllCompiledPOUsEx() if str(p.ObjectGuid).lower() == object_guid.lower()]
    if len(found) != 1:
        raise ValueError('No unique compiled POU for this object GUID')
    cp = found[0]
    result = []
    for bp in cp.BreakpointList:
        item = source_location(application, cp, bp)
        if item['mapped']:
            result.append((item, cp, bp))
    return sorted(result, key=lambda v:(v[0]['line'], v[0]['column']))


def select_location(items, line, column=None):
    if isinstance(line, bool) or not isinstance(line, (int, long)) or line < 1:
        raise ValueError('Line is a positive 1-based integer')
    if column is not None and (isinstance(column, bool) or not isinstance(column, (int, long)) or column < 1):
        raise ValueError('Column is a positive 1-based integer')
    matches = [i for i in items if i[0]['line'] == line and (column is None or i[0]['column'] == column)]
    if len(matches) != 1:
        raise ValueError('No unique executable position at this line/column; inspect debug_locations, no automatic snapping')
    return matches[0]


def execution_precondition(obj, op):
    status = unicode(obj.application_state).lower()
    if bool(int(obj.operation_state) & 32):
        raise RuntimeError('Runtime exception active; inspect and explicitly recover, no implicit reset/start')
    if (op == 'debug_step' and status != 'halt_on_bp') or (op == 'debug_continue' and status not in ('stop', 'halt_on_bp')):
        raise ValueError('Step requires HALT; Continue requires STOP/HALT')
    return status


def point_info(point):
    result = {}
    for name in ('ApplicationGuid', 'ProjectHandle', 'ObjectGuid', 'Position', 'IsEnabled', 'IsSet', 'InstancePath'):
        try:
            result[name] = unicode(getattr(point, name))
        except AttributeError:
            pass
    owner = [key for key, record in _owned.items() if record['point'].Equals(point)]
    result.update(breakpoint_id=owner[0] if len(owner) == 1 else None, owned_by_session=len(owner) == 1)
    return result


def snapshot(application, obj, native, ctx):
    status = unicode(obj.application_state).lower()
    result = {'application_state': status, 'operating_state': unicode(obj.operation_state),
              'exception_active': bool(int(obj.operation_state) & 32), 'timestamp_unix_ms': int(time.time()*1000),
              'location': None, 'frames': [], 'frame_locals_supported': False,
              'halt_pauses_all_tasks': False, 'debug_task_index': None}
    if status == 'halt_on_bp':
        result['debug_task_index'] = int(native.DebugTaskIndex)
        cp = native.GetType().GetField('_cpouCurrent', flags()).GetValue(native)
        bp = native.GetType().GetField('_bpCurrent', flags()).GetValue(native)
        if cp is not None and bp is not None:
            result['location'] = source_location(application, cp, bp)
        result['instance_path'] = unicode(native.CurrentInstancePath)
        for index, frame in enumerate(native.CallStack or []):
            entry = {'index': index}
            for name in ('LocationPOU', 'LocationInstance'):
                try:
                    value = getattr(frame, name)
                    if hasattr(value, 'Area') and hasattr(value, 'Offset'):
                        entry[name] = {'area': int(value.Area), 'offset': int(value.Offset)}
                    else:
                        entry[name] = unicode(value)
                except AttributeError:
                    pass
            try:
                from System import UInt16, UInt32
                loc = frame.LocationPOU
                current_bp, current_cp = ctx.GetBreakpointByCodePosition(UInt16(loc.Area), UInt32(loc.Offset))
                if current_bp is not None and current_cp is not None:
                    entry['location'] = source_location(application, current_cp, current_bp)
            except Exception as e:
                entry['source_mapping_error'] = unicode(e)
            result['frames'].append(entry)
    invt_frames.decorate(application, obj, native, ctx, result)
    return result


def cleanup(application, obj):
    global _active
    if _owned:
        native = core(obj, application)
        manager = bp_manager()
        for key, record in list(_owned.items()):
            if str(application.guid) != record['app'] or code_ids(native) != record['ids']:
                raise RuntimeError('Owned breakpoint cleanup cannot verify downloaded code; retain ledger')
            manager.ClearBreakpoint(record['point'])
            if record['point'].IsSet:
                raise RuntimeError('Owned breakpoint still set after selective clear')
            _owned.pop(key)
    _active = None
    invt_frames.invalidate()


def prepare_logout(application, obj):
    if _active is None and not _owned and _download is None:
        return
    native = core(obj, application)
    from System import Array, Object
    manager = bp_manager()
    disable = manager.GetType().GetMethod('DisableBreakpoint', flags())
    for point in manager.GetBreakpoints(application.guid):
        if point.IsEnabled:
            disable.Invoke(manager, Array[Object]([point]))
            if point.IsEnabled or not point.IsSet:
                raise RuntimeError('Runtime point deactivation failed or definition was removed')
    # Use the tested no-retention logout path after explicit STOP. Deactivate
    # runtime points without deleting foreign definitions. The exception observed
    # in earlier HALT tests occurred at Core Stop, before logout.
    native.ExecutionpointsRemainActive = False
    if native.ExecutionpointsRemainActive:
        raise RuntimeError('Runtime execution-point retention could not be disabled')
    return native


def logout_core(native):
    from System import Array, Object
    methods = [m for m in native.GetType().GetMethods(flags()) if m.Name == 'Logout' and
               len(m.GetParameters()) == 1 and m.GetParameters()[0].ParameterType.FullName == 'System.Boolean']
    if len(methods) != 1:
        raise RuntimeError('Verified Boolean Core Logout overload unavailable')
    methods[0].Invoke(native, Array[Object]([False]))


def stop_halted(application, obj):
    native = core(obj, application)
    native.Stop()
    se.system.delay(250)
    if unicode(obj.application_state).lower() != 'stop':
        raise RuntimeError('Core STOP from HALT not confirmed')


def stop_with_behavior(application, obj, behavior):
    if behavior not in ('finish_cycle', 'abort_cycle'):
        raise HaltRequiresExplicitStop('HALT requires explicit halt_behavior: finish_cycle or abort_cycle; cleanup will not resume implicitly')
    invt_frames.invalidate()
    native = core(obj, application)
    manager = bp_manager()
    enabled = [p for p in manager.GetBreakpoints(application.guid) if p.IsEnabled]
    if behavior == 'finish_cycle':
        from System import Array, Object
        disable = manager.GetType().GetMethod('DisableBreakpoint', flags())
        for point in enabled:
            disable.Invoke(manager, Array[Object]([point]))
    stop_halted(application, obj)
    if behavior == 'finish_cycle':
        from System import Array, Object
        if bool(int(obj.operation_state) & 32):
            raise RuntimeError('Finishing current cycle produced a runtime exception')
        enable = manager.GetType().GetMethod('EnableBreakpoint', flags())
        for point in enabled:
            if not enable.Invoke(manager, Array[Object]([point])) or not point.IsEnabled:
                raise RuntimeError('Breakpoint activation could not be restored after explicit cycle completion')
    return {'halt_behavior': behavior, 'remaining_cycle_execution_allowed': behavior == 'finish_cycle',
            'exception_active': bool(int(obj.operation_state) & 32)}


def perform(project, application, request):
    import invt_runtime as rt
    global _active
    info, device = rt.checked(project, application, request)
    project.active_application = application
    op = request['operation']
    dispatched = [False]
    def act(obj):
        global _active
        rt.checked(project, application, request)
        if not rt._attached or not obj.is_logged_in:
            disconnected()
            raise RuntimeError('Owned simulation connection required')
        native, ctx = core(obj, application), context(application)
        if op == 'prepare_debug':
            invt_frames.subscribe()
            if _download is None:
                raise RuntimeError(_unavailable)
            if _download['target_id'] != info['target_id'] or _download['project'] != project.path:
                raise RuntimeError('A full download in this project/target is required')
            ids = verify_ids(ctx, native)
            stamp = source_hash(application)
            if _download['app'] != str(application.guid) or ids != _download['ids'] or stamp != _download['source_hash']:
                raise RuntimeError('An explicit full download of the current source is required')
            if _active is None:
                if _owned:
                    raise RuntimeError('Lost debugger connection with owned points; explicitly recover/cleanup before preparing')
                _active = dict(_download, debug_id=str(uuid.uuid4()), session_id=int(native.ApplicationSessionId))
            elif int(native.ApplicationSessionId) != _active['session_id']:
                raise RuntimeError('Runtime session changed; disconnect/cleanup and prepare explicitly')
            return {'ok': True, 'target': info, 'debug_id': _active['debug_id'], 'source_sha256': stamp,
                    'code_id': ids[0], 'data_id': ids[1], 'component_version': CORE_VERSION}
        validate_generation(request, application, ctx, native)
        result = {'ok': True, 'target': info, 'debug_id': _active['debug_id']}
        if op == 'read_frame_variables':
            result.update(invt_frames.read(application, obj, native, ctx, request))
        elif op == 'debug_locations':
            result['locations'] = [v[0] for v in locations(application, ctx, request['object_guid'])]
        elif op == 'list_breakpoints':
            result['breakpoints'] = [point_info(p) for p in bp_manager().GetBreakpoints(application.guid)]
        elif op in ('set_breakpoint', 'remove_breakpoint'):
            if rt._uncertain:
                raise RuntimeError('Previous mutation uncertain; inspect and disconnect, never replay')
            manager = bp_manager()
            if op == 'remove_breakpoint':
                key = request['breakpoint_id']
                if key not in _owned:
                    raise ValueError('Removal is limited to this session owned breakpoint IDs')
                point = _owned[key]['point']
                dispatched[0] = True
                manager.ClearBreakpoint(point)
                if point.IsSet:
                    raise RuntimeError('Selective breakpoint removal not confirmed')
                _owned.pop(key)
                result['removed'] = key
            else:
                from System import Array, Object, String, Int32, Int64, Enum
                if unicode(obj.application_state).lower() not in ('stop', 'halt_on_bp'):
                    raise ValueError('Set breakpoints only in STOP/HALT; stop explicitly first')
                item, cp, bp = select_location(locations(application, ctx, request['object_guid']), request['line'], request.get('column'))
                tasks = [t for t in application.get_children(True) if getattr(t, 'is_task', False) and str(t.guid).lower() == request['task_guid'].lower()]
                if len(tasks) != 1:
                    raise ValueError('Choose a task GUID in the selected application')
                factory = [m for m in manager.GetType().GetMethods(flags()) if m.Name == 'CreateBreakpoint' and len(m.GetParameters()) == 8][0]
                condition_type = factory.GetParameters()[6].ParameterType
                names = [n for n in Enum.GetNames(condition_type) if unicode(n).lower() in ('none', 'always')]
                if len(names) != 1:
                    raise RuntimeError('Unconditional breakpoint enum unavailable')
                pos = cp.GetSourcePositionOfBreakpoint(bp)
                point = factory.Invoke(manager, Array[Object]([application.guid, Int32(pos.ProjectHandle), cp.ObjectGuid,
                    Int64(pos.PositionCombination), None, Array[String]([tasks[0].get_name()]), Enum.Parse(condition_type, names[0]), Int32(0)]))
                if any(str(p.ObjectGuid) == str(point.ObjectGuid) and str(p.Position) == str(point.Position)
                       for p in manager.GetBreakpoints(application.guid)):
                    raise ValueError('A breakpoint already exists here; preserve its owner/settings')
                key = str(uuid.uuid4())
                _owned[key] = {'point': point, 'location': item, 'ids': _active['ids'], 'app': _active['app']}
                dispatched[0] = True
                if not manager.SetBreakpoint(point) or not point.IsSet:
                    raise RuntimeError('Breakpoint installation not confirmed; ownership retained')
                enable = manager.GetType().GetMethod('EnableBreakpoint', flags())
                if not enable.Invoke(manager, Array[Object]([point])) or not point.IsEnabled:
                    raise RuntimeError('Runtime breakpoint activation not confirmed; ownership retained')
                result.update(breakpoint_id=key, location=item)
        elif op in ('debug_continue', 'debug_step'):
            if rt._uncertain:
                raise RuntimeError('Previous mutation uncertain; inspect and disconnect, never replay')
            status = execution_precondition(obj, op)
            if op == 'debug_continue':
                if status not in ('stop', 'halt_on_bp'):
                    raise ValueError('Continue requires STOP/HALT')
                dispatched[0] = True
                invt_frames.invalidate()
                native.Start()
            else:
                from System import Array, String
                if status != 'halt_on_bp':
                    raise ValueError('A halted breakpoint is required for stepping')
                tokens, guid = STEP_COMMANDS[request['kind']]
                command = se.system.commands[tokens]
                if str(command.guid).lower() != guid:
                    raise RuntimeError('Step command GUID differs from the verified component')
                implementation = command.GetType().GetField('_command', flags()).GetValue(command)
                if not implementation.Enabled:
                    raise ValueError('Requested step is not enabled in this context')
                dispatched[0] = True
                invt_frames.invalidate()
                command.execute(Array[String]([]))
            se.system.delay(250)
            for attempt in range(35):
                rt.checked(project, application, request)
                if not obj.is_logged_in:
                    raise RuntimeError('Connection lost during debugger transition')
                now = unicode(obj.application_state).lower()
                if bool(int(obj.operation_state) & 32):
                    raise RuntimeError('Runtime exception during debugger transition; STOP is not successful Continue')
                if op == 'debug_continue' and now == 'stop':
                    raise RuntimeError('Continue returned STOP; execution was not confirmed')
                if now in ('halt_on_bp', 'stop') or (op == 'debug_continue' and now == 'run'):
                    break
                se.system.delay(50)
            else:
                raise RuntimeError('Debugger transition not confirmed before deadline')
        elif op != 'debug_state':
            raise ValueError('Unknown fixed debugger operation')
        result['state'] = snapshot(application, obj, native, ctx)
        return result
    try:
        return rt.with_executor(lambda: rt.use_online(application, act))
    except Exception:
        if dispatched[0]:
            rt._uncertain = True
        return {'ok': False, 'target': info, 'operation': op, 'exception': traceback.format_exc(),
                'uncertain_previous_operation': rt._uncertain, 'owned_breakpoints': list(_owned)}
