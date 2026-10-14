# -*- coding: utf-8 -*-
"""Owned simulation trace configurations and bounded runtime captures."""
import os
import re
import time
import json
import uuid
import traceback
import scriptengine as se

OPS = ('create_trace', 'capture_trace', 'list_traces', 'delete_trace')
_records = {}


def has_packets():
    return any(r.get('packet_owned') for r in _records.values())


def check_version(value, expected):
    if str(value.GetType().Assembly.GetName().Version) != expected:
        raise RuntimeError('Trace component version not verified: expected '+expected)


def native_property(value, name):
    import invt_debugger as dbg
    prop = value.GetType().GetProperty(name,dbg.flags())
    if prop is None:
        raise RuntimeError('Verified trace property unavailable: '+name)
    return prop.GetValue(value,None)


def descriptor(record):
    return {k: record.get(k) for k in ('trace_id','object_guid','name','task_guid','variables',
                                      'every_n_cycles','packet_owned','packet_name','uncertain')}


def selected(project, app, trace_id):
    if trace_id not in _records:
        raise ValueError('Unknown trace_id; foreign configurations cannot be adopted/deleted')
    r = _records[trace_id]
    if r['project'] != project.path or r['app'] != str(app.guid):
        raise ValueError('Trace belongs to another project/application')
    nodes = [o for o in app.get_children(True) if str(o.guid) == r.get('object_guid')]
    if len(nodes) != 1 or nodes[0].get_name() != r['name']:
        raise RuntimeError('Owned trace configuration identity changed')
    if (r['wrapper'].record_name != r['record_name'] or
        list(r['wrapper'].variable_list[i].variable_name for i in range(len(r['wrapper'].variable_list))) != r['variables'] or
        r['wrapper'].task_name != r['task_name'] or bool(r['wrapper'].auto_start) or
        int(r['wrapper'].every_n_cycles) != r['every_n_cycles'] or bool(r['wrapper'].trigger_enabled)):
        raise RuntimeError('Trace configuration edited outside this session; preserve evidence')
    return r, nodes[0]


def editor_parts(record):
    import invt_debugger as dbg
    if record.get('editor') is None:
        record['editor'] = record['wrapper'].open_editor()
    editor = record['editor']
    check_version(editor, '4.2.0.0')
    view = editor.GetType().GetField('_view', dbg.flags()).GetValue(editor)
    check_version(view, '4.2.0.2')
    manager = view.GetType().GetField('_tmManager', dbg.flags()).GetValue(view)
    check_version(manager, '4.2.0.2')
    native_record = view.GetType().GetField('_trRecord', dbg.flags()).GetValue(view)
    packet = unicode(manager.GetType().GetProperty('PacketName', dbg.flags()).GetValue(manager, None))
    if not packet:
        raise RuntimeError('No unique runtime trace packet name')
    return editor, manager, native_record, packet


def wait_running(editor, expected):
    until = time.time()+5
    while time.time() < until:
        if bool(editor.is_running) == expected:
            return
        se.system.delay(100)
    raise RuntimeError('Trace transition unconfirmed; do not replay start/stop')


def packet_online(manager, name):
    import invt_debugger as dbg
    from System import Array, Object
    methods = [m for m in manager.GetType().GetMethods(dbg.flags()) if m.Name=='IsPacketOnline'
               and len(m.GetParameters())==1 and m.GetParameters()[0].ParameterType.FullName=='System.String']
    if len(methods)!=1:
        raise RuntimeError('Verified named packet query unavailable')
    return bool(methods[0].Invoke(manager,Array[Object]([name])))


def release_packet(record, obj, application):
    import invt_debugger as dbg
    if not record.get('packet_owned'):
        return
    if not obj.is_logged_in:
        raise RuntimeError('Trace connection lost; packet cleanup unconfirmed, ledger retained')
    native = dbg.core(obj, application)
    editor, manager, data, name = editor_parts(record)
    if name != record['packet_name']:
        raise RuntimeError('Runtime packet identity changed; cleanup refused')
    if not packet_online(manager,name):
        record['packet_owned'] = False
        record['uncertain'] = False
        record['packet_absence_verified'] = True
        return
    if dbg.code_ids(native) != record['ids']:
        raise RuntimeError('Downloaded code changed with owned trace packet; cleanup refused')
    if editor.is_running:
        if record.get('transition_pending') == 'stop':
            raise RuntimeError('Previous trace STOP unconfirmed; no automatic replay, ledger retained')
        record['transition_pending'] = 'stop'
        editor.stop()
        wait_running(editor, False)
    manager.DeletePacket(name)
    if packet_online(manager,name):
        raise RuntimeError('Owned trace packet deletion not confirmed')
    record['packet_owned'] = False
    record['uncertain'] = False
    record['transition_pending'] = None
    record['packet_absence_verified'] = True


