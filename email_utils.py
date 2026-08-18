"""
Email Notification Utility — GR Asset Management System
Supports STARTTLS (port 587) and SSL (port 465)
"""

import smtplib
import traceback
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from flask import current_app


def send_welcome_email(to_email, to_name, username, role):
    """
    Send a notification email when a new user account is created.
    Returns (True, None) on success or (False, error_message) on failure.
    """
    cfg = current_app.config

    sender      = cfg.get('MAIL_USERNAME', '')
    mail_pass   = cfg.get('MAIL_PASSWORD', '')
    smtp_server = cfg.get('MAIL_SERVER',   'smtp.office365.com')
    smtp_port   = int(cfg.get('MAIL_PORT', 587))
    use_ssl     = str(cfg.get('MAIL_USE_SSL', 'false')).lower() == 'true'
    app_url     = cfg.get('APP_URL',  'http://127.0.0.1:5000')
    org_name    = cfg.get('ORG_NAME', 'GR')

    if not sender or not mail_pass:
        return False, "Email not configured. Set MAIL_USERNAME and MAIL_PASSWORD in .env"

    if not to_email:
        return False, "User has no email address."

    role_label = {
        'admin':   'Administrator',
        'finance': 'Finance Officer',
        'user':    'Staff User'
    }.get(role, role)

    # ── Build message ──────────────────────────────────────────
    msg = MIMEMultipart('alternative')
    msg['Subject'] = f"Welcome to {org_name} Asset Management System"
    msg['From']    = f"{org_name} AMS <{sender}>"
    msg['To']      = to_email

    text_body = f"""
Dear {to_name},

An account has been created for you on the {org_name} Asset Management System.

Login details:
  System URL : {app_url}
  Username   : {username}
  Role       : {role_label}

Please sign in using the credentials provided separately by your administrator, then change your password immediately.

Regards,
{org_name} Administration
    """.strip()

    html_body = f"""
<!DOCTYPE html>
<html>
<head><meta charset="UTF-8">
<style>
body{{font-family:'Segoe UI',Arial,sans-serif;background:#f0f2f5;margin:0;padding:30px}}
.wrap{{max-width:560px;margin:0 auto;background:#fff;border-radius:12px;overflow:hidden;box-shadow:0 2px 12px rgba(0,0,0,.1)}}
.hdr{{background:#1a3a5c;padding:28px 32px;text-align:center}}
.hdr h1{{color:#fff;font-size:22px;margin:0}}.hdr p{{color:rgba(255,255,255,.65);font-size:13px;margin:6px 0 0}}
.body{{padding:32px}}.body p{{color:#374151;font-size:14px;line-height:1.6;margin:0 0 16px}}
.creds{{background:#f7f8fa;border:1px solid #d8dce3;border-radius:8px;padding:20px 24px;margin:20px 0}}
.creds table{{width:100%;border-collapse:collapse}}
.creds td{{padding:8px 0;font-size:14px;color:#1a2230;border-bottom:1px solid #e5e7eb}}
.creds tr:last-child td{{border-bottom:none}}
.creds td:first-child{{font-weight:600;color:#6b7280;font-size:11px;text-transform:uppercase;letter-spacing:.3px;width:110px}}
.creds .val{{font-family:'Courier New',monospace;font-size:15px;color:#1a3a5c;font-weight:700}}
.btn{{display:block;text-align:center;background:#e8840a;color:#fff;text-decoration:none;padding:13px 24px;border-radius:8px;font-size:14px;font-weight:600;margin:24px 0}}
.note{{background:#fef9c3;border:1px solid #fde047;border-radius:6px;padding:12px 16px;font-size:13px;color:#854d0e}}
.footer{{background:#f7f8fa;border-top:1px solid #e5e7eb;padding:16px 32px;text-align:center;font-size:12px;color:#9ca3af}}
</style></head>
<body>
<div class="wrap">
  <div class="hdr"><h1>{org_name}</h1><p>Asset Management System</p></div>
  <div class="body">
    <p>Dear <strong>{to_name}</strong>,</p>
    <p>Your account has been successfully created on the <strong>{org_name} Asset Management System</strong>. Use the details below to sign in.</p>
    <div class="creds">
      <table>
        <tr><td>System URL</td><td class="val"><a href="{app_url}" style="color:#1a3a5c">{app_url}</a></td></tr>
        <tr><td>Username</td><td class="val">{username}</td></tr>
        <tr><td>Password</td><td class="val">Provided separately</td></tr>
        <tr><td>Role</td><td>{role_label}</td></tr>
      </table>
    </div>
    <a href="{app_url}" class="btn">Sign In to {org_name} AMS →</a>
    <div class="note">⚠ Please log in and <strong>change your password</strong> immediately. Do not share your credentials.</div>
    <p style="margin-top:20px">If you have trouble accessing the system, contact your administrator.</p>
    <p>Regards,<br><strong>{org_name} Administration</strong></p>
  </div>
  <div class="footer">{org_name} Asset Management System &middot; This is an automated message, please do not reply.</div>
</div>
</body></html>
    """.strip()

    msg.attach(MIMEText(text_body, 'plain'))
    msg.attach(MIMEText(html_body, 'html'))

    # ── Send ───────────────────────────────────────────────────
    try:
        if use_ssl:
            # Port 465 — direct SSL
            server = smtplib.SMTP_SSL(smtp_server, smtp_port, timeout=10)
        else:
            # Port 587 — STARTTLS
            server = smtplib.SMTP(smtp_server, smtp_port, timeout=10)
            server.ehlo()
            server.starttls()
            server.ehlo()

        server.login(sender, mail_pass)
        server.sendmail(sender, to_email, msg.as_string())
        server.quit()

        print(f"  [Email] Welcome email sent to {to_email}")
        return True, None

    except smtplib.SMTPAuthenticationError:
        err = ("Login failed. Check MAIL_PASSWORD in .env. "
               "If MFA is enabled, use an App Password from "
               "https://mysignins.microsoft.com/security-info")
        print(f"  [Email] AUTH ERROR: {err}")
        return False, err

    except smtplib.SMTPException as e:
        err = f"SMTP error: {str(e)}"
        print(f"  [Email] SMTP ERROR: {err}")
        return False, err

    except Exception as e:
        err = f"Unexpected error: {str(e)}"
        print(f"  [Email] ERROR: {traceback.format_exc()}")
        return False, err


