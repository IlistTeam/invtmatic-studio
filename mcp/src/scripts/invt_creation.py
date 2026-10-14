# -*- coding: utf-8 -*-
"""Validated object creation in an owned application (IronPython 2.7)."""
import re
import scriptengine as se

IDENTIFIER = re.compile(r'^[A-Za-z_][A-Za-z0-9_]{0,127}\Z')
TYPE_NAME = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)*\Z')
POU_TYPES = {'program': 'Program', 'function_block': 'FunctionBlock', 'function': 'Function'}
DUT_TYPES = {'structure': 'Structure', 'enumeration': 'Enumeration', 'alias': 'Alias', 'union': 'Union'}


def declaration_start(text):
    """Remove leading ST comments/attributes only; do not interpret their headers."""
    text = text.lstrip()
    while text:
        if text.startswith('//'):
            end = text.find('\n')
            text = '' if end < 0 else text[end + 1:].lstrip()
        elif text.startswith('(*'):
            depth, position = 1, 2
            while depth and position < len(text):
                if text[position:position + 2] == '(*':
                    depth += 1
                    position += 2
                elif text[position:position + 2] == '*)':
                    depth -= 1
                    position += 2
                else:
                    position += 1
            if depth:
                raise ValueError('Unclosed leading ST comment')
            text = text[position:].lstrip()
        elif text.startswith('{'):
            end = text.find('}')
            if end < 0:
                raise ValueError('Unclosed leading ST attribute')
            text = text[end + 1:].lstrip()
        else:
            return text
    return text


def preflight(request):
    op, name = request['operation'], request['name']
    if not IDENTIFIER.match(name):
        raise ValueError('Use an ASCII IEC identifier, 1-128 characters')
    declaration = request['declaration']
    if not isinstance(declaration, basestring) or not declaration.strip() or len(declaration) > 1000000:
        raise ValueError('Supply a nonempty complete declaration up to 1000000 characters')
    text = declaration_start(declaration)
    if op == 'create_gvl':
        if not re.match(r'^VAR_GLOBAL\b', text, re.I):
            raise ValueError('GVL declaration must start with VAR_GLOBAL after attributes/comments')
        return None
    if op == 'create_pou':
        kind = request['pou_type']
        if kind not in POU_TYPES:
            raise ValueError('Unsupported POU type')
        header = {'program': 'PROGRAM', 'function_block': 'FUNCTION_BLOCK', 'function': 'FUNCTION'}[kind]
        match = re.match(r'^' + header + r'\s+([A-Za-z_][A-Za-z0-9_]*)\b', text, re.I)
        if not match or match.group(1).lower() != name.lower():
            raise ValueError('POU declaration header must match name and pou_type')
        return_type = request.get('return_type')
        if kind == 'function':
            if not return_type or len(return_type) > 256 or not TYPE_NAME.match(return_type):
                raise ValueError('Function requires a simple or qualified return_type')
            result_type = re.match(r'^\s*:\s*([A-Za-z_][A-Za-z0-9_.]*)', text[match.end():])
            if not result_type or result_type.group(1).lower() != return_type.lower():
                raise ValueError('Function declaration must match return_type')
        elif return_type is not None:
            raise ValueError('return_type is allowed only for functions')
        implementation = request.get('implementation', '')
        if not isinstance(implementation, basestring) or len(implementation) > 1000000:
            raise ValueError('Implementation must be ST text up to 1000000 characters')
        return getattr(se.PouType, POU_TYPES[kind])
    if op != 'create_dut':
        raise ValueError('Unsupported creation operation')
    kind = request['dut_type']
    if kind not in DUT_TYPES:
        raise ValueError('Unsupported DUT type')
    match = re.match(r'^TYPE\s+([A-Za-z_][A-Za-z0-9_]*)\s*:\s*', text, re.I)
    if not match or match.group(1).lower() != name.lower():
        raise ValueError('DUT declaration header must match name')
    body = declaration_start(text[match.end():])
    base_type = request.get('base_type')
    if kind == 'alias':
        if not base_type or len(base_type) > 256 or not TYPE_NAME.match(base_type):
            raise ValueError('Alias requires a simple or qualified base_type')
        alias = re.match(r'^([A-Za-z_][A-Za-z0-9_.]*)\s*;', body)
        if not alias or alias.group(1).lower() != base_type.lower():
            raise ValueError('Alias declaration must match base_type')
    else:
        if base_type is not None:
            raise ValueError('base_type is exposed only for aliases')
        expected = {'structure': r'^STRUCT\b', 'union': r'^UNION\b', 'enumeration': r'^\('}[kind]
        if not re.match(expected, body, re.I):
            raise ValueError('DUT declaration body must match dut_type')
    return getattr(se.DutType, DUT_TYPES[kind])


def create(application, request, enum_type):
    name, op = request['name'], request['operation']
    # Case insensitive across the application namespace, not only direct siblings.
    if application.get_name().lower() == name.lower() or any(
            child.get_name().lower() == name.lower() for child in application.get_children(True)):
        raise ValueError('Name already exists in application; inspect/patch it instead')
    method = getattr(application, op, None)
    if method is None:
        raise NotImplementedError('Installed application API does not expose ' + op)
    if op == 'create_pou':
        # The installed API documents overload ambiguity: use explicit keywords.
        return method(name=name, type=enum_type, language=None,
                      return_type=request.get('return_type'), base_type=None, interfaces=None)
    if op == 'create_gvl':
        return method(name=name)
    return method(name=name, type=enum_type, baseType=request.get('base_type'))
