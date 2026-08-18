from extensions import db, login_manager
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

@login_manager.user_loader
def load_user(uid):
    return User.query.get(int(uid))

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id            = db.Column(db.Integer, primary_key=True)
    username      = db.Column(db.String(80),  unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    name          = db.Column(db.String(150), nullable=False)
    email         = db.Column(db.String(150))
    department    = db.Column(db.String(100))
    project_id    = db.Column(db.Integer, db.ForeignKey('projects.id'))
    role          = db.Column(db.String(20),  nullable=False, default='user')
    status        = db.Column(db.String(20),  nullable=False, default='active')
    created_at    = db.Column(db.DateTime,    default=datetime.utcnow)
    assigned_assets = db.relationship('Asset', foreign_keys='Asset.assigned_to_id',
                                      backref='assigned_user', lazy='dynamic')
    project         = db.relationship('Project', backref='users')
    return_records  = db.relationship('ReturnRecord', backref='user',
                                      foreign_keys='ReturnRecord.user_id', lazy='dynamic')
    def set_password(self, pw): self.password_hash = generate_password_hash(pw)
    def check_password(self, pw): return check_password_hash(self.password_hash, pw)
    def get_auth_token(self):
        return self.session_token or ''

    @property
    def initials(self):
        p = self.name.split()
        return ''.join(x[0] for x in p[:2]).upper()

    @property
    def is_staff_portal(self):
        """Staff users with personal assets, requests, and profile (user + finance)."""
        return self.role in ('user', 'finance')

    session_token = db.Column(db.String(128), nullable=True)
    last_login_at = db.Column(db.DateTime)
    last_login_ip = db.Column(db.String(100))

    @property
    def role_label(self):
        from models import Role
        role = Role.query.filter_by(name=self.role).first()
        if role:
            return role.label
        return {'admin':'Administrator','finance':'Finance Officer','user':'Staff User'}.get(self.role, self.role)

class AuditLog(db.Model):
    __tablename__ = 'audit_logs'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    event_type = db.Column(db.String(50), nullable=False)
    target_type = db.Column(db.String(50))
    target_id = db.Column(db.String(100))
    details = db.Column(db.Text)
    ip_address = db.Column(db.String(100))
    user_agent = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', foreign_keys=[user_id])

class Role(db.Model):
    __tablename__ = 'roles'
    id          = db.Column(db.Integer, primary_key=True)
    name        = db.Column(db.String(50), unique=True, nullable=False)
    label       = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)

class AssetCategory(db.Model):
    __tablename__ = 'asset_categories'
    id          = db.Column(db.Integer, primary_key=True)
    name        = db.Column(db.String(100), nullable=False)
    code        = db.Column(db.String(20),  unique=True, nullable=False)
    description = db.Column(db.Text)
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)
    assets      = db.relationship('Asset', backref='category', lazy='dynamic')

class Project(db.Model):
    __tablename__ = 'projects'
    id          = db.Column(db.Integer, primary_key=True)
    code        = db.Column(db.String(20),  unique=True, nullable=False)
    name        = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text)
    year        = db.Column(db.String(10))
    status      = db.Column(db.String(20), default='active')
    created_at  = db.Column(db.DateTime,   default=datetime.utcnow)
    assets      = db.relationship('Asset', backref='project', lazy='dynamic')

class Vendor(db.Model):
    __tablename__ = 'vendors'
    id         = db.Column(db.Integer, primary_key=True)
    name       = db.Column(db.String(150), nullable=False)
    contact    = db.Column(db.String(50))
    email      = db.Column(db.String(150))
    address    = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    assets     = db.relationship('Asset', backref='vendor', lazy='dynamic')

class Asset(db.Model):
    __tablename__ = 'assets'
    id             = db.Column(db.Integer, primary_key=True)
    asset_number   = db.Column(db.Integer, unique=True, nullable=False)
    tag            = db.Column(db.String(60), unique=True, nullable=False)
    name           = db.Column(db.String(200), nullable=False)
    serial_number  = db.Column(db.String(100))
    description    = db.Column(db.Text)
    price          = db.Column(db.Numeric(15,2), default=0)
    date_purchased = db.Column(db.Date)
    condition      = db.Column(db.String(20), default='good')
    status         = db.Column(db.String(20), default='active')
    location       = db.Column(db.String(150))
    assigned_on    = db.Column(db.Date)
    created_at     = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at     = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    category_id    = db.Column(db.Integer, db.ForeignKey('asset_categories.id'), nullable=False)
    project_id     = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=True)
    vendor_id      = db.Column(db.Integer, db.ForeignKey('vendors.id'))
    processor      = db.Column(db.String(200))
    age_years      = db.Column(db.Integer)
    age_months     = db.Column(db.Integer)
    assigned_to_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    return_records = db.relationship('ReturnRecord', backref='asset', lazy='dynamic')

class ReturnRecord(db.Model):
    __tablename__ = 'return_records'
    id                  = db.Column(db.Integer, primary_key=True)
    asset_id            = db.Column(db.Integer, db.ForeignKey('assets.id'),  nullable=False)
    user_id             = db.Column(db.Integer, db.ForeignKey('users.id'),   nullable=False)
    processed_by_id     = db.Column(db.Integer, db.ForeignKey('users.id'))
    condition_at_return = db.Column(db.String(20))
    returned_at         = db.Column(db.Date, nullable=False)
    notes               = db.Column(db.Text)
    created_at          = db.Column(db.DateTime, default=datetime.utcnow)
    processed_by        = db.relationship('User', foreign_keys=[processed_by_id])