def send_admin_notification(subject, body):
    """Notify system admin mailbox about a new user request."""
    cfg = current_app.config
    sender = cfg.get('MAIL_USERNAME', '')
    if not sender:
        return False, 'Email not configured'
    admin_email = cfg.get('ADMIN_EMAIL', sender)
    msg = MIMEMultipart('alternative')
    msg['Subject'] = f"[GR AMS] {subject}"
    msg['From'] = sender
    msg['To'] = admin_email
    html = f"""<html><body style="font-family:Arial,sans-serif">
    <h2 style="color:#0d3d23">{subject}</h2>
    <p>{body}</p>
    <p style="color:#666;font-size:12px">GR Asset Management System</p>
    </body></html>"""
    msg.attach(MIMEText(body, 'plain'))
    msg.attach(MIMEText(html, 'html'))
    try:
        smtp_server = cfg.get('MAIL_SERVER', 'smtp.office365.com')
        smtp_port = int(cfg.get('MAIL_PORT', 587))
        use_ssl = str(cfg.get('MAIL_USE_SSL', 'false')).lower() == 'true'
        if use_ssl:
            server = smtplib.SMTP_SSL(smtp_server, smtp_port)
        else:
            server = smtplib.SMTP(smtp_server, smtp_port)
            server.starttls()
        server.login(sender, cfg.get('MAIL_PASSWORD', ''))
        server.sendmail(sender, [admin_email], msg.as_string())
        server.quit()
        return True, None
    except Exception as e:
        print(f"  [Email] Admin notify failed: {e}")
        return False, str(e)


