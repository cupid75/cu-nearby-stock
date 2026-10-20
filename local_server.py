"""Windows local launcher: detached server, hidden key input, no key file."""
import argparse
import ctypes
from ctypes import wintypes
import getpass
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parent
RUN = ROOT / '.local-run'
ORIGIN = 'http://127.0.0.1:8000'


def read_api(path):
    # Local requests must not go through system proxy settings.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(ORIGIN + path, timeout=2) as response:
        return json.load(response)


def check():
    try:
        data = read_api('/health')
        if data.get('service') != 'cu-nearby-stock':
            return None
        return {'running': True, 'kakao_key_configured': bool(read_api('/api/config').get('kakao_js_key'))}
    except (OSError, ValueError, urllib.error.URLError):
        return None


def creation_time(pid):
    """Windows process birth time prevents stopping a reused PID."""
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.GetProcessTimes.argtypes = (wintypes.HANDLE,) + (ctypes.POINTER(wintypes.FILETIME),) * 4
    kernel.CloseHandle.argtypes = (wintypes.HANDLE,)
    handle = kernel.OpenProcess(0x1000, False, pid)
    if not handle:
        return None
    try:
        created, ended, system, user = (wintypes.FILETIME() for _ in range(4))
        if not kernel.GetProcessTimes(handle, ctypes.byref(created), ctypes.byref(ended), ctypes.byref(system), ctypes.byref(user)):
            return None
        return (created.dwHighDateTime << 32) | created.dwLowDateTime
    finally:
        kernel.CloseHandle(handle)


def stop():
    metadata = RUN / 'server.json'
    if not metadata.exists():
        print('No server started by this launcher. Nothing was stopped.')
        return 1
    data = json.loads(metadata.read_text(encoding='utf-8'))
    if creation_time(data['pid']) != data['created']:
        print('Saved server is no longer running. Nothing was stopped.')
        return 0
    result = subprocess.run(['taskkill', '/PID', str(data['pid']), '/T', '/F'], capture_output=True)
    if result.returncode:
        print('Could not stop the saved server.')
        return 1
    metadata.unlink(missing_ok=True)
    print('Local CU server stopped.')
    return 0


def start(without_key=False):
    existing = check()
    if existing:
        print('Local CU server is already running:', ORIGIN)
        print('Kakao key configured:', existing['kakao_key_configured'])
        return 0
    with socket.socket() as probe:
        if probe.connect_ex(('127.0.0.1', 8000)) == 0:
            print('Port 8000 is used by another service. Nothing was stopped.')
            return 1
    env = os.environ.copy()
    if not without_key and not env.get('KAKAO_JS_KEY', '').strip():
        key = getpass.getpass('Paste Kakao JavaScript key, then Enter (input is hidden): ').strip()
        if not key:
            print('No key entered. Server was not started.')
            return 1
        env['KAKAO_JS_KEY'] = key
    RUN.mkdir(exist_ok=True)
    python = ROOT / '.venv' / 'Scripts' / 'python.exe'
    if not python.exists():
        print('Python environment is missing. See README.md.')
        return 1
    with (RUN / 'stdout.log').open('w', encoding='utf-8') as out, (RUN / 'stderr.log').open('w', encoding='utf-8') as err:
        child = subprocess.Popen([str(python), '-m', 'uvicorn', 'app:app', '--host', '127.0.0.1',
                                  '--port', '8000', '--workers', '1', '--no-access-log'],
                                 cwd=ROOT, env=env, stdin=subprocess.DEVNULL, stdout=out, stderr=err,
                                 creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
                                 close_fds=True)
    created = creation_time(child.pid)
    if created is None:
        print('Server did not start. See .local-run/stderr.log.')
        return 1
    (RUN / 'server.json').write_text(json.dumps({'pid': child.pid, 'created': created}), encoding='utf-8')
    for _ in range(40):
        if child.poll() is not None:
            print('Server exited. See .local-run/stderr.log.')
            return 1
        status = check()
        if status:
            print('Local CU server is ready:', ORIGIN)
            print('Kakao key configured:', status['kakao_key_configured'])
            print('The server keeps running after this terminal closes.')
            print('Stop: .\\.venv\\Scripts\\python.exe local_server.py --stop')
            return 0
        time.sleep(.25)
    print('Startup not confirmed. See .local-run/stderr.log.')
    return 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group()
    action.add_argument('--stop', action='store_true')
    action.add_argument('--check', action='store_true')
    parser.add_argument('--without-key', action='store_true', help='Only for local UI verification without maps')
    args = parser.parse_args()
    if args.check:
        print(json.dumps(check() or {'running': False}))
        return 0
    if os.name != 'nt':
        print('This launcher is for Windows. Use the normal uvicorn command elsewhere.')
        return 1
    if args.stop:
        return stop()
    return start(args.without_key)


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print('\nLauncher cancelled. A server already started stays running; use --stop to stop it.')
