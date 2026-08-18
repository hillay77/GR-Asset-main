from flask import Blueprint, render_template, redirect, url_for, flash, request, session
from flask_login import login_user, logout_user, login_required, current_user
from models import AuditLog, User
from extensions import db, limiter
from email_utils import send_password_reset_email
from datetime import datetime
from urllib.parse import urlparse
import secrets, string

auth_bp = Blueprint('auth', __name__)


def _audit_log(event_type, user_id=None, target_type=None, target_id=None, details=None):
    try:
        log = AuditLog(
            user_id=user_id,
            event_type=event_type,
            target_type=target_type,
            target_id=target_id,
            details=details,
            ip_address=request.remote_addr or 'unknown',
            user_agent=request.user_agent.string[:255],
        )
        db.session.add(log)
        db.session.commit()
    except Exception:
        db.session.rollback()


@auth_bp.route('/login', methods=['GET', 'POST'])
@limiter.limit('10 per minute')
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))

    error = None
    if request.method == 'POST':
        username = request.form.get('username', '').strip().lower()
        password = request.form.get('password', '')
        user = User.query.filter(
            db.func.lower(User.username) == username,
            User.status == 'active',
        ).first()

        if user and user.check_password(password):
            user.last_login_at = datetime.utcnow()
            user.last_login_ip = request.remote_addr or 'unknown'
            user.session_token = secrets.token_urlsafe(32)
            db.session.commit()
            session['session_token'] = user.session_token
            login_user(user, remember=True, fresh=True)
            _audit_log('login_success', user_id=user.id, details='User logged in successfully.')
            next_page = request.args.get('next')
            if next_page and urlparse(next_page).netloc == '':
                return redirect(next_page)
            return redirect(url_for('main.dashboard'))
        else:
            error = 'Invalid username or password.'
            _audit_log('login_failed', target_type='user', target_id=username,
                       details='Invalid username or password.')

    return render_template('auth/login.html', error=error)


@auth_bp.before_app_request
def _protect_session_token():
    if current_user.is_authenticated:
        token = session.get('session_token')
        if token:
            if current_user.session_token and token != current_user.session_token:
                logout_user()
                session.pop('session_token', None)
        else:
            if current_user.session_token:
                session['session_token'] = current_user.session_token
            else:
                current_user.session_token = secrets.token_urlsafe(32)
                db.session.commit()
                session['session_token'] = current_user.session_token

@auth_bp.route('/reset-password', methods=['GET', 'POST'])
@limiter.limit('5 per minute')
def reset_password():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))

    message = None
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        user = User.query.filter_by(username=username, status='active').first()

        if not user or not user.email:
            message = 'If an active account exists with that username, a password reset email has been sent.'
            _audit_log('password_reset_requested', target_type='user', target_id=username,
                       details='Password reset requested for username.')
            return render_template('auth/reset_password.html', error=message)
        else:
            temp_password = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(10))
            user.set_password(temp_password)
            db.session.commit()
            ok, err = send_password_reset_email(
                to_email=user.email,
                to_name=user.name,
                username=user.username,
                password=temp_password
            )
            if ok:
                _audit_log('password_reset_requested', user_id=user.id,
                           details='Password reset email sent successfully.')
                flash('If an active account exists with that username, a password reset email has been sent.', 'success')
                return redirect(url_for('auth.login'))
            message = 'Unable to send password reset email. Please contact your administrator.'
            _audit_log('password_reset_failed', user_id=user.id,
                       details=f'Password reset email failed: {err}')

    return render_template('auth/reset_password.html', error=message)


@auth_bp.route('/logout')
@login_required
def logout():
    user_id = current_user.id
    logout_user()
    session.pop('session_token', None)
    _audit_log('logout', user_id=user_id, details='User logged out.')
    return redirect(url_for('auth.login'))
