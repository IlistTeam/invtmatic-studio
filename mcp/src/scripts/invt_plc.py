# -*- coding: utf-8 -*-
"""Explicit physical PLC operations, separate from the simulation policy."""
import os
import uuid
import time
import traceback
import scriptengine as se
import invt_hardware
import invt_runtime
from invt_executor import with_executor

OPS = ('plc_bind', 'plc_target', 'plc_connect', 'plc_disconnect', 'plc_state',
       'plc_download', 'plc_start', 'plc_stop', 'plc_read', 'plc_write')
CORE_VERSION = '3.5.20.61'
_binding = None
_attached = False
_uncertain = False


def enabled():
    invt_hardware.configured_address()
    if os.environ.get('INVT_MCP_PHYSICAL_RUNTIME') != '1':
        raise RuntimeError('Physical runtime was not explicitly enabled')


def flags():
    from System.Reflection import BindingFlags
    return BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance


def assert_offline():
    if _attached or _uncertain:
        raise RuntimeError('Disconnect the physical PLC before editing, rebuilding or rebinding')


def signature(project, application, device):
    from invt_debugger import source_hash
    identity = device.get_device_identification()
    return (project.path, str(application.guid), str(device.guid),
            bool(device.get_simulation_mode()), str(device.get_gateway()),
            unicode(device.get_address()), int(identity.type), unicode(identity.id),
            unicode(identity.version), source_hash(application))


def verified_core(value, expected):
    typ = value.GetType()
    if typ.FullName != '_3S.CoDeSys.OnlineManager.' + expected or str(typ.Assembly.GetName().Version) != CORE_VERSION:
        raise RuntimeError('Physical core API version/type not verified')
    return value


def read_identity(device):
    """Targeted device connection; no application login or download."""
    import clr
    from System import Array, Object
    obj = se.online.create_online_device(device)
    try:
        core = clr.GetClrType(type(obj)).GetField('OnlineDevice', flags()).GetValue(obj)
        verified_core(core, 'OnlineDevice')
        obj.connect()
        methods = [m for m in core.GetType().GetMethods(flags())
                   if m.Name == 'GetTargetIdent' and m.GetParameters().Length == 4]
        if len(methods) != 1:
            raise RuntimeError('Verified target identity getter unavailable')
        args = Array[Object]([None, None, None, None])
        ident = methods[0].Invoke(core, args)
        return {'type': int(ident.Type), 'id': unicode(ident.Id), 'version': unicode(ident.Version),
                'device_name': unicode(args[0]), 'vendor': unicode(args[1]),
                'model': unicode(args[2]), 'reported_runtime_version': unicode(args[3]),
                'source': 'connected device GetTargetIdent; not local description'}
    finally:
        if obj.connected:
            obj.disconnect()
        obj.Dispose()


def match_identity(actual, device):
    expected = device.get_device_identification()
    if (actual['type'], actual['id'], actual['version']) != (int(expected.type), unicode(expected.id), unicode(expected.version)):
        raise RuntimeError('Connected PLC identity does not match the selected project device')


def checked(project, application, request):
    enabled()
    device = invt_runtime.ancestor_device(application)
    if device.get_simulation_mode() != False:
        raise RuntimeError('Physical mode must be positively verified')
    if _binding is None or request.get('target_id') != _binding['target_id']:
        raise ValueError('Stale or missing physical target_id; bind explicitly')
    if signature(project, application, device) != _binding['signature']:
        raise RuntimeError('Physical project/source/device/gateway/address changed; bind again while offline')
    return device


def boot_settings(obj):
    core = verified_core(obj.GetType().GetProperty('Application', flags()).GetValue(obj, None), 'OnlineApplication')
    application_object = core.GetType().GetProperty('OnlApplObject', flags()).GetValue(core, None)
    typ = application_object.GetType()
    if typ.FullName != '_3S.CoDeSys.ApplicationObject.ApplicationObject' or str(typ.Assembly.GetName().Version) != '3.5.20.60':
        raise RuntimeError('Boot settings API not verified')
    settings = typ.GetProperty('BootApplicationSettings', flags()).GetValue(application_object, None)
    before, after = {}, {}
    for name in ('CreateBootApplicationOnDownload', 'CreateBootApplicationOnOnlineChange'):
        prop = settings.GetType().GetProperty(name, flags())
        before[name] = bool(prop.GetValue(settings, None))
        prop.SetValue(settings, False, None)
        after[name] = bool(prop.GetValue(settings, None))
        if after[name]:
            raise RuntimeError('Automatic boot application creation still enabled')
    return {'before': before, 'after': after}


def state(obj):
    result = {'connected': bool(obj.is_logged_in), 'owned_connection': _attached,
              'uncertain_previous_operation': _uncertain, 'timestamp_unix_ms': int(time.time()*1000)}
    if obj.is_logged_in:
        result.update(application_state=unicode(obj.application_state), operating_state=unicode(obj.operation_state),
                      exception_active=bool(int(obj.operation_state) & 32))
    return result


def cleanup(project, application):
    global _attached, _uncertain, _binding
    if _binding is None or _binding['application_guid'] != str(application.guid):
        return
    if _attached or _uncertain:
        request = {'target_id': _binding['target_id'] if _binding else None, 'operation': 'plc_disconnect'}
        result = perform(project, application, request)
        if not result['ok']:
            raise RuntimeError('Physical logout unconfirmed: ' + repr(result))
    _binding = None


