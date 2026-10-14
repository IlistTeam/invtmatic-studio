# -*- coding: utf-8 -*-
"""Simulation-only, fixed runtime operations. No scans, credentials or physical login."""
import re
import time
import uuid
import traceback
import scriptengine as se
import invt_debugger
import invt_trace
from invt_executor import with_executor

OPS = ('debug_capabilities', 'runtime_target', 'simulation_mode', 'connect_runtime',
       'disconnect_runtime', 'runtime_state', 'download_application',
       'start_application', 'stop_application', 'read_variables', 'write_variable',
       'force_variable', 'unforce_variable', 'list_forces')
_binding = None
_attached = False
_forces = {}
_uncertain = False
_path_pattern = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*(?:\[[0-9]+\])*(?:\.[A-Za-z_][A-Za-z0-9_]*(?:\[[0-9]+\])*)*\Z')


def variable_path(value):
    if not isinstance(value, basestring) or len(value) > 512 or not _path_pattern.match(value):
        raise ValueError('Supply a variable path, not an arbitrary expression')
    return value


def ancestor_device(application):
    obj = application.parent
    while obj is not None:
        if hasattr(obj, 'get_simulation_mode') and hasattr(obj, 'get_device_identification'):
            return obj
        obj = getattr(obj, 'parent', None)
    raise RuntimeError('Application has no identifiable owning simulation device')


def target(project, application):
    global _binding
    device = ancestor_device(application)
    identity = device.get_device_identification()
    mode = None
    error = None
    try:
        raw = device.get_simulation_mode()
        if raw == True:
            mode = 'simulation'
        elif raw == False:
            mode = 'physical'
    except Exception as e:
        error = unicode(e)
    signature = (project.path, str(application.guid), str(device.guid), mode,
                 unicode(identity.type), unicode(identity.id), unicode(identity.version))
    if _binding is None or _binding['signature'] != signature:
        if _attached or _forces:
            raise RuntimeError('Runtime target changed while attached; preserve evidence and recover the owned session')
        _binding = {'signature': signature, 'target_id': str(uuid.uuid4())}
    return {'project': project.path, 'application_guid': str(application.guid),
            'application': application.get_name(), 'device_guid': str(device.guid),
            'device_name': device.get_name(), 'device_identification': {
                'type': identity.type, 'id': identity.id, 'version': identity.version},
            'mode': mode or 'unknown', 'mode_error': error,
            'mode_evidence': 'owning_device.get_simulation_mode',
            'configured_address': unicode(device.get_address()),
            'target_id': _binding['target_id'], 'timestamp_unix_ms': int(time.time()*1000)}, device


def checked(project, application, request):
    info, device = target(project, application)
    if info['mode'] != 'simulation':
        raise RuntimeError('Only positively verified simulation is allowed; target mode is ' + info['mode'])
    if request.get('target_id') != info['target_id']:
        raise ValueError('Stale or missing target_id; inspect the target again')
    return info, device


def assert_offline():
    if _attached or _forces or _uncertain or invt_debugger._owned or invt_trace.has_packets():
        raise RuntimeError('Disconnect the simulation runtime before editing or rebuilding the project')


def online(application):
    obj = se.online.create_online_application(application)
    obj.timeout = 10000
    return obj


def use_online(application, callback):
    obj = online(application)
    try:
        return callback(obj)
    finally:
        obj.Dispose()


def state(obj):
    connected = bool(obj.is_logged_in)
    if not connected:
        invt_debugger.disconnected()
    result = {'connected': connected, 'uncertain_previous_operation': _uncertain}
    if connected:
        result.update(application_state=unicode(obj.application_state),
                      operating_state=unicode(obj.operation_state),
                      exception_active=bool(int(obj.operation_state) & 32))
    return result


def prepared_empty(obj):
    if list(obj.get_prepared_expressions()):
        raise RuntimeError('Prepared values already exist; do not apply editor/foreign preparations')


def forced_paths(obj):
    return [unicode(p) for p in obj.get_forced_expressions()]


def unforce_owned(obj, expression):
    if expression not in _forces:
        raise ValueError('Selective unforce is limited to forces created by this MCP session')
    prepared_empty(obj)
    if expression in forced_paths(obj):
        obj.set_unforce_value(expression, False)
        obj.force_prepared_values()
        if expression in forced_paths(obj):
            raise RuntimeError('Force still active after selective unforce')
    _forces.pop(expression, None)


