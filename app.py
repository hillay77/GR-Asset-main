"""GR Asset Management System — app factory"""
from datetime import datetime
from urllib.parse import urljoin, urlparse
import os

from flask import Flask, render_template, request, url_for
from flask_wtf.csrf import CSRFProtect, generate_csrf
from extensions import db, login_manager, limiter

csrf = CSRFProtect()


def _is_safe_url(target):
    if not target:
        return False
    ref_url = urlparse(request.host_url)
    test_url = urlparse(urljoin(request.host_url, target))
    return test_url.scheme in ('http', 'https') and ref_url.netloc == test_url.netloc


def create_app():
    app = Flask(__name__, instance_relative_config=True)

    # ── Load .env file if it exists ──────────────────────────────
    _load_env(os.path.join(os.path.dirname(__file__), '.env'))

    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'change-this-secret-key')
    app.config['SQLALCHEMY_DATABASE_URI'] = (
        os.environ.get('DATABASE_URL')
        or 'sqlite:///' + os.path.join(app.instance_path, 'gr_ams.db')
    )
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['TEMPLATES_AUTO_RELOAD'] = True
    app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0
    app.config['WTF_CSRF_TIME_LIMIT'] = 3600
    app.config['WTF_CSRF_CHECK_DEFAULT'] = True
    app.config['WTF_CSRF_METHODS'] = ['POST', 'PUT', 'PATCH', 'DELETE']
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
    app.config['SESSION_COOKIE_SECURE'] = os.environ.get('FLASK_ENV', '').lower() == 'production'
    app.config['REMEMBER_COOKIE_HTTPONLY'] = True
    app.config['REMEMBER_COOKIE_DURATION'] = 60 * 60 * 24 * 30
    app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024
    app.config['RATELIMIT_HEADERS_ENABLED'] = True
    app.config['ADMIN_EMAIL'] = os.environ.get('ADMIN_EMAIL', os.environ.get('MAIL_USERNAME', ''))
    app.config['PREFERRED_URL_SCHEME'] = 'https'

    os.makedirs(app.instance_path, exist_ok=True)

    # ── Mail config (loaded from .env) ───────────────────────────
    app.config['MAIL_SERVER']   = os.environ.get('MAIL_SERVER',   'smtp.office365.com')
    app.config['MAIL_PORT']     = int(os.environ.get('MAIL_PORT', 587))
    app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME', '')
    app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD', '')
    app.config['APP_URL']       = os.environ.get('APP_URL',       'http://127.0.0.1:5000')
    app.config['MAIL_USE_SSL']  = os.environ.get('MAIL_USE_SSL',  'false')
    app.config['ORG_NAME']      = os.environ.get('ORG_NAME',      'GR')

    db.init_app(app)
    login_manager.init_app(app)
    limiter.init_app(app)
    csrf.init_app(app)

    from routes.auth     import auth_bp
    from routes.main     import main_bp
    from routes.assets   import assets_bp
    from routes.users    import users_bp
    from routes.admin    import admin_bp
    from routes.reports  import reports_bp
    from routes.requests import requests_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(assets_bp,   url_prefix='/assets')
    app.register_blueprint(users_bp,    url_prefix='/users')
    app.register_blueprint(admin_bp,    url_prefix='/admin')
    app.register_blueprint(reports_bp,  url_prefix='/reports')
    app.register_blueprint(requests_bp, url_prefix='/requests')

    @app.after_request
    def set_security_headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        response.headers['Permissions-Policy'] = 'geolocation=(), microphone=(), camera=()'
        response.headers['X-XSS-Protection'] = '0'
        response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; object-src 'none'; frame-ancestors 'none';"
        if request.is_secure:
            response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains; preload'
        response.set_cookie('csrf_token', generate_csrf(), secure=app.config['SESSION_COOKIE_SECURE'], httponly=False, samesite='Lax')
        return response

    @app.context_processor
    def inject_globals():
        from flask_login import current_user
        counts = {
            'pending_asset_requests': 0,
            'pending_return_requests': 0,
            'pending_repair_requests': 0,
            'pending_damage_reports': 0,
        }
        try:
            if current_user.is_authenticated and current_user.role in ('admin', 'finance'):
                from models import AssetRequest, ReturnRequest, RepairRequest, DamageReport
                counts['pending_asset_requests']  = AssetRequest.query.filter_by(status='pending').count()
                counts['pending_return_requests'] = ReturnRequest.query.filter_by(status='pending').count()
                counts['pending_repair_requests'] = RepairRequest.query.filter_by(status='pending').count()
                counts['pending_damage_reports']  = DamageReport.query.filter_by(status='pending').count()
        except Exception:
            pass
        counts['now'] = datetime.utcnow()
        counts['is_staff_portal'] = (
            current_user.is_authenticated
            and current_user.role in ('user', 'finance')
        )
        counts['app_build'] = '2026-07-08-staff-portal'
        counts['privacy_policy_url'] = url_for('main.privacy_policy')
        return counts

    @app.template_filter('currency')
    def currency_filter(v):
        try:    return 'USD {:,.2f}'.format(float(v or 0))
        except: return 'USD 0.00'

    @app.template_filter('dateformat')
    def date_filter(v):
        if not v: return '—'
        if isinstance(v, str):
            try: v = datetime.strptime(v, '%Y-%m-%d')
            except: return v
        return v.strftime('%d %b %Y')

    with app.app_context():
        db.create_all()
        # Ensure new columns added when model changed (simple SQLite-friendly migration)
        try:
            from sqlalchemy import text
            cols = [r['name'] for r in db.session.execute(text("PRAGMA table_info('assets')")).mappings()]
        except Exception:
            cols = []
        alter_stmts = []
        if 'processor' not in cols:
            alter_stmts.append("ALTER TABLE assets ADD COLUMN processor TEXT")
        if 'age_years' not in cols:
            alter_stmts.append("ALTER TABLE assets ADD COLUMN age_years INTEGER")
        if 'age_months' not in cols:
            alter_stmts.append("ALTER TABLE assets ADD COLUMN age_months INTEGER")
        try:
            user_cols = [r['name'] for r in db.session.execute(text("PRAGMA table_info('users')")).mappings()]
        except Exception:
            user_cols = []
        if 'project_id' not in user_cols:
            alter_stmts.append("ALTER TABLE users ADD COLUMN project_id INTEGER REFERENCES projects(id)")
        if 'session_token' not in user_cols:
            alter_stmts.append("ALTER TABLE users ADD COLUMN session_token TEXT")
        if 'last_login_at' not in user_cols:
            alter_stmts.append("ALTER TABLE users ADD COLUMN last_login_at DATETIME")
        if 'last_login_ip' not in user_cols:
            alter_stmts.append("ALTER TABLE users ADD COLUMN last_login_ip TEXT")
        try:
            ar_cols = [r['name'] for r in db.session.execute(text("PRAGMA table_info('asset_requests')")).mappings()]
        except Exception:
            ar_cols = []
        if 'project_id' not in ar_cols:
            alter_stmts.append("ALTER TABLE asset_requests ADD COLUMN project_id INTEGER REFERENCES projects(id)")
        if 'department' not in ar_cols:
            alter_stmts.append("ALTER TABLE asset_requests ADD COLUMN department TEXT")
        if 'priority' not in ar_cols:
            alter_stmts.append("ALTER TABLE asset_requests ADD COLUMN priority TEXT DEFAULT 'medium'")
        for s in alter_stmts:
            try:
                db.session.execute(text(s))
            except Exception:
                pass
        if alter_stmts:
            db.session.commit()

        try:
            from models import User
            if User.query.filter_by(username='user').first() is None:
                legacy = User.query.filter_by(username='finance').first()
                if legacy:
                    legacy.username = 'user'
                    legacy.role = 'user'
                    legacy.set_password('user123')
                    db.session.commit()
        except Exception:
            pass

        if os.environ.get('FLASK_ENV', '').lower() != 'production':
            _seed()
            _ensure_demo_accounts()

    return app


