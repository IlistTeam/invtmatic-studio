# -*- coding: utf-8 -*-
"""Offline task inspection/configuration using installed ScriptEngine (IronPython)."""
import re
import traceback
import scriptengine as se
from invt_project import describe, select
from invt_creation import IDENTIFIER, declaration_start


def duration_ms(text, unit):
    value = unicode(text).strip().lower().replace('_', '')
    literal = re.match(r'^(?:t|time)#([0-9]+(?:\.[0-9]+)?)(us|ms|s|m|h|d)\Z', value)
    factors = {'us': 0.001, 'ms': 1, 's': 1000, 'm': 60000, 'h': 3600000, 'd': 86400000}
    if literal:
        return float(literal.group(1)) * factors[literal.group(2)]
    if re.match(r'^[0-9]+(?:\.[0-9]+)?\Z', value) and unit in factors:
        return float(value) * factors[unit]
    return None  # Retain raw expressions; do not guess the value of a variable.


def task_record(task):
    result = describe(task)
    result['kind'] = unicode(task.kind_of_task)
    result['priority'] = unicode(task.priority)
    result['bindings'] = [{'index': index, 'program_name': unicode(task.pous[index][0]),
                           'comment': unicode(task.pous[index][1] or '')}
                          for index in range(len(task.pous))]
    errors = {}
    for key in ('interval', 'interval_unit', 'event', 'external_event', 'core_binding', 'parent_synchron_task'):
        try:
            value = getattr(task, key)
            result[key] = int(value) if key == 'core_binding' else unicode(value)
        except Exception as error:
            errors[key] = unicode(error)
    watchdog = task.watchdog
    result['watchdog'] = {'enabled': bool(watchdog.enabled), 'time': unicode(watchdog.time),
                          'time_unit': unicode(watchdog.time_unit), 'sensitivity': unicode(watchdog.sensitivity)}
    result['interval_ms'] = duration_ms(result.get('interval', ''), result.get('interval_unit', ''))
    result['watchdog']['time_ms'] = duration_ms(result['watchdog']['time'], result['watchdog']['time_unit'])
    if errors:
        result['unavailable_fields'] = errors
    return result


def inspect(application):
    objects = list(application.get_children(True))
    return {'application_guid': str(application.guid),
            'task_configurations': [describe(o) for o in objects if getattr(o, 'is_task_configuration', False)],
            'tasks': [task_record(o) for o in objects if getattr(o, 'is_task', False)]}


def integer(value, minimum, maximum, label):
    if isinstance(value, bool) or not isinstance(value, (int, long)) or not minimum <= value <= maximum:
        raise ValueError(label + ' outside supported integer range')


def validate_settings(settings, creating=False):
    if not settings or set(settings) - set(('interval_ms', 'priority', 'watchdog')):
        raise ValueError('Supply at least one supported task setting')
    if creating and not all(key in settings for key in ('priority', 'interval_ms')):
        raise ValueError('Creation requires priority and interval_ms')
    if 'priority' in settings:
        integer(settings['priority'], 0, 31, 'priority')
    if 'interval_ms' in settings:
        integer(settings['interval_ms'], 1, 60000, 'interval_ms')
    if 'watchdog' in settings:
        watchdog = settings['watchdog']
        if set(watchdog) - set(('enabled', 'time_ms', 'sensitivity')) or not isinstance(watchdog.get('enabled'), bool):
            raise ValueError('Watchdog requires enabled and only supported settings')
        if watchdog['enabled'] and not all(key in watchdog for key in ('time_ms', 'sensitivity')):
            raise ValueError('Enabling watchdog requires time_ms and sensitivity')
        if 'time_ms' in watchdog:
            integer(watchdog['time_ms'], 1, 60000, 'watchdog.time_ms')
        if 'sensitivity' in watchdog:
            integer(watchdog['sensitivity'], 1, 1000, 'watchdog.sensitivity')


def configure(task, settings):
    if task.kind_of_task != se.KindOfTask.Cyclic:
        raise ValueError('Task settings are exposed only for cyclic tasks')
    if 'priority' in settings:
        task.priority = str(settings['priority'])
    if 'interval_ms' in settings:
        task.interval_unit = 'ms'
        task.interval = 't#%dms' % settings['interval_ms']
    if 'watchdog' in settings:
        values, watchdog = settings['watchdog'], task.watchdog
        if 'time_ms' in values:
            watchdog.time_unit = 'ms'
            watchdog.time = 't#%dms' % values['time_ms']
        if 'sensitivity' in values:
            watchdog.sensitivity = str(values['sensitivity'])
        watchdog.enabled = values['enabled']
    actual = task_record(task)
    if 'priority' in settings and int(actual['priority']) != settings['priority']:
        raise RuntimeError('Priority read-back mismatch')
    if 'interval_ms' in settings and actual['interval_ms'] != settings['interval_ms']:
        raise RuntimeError('Interval read-back mismatch')
    if 'watchdog' in settings:
        values, observed = settings['watchdog'], actual['watchdog']
        if observed['enabled'] != values['enabled']:
            raise RuntimeError('Watchdog enabled read-back mismatch')
        if 'time_ms' in values and observed['time_ms'] != values['time_ms']:
            raise RuntimeError('Watchdog time read-back mismatch')
        if 'sensitivity' in values and int(observed['sensitivity']) != values['sensitivity']:
            raise RuntimeError('Watchdog sensitivity read-back mismatch')
    return actual


