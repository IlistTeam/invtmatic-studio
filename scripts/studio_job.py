# -*- coding: utf-8 -*-
"""IronPython 2.7 entry point; invoked only in a dedicated offline Studio process."""
from __future__ import print_function
import json
import os
import traceback
import scriptengine as se


def write_json(path, value):
    temporary = path + '.tmp'
    with open(temporary, 'w') as stream:
        json.dump(value, stream, ensure_ascii=True, indent=2)
    # Destination is new for final results; progress is replaced on Windows.
    if os.path.exists(path):
        os.remove(path)
    os.rename(temporary, path)


def diagnostics():
    result = []
    for category in se.system.get_message_categories():
        for message in se.system.get_message_objects(category):
            result.append({'category': str(category), 'severity': str(message.severity),
                           'text': unicode(message.text),
                           'position': unicode(message.position_text or '')})
    return result


def object_path(obj):
    parts = []
    while not obj.is_root:
        parts.insert(0, obj.get_name())
        obj = obj.parent
    return parts


def describe(obj, include_code=False):
    value = {'name': obj.get_name(), 'path': object_path(obj), 'guid': str(obj.guid),
             'application': bool(getattr(obj, 'is_application', False)),
             'textual': hasattr(obj, 'textual_declaration')}
    if include_code and value['textual']:
        value['declaration'] = obj.textual_declaration.text
        if hasattr(obj, 'textual_implementation'):
            value['implementation'] = obj.textual_implementation.text
    return value


def library_inventory(objects):
    result = []
    for manager in objects:
        if not getattr(manager, 'is_libman', False):
            continue
        entries = []
        for ref in manager.references:
            item = {'name': ref.name, 'placeholder': ref.is_placeholder}
            if ref.is_placeholder:
                item.update(default=ref.default_resolution, effective=ref.effective_resolution)
            entries.append(item)
        result.append({'path': object_path(manager), 'references': entries})
    return result


def select(objects, guid):
    found = [obj for obj in objects if str(obj.guid).lower() == guid.lower()]
    if len(found) != 1:
        raise ValueError('Expected exactly one object for GUID ' + guid)
    return found[0]


def execute(request_path):
    with open(request_path, 'r') as stream:
        request = json.load(stream)
    directory = os.path.dirname(request_path)
    report_path = os.path.join(directory, 'result.json')
    result = {'schema': 1, 'job_id': request['job_id'], 'operation': request['operation'],
              'ok': False, 'online_operations': False, 'project': request['project']}
    project = None
    def stage(name):
        write_json(os.path.join(directory, 'progress.json'), {'job_id': request['job_id'], 'stage': name})
    try:
        stage('script_started')
        if se.projects.primary is not None:
            raise RuntimeError('Dedicated Studio process must start without a project')
        project = se.projects.open(request['project'])
        stage('project_opened')
        objects = list(project.get_children(True))
        result['open_diagnostics'] = diagnostics()
        result['libraries'] = library_inventory(objects)
        operation = request['operation']
        if operation == 'inspect':
            result['objects'] = [describe(obj, True) for obj in objects]
        elif operation in ('build', 'patch_st', 'export_pou'):
            if operation in ('patch_st', 'export_pou'):
                obj = select(objects, request['object_guid'])
                if not hasattr(obj, 'textual_declaration'):
                    raise ValueError('Selected object has no textual declaration')
            if operation == 'patch_st':
                result['before'] = describe(obj, True)
                for key, attribute in (('declaration', 'textual_declaration'),
                                       ('implementation', 'textual_implementation')):
                    if key in request:
                        document = getattr(obj, attribute)
                        document.replace(request[key])
                        if document.text.replace('\r\n', '\n').strip() != request[key].replace('\r\n', '\n').strip():
                            raise RuntimeError('ST read-back mismatch: ' + key)
                result['after'] = describe(obj, True)
                project.save()
                stage('patched_copy_saved')
            if operation == 'export_pou':
                native = os.path.join(directory, 'pou.export')
                xml = os.path.join(directory, 'pou.xml')
                obj.export_native(native)
                obj.export_xml(path=xml, recursive=True, declarations_as_plaintext=True)
                result['exports'] = {'native': native, 'plcopen_xml': xml}
            else:
                apps = [o for o in objects if getattr(o, 'is_application', False)]
                if request.get('application_guid'):
                    apps = [a for a in apps if str(a.guid).lower() == request['application_guid'].lower()]
                if len(apps) != 1:
                    raise ValueError('Choose application_guid; application count is ' + str(len(apps)))
                project.active_application = apps[0]
                stage('building')
                apps[0].rebuild()
                result['build_diagnostics'] = diagnostics()
                compiler_category = '97f48d64-a2a3-4856-b640-75c046e37ea9'
                result['compiler_messages_seen'] = any(m['category'].lower() == compiler_category for m in result['build_diagnostics'])
                result['build_ok'] = result['compiler_messages_seen'] and not any(m['severity'] in ('Error', 'FatalError') for m in result['build_diagnostics'])
                project.save()
        else:
            raise ValueError('Unsupported operation: ' + operation)
        result['diagnostics'] = diagnostics()
        result['ok'] = result.get('build_ok', True)
    except Exception:
        result['exception'] = traceback.format_exc()
        result['ok'] = False
    finally:
        if project is not None:
            try:
                project.close()
            except Exception:
                result['close_exception'] = traceback.format_exc()
                result['ok'] = False
        result['finished'] = True
        write_json(report_path, result)
        stage('finished')
    se.system.exit(0 if result['ok'] else 1)