def _seed():
    from models import User, AssetCategory, Project, Vendor, Asset, Role
    from werkzeug.security import generate_password_hash
    if not Role.query.first():
        roles = [
            Role(name='admin', label='Administrator', description='Full system administrator access.'),
            Role(name='finance', label='Finance Officer', description='Finance team access and reporting approvals.'),
            Role(name='user', label='Staff User', description='Standard staff access to own assets and requests.'),
        ]
        db.session.add_all(roles)
        db.session.flush()
    if User.query.first():
        return
    print("  Seeding database ...")
    users = [
        User(username='admin',   name='System Administrator', email='admin@gr.org',
             role='admin',   department='IT',       status='active',
             password_hash=generate_password_hash('admin123')),
        User(username='user',    name='Demo Staff User',       email='user@gr.org',
             role='user',    department='Programs', status='active',
             password_hash=generate_password_hash('user123')),
        User(username='john',    name='John Okello',           email='john@gr.org',
             role='user',    department='Programs', status='active',
             password_hash=generate_password_hash('user123')),
        User(username='mary',    name='Mary Apio',             email='mary@gr.org',
             role='user',    department='Admin',    status='active',
             password_hash=generate_password_hash('user123')),
    ]
    db.session.add_all(users); db.session.flush()

    cats = [
        AssetCategory(name='Laptop',    code='LP',   description='Laptop computers'),
        AssetCategory(name='Desktop',   code='DISC', description='Desktop computers'),
        AssetCategory(name='Printer',   code='PRN',  description='Printers and scanners'),
        AssetCategory(name='Furniture', code='FRN',  description='Office furniture'),
        AssetCategory(name='Vehicle',   code='VEH',  description='Vehicles'),
        AssetCategory(name='UPS',       code='UPS',  description='Uninterruptible power supply'),
        AssetCategory(name='Projector', code='PROJ', description='Projectors'),
        AssetCategory(name='Phone',     code='PHN',  description='Mobile phones'),
    ]
    db.session.add_all(cats); db.session.flush()

    projs = [
        Project(code='CORE', name='Core Operations',   description='Main operational budget',   status='active', year='2024'),
        Project(code='HLTH', name='Health Initiative',  description='Community health programs', status='active', year='2024'),
        Project(code='EDU',  name='Education Program',  description='Schools and training',      status='active', year='2024'),
    ]
    db.session.add_all(projs); db.session.flush()

    vendors = [
        Vendor(name='TechHub Uganda',       contact='+256 700 111 222', email='info@techhub.ug', address='Kampala'),
        Vendor(name='Computer Palace',      contact='+256 700 333 444', email='info@cpalace.ug', address='Kampala'),
        Vendor(name='Office Solutions Ltd', contact='+256 700 555 666', email='info@osl.ug',     address='Jinja'),
    ]
    db.session.add_all(vendors); db.session.flush()

    from datetime import date
    lp,disc,prn  = cats[0],cats[1],cats[2]
    core,hlth,edu= projs[0],projs[1],projs[2]
    v1,v2,v3     = vendors[0],vendors[1],vendors[2]
    john,demo_user,mary = users[2],users[1],users[3]
    def t(p,c,n): return f"GR-{c.code}-{p.code}-{n:03d}"

    assets = [
        Asset(asset_number=1,tag=t(core,lp,1),serial_number='SN-DELL-001',name='Dell Latitude 5420',
              category=lp,project=core,vendor=v1,price=1800000,date_purchased=date(2024,1,15),
              condition='good',status='active',assigned_to_id=john.id,assigned_on=date(2024,1,20),
              description='Intel Core i5, 8GB RAM, 256GB SSD',location='Kampala Office'),
        Asset(asset_number=2,tag=t(core,lp,2),serial_number='SN-HP-002',name='HP ProBook 450',
              category=lp,project=core,vendor=v2,price=1500000,date_purchased=date(2024,1,20),
              condition='good',status='active',assigned_to_id=demo_user.id,assigned_on=date(2024,1,25),
              description='Intel Core i5, 8GB RAM',location='Kampala Office'),
        Asset(asset_number=3,tag=t(hlth,disc,1),serial_number='SN-DESK-003',name='HP Desktop ProDesk',
              category=disc,project=hlth,vendor=v1,price=1200000,date_purchased=date(2024,2,10),
              condition='good',status='active',assigned_to_id=mary.id,assigned_on=date(2024,2,15),
              description='Core i5, 16GB RAM, 1TB HDD',location='Jinja Office'),
        Asset(asset_number=4,tag=t(edu,prn,1),serial_number='SN-PRN-004',name='HP LaserJet Pro',
              category=prn,project=edu,vendor=v3,price=850000,date_purchased=date(2024,2,20),
              condition='fair',status='active',description='A4 laser printer',location='Training Center'),
        Asset(asset_number=5,tag=t(core,lp,3),serial_number='SN-LENOVO-005',name='Lenovo ThinkPad L14',
              category=lp,project=core,vendor=v1,price=1950000,date_purchased=date(2024,3,5),
              condition='new',status='active',description='AMD Ryzen 5, 16GB RAM, 512GB SSD',location='Kampala Office'),
    ]
    db.session.add_all(assets)
    db.session.commit()
    print("  Database seeded OK.")


