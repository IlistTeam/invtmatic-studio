# -*- coding: utf-8 -*-
"""IronPython 2.7 inspection helpers for a dedicated owned Studio process."""
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
