"""Local stdio MCP adapter (2024-11-05); jobs use the same tested CLI runner."""
from __future__ import annotations
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import sys
import threading
import uuid

from invt_cli import DEFAULT_EXE, DEFAULT_PROFILE, OPERATIONS, run_job, validate_request

PROTOCOL = '2024-11-05'
JOB_SCHEMA = {
    'type': 'object', 'additionalProperties': False,
    'properties': {
        'operation': {'type': 'string', 'enum': list(OPERATIONS)},
        'project': {'type': 'string', 'description': 'Native .project inside configured workspace'},
        'object_guid': {'type': 'string'}, 'application_guid': {'type': 'string'},
        'declaration': {'type': 'string', 'maxLength': 1000000},
        'implementation': {'type': 'string', 'maxLength': 1000000},
        'expected_sha256': {'type': 'string'},
    }, 'required': ['operation', 'project']
}
ID_SCHEMA = {'type': 'object', 'additionalProperties': False,
             'properties': {'ticket': {'type': 'string'}}, 'required': ['ticket']}
TOOLS = [
    {'name': 'invt_submit', 'description': 'Start an offline Studio job on a new project copy. '
     'Returns a ticket immediately; poll invt_status. Does not connect to PLCs or overwrite the source.',
     'inputSchema': JOB_SCHEMA},
    {'name': 'invt_status', 'description': 'Get job state, diagnostics summary and local artifact paths. '
     'Read result_file for complete ST, tree and diagnostics.', 'inputSchema': ID_SCHEMA},
    {'name': 'invt_cancel', 'description': 'Cancel this server\'s job and stop only its dedicated Studio process.',
     'inputSchema': ID_SCHEMA},
]


class Server:
    def __init__(self, workspace, exe=DEFAULT_EXE, profile=DEFAULT_PROFILE, timeout=180):
        self.workspace = Path(workspace).resolve(strict=True)
        self.exe, self.profile, self.timeout = exe, profile, timeout
        self.pool = ThreadPoolExecutor(max_workers=1)
        self.jobs = {}
        self.initialized = False
        self.ready = False

    def tool(self, name, arguments):
        if not isinstance(arguments, dict):
            raise ValueError('arguments must be an object')
        if name == 'invt_submit':
            validate_request(self.workspace, arguments)
            if any(not job['future'].done() for job in self.jobs.values()):
                raise ValueError('Another job is running; poll or cancel it first')
            ticket = uuid.uuid4().hex
            cancel = threading.Event()
            future = self.pool.submit(run_job, self.workspace, arguments, self.exe,
                                      self.profile, 'ui', self.timeout, cancel)
            self.jobs[ticket] = {'future': future, 'cancel': cancel}
            return {'ticket': ticket, 'state': 'submitted', 'poll_after_seconds': 10}
        if name not in ('invt_status', 'invt_cancel'):
            raise ValueError('Unknown tool: ' + name)
        if set(arguments) != {'ticket'} or arguments['ticket'] not in self.jobs:
            raise ValueError('Unknown ticket')
        job = self.jobs[arguments['ticket']]
        if name == 'invt_cancel':
            job['cancel'].set()
        if not job['future'].done():
            return {'state': 'cancelling' if job['cancel'].is_set() else 'running', 'poll_after_seconds': 10}
        result = job['future'].result()
        summary = {k: v for k, v in result.items() if k != 'result'}
        report = result.get('result') or {}
        summary['build_ok'] = report.get('build_ok')
        summary['exception'] = report.get('exception')
        messages = report.get('diagnostics', report.get('build_diagnostics', []))
        errors = [m for m in messages if m['severity'] in ('Error', 'FatalError')]
        summary.update(error_count=len(errors), first_errors=errors[:10])
        return summary

    def handle(self, message):
        if not isinstance(message, dict) or message.get('jsonrpc') != '2.0':
            return {'jsonrpc': '2.0', 'id': None, 'error': {'code': -32600, 'message': 'Invalid Request'}}
        method, params = message.get('method'), message.get('params', {})
        if 'id' not in message:
            if method == 'notifications/initialized' and self.initialized:
                self.ready = True
            return None
        response = {'jsonrpc': '2.0', 'id': message['id']}
        if method == 'initialize':
            self.initialized = True
            response['result'] = {'protocolVersion': PROTOCOL, 'capabilities': {'tools': {}},
                                  'serverInfo': {'name': 'invtmatic-offline', 'version': '0.1.0'}}
        elif method == 'ping':
            response['result'] = {}
        elif not self.ready:
            response['error'] = {'code': -32600, 'message': 'Initialize the session first'}
        elif method == 'tools/list':
            response['result'] = {'tools': TOOLS}
        elif method == 'tools/call':
            try:
                data = self.tool(params['name'], params.get('arguments', {}))
                response['result'] = {'content': [{'type': 'text', 'text': json.dumps(data, ensure_ascii=True)}],
                                      'isError': data.get('ok') is False}
            except Exception as error:
                response['result'] = {'content': [{'type': 'text', 'text': str(error)}], 'isError': True}
        else:
            response['error'] = {'code': -32601, 'message': 'Method not found'}
        return response

    def close(self):
        for job in self.jobs.values():
            job['cancel'].set()
        self.pool.shutdown(wait=True, cancel_futures=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace', required=True)
    parser.add_argument('--exe', default=DEFAULT_EXE)
    parser.add_argument('--profile', default=DEFAULT_PROFILE)
    parser.add_argument('--timeout', type=int, default=180)
    args = parser.parse_args()
    server = Server(args.workspace, args.exe, args.profile, args.timeout)
    try:
        for line in sys.stdin.buffer:
            try:
                message = json.loads(line.decode('utf-8'))
                response = server.handle(message)
            except (ValueError, UnicodeError):
                response = {'jsonrpc': '2.0', 'id': None, 'error': {'code': -32700, 'message': 'Parse error'}}
            if response is not None:
                sys.stdout.write(json.dumps(response, ensure_ascii=True) + '\n')
                sys.stdout.flush()
    finally:
        server.close()


if __name__ == '__main__':
    main()
