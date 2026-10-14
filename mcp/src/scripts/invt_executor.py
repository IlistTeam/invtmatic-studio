# -*- coding: utf-8 -*-
"""Executor-frame workaround adapted from MIT Codesys-MCP ensure_online_connection.
Only the executor workaround is used, never its device discovery or login helpers.
"""
def with_executor(fn, *args):
    import scriptengine as se
    import clr
    from System.Reflection import BindingFlags
    import __builtin__ as b
    flags = BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance
    field = clr.GetClrType(type(se.online)).GetField('_executor', flags)
    if field is None:
        raise RuntimeError('Installed online executor unavailable; no direct-call fallback')
    executor = field.GetValue(se.online)
    b._invt_online_fn, b._invt_online_args = fn, args
    b._invt_online_result, b._invt_online_error = None, None
    try:
        executor.ExecuteSource("import __builtin__ as b\ntry:\n    b._invt_online_result = b._invt_online_fn(*b._invt_online_args)\nexcept BaseException as e:\n    b._invt_online_error = e\n")
        if b._invt_online_error is not None:
            raise b._invt_online_error
        return b._invt_online_result
    finally:
        for name in ('_invt_online_fn', '_invt_online_args', '_invt_online_result', '_invt_online_error'):
            if hasattr(b, name):
                delattr(b, name)