def send_password_reset_email(to_email, to_name, username, password):
    cfg = current_app.config

    sender      = cfg.get('MAIL_USERNAME', '')
    mail_pass   = cfg.get('MAIL_PASSWORD', '')
    smtp_server = cfg.get('MAIL_SERVER',   'smtp.office365.com')
    smtp_port   = int(cfg.get('MAIL_PORT', 587))
    use_ssl     = str(cfg.get('MAIL_USE_SSL', 'false')).lower() == 'true'
    app_url     = cfg.get('APP_URL',  'http://127.0.0.1:5000')
    org_name    = cfg.get('ORG_NAME', 'GR')

    if not sender or not mail_pass:
        return False, "Email not configured. Set MAIL_USERNAME and MAIL_PASSWORD in .env"

    if not to_email:
        return False, "No recipient email address provided."

    msg = MIMEMultipart('alternative')
    msg['Subject'] = f"{org_name} Password Reset"
    msg['From']    = f"{org_name} AMS <{sender}>"
    msg['To']      = to_email

    text_body = f"""
Dear {to_name},

A password reset request was received for your account on the {org_name} Asset Management System.

Your temporary password is:
  {password}

Log in using your username and this temporary password, then change your password immediately.

System URL: {app_url}
Username  : {username}

If you did not request this reset, please contact your administrator immediately.

Regards,
{org_name} Administration
    """.strip()

    html_body = f"""
<!DOCTYPE html>
<html>
<head><meta charset="UTF-8">
<style>
body{{font-family:'Segoe UI',Arial,sans-serif;background:#f0f2f5;margin:0;padding:30px}}
.wrap{{max-width:560px;margin:0 auto;background:#fff;border-radius:12px;overflow:hidden;box-shadow:0 2px 12px rgba(0,0,0,.1)}}
.hdr{{background:#0d3d23;padding:28px 32px;text-align:center}}
.hdr h1{{color:#fff;font-size:22px;margin:0}}.hdr p{{color:rgba(255,255,255,.65);font-size:13px;margin:6px 0 0}}
.body{{padding:32px}}.body p{{color:#374151;font-size:14px;line-height:1.6;margin:0 0 16px}}
.creds{{background:#f7f8fa;border:1px solid #d8dce3;border-radius:8px;padding:20px 24px;margin:20px 0}}
.creds table{{width:100%;border-collapse:collapse}}
.creds td{{padding:8px 0;font-size:14px;color:#1a2230;border-bottom:1px solid #e5e7eb}}
.creds tr:last-child td{{border-bottom:none}}
.creds td:first-child{{font-weight:600;color:#6b7280;font-size:11px;text-transform:uppercase;letter-spacing:.3px;width:110px}}
.creds .val{{font-family:'Courier New',monospace;font-size:15px;color:#0d3d23;font-weight:700}}
.btn{{display:block;text-align:center;background:#0d3d23;color:#fff;text-decoration:none;padding:13px 24px;border-radius:8px;font-size:14px;font-weight:600;margin:24px 0}}
.note{{background:#d1fae5;border:1px solid #10b981;border-radius:6px;padding:12px 16px;font-size:13px;color:#065f46}}
.footer{{background:#f7f8fa;border-top:1px solid #e5e7eb;padding:16px 32px;text-align:center;font-size:12px;color:#9ca3af}}
</style></head>
<body>
<div class="wrap">
  <div class="hdr"><h1>{org_name}</h1><p>Password Reset</p></div>
  <div class="body">
    <p>Dear <strong>{to_name}</strong>,</p>
    <p>A password reset request was received for your account on the <strong>{org_name} Asset Management System</strong>.</p>
    <div class="creds">
      <table>
        <tr><td>System URL</td><td class="val"><a href="{app_url}" style="color:#0d3d23">{app_url}</a></td></tr>
        <tr><td>Username</td><td class="val">{username}</td></tr>
        <tr><td>Temporary Password</td><td class="val">{password}</td></tr>
      </table>
    </div>
    <a href="{app_url}" class="btn">Sign In to {org_name} AMS →</a>
    <div class="note">Please change your password immediately after signing in.</div>
    <p>If you did not request this reset, contact your administrator immediately.</p>
    <p>Regards,<br><strong>{org_name} Administration</strong></p>
  </div>
  <div class="footer">{org_name} Asset Management System &middot; This is an automated message, please do not reply.</div>
</div>
</body>
</html>
    """.strip()

    msg.attach(MIMEText(text_body, 'plain'))
    msg.attach(MIMEText(html_body, 'html'))

    try:
        if use_ssl:
            server = smtplib.SMTP_SSL(smtp_server, smtp_port, timeout=10)
        else:
            server = smtplib.SMTP(smtp_server, smtp_port, timeout=10)
            server.ehlo()
            server.starttls()
            server.ehlo()

        server.login(sender, mail_pass)
        server.sendmail(sender, to_email, msg.as_string())
        server.quit()
        print(f"  [Email] Password reset email sent to {to_email}")
        return True, None

    except smtplib.SMTPAuthenticationError:
        err = ("Login failed. Check MAIL_PASSWORD in .env. "
               "If MFA is enabled, use an App Password from "
               "https://mysignins.microsoft.com/security-info")
        print(f"  [Email] AUTH ERROR: {err}")
        return False, err

    except smtplib.SMTPException as e:
        err = f"SMTP error: {str(e)}"
        print(f"  [Email] SMTP ERROR: {err}")
        return False, err

    except Exception as e:
        err = f"Unexpected error: {str(e)}"
        print(f"  [Email] ERROR: {traceback.format_exc()}")
        return False, err