def _ensure_demo_accounts():
    """Keep demo login accounts in sync so documented passwords always work."""
    from models import User
    from werkzeug.security import generate_password_hash

    demos = [
        dict(username='admin', password='admin123', name='System Administrator',
             role='admin', email='admin@gr.org', department='IT'),
        dict(username='user', password='user123', name='Demo Staff User',
             role='user', email='user@gr.org', department='Programs'),
        dict(username='john', password='user123', name='John Okello',
             role='user', email='john@gr.org', department='Programs'),
        dict(username='finance', password='finance123', name='Sarah Nakato',
             role='finance', email='finance@gr.org', department='Finance'),
    ]
    for d in demos:
        u = User.query.filter_by(username=d['username']).first()
        if u:
            u.name = d['name']
            u.role = d['role']
            u.email = d['email']
            u.department = d['department']
            u.status = 'active'
            u.set_password(d['password'])
        else:
            db.session.add(User(
                username=d['username'], name=d['name'], email=d['email'],
                department=d['department'], role=d['role'], status='active',
                password_hash=generate_password_hash(d['password']),
            ))
    db.session.commit()

    from datetime import date
    from models import Asset
    finance_user = User.query.filter_by(username='finance').first()
    if finance_user and not Asset.query.filter_by(assigned_to_id=finance_user.id).first():
        spare = Asset.query.filter_by(assigned_to_id=None, status='active').first()
        if spare:
            spare.assigned_to_id = finance_user.id
            spare.assigned_on = date.today()
            db.session.commit()


def _load_env(path):
    """Simple .env loader — no dependencies needed."""
    if not os.path.exists(path):
        return
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            key, _, value = line.partition('=')
            key   = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value
