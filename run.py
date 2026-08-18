from app import create_app
import os
import socket
import sys

app = create_app()
APP_BUILD = '2026-07-09-cancel-repair'


def _port_free(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(('0.0.0.0', port))
            return True
        except OSError:
            return False


def _pick_port(start=5000, end=5019):
    for port in range(start, end + 1):
        if _port_free(port):
            return port
    return None


if __name__ == '__main__':
    preferred = 5000
    port = _pick_port(preferred)

    if port is None:
        print('\n  ERROR: No free port found (5000-5019). End other Python servers and try again.\n')
        sys.exit(1)

    print('\n  GR Asset Management System')
    print('  -----------------------------')
    print(f'  Build:      {APP_BUILD}')
    if port != preferred:
        print(f'\n  Port {preferred} is in use - using http://127.0.0.1:{port} instead.')
        print(f'  Open:  http://127.0.0.1:{port}\n')
    print(f'  Running at: http://127.0.0.1:{port}')
    print(f'  Network:    http://0.0.0.0:{port}')
    if os.environ.get('FLASK_ENV', '').lower() != 'production':
        print('  Accounts:   admin/admin123  user/user123  finance/finance123  john/user123')
    print('  Press Ctrl+C to stop\n')
    app.run(host='0.0.0.0', port=port, debug=os.environ.get('FLASK_ENV', '').lower() != 'production', use_reloader=False)