def detach(obj, application=None):
    global _attached, _uncertain
    if not obj.is_logged_in:
        if _forces or invt_debugger._owned or invt_trace.has_packets():
            raise RuntimeError('Connection lost with owned forces/breakpoints; cleanup unconfirmed, recover explicitly')
        _attached = False
        _uncertain = False
        return {'connected': False, 'cleaned_forces': []}
    cleanup_trace = [{'phase': 'before_stop', 'state': state(obj)}]
    if _attached and unicode(obj.application_state).lower() == 'halt_on_bp':
        raise invt_debugger.HaltRequiresExplicitStop('Explicit stop_application halt_behavior required before disconnect/close/shutdown from HALT')
    if application is not None:
        import invt_operations
        invt_trace.cleanup(invt_operations.owned(),application,obj)
    native_logout = invt_debugger.prepare_logout(application, obj) if _attached else None
    cleanup_trace.append({'phase': 'before_stop_after_deactivate', 'state': state(obj)})
    # HALT was refused above: disconnect must never complete a paused cycle.
    # Quiesce the owned RUN application before removing its points/forces.
    if _attached and unicode(obj.application_state).lower() != 'stop':
        if unicode(obj.application_state).lower() == 'halt_on_bp':
            invt_debugger.stop_halted(application, obj)
        else:
            obj.stop()
    cleanup_trace.append({'phase': 'after_stop', 'state': state(obj)})
    invt_debugger.cleanup(application, obj)
    cleanup_trace.append({'phase': 'after_clear_owned', 'state': state(obj)})
    cleaned = []
    for expression in list(_forces):
        unforce_owned(obj, expression)
        cleaned.append(expression)
    # Only a runtime this MCP explicitly attached is stopped/logged out.
    if _attached:
        cleanup_trace.append({'phase': 'after_deactivate', 'state': state(obj)})
        if native_logout is not None:
            invt_debugger.logout_core(native_logout)
        else:
            obj.logout()
    _attached = False
    _uncertain = False
    return {'connected': bool(obj.is_logged_in), 'cleaned_forces': cleaned, 'cleanup_trace': cleanup_trace}


def cleanup(project, application, abort_halt=False):
    if not (_attached or _forces or _uncertain or invt_debugger._owned or invt_trace.has_packets()):
        return
    info, device = target(project, application)
    if info['mode'] != 'simulation':
        raise RuntimeError('Cannot cleanup an unverified runtime target')
    def action(obj):
        if abort_halt and obj.is_logged_in and _attached and unicode(obj.application_state).lower() == 'halt_on_bp':
            invt_debugger.stop_with_behavior(application, obj, 'abort_cycle')
        return detach(obj, application)
    with_executor(lambda: use_online(application, action))


