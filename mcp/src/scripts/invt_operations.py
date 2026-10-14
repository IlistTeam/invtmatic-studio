# -*- coding: utf-8 -*-
"""Project and verified-simulation operations for one owned INVT process."""
import json
import os
import traceback
import scriptengine as se
from invt_project import describe, diagnostics, library_inventory, select
import invt_creation
import invt_tasks
import invt_runtime
import invt_debugger

_project = None
_path = None
_root = os.path.realpath(os.environ['INVT_IPC_SESSION'])


def owned():
    current = se.projects.primary
    if current is None:
        raise RuntimeError('No project open')
    if _project is None or os.path.normcase(current.path) != os.path.normcase(_path):
        raise RuntimeError('Unowned project in managed Studio; operation refused')
    return current


def within(path):
    resolved = os.path.realpath(path)
    if not resolved.lower().startswith(_root.lower() + os.sep):
        raise ValueError('Path outside owned session')
    return resolved


def prepare_shutdown(abort_halt=False):
    global _project, _path
    if se.projects.primary is not None:
        try:
            project = owned()
        except RuntimeError:
            return False
        objects = list(project.get_children(True))
        for application in [o for o in objects if getattr(o, 'is_application', False)]:
            invt_runtime.cleanup(project, application, abort_halt)
        project.save()
        project.close()
    _project = None
    _path = None
    return True


def choose_application(objects, request):
    apps = [o for o in objects if getattr(o, 'is_application', False)]
    if request.get('application_guid'):
        apps = [o for o in apps if str(o.guid).lower() == request['application_guid'].lower()]
    if len(apps) != 1:
        raise ValueError('Choose a unique application GUID')
    return apps[0]


def replace_and_verify(obj, request):
    for key, attr in (('declaration', 'textual_declaration'), ('implementation', 'textual_implementation')):
        if key in request and not hasattr(obj, attr):
            raise ValueError('Object does not have ' + attr)
    for key, attr in (('declaration', 'textual_declaration'), ('implementation', 'textual_implementation')):
        if key in request:
            doc = getattr(obj, attr)
            doc.replace(request[key])
            if doc.text.replace('\r\n', '\n').strip() != request[key].replace('\r\n', '\n').strip():
                raise RuntimeError('ST read-back mismatch')


def rebuild(project, application, result):
    result['previous_diagnostics'] = diagnostics()
    for category in se.system.get_message_categories():
        se.system.clear_messages(category)
    application.rebuild()
    result['diagnostics'] = diagnostics()
    seen = any(m['category'].lower() == '97f48d64-a2a3-4856-b640-75c046e37ea9' for m in result['diagnostics'])
    result['build_ok'] = seen and not any(m['severity'] in ('Error', 'FatalError') for m in result['diagnostics'])
    result['ok'] = result['build_ok']
    project.save()


def create_object(project, objects, request):
    result = {'ok': False, 'operation': request['operation'], 'project': _path,
              'created': False, 'saved': False}
    obj = None
    try:
        enum_type = invt_creation.preflight(request)
        application = choose_application(objects, request)
        project.active_application = application
        result['application_guid'] = str(application.guid)
        obj = invt_creation.create(application, request, enum_type)
        result['created'] = True
        result['created_guid'] = str(obj.guid)
        replace_and_verify(obj, request)
        result['object'] = describe(obj, True)
        project.save()
        result['saved'] = True
        rebuild(project, application, result)
    except Exception:
        result['ok'] = False
        result['exception'] = traceback.format_exc()
        # Preserve identity and actual side effects even if text/build processing
        # fails after creation. Never replay a creation automatically.
        if obj is not None:
            try:
                result['object'] = describe(obj, True)
                project.save()
                result['saved'] = True
            except Exception:
                result['save_exception'] = traceback.format_exc()
    return result


def perform(request):
    global _project, _path
    op = request['operation']
    if op == 'ping':
        return {'ok': True, 'pid': os.getpid(), 'project': _path}
    if op == 'prepare_shutdown':
        prepared = prepare_shutdown(bool(request.get('abort_halt', False)))
        return {'ok': prepared, 'reason': None if prepared else 'unowned_project'}
    if op == 'open_copy':
        if se.projects.primary is not None:
            raise RuntimeError('Close the current session before opening another project')
        candidate = within(request['project'])
        _project = se.projects.open(candidate)
        _path = candidate
        return {'ok': True, 'project': _path, 'diagnostics': diagnostics()}
    project = owned()
    objects = list(project.get_children(True))
    if op in invt_debugger.OPS:
        return invt_debugger.perform(project, choose_application(objects, request), request)
    if op in invt_runtime.OPS:
        application = choose_application(objects, request)
        if op == 'download_application':
            invt_runtime.checked(project, application, request)
            invt_runtime.assert_offline()
            build = {'ok': False}
            rebuild(project, application, build)
            if not build['build_ok']:
                return build
        return invt_runtime.perform(project, application, request)
    if op == 'inspect':
        return {'ok': True, 'project': _path,
                'objects': [describe(obj, True) for obj in objects],
                'libraries': library_inventory(objects), 'diagnostics': diagnostics()}
    if op == 'close_project':
        for application in [o for o in objects if getattr(o, 'is_application', False)]:
            invt_runtime.cleanup(project, application)
        project.save()
        project.close()
        _project = None
        _path = None
        return {'ok': True}
    if op == 'inspect_tasks':
        result = invt_tasks.inspect(choose_application(objects, request))
        result.update(ok=True, project=_path)
        return result
    if op in ('create_task', 'configure_task', 'bind_program'):
        invt_runtime.assert_offline()
        application = choose_application(objects, request)
        project.active_application = application
        result = invt_tasks.mutate(project, application, request, rebuild)
        result['project'] = _path
        return result
    if op in ('create_pou', 'create_gvl', 'create_dut'):
        invt_runtime.assert_offline()
        return create_object(project, objects, request)
    if op not in ('build', 'patch_st', 'export_pou'):
        raise ValueError('Unsupported offline operation')
    result = {'ok': True, 'project': _path}
    if op in ('build', 'patch_st'):
        invt_runtime.assert_offline()
        application = choose_application(objects, request)
        project.active_application = application
    if op in ('patch_st', 'export_pou'):
        obj = select(objects, request['object_guid'])
        if not hasattr(obj, 'textual_declaration'):
            raise ValueError('Not a textual object')
    if op == 'patch_st':
        result['before'] = describe(obj, True)
        replace_and_verify(obj, request)
        result['after'] = describe(obj, True)
        project.save()
    if op == 'export_pou':
        folder = within(request['export_directory'])
        obj.export_native(os.path.join(folder, 'pou.export'))
        obj.export_xml(path=os.path.join(folder, 'pou.xml'), recursive=True, declarations_as_plaintext=True)
        result['exports'] = [os.path.join(folder, 'pou.export'), os.path.join(folder, 'pou.xml')]
    else:
        rebuild(project, application, result)
    return result


def dispatch(request):
    try:
        result = perform(request)
    except invt_debugger.HaltRequiresExplicitStop as error:
        result = {'ok': False, 'reason': 'halt_requires_explicit_stop', 'error': unicode(error)}
    except Exception:
        result = {'ok': False, 'exception': traceback.format_exc()}
    result['runtime_scope'] = 'verified_simulation_only'
    result['physical_runtime_allowed'] = False
    return result
