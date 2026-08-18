"""
GR AMS — Email Diagnostics
Tests multiple ports and providers to find what works on your network.
Usage: python test_email.py
"""

import smtplib
import os
import socket
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


def load_env(path='.env'):
    if not os.path.exists(path):
        print(f"  WARNING: .env file not found")
        return
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            key, _, value = line.partition('=')
            key   = key.strip()
            value = value.strip().strip('"').strip("'")
            if key:
                os.environ[key] = value


def check_port(host, port, timeout=5):
    """Test if a port is reachable."""
    try:
        sock = socket.create_connection((host, port), timeout=timeout)
        sock.close()
        return True
    except:
        return False


def try_send(server, port, use_ssl, username, password, recipient, app_url):
    """Attempt to send using given settings."""
    msg = MIMEMultipart('alternative')
    msg['Subject'] = 'GR AMS — Email Test'
    msg['From']    = username
    msg['To']      = recipient
    html = f"""
    <div style="font-family:Arial,sans-serif;padding:24px;max-width:500px">
      <div style="background:#1a3a5c;padding:20px;border-radius:8px;text-align:center;margin-bottom:20px">
        <h1 style="color:#fff;margin:0">GR AMS</h1>
        <p style="color:rgba(255,255,255,.7);margin:4px 0 0;font-size:13px">Asset Management System</p>
      </div>
      <p>This is a <strong>test email</strong> confirming your email settings are working.</p>
      <p>System URL: <a href="{app_url}">{app_url}</a></p>
    </div>"""
    msg.attach(MIMEText(html, 'html'))

    try:
        if use_ssl:
            s = smtplib.SMTP_SSL(server, port, timeout=10)
        else:
            s = smtplib.SMTP(server, port, timeout=10)
            s.ehlo()
            s.starttls()
            s.ehlo()
        s.login(username, password)
        s.sendmail(username, recipient, msg.as_string())
        s.quit()
        return True, None
    except smtplib.SMTPAuthenticationError:
        return False, 'AUTH_FAIL'
    except Exception as e:
        return False, str(e)


def test_email():
    load_env()

    print("\n  GR AMS — Email Diagnostics")
    print("  " + "─" * 42)

    username = os.environ.get('MAIL_USERNAME', '')
    password = os.environ.get('MAIL_PASSWORD', '')
    app_url  = os.environ.get('APP_URL', 'http://127.0.0.1:5000')

    if not username or 'yourname' in username:
        print("  FAIL: MAIL_USERNAME not set in .env")
        input("\n  Press Enter to close..."); return
    if not password or 'your-outlook' in password:
        print("  FAIL: MAIL_PASSWORD not set in .env")
        input("\n  Press Enter to close..."); return

    recipient = input(f"\n  Send test to (Enter = {username}): ").strip() or username
    print()

    # ── Step 1: Port scan ──────────────────────────────────────
    print("  Scanning ports on your network...")
    print()

    configs = [
        ('smtp.office365.com', 587, False, 'Outlook — port 587 (STARTTLS)'),
        ('smtp.office365.com', 465, True,  'Outlook — port 465 (SSL)'),
        ('smtp.office365.com', 25,  False, 'Outlook — port 25  (legacy)'),
        ('smtp.gmail.com',     587, False, 'Gmail   — port 587 (STARTTLS)'),
        ('smtp.gmail.com',     465, True,  'Gmail   — port 465 (SSL)'),
    ]

    reachable = []
    for server, port, ssl, label in configs:
        ok = check_port(server, port)
        status = '✓ OPEN  ' if ok else '✗ BLOCKED'
        print(f"  {status} — {label}")
        if ok:
            reachable.append((server, port, ssl, label))

    print()

    if not reachable:
        print("  ALL PORTS ARE BLOCKED on this network.")
        print()
        print("  Your options:")
        print("  1. Ask your IT admin to open outgoing port 587 or 465")
        print("  2. Use a mobile hotspot temporarily to send emails")
        print("  3. Use a local relay server on your office network")
        input("\n  Press Enter to close..."); return

    # ── Step 2: Try sending on open ports ─────────────────────
    print("  Trying to send on open ports...")
    print()

    working_server = None
    working_port   = None
    working_ssl    = None

    for server, port, ssl, label in reachable:
        print(f"  Trying {label} ...")
        ok, err = try_send(server, port, ssl, username, password, recipient, app_url)
        if ok:
            print(f"  ✓ SUCCESS — email sent to {recipient}!")
            working_server = server
            working_port   = port
            working_ssl    = ssl
            break
        elif err == 'AUTH_FAIL':
            print(f"  ✗ Port open but login failed — wrong password or App Password needed")
            print()
            print("  FIX: Your account likely has MFA enabled. Generate an App Password:")
            print("  1. Go to https://mysignins.microsoft.com/security-info")
            print("  2. Add sign-in method → App password → name it 'GR AMS'")
            print("  3. Copy the password into your .env as MAIL_PASSWORD")
            break
        else:
            print(f"  ✗ Failed — {err}")

    print()

    if working_server:
        print("  ─" * 21)
        print("  UPDATE YOUR .env WITH THESE WORKING SETTINGS:")
        print()
        print(f"  MAIL_SERVER={working_server}")
        print(f"  MAIL_PORT={working_port}")
        print(f"  MAIL_USE_SSL={'true' if working_ssl else 'false'}")
        print()
        print("  Also update email_utils.py — see instructions below.")

    input("\n  Press Enter to close...")


if __name__ == '__main__':
    test_email()