class ReturnRequest(db.Model):
    """User submits a return request — admin must approve or reject it."""
    __tablename__ = 'return_requests'
    id              = db.Column(db.Integer, primary_key=True)
    asset_id        = db.Column(db.Integer, db.ForeignKey('assets.id'),  nullable=False)
    requested_by_id = db.Column(db.Integer, db.ForeignKey('users.id'),   nullable=False)
    reviewed_by_id  = db.Column(db.Integer, db.ForeignKey('users.id'))
    # pending | approved | rejected
    status          = db.Column(db.String(20), default='pending', nullable=False)
    reason          = db.Column(db.Text)
    condition_at_return = db.Column(db.String(20), default='good')
    admin_note      = db.Column(db.Text)
    requested_at    = db.Column(db.DateTime, default=datetime.utcnow)
    reviewed_at     = db.Column(db.DateTime)

    asset        = db.relationship('Asset',  foreign_keys=[asset_id])
    requested_by = db.relationship('User',   foreign_keys=[requested_by_id])
    reviewed_by  = db.relationship('User',   foreign_keys=[reviewed_by_id])


class AssetRequest(db.Model):
    """User requests to borrow an asset for a period."""
    __tablename__ = 'asset_requests'
    id              = db.Column(db.Integer, primary_key=True)
    requested_by_id = db.Column(db.Integer, db.ForeignKey('users.id'),           nullable=False)
    reviewed_by_id  = db.Column(db.Integer, db.ForeignKey('users.id'))
    category_id     = db.Column(db.Integer, db.ForeignKey('asset_categories.id'))
    assigned_asset_id = db.Column(db.Integer, db.ForeignKey('assets.id'))
    # pending | approved | rejected
    status          = db.Column(db.String(20), default='pending', nullable=False)
    item_requested  = db.Column(db.String(200), nullable=False)  # free text e.g. "Projector"
    purpose         = db.Column(db.Text, nullable=False)
    duration_days   = db.Column(db.Integer)                       # number of days needed
    date_needed_from= db.Column(db.Date)
    date_needed_to  = db.Column(db.Date)
    project_id      = db.Column(db.Integer, db.ForeignKey('projects.id'))
    department      = db.Column(db.String(100))
    priority        = db.Column(db.String(20), default='medium')
    admin_note      = db.Column(db.Text)
    requested_at    = db.Column(db.DateTime, default=datetime.utcnow)
    reviewed_at     = db.Column(db.DateTime)

    requested_by   = db.relationship('User',          foreign_keys=[requested_by_id])
    reviewed_by    = db.relationship('User',          foreign_keys=[reviewed_by_id])
    category       = db.relationship('AssetCategory', foreign_keys=[category_id])
    assigned_asset = db.relationship('Asset',         foreign_keys=[assigned_asset_id])
    country        = db.relationship('Project',       foreign_keys=[project_id])


class RepairRequest(db.Model):
    """User submits a repair request for an assigned asset."""
    __tablename__ = 'repair_requests'
    id               = db.Column(db.Integer, primary_key=True)
    asset_id         = db.Column(db.Integer, db.ForeignKey('assets.id'), nullable=False)
    requested_by_id  = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    reviewed_by_id   = db.Column(db.Integer, db.ForeignKey('users.id'))
    problem_category = db.Column(db.String(30), nullable=False)
    description      = db.Column(db.Text, nullable=False)
    priority         = db.Column(db.String(20), default='medium', nullable=False)
    photo_path       = db.Column(db.String(255))
    status           = db.Column(db.String(30), default='pending', nullable=False)
    admin_note       = db.Column(db.Text)
    requested_at     = db.Column(db.DateTime, default=datetime.utcnow)
    reviewed_at      = db.Column(db.DateTime)

    asset        = db.relationship('Asset', foreign_keys=[asset_id])
    requested_by = db.relationship('User',  foreign_keys=[requested_by_id])
    reviewed_by  = db.relationship('User',  foreign_keys=[reviewed_by_id])


class DamageReport(db.Model):
    """User reports damage, loss, or maintenance need."""
    __tablename__ = 'damage_reports'
    id              = db.Column(db.Integer, primary_key=True)
    asset_id        = db.Column(db.Integer, db.ForeignKey('assets.id'))
    reported_by_id  = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    reviewed_by_id  = db.Column(db.Integer, db.ForeignKey('users.id'))
    report_type     = db.Column(db.String(30), nullable=False)
    description     = db.Column(db.Text, nullable=False)
    priority        = db.Column(db.String(20), default='medium', nullable=False)
    status          = db.Column(db.String(30), default='pending', nullable=False)
    admin_note      = db.Column(db.Text)
    reported_at     = db.Column(db.DateTime, default=datetime.utcnow)
    reviewed_at     = db.Column(db.DateTime)

    asset       = db.relationship('Asset', foreign_keys=[asset_id])
    reported_by = db.relationship('User',  foreign_keys=[reported_by_id])
    reviewed_by = db.relationship('User',  foreign_keys=[reviewed_by_id])
