# -*- coding: utf-8 -*-
"""Read-only frame watches, bound to a current HALT and native state events."""
import time
import uuid
import traceback

_revision = 0
_stamp = None
_handles = {}
_manager = None
_handlers = None


def invalidate(*args):
    global _revision, _stamp
    _revision += 1
    _stamp = None
    _handles.clear()


def manager():
    import invt_debugger as dbg
    from System import AppDomain
    asm = [a for a in AppDomain.CurrentDomain.GetAssemblies() if a.GetName().Name == 'SystemInstances'][0]
    return asm.GetType('_3S.CoDeSys.Core.SystemInstances').GetProperty('OnlineMgr', dbg.flags()).GetValue(None, None)


def subscribe():
    global _manager, _handlers
    if _manager is None:
        import invt_debugger as dbg
        value = manager()
        if str(value.GetType().Assembly.GetName().Version) != dbg.CORE_VERSION:
            raise RuntimeError('Frame event component version not verified')
        # Any application's event conservatively invalidates our handles. The
        # dedicated IDE has one owned target; callbacks never call IDE APIs.
        value.ApplicationStateChanged += invalidate
        value.CurrentPositionChanged += invalidate
        _manager, _handlers = value, (invalidate, invalidate)


def stack_identity(native):
    return tuple((str(f.LocationPOU.Area), str(f.LocationPOU.Offset),
                  str(f.StackPointer), str(f.LocationInformation.CompiledPOU.ObjectGuid)
                  if f.LocationInformation.CompiledPOU is not None else '')
                 for f in native.CallStack or [])


def state_identity(native):
    import invt_debugger as dbg
    field = native.GetType().GetField('_uiLastChangeOfAppState',dbg.flags())
    if field is None:
        raise RuntimeError('Verified runtime state-change stamp unavailable')
    return (str(field.GetValue(native)),int(native.CurrentHitCount))


def synchronize(native, generation):
    global _stamp
    new = (generation, _revision, int(native.ApplicationSessionId), state_identity(native), stack_identity(native))
    if _stamp != new:
        _handles.clear()
        _stamp = new
    return new


def decorate(application, obj, native, ctx, snapshot):
    import invt_debugger as dbg
    if snapshot['application_state'] != 'halt_on_bp':
        invalidate()
        return
    subscribe()
    if dbg._active is None:
        return
    stamp = synchronize(native, dbg._active['debug_id'])
    textual = set(str(o.guid) for o in application.get_children(True) if hasattr(o,'textual_declaration'))
    for entry, frame in zip(snapshot['frames'], native.CallStack or []):
        cp = frame.LocationInformation.CompiledPOU
        if cp is None or str(cp.ObjectGuid) not in textual:
            entry['locals_readable'] = False
            continue
        guid = str(cp.ObjectGuid)
        matches = [f for f in native.CallStack or [] if f.LocationInformation.CompiledPOU is not None
                   and str(f.LocationInformation.CompiledPOU.ObjectGuid) == guid]
        entry['locals_readable'] = len(matches) == 1
        if len(matches) != 1:
            entry['locals_reason'] = 'ambiguous_repeated_pou'
            continue
        ids = [key for key, r in _handles.items() if r['index'] == entry['index'] and r['stamp'] == stamp]
        key = ids[0] if ids else str(uuid.uuid4())
        _handles[key] = {'index': entry['index'], 'stamp': stamp, 'guid': guid}
        entry['frame_id'] = key
    snapshot['halt_revision'] = _revision
    snapshot['halt_runtime_stamp'] = list(stamp[3])
    snapshot['frame_locals_supported'] = True


def checked_frame(request, native):
    import invt_debugger as dbg
    if int(native.ApplicationState) != 3:
        invalidate()
        raise ValueError('Frame values require a current HALT')
    record = _handles.get(request['frame_id'])
    stamp = synchronize(native, dbg._active['debug_id'])
    if record is None or record['stamp'] != stamp or request['frame_id'] not in _handles:
        raise ValueError('Stale or unknown frame_id; obtain a fresh debug_state after every step/resume')
    frame = native.CallStack[record['index']]
    cp = frame.LocationInformation.CompiledPOU
    if cp is None or str(cp.ObjectGuid) != record['guid']:
        raise RuntimeError('Selected frame source identity changed')
    if sum(1 for f in native.CallStack if f.LocationInformation.CompiledPOU is not None
           and str(f.LocationInformation.CompiledPOU.ObjectGuid) == record['guid']) != 1:
        raise ValueError('Repeated/recursive POU frames are not uniquely selectable by this API')
    return frame, stamp


def read(application, obj, native, ctx, request):
    import invt_debugger as dbg
    import invt_runtime as rt
    from System import AppDomain, Int32
    if rt._uncertain:
        raise RuntimeError('Previous operation uncertain; recover before creating watches')
    frame, stamp = checked_frame(request, native)
    info = frame.LocationInformation
    asm = [a for a in AppDomain.CurrentDomain.GetAssemblies() if a.GetName().Name == 'SystemInstances'][0]
    lm = asm.GetType('_3S.CoDeSys.Core.SystemInstances').GetProperty('LanguageModelMgr', dbg.flags()).GetValue(None, None)
    online = manager()
    result = []
    for expression in request['variables']:
        rt.variable_path(expression)
        item = {'variable': expression, 'frame_id': request['frame_id'], 'ok': False}
        watch = None
        try:
            checked_frame(request, native)
            ref = lm.GetVarReference(application.guid, info.EditorInstancePath, expression,
                                     Int32(info.SourcePosition.ProjectHandle), info.CompiledPOU.ObjectGuid)
            if ref is None or str(ref.ApplicationGuid) != str(application.guid):
                raise ValueError('No variable reference in the selected application/frame')
            watch = online.CreateWatch(ref)
            until = time.time() + 2
            while time.time() < until:
                import scriptengine as se
                se.system.delay(100)
                checked_frame(request, native)
                item['state'] = unicode(watch.State)
                if item['state'] == 'Good':
                    value = watch.Value
                    item.update(ok=True, value=unicode(value), value_type=unicode(value.GetType().FullName)
                                if value is not None and hasattr(value, 'GetType') else type(value).__name__,
                                stack_relative=bool(ref.AddressInfo.ContainsStackRelativeAddress))
                    break
            if not item['ok']:
                item['error'] = unicode(watch.GetStateMessage())
        except Exception as error:
            item['error'] = unicode(error)
        finally:
            if watch is not None:
                watch.Release()
            item['timestamp_unix_ms'] = int(time.time() * 1000)
        result.append(item)
    # A transition during observation invalidates the whole result, rather than
    # returning values from several halts as one current-frame observation.
    checked_frame(request, native)
    return {'frame_id': request['frame_id'], 'halt_revision': stamp[1], 'values': result,
            'atomic': False, 'ok': all(v['ok'] for v in result)}