def cleanup(project, application, obj):
    for key, r in list(_records.items()):
        if r['project'] == project.path and r['app'] == str(application.guid):
            if r.get('packet_owned'):
                selected(project, application, key)
                release_packet(r, obj, application)
            elif r.get('editor') is not None and obj.is_logged_in:
                editor,manager,data,name = editor_parts(r)
                r['packet_absence_verified'] = not packet_online(manager,name)


def parse_csv(path, expected):
    # Vendor CSV contains configuration and separate variable sections. Preserve
    # typed sample spelling (including locale decimals), never invent one atomic row.
    import io
    if os.path.getsize(path) > 2*1024*1024:
        raise RuntimeError('Trace export exceeds bounded result size')
    data, types, current, buffer_entries = {}, {}, None, None
    with io.open(path, encoding='utf-8-sig') as source:
        for line in source:
            f = [v.strip() for v in line.split(';')]
            if re.match(r'^[0-9]+\.Variable$',f[0]):
                current = f[1]
                if current not in expected or current in data:
                    raise RuntimeError('Unexpected/duplicate trace variable in export')
                data[current] = []
            elif f[0] == 'BufferEntries':
                buffer_entries = int(f[1])
            elif current and re.match(r'^[0-9]+\.Class$',f[0]):
                types[current] = f[1]
            elif current and f[0] == '' and len(f) == 3:
                samples = data[current]
                timestamp = int(f[1])
                if len(samples) >= 10000 or (samples and timestamp <= int(samples[-1]['timestamp'])):
                    raise RuntimeError('Trace count/timestamps outside supported format')
                samples.append({'timestamp': str(timestamp), 'value': f[2]})
    if set(data) != set(expected) or any(not v for v in data.values()):
        raise RuntimeError('Trace export contains no samples for one or more requested variables')
    return {'signals':[{'variable':v,'native_type_class':types.get(v),'samples':data[v]} for v in expected],
            'buffer_entries':buffer_entries, 'atomic':False}


