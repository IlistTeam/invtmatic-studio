"""Host Python 3 adapter. Copies source projects; no online PLC operations."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import uuid

DEFAULT_EXE = r'C:\INVT\Invtmatic Studio V3.0.1.4\CODESYS\Common\Invtmatic Studio.exe'
DEFAULT_PROFILE = 'Invtmatic Studio V3.0'
OPERATIONS = ('inspect', 'build', 'patch_st', 'export_pou')


def dump(path, value):
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=True, indent=2), encoding='utf-8')
    temp.replace(path)


def scoped_file(workspace, value):
    path = Path(value)
    if not path.is_absolute():
        path = workspace / path
    path = path.resolve(strict=True)
    if not path.is_relative_to(workspace) or not path.is_file():
        raise ValueError('Input must be a file within workspace: ' + str(path))
    return path


def quoted(value):
    value = str(value)
    if any(c in value for c in ('"', '\r', '\n', '\x00')) or value.endswith('\\'):
        raise ValueError('Unsupported character in Studio command argument')
    return '"' + value + '"'


def command_line(exe, profile, script, mode):
    # Studio parses the original Windows command line. list2cmdline would quote
    # the whole --profile=... argument and Studio would fail to find the profile.
    command = quoted(exe) + ' --profile=' + quoted(profile) + ' --runscript=' + quoted(script)
    if mode == 'headless':
        command += ' --noUI'
    return command


def validate_request(workspace, request):
    if not isinstance(request, dict):
        raise ValueError('Request must be an object')
    allowed = {'operation', 'project', 'object_guid', 'application_guid', 'declaration', 'implementation', 'expected_sha256'}
    if set(request) - allowed:
        raise ValueError('Unknown request fields: ' + ', '.join(sorted(set(request)-allowed)))
    operation = request.get('operation')
    if operation not in OPERATIONS:
        raise ValueError('Unsupported offline operation')
    source = scoped_file(workspace, request['project'])
    if source.suffix.lower() != '.project':
        raise ValueError('A native .project file is required')
    for key in ('object_guid', 'application_guid'):
        if key in request:
            uuid.UUID(request[key])
    if operation in ('patch_st', 'export_pou') and not request.get('object_guid'):
        raise ValueError('Inspect the project first and supply object_guid')
    if operation == 'patch_st' and not any(k in request for k in ('declaration', 'implementation')):
        raise ValueError('patch_st needs declaration and/or implementation')
    for key in ('declaration', 'implementation'):
        if key in request and (not isinstance(request[key], str) or len(request[key]) > 1_000_000):
            raise ValueError('ST fields must be strings up to 1,000,000 characters')
    return source


def run_job(workspace, request, exe=DEFAULT_EXE, profile=DEFAULT_PROFILE, mode='ui', timeout=180, cancelled=None):
    workspace = Path(workspace).resolve(strict=True)
    if mode not in ('ui', 'headless') or not 1 <= timeout <= 600:
        raise ValueError('Invalid execution mode or timeout (1..600 seconds)')
    source = validate_request(workspace, request)
    executable = Path(exe).resolve(strict=True)
    payload = source.read_bytes()
    digest = hashlib.sha256(payload).hexdigest()
    if request.get('expected_sha256', digest).lower() != digest:
        raise ValueError('Source project changed: SHA-256 mismatch')
    runs = workspace / '.invt' / 'runs'
    if not runs.resolve().is_relative_to(workspace):
        raise ValueError('Runs directory resolves outside workspace')
    runs.mkdir(parents=True, exist_ok=True)
    # Serialise Studio operations even across independent CLI and MCP clients.
    lock = workspace / '.invt' / 'runner.lock'
    with lock.open('a+b') as lockfile:
        import msvcrt
        lockfile.seek(0)
        try:
            msvcrt.locking(lockfile.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError:
            raise RuntimeError('Another Studio job is running in this workspace')
        try:
            return _run_locked(workspace, request, executable, profile, mode, timeout,
                               cancelled, source, payload, digest, runs)
        finally:
            lockfile.seek(0)
            msvcrt.locking(lockfile.fileno(), msvcrt.LK_UNLCK, 1)


def _run_locked(workspace, request, executable, profile, mode, timeout, cancelled, source, payload, digest, runs):
    job_id = uuid.uuid4().hex
    job = runs / job_id
    job.mkdir()
    project = job / source.name
    project.write_bytes(payload)
    resolved = dict(request, job_id=job_id, project=str(project))
    dump(job / 'request.json', resolved)
    entry = Path(__file__).with_name('studio_job.py').resolve()
    # repr via ASCII-safe JSON protects Cyrillic paths in IronPython source.
    bootstrap = 'import sys, json\nsys.path.insert(0, json.loads({0}))\nimport studio_job\nstudio_job.execute(json.loads({1}))\n'.format(
        repr(json.dumps(str(entry.parent), ensure_ascii=True)),
        repr(json.dumps(str(job / 'request.json'), ensure_ascii=True)))
    script = job / 'launch.py'
    script.write_text(bootstrap, encoding='ascii')
    command = command_line(executable, profile, script, mode)
    metadata = {'schema': 1, 'job_id': job_id, 'source_project': str(source), 'source_sha256': digest,
                'project_copy': str(project), 'mode': mode, 'command': command, 'run_directory': str(job)}
    start = time.monotonic()
    with (job/'stdout.log').open('wb') as out, (job/'stderr.log').open('wb') as err:
        process = subprocess.Popen(command, executable=str(executable), cwd=str(executable.parent),
                                   shell=False, stdin=subprocess.DEVNULL, stdout=out, stderr=err,
                                   creationflags=subprocess.CREATE_NO_WINDOW)
        metadata.update(pid=process.pid, state='running')
        dump(job/'host.json', metadata)
        reason = None
        try:
            while process.poll() is None:
                if cancelled is not None and cancelled.is_set():
                    reason = 'cancelled'
                    break
                if time.monotonic()-start > timeout:
                    reason = 'timeout'
                    break
                time.sleep(0.2)
        finally:
            if process.poll() is None:
                # Only the process handle created above, editing only our copy.
                process.kill()
                process.wait(timeout=10)
        metadata.update(state=reason or 'exited', exit_code=process.returncode,
                        elapsed_seconds=round(time.monotonic()-start, 2))
    result_path = job/'result.json'
    result = None
    if result_path.exists():
        try:
            result = json.loads(result_path.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            metadata['result_error'] = 'Malformed result.json'
    valid = isinstance(result, dict) and result.get('job_id') == job_id and result.get('finished') is True
    metadata['ok'] = bool(valid and result.get('ok') is True and process.returncode == 0 and reason is None)
    metadata['source_unchanged'] = hashlib.sha256(source.read_bytes()).hexdigest() == digest
    dump(job/'host.json', metadata)
    return dict(metadata, result=result, result_file=str(result_path))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace', required=True)
    parser.add_argument('--request', required=True, help='JSON job (see SKILL.md)')
    parser.add_argument('--exe', default=DEFAULT_EXE)
    parser.add_argument('--profile', default=DEFAULT_PROFILE)
    parser.add_argument('--mode', choices=('ui','headless'), default='ui')
    parser.add_argument('--timeout', type=int, default=180)
    args = parser.parse_args()
    try:
        request = json.loads(Path(args.request).read_text(encoding='utf-8-sig'))
        result = run_job(args.workspace, request, args.exe, args.profile, args.mode, args.timeout)
    except Exception as error:
        result = {'ok': False, 'host_error': str(error)}
    print(json.dumps(result, ensure_ascii=True, indent=2))
    return 0 if result.get('ok') else 1


if __name__ == '__main__':
    raise SystemExit(main())
