from flask import Blueprint, render_template, abort, make_response, url_for
from flask_login import login_required, current_user
from models import Asset, User, Project, ReturnRecord
from extensions import db
from sqlalchemy import func
from functools import wraps
from datetime import datetime
import csv
import io

from pdf_utils import (
    build_gr_pdf,
    build_pdf_table,
    asset_register_col_widths,
    return_log_col_widths,
    pdf_response,
    PRIMARY,
)
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, Spacer

reports_bp = Blueprint('reports', __name__)


def _format_age(a):
    if getattr(a, 'age_years', None) is not None or getattr(a, 'age_months', None) is not None:
        y = a.age_years or 0
        m = a.age_months or 0
        parts = []
        if y: parts.append(f"{y} yr")
        if m: parts.append(f"{m} mo")
        return ' '.join(parts) if parts else '—'
    if not a.date_purchased:
        return '—'
    today = datetime.utcnow().date()
    dp = a.date_purchased
    years = today.year - dp.year - ((today.month, today.day) < (dp.month, dp.day))
    months = (today.month - dp.month - (today.day < dp.day)) % 12
    parts = []
    if years: parts.append(f"{years} yr")
    if months: parts.append(f"{months} mo")
    return ' '.join(parts) if parts else '0 mo'


def admin_or_finance(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role not in ('admin', 'finance'):
            abort(403)
        return f(*args, **kwargs)
    return decorated


@reports_bp.route('/')
@login_required
@admin_or_finance
def index():
    assets = Asset.query.filter_by(status='active').order_by(Asset.asset_number).all()
    total  = sum(float(a.price or 0) for a in assets)
    assigned   = [a for a in assets if a.assigned_to_id]
    unassigned = [a for a in assets if not a.assigned_to_id]
    returns = ReturnRecord.query.order_by(ReturnRecord.returned_at.desc()).all()
    compute_age = _format_age

    return render_template('reports/index.html',
                           assets=assets, total=total,
                           assigned=assigned, unassigned=unassigned,
                           returns=returns, compute_age=compute_age)


@reports_bp.route('/print-by-user')
@login_required
@admin_or_finance
def print_by_user():
    users = User.query.filter_by(status='active').order_by(User.name).all()
    return render_template('reports/print_by_user.html', users=users)


def _build_asset_rows(assets):
    rows = [[
        'Asset Tag', 'Category', 'Name', 'Processor', 'Serial Number', 'Department',
        'Date Purchased', 'Age', 'Assigned To', 'Condition', 'Vendor'
    ]]
    for a in assets:
        rows.append([
            a.tag,
            a.category.name,
            a.name,
            a.processor or '—',
            a.serial_number or '—',
            a.assigned_user.department if a.assigned_user and a.assigned_user.department else '—',
            a.date_purchased.strftime('%d %b %Y') if a.date_purchased else '—',
            _format_age(a),
            a.assigned_user.name if a.assigned_user else '—',
            a.condition.title(),
            a.vendor.name if a.vendor else '—'
        ])
    return rows


def _build_return_rows(returns):
    rows = [[
        'Asset Tag', 'Asset Name', 'Returned By', 'Return Date', 'Condition', 'Notes'
    ]]
    for r in returns:
        rows.append([
            r.asset.tag,
            r.asset.name,
            r.user.name,
            r.returned_at.strftime('%d %b %Y') if r.returned_at else '—',
            (r.condition_at_return or '—').title(),
            r.notes or '—'
        ])
    return rows


@reports_bp.route('/download/csv')
@login_required
@admin_or_finance
def download_csv():
    assets = Asset.query.filter_by(status='active').order_by(Asset.asset_number).all()
    returns = ReturnRecord.query.order_by(ReturnRecord.returned_at.desc()).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['GR Asset Management System - Asset Register'])
    writer.writerows(_build_asset_rows(assets))
    writer.writerow([])
    writer.writerow(['GR Asset Management System - Return Log'])
    writer.writerows(_build_return_rows(returns))

    csv_data = output.getvalue()
    output.close()

    response = make_response(csv_data)
    response.headers['Content-Type'] = 'text/csv; charset=utf-8'
    response.headers['Content-Disposition'] = 'attachment; filename=gr_asset_report.csv'
    return response


@reports_bp.route('/download/pdf')
@login_required
@admin_or_finance
def download_pdf():
    assets = Asset.query.filter_by(status='active').order_by(Asset.asset_number).all()
    returns = ReturnRecord.query.order_by(ReturnRecord.returned_at.desc()).all()
    styles = getSampleStyleSheet()

    def body(doc):
        items = [
            build_pdf_table(_build_asset_rows(assets), asset_register_col_widths(doc.width)),
            Spacer(1, 18),
        ]
        if returns:
            section_style = styles['Heading2'].clone('ReportSection')
            section_style.textColor = PRIMARY
            section_style.fontSize = 11
            section_style.spaceAfter = 6
            items.append(Paragraph('Return Log', section_style))
            items.append(Spacer(1, 6))
            items.append(build_pdf_table(_build_return_rows(returns), return_log_col_widths(doc.width)))
        return items

    return pdf_response(build_gr_pdf(body), 'gr_asset_report.pdf')