def mutate(project, application, request, rebuild):
    op = request['operation']
    result = {'ok': False, 'operation': op, 'application_guid': str(application.guid),
              'created': False, 'changed': False, 'saved': False}
    task = None
    try:
        objects = list(application.get_children(True))
        if op == 'create_task':
            settings = {key: request[key] for key in ('priority', 'interval_ms', 'watchdog') if key in request}
            validate_settings(settings, True)
            if not IDENTIFIER.match(request['name']):
                raise ValueError('Use an ASCII task identifier, 1-128 characters')
            configs = [o for o in objects if getattr(o, 'is_task_configuration', False)]
            if request.get('task_configuration_guid'):
                configs = [o for o in configs if str(o.guid).lower() == request['task_configuration_guid'].lower()]
            if len(configs) != 1:
                raise ValueError('Choose a unique existing task_configuration_guid')
            config = configs[0]
            if any(o.get_name().lower() == request['name'].lower() for o in config.get_children(True)):
                raise ValueError('Task name already exists; inspect/configure it instead')
            task = config.create_task(name=request['name'])
            result.update(created=True, changed=True, task_guid=str(task.guid))
            task.kind_of_task = se.KindOfTask.Cyclic
            result['after'] = configure(task, settings)
        elif op == 'configure_task':
            settings = request['settings']
            validate_settings(settings)
            task = select(objects, request['task_guid'])
            if not getattr(task, 'is_task', False) or task.kind_of_task != se.KindOfTask.Cyclic:
                raise ValueError('Select a cyclic task in the chosen application')
            result['before'] = task_record(task)
            result['task_guid'] = str(task.guid)
            result['changed'] = True
            result['after'] = configure(task, settings)
        elif op == 'bind_program':
            task = select(objects, request['task_guid'])
            program = select(objects, request['program_guid'])
            if not getattr(task, 'is_task', False) or not hasattr(program, 'textual_declaration'):
                raise ValueError('Select a task and textual program in the chosen application')
            header = re.match(r'^PROGRAM\s+([^\s:;]+)', declaration_start(program.textual_declaration.text), re.I)
            name = program.get_name()
            if not header or header.group(1).lower() != name.lower():
                raise ValueError('Only PROGRAM POUs can be bound; FB/functions need a program caller')
            before = task_record(task)
            if any(binding['program_name'].lower() == name.lower() for binding in before['bindings']):
                raise ValueError('Program already bound to this task')
            other_tasks = [o for o in objects if getattr(o, 'is_task', False) and str(o.guid) != str(task.guid)]
            existing = [str(other.guid) for other in other_tasks if any(
                binding['program_name'].lower() == name.lower() for binding in task_record(other)['bindings'])]
            if existing and not request.get('allow_multi_task', False):
                raise ValueError('Program bound to another task; explicit allow_multi_task is required')
            index = request.get('index', len(before['bindings']))
            integer(index, 0, len(before['bindings']), 'index')
            comment = request.get('comment', '')
            if not isinstance(comment, basestring) or len(comment) > 2048:
                raise ValueError('Binding comment must be text up to 2048 characters')
            result.update(before=before, task_guid=str(task.guid), program_guid=str(program.guid),
                          existing_task_bindings=existing, changed=True)
            task.pous.insert(index, name, comment)
            # In the verified INVT profile add/insert ignore their comment value.
            # The documented replace method preserves it. Keep the same newly
            # inserted program/index and then verify the entire ordered list.
            task.pous.replace(index, name, comment)
            result['after'] = task_record(task)
            expected = [(b['program_name'], b['comment']) for b in before['bindings']]
            expected.insert(index, (name, comment))
            actual = [(b['program_name'], b['comment']) for b in result['after']['bindings']]
            if actual != expected:
                raise RuntimeError('Ordered program binding read-back mismatch')
        else:
            raise ValueError('Unsupported task mutation')
        project.save()
        result['saved'] = True
        rebuild(project, application, result)
    except Exception:
        result['ok'] = False
        result['exception'] = traceback.format_exc()
        if task is not None and result['changed']:
            try:
                result['after'] = task_record(task)
                project.save()
                result['saved'] = True
            except Exception:
                result['save_exception'] = traceback.format_exc()
    return result