def perform(project, application, request):
    global _attached, _uncertain, _binding
    op = request['operation']
    info, device = target(project, application)
    if op == 'runtime_target':
        return {'ok': True, 'target': info}
    if op == 'debug_capabilities':
        return {'ok': True, 'target': info, 'online_api_present': hasattr(se, 'online'),
                'simulation_getter_present': hasattr(device, 'get_simulation_mode'),
                'physical_runtime_allowed': False,
                'breakpoints_step_exposed': True, 'debugger_component_version': invt_debugger.CORE_VERSION,
                'debugger_requires_owned_full_download': True, 'frame_locals_supported': True,
                'frame_locals_repeated_pou_supported': False,
                'trace_exposed': True, 'trace_buffer_entries': 100,
                'trace_configuration_delete_requires_disconnect': True,
                'matrix': 'docs/invt-debug-capabilities.md'}
    if op == 'simulation_mode':
        assert_offline()
        if info['target_id'] != request.get('target_id'):
            raise ValueError('Stale or missing target_id')
        device.set_simulation_mode(request['enabled'])
        project.save()
        _binding = None
        after, device = target(project, application)
        expected = 'simulation' if request['enabled'] else 'physical'
        if after['mode'] != expected:
            raise RuntimeError('Simulation mode read-back did not match request')
        return {'ok': True, 'before': info, 'target': after, 'saved': True}
    info, device = checked(project, application, request)
    mutations = ('connect_runtime', 'download_application', 'start_application',
                 'stop_application', 'write_variable', 'force_variable', 'unforce_variable')
    if _uncertain and op in mutations:
        raise RuntimeError('Previous runtime mutation result uncertain; inspect state and disconnect, never replay')
    if op in ('read_variables',):
        for expression in request['variables']:
            variable_path(expression)
    if op in ('write_variable', 'force_variable', 'unforce_variable'):
        variable_path(request['variable'])
    project.active_application = application

    def action(obj):
        global _attached, _uncertain
        # Recheck the getter inside the executor frame immediately before API calls.
        checked(project, application, request)
        result = {'ok': True, 'target': info}
        if op in ('connect_runtime', 'download_application'):
            if obj.is_logged_in and not _attached:
                raise ValueError('Existing unowned online connection; do not adopt it')
            if op == 'download_application' and (obj.is_logged_in or _forces):
                raise ValueError('Disconnect and clean forces before explicit full download')
            option = se.OnlineChangeOption.Keep if op == 'connect_runtime' else se.OnlineChangeOption.Never
            _attached = True  # Retain ownership if login partially succeeds then raises.
            obj.login(option, False)
            _attached = bool(obj.is_logged_in)
            if not _attached:
                raise RuntimeError('Login did not establish connection')
            result.update(login_option=unicode(option), boot_created=False, automatic_start=False)
            if op == 'download_application':
                invt_debugger.downloaded(application, obj, info)
                result['debugger_available'] = invt_debugger._download is not None
                result['debugger_error'] = invt_debugger._unavailable
        elif op == 'disconnect_runtime':
            result.update(detach(obj, application))
        elif op == 'runtime_state':
            pass
        else:
            if not obj.is_logged_in or not _attached:
                if op == 'read_variables':
                    stamp = int(time.time()*1000)
                    return {'ok': False, 'target': info, 'state': state(obj), 'atomic': False,
                            'values': [{'variable': expression, 'ok': False,
                                        'error': 'No owned runtime connection; connect explicitly',
                                        'timestamp_unix_ms': stamp, 'completed_unix_ms': stamp}
                                       for expression in request['variables']]}
                raise RuntimeError('No owned runtime connection; connect explicitly')
            if op == 'start_application':
                if invt_debugger._active is not None and list(invt_debugger.bp_manager().GetBreakpoints(application.guid)):
                    return {'ok': False, 'target': info, 'error': 'Breakpoints exist; use explicit debug_continue', 'state': state(obj)}
                if unicode(obj.application_state).lower() != 'run':
                    obj.start()
            elif op == 'stop_application':
                if unicode(obj.application_state).lower() != 'stop':
                    if unicode(obj.application_state).lower() == 'halt_on_bp':
                        result.update(invt_debugger.stop_with_behavior(application, obj, request.get('halt_behavior')))
                    else:
                        obj.stop()
            elif op == 'read_variables':
                values = []
                for expression in request['variables']:
                    stamp = int(time.time()*1000)
                    try:
                        if not obj.is_logged_in:
                            raise RuntimeError('Runtime disconnected')
                        value = obj.read_value(expression)
                        if value is None:
                            raise RuntimeError('No fresh value returned')
                        values.append({'variable': expression, 'ok': True, 'value': unicode(value),
                                       'timestamp_unix_ms': stamp, 'completed_unix_ms': int(time.time()*1000)})
                    except Exception as e:
                        values.append({'variable': expression, 'ok': False, 'error': unicode(e),
                                       'timestamp_unix_ms': stamp, 'completed_unix_ms': int(time.time()*1000)})
                result.update(values=values, atomic=False, ok=all(v['ok'] for v in values))
            elif op == 'list_forces':
                result['forces'] = [{'variable': p, 'owned_by_session': p in _forces} for p in forced_paths(obj)]
                result['owned_forces'] = dict(_forces)
            elif op == 'unforce_variable':
                unforce_owned(obj, request['variable'])
                result['unforced'] = request['variable']
            elif op in ('write_variable', 'force_variable'):
                expression, value = request['variable'], request['value']
                prepared_empty(obj)
                if expression in forced_paths(obj):
                    raise ValueError('Variable already forced; unforce explicitly before writing')
                # Status can be ahead of the expression-monitoring channel just
                # after reconnect. Validate a fresh path before preparing anything.
                before = obj.read_value(expression)
                if before is None or not obj.is_logged_in:
                    raise RuntimeError('No fresh connected value before variable mutation')
                if op == 'force_variable':
                    # Register before the call so an uncertain result retains cleanup ownership.
                    _forces[expression] = value
                try:
                    obj.set_prepared_value(expression, value)
                    if op == 'write_variable':
                        obj.write_prepared_values()
                    else:
                        obj.force_prepared_values()
                finally:
                    obj.set_prepared_value(expression, None)
                active = expression in forced_paths(obj)
                if active != (op == 'force_variable'):
                    raise RuntimeError('Force-state verification mismatch')
                result.update(variable=expression, requested_value=value, forced=active, value_before=unicode(before),
                              value_after=unicode(obj.read_value(expression)))
        result['state'] = state(obj)
        if op == 'start_application' and result['state'].get('application_state', '').lower() != 'run':
            raise RuntimeError('RUN read-back mismatch')
        if op == 'stop_application' and result['state'].get('application_state', '').lower() != 'stop':
            raise RuntimeError('STOP read-back mismatch')
        return result
    try:
        return with_executor(lambda: use_online(application, action))
    except invt_debugger.HaltRequiresExplicitStop as error:
        return {'ok': False, 'target': info, 'reason': 'halt_requires_explicit_stop', 'error': unicode(error),
                'uncertain_previous_operation': _uncertain}
    except Exception:
        if op in mutations:
            _uncertain = True
        return {'ok': False, 'target': info, 'operation': op,
                'exception': traceback.format_exc(), 'uncertain_previous_operation': _uncertain,
                'owned_forces': dict(_forces)}