def perform(project, application, request):
    import invt_runtime as rt
    import invt_debugger as dbg
    import invt_tasks
    op = request['operation']
    info, device = rt.checked(project, application, request)
    project.active_application = application
    if op == 'list_traces':
        return {'ok':True,'target':info,'traces':[descriptor(r) for r in _records.values()
                if r['project'] == project.path and r['app'] == str(application.guid)]}
    if op == 'create_trace':
        rt.assert_offline()
        check_version(se.trace, '4.2.0.0')
        name = request.get('name') or 'CodexTrace_'+uuid.uuid4().hex[:16]
        if not re.match(r'^[A-Za-z_][A-Za-z0-9_]{0,63}\Z',name):
            raise ValueError('Trace name must be an identifier up to 64 characters')
        if any(o.get_name().lower() == name.lower() for o in application.get_children(True)):
            raise ValueError('Name exists; never overwrite/adopt a foreign trace')
        variables = request['variables']
        if not 1 <= len(variables) <= 8 or len(set(v.lower() for v in variables)) != len(variables):
            raise ValueError('Choose 1..8 distinct variable paths')
        for variable in variables:
            rt.variable_path(variable)
        invt_tasks.integer(request.get('every_n_cycles',1),1,1000,'every_n_cycles')
        tasks = [o for o in application.get_children(True) if getattr(o,'is_task',False)
                 and str(o.guid).lower() == request['task_guid'].lower()]
        if len(tasks) != 1 or unicode(tasks[0].kind_of_task).lower() != 'cyclic':
            raise ValueError('Select an owned cyclic task')
        key = str(uuid.uuid4())
        r = {'trace_id':key,'project':project.path,'app':str(application.guid),'name':name,
             'variables':variables,'task_guid':str(tasks[0].guid),'task_name':tasks[0].get_name(),
             'every_n_cycles':request.get('every_n_cycles',1),'packet_owned':False,'uncertain':False}
        _records[key] = r
        try:
            r['wrapper'] = se.trace.create(application, name, r['task_name'])
            nodes = [o for o in application.get_children(True) if o.get_name() == name]
            r['object_guid'] = str(nodes[0].guid)
            wrapper = r['wrapper']
            check_version(wrapper,'4.2.0.0')
            wrapper.auto_start = False
            wrapper.trigger_enabled = False
            wrapper.every_n_cycles = r['every_n_cycles']
            r['record_name'] = 'Codex_'+uuid.uuid4().hex
            wrapper.record_name = r['record_name']
            for variable in variables:
                v = wrapper.variable_list.add()
                v.variable_name = variable
                v.enabled = True
            project.save()
            return dict(descriptor(r),ok=True,target=info,auto_start=False)
        except Exception:
            return dict(descriptor(r),ok=False,target=info,exception=traceback.format_exc(),
                        created=bool(r.get('object_guid')),creation_outcome='confirmed' if r.get('object_guid') else 'unknown')
    r, node = selected(project, application, request['trace_id'])
    def action(obj):
        rt.checked(project, application, request)
        if op == 'delete_trace':
            release_packet(r,obj,application)
            if obj.is_logged_in:
                editor,manager,data,name = editor_parts(r)
                if packet_online(manager,name):
                    raise RuntimeError('Non-owned packet exists for this configuration; deletion refused')
                r['packet_absence_verified'] = True
                return {'ok':False,'reason':'disconnect_required_for_config_delete','trace_id':r['trace_id'],
                        'packet_cleanup_confirmed':True,'configuration_preserved':True}
            if r.get('editor') is not None and not r.get('packet_absence_verified'):
                raise RuntimeError('No packet absence confirmation; reconnect explicitly, preserve foreign recording')
            node.remove()
            project.save()
            _records.pop(r['trace_id'])
            return {'ok':True,'target':info,'removed_trace_id':r['trace_id']}
        if op != 'capture_trace':
            raise ValueError('Unknown fixed trace operation')
        if not rt._attached or not obj.is_logged_in or rt._uncertain or r['uncertain']:
            raise RuntimeError('Known owned simulation connection required; recover uncertain state explicitly')
        native,ctx = dbg.core(obj,application),dbg.context(application)
        dbg.validate_generation(request,application,ctx,native)
        if unicode(obj.application_state).lower() != 'run':
            raise ValueError('Trace capture requires explicit application RUN; no auto-start or HALT resume')
        invt_tasks.integer(request['duration_ms'],100,10000,'duration_ms')
        task = [t for t in invt_tasks.inspect(application)['tasks'] if t['guid'] == r['task_guid']][0]
        period = task['interval_ms']
        if not period or (request['duration_ms']+500)/(period*r['every_n_cycles']) > 90:
            raise ValueError('Capture could wrap the default buffer; shorten duration or explicitly increase every_n_cycles')
        for variable in r['variables']:
            obj.read_value(variable)  # Validate paths/channel before downloading any packet.
        editor,manager,data,name = editor_parts(r)
        if int(native_property(data,'BufferEntries')) != 100:
            raise RuntimeError('Trace buffer configuration is outside the verified 100-entry profile')
        if packet_online(manager,name):
            raise ValueError('Packet already exists; never replace a foreign or uncertain recording')
        before = list(editor.get_online_traces())
        r.update(packet_owned=True,packet_name=name,ids=dbg.code_ids(native))
        capture = {'ok':False,'target':info,'trace_id':r['trace_id']}
        try:
            r['transition_pending'] = 'download'
            editor.download()
            if not editor.is_logged_in:
                raise RuntimeError('Trace login not confirmed')
            r['transition_pending'] = 'start'
            editor.start()
            wait_running(editor,True)
            r['transition_pending'] = None
            started = time.time()
            until = started+request['duration_ms']/1000.0
            while time.time() < until:
                se.system.delay(100)
                rt.checked(project,application,request)
                if not obj.is_logged_in or unicode(obj.application_state).lower() != 'run':
                    raise RuntimeError('Connection/execution changed during capture; no stale recording acceptance')
            r['transition_pending'] = 'stop'
            editor.stop()
            wait_running(editor,False)
            r['transition_pending'] = None
            dbg.validate_generation(request,application,ctx,native)
            folder = os.path.join(os.path.dirname(__file__),'exports','trace',uuid.uuid4().hex)
            os.makedirs(folder)
            path = os.path.join(folder,'recording.csv')
            editor.save(path)
            parsed = parse_csv(path,r['variables'])
            capture.update(parsed)
            capture.update(ok=True,csv_file=path,elapsed_ms=int((time.time()-started)*1000),
                           timestamp_unit='us' if bool(native_property(data,'MicroSeconds')) else 'ms',
                           overflow=bool(native_property(data,'Overflow')),overflow_count=int(native_property(data,'CountOverflows')))
        except Exception:
            capture['exception'] = traceback.format_exc()
        finally:
            try:
                release_packet(r,obj,application)
                capture['packet_cleanup_confirmed'] = True
                after = list(editor.get_online_traces())
                if any(n not in after for n in before):
                    raise RuntimeError('Foreign trace packet disappeared during capture')
            except Exception:
                r['uncertain'] = True
                capture.update(ok=False,packet_cleanup_confirmed=False,cleanup_exception=traceback.format_exc())
        return capture
    return rt.with_executor(lambda:rt.use_online(application,action))