def perform(project, application, request):
    global _binding, _attached, _uncertain
    enabled()
    op = request['operation']
    device = invt_runtime.ancestor_device(application)
    project.active_application = application
    if op == 'plc_bind':
        invt_runtime.assert_offline()
        assert_offline()
        if device.get_simulation_mode() != False:
            raise RuntimeError('Disable simulation explicitly before binding a physical PLC')
        gateways = [g for g in se.online.gateways if str(g.guid).lower() == request.get('gateway_guid','').lower()]
        if len(gateways) != 1:
            raise ValueError('Choose one configured gateway GUID')
        gateway = gateways[0]
        def bind():
            address = gateway.find_address_by_ip(invt_hardware.configured_address(),11740)
            if not address:
                raise RuntimeError('PLC address lookup returned no address')
            device.set_gateway_and_address(gateway, address)
            actual = read_identity(device)
            match_identity(actual, device)
            if actual['id'] != request.get('expected_device_id'):
                raise ValueError('Measured device ID does not match the explicitly expected device ID')
            project.save()
            return actual
        actual = with_executor(bind)
        _binding = {'target_id': str(uuid.uuid4()), 'signature': signature(project,application,device),
                    'identity': actual, 'application_guid': str(application.guid), 'gateway_guid': str(gateway.guid),
                    'address': unicode(device.get_address()), 'physical_address': invt_hardware.configured_address()}
        return {'ok': True, 'target': {k:v for k,v in _binding.items() if k != 'signature'}, 'login_performed': False}
    device = checked(project,application,request)
    if op == 'plc_target':
        return {'ok': True, 'target': {k:v for k,v in _binding.items() if k != 'signature'}}
    if _uncertain and op not in ('plc_state','plc_disconnect','plc_read'):
        raise RuntimeError('Previous physical operation uncertain; inspect and disconnect, never replay')
    if op == 'plc_read':
        for variable in request['variables']: invt_runtime.variable_path(variable)
    if op == 'plc_write': invt_runtime.variable_path(request['variable'])
    mutation_started = [False]
    def action():
        global _attached, _uncertain
        checked(project,application,request)
        obj = se.online.create_online_application(application)
        obj.timeout = 10000
        try:
            result = {'ok': True, 'target_id': _binding['target_id'], 'operation': op}
            if obj.is_logged_in and not _attached:
                raise RuntimeError('Existing unowned physical connection; do not adopt')
            if op in ('plc_connect','plc_download'):
                if obj.is_logged_in or _attached:
                    raise RuntimeError('Disconnect before a new physical login/download')
                match_identity(read_identity(device),device)
                if op == 'plc_download':
                    result['boot_settings'] = boot_settings(obj)
                    project.save()
                option = se.OnlineChangeOption.Never if op == 'plc_download' else se.OnlineChangeOption.Keep
                mutation_started[0] = True
                _attached = True
                obj.login(option,False)
                if not obj.is_logged_in: raise RuntimeError('Physical login did not establish a connection')
                _binding['target_id'] = str(uuid.uuid4())
                result['target_id'] = _binding['target_id']
                result.update(login_option=unicode(option), automatic_start=False, boot_created=False)
            elif op == 'plc_disconnect':
                if obj.is_logged_in:
                    mutation_started[0] = True
                    obj.logout()
                if obj.is_logged_in: raise RuntimeError('Physical logout read-back mismatch')
                _attached, _uncertain = False, False
                _binding['target_id'] = str(uuid.uuid4())
                result['target_id'] = _binding['target_id']
                result['application_stop_requested'] = False
            elif op == 'plc_state':
                pass
            else:
                if not _attached or not obj.is_logged_in:
                    raise RuntimeError('No owned physical PLC connection; connect explicitly')
                if op in ('plc_start','plc_stop'):
                    if int(obj.operation_state) & 32: raise RuntimeError('PLC exception active; no implicit recovery')
                    if unicode(obj.application_state).lower() == 'halt_on_bp': raise RuntimeError('HALT recovery is not verified for physical targets')
                    mutation_started[0] = True
                    if op == 'plc_start': obj.start()
                    else: obj.stop()
                    expected = 'run' if op == 'plc_start' else 'stop'
                    if unicode(obj.application_state).lower() != expected: raise RuntimeError('Physical execution state read-back mismatch')
                elif op == 'plc_read':
                    values=[]
                    for variable in request['variables']:
                        stamp=int(time.time()*1000)
                        value=obj.read_value(variable)
                        if value is None or not obj.is_logged_in: raise RuntimeError('No fresh physical value returned')
                        values.append({'variable':variable,'value':unicode(value),'timestamp_unix_ms':stamp,'completed_unix_ms':int(time.time()*1000)})
                    result.update(values=values,atomic=False)
                elif op == 'plc_write':
                    variable=request['variable']
                    invt_runtime.prepared_empty(obj)
                    if variable in invt_runtime.forced_paths(obj): raise RuntimeError('Variable is forced; do not overwrite')
                    before=obj.read_value(variable)
                    if before is None or not obj.is_logged_in: raise RuntimeError('No fresh connected value before write')
                    mutation_started[0]=True
                    try:
                        obj.set_prepared_value(variable,request['value'])
                        obj.write_prepared_values()
                    finally: obj.set_prepared_value(variable,None)
                    after=obj.read_value(variable)
                    if after is None or not obj.is_logged_in: raise RuntimeError('Write result has no fresh connected read-back')
                    result.update(variable=variable,value_before=unicode(before),value_after=unicode(after),requested_value=request['value'],forced=False)
                else: raise ValueError('Unsupported physical operation')
            result['state']=state(obj)
            return result
        finally: obj.Dispose()
    try:
        return with_executor(action)
    except Exception:
        if mutation_started[0]: _uncertain=True
        return {'ok':False,'operation':op,'exception':traceback.format_exc(),'uncertain_previous_operation':_uncertain}
