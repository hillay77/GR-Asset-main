"""
Asset Request & Return Request routes — GR AMS
"""

import csv
import io
import os
from datetime import datetime, date
from functools import wraps

from flask import Blueprint, render_template, redirect, url_for, flash, request, abort, make_response, current_app, send_from_directory
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename

from models import (
    AssetRequest, ReturnRequest, RepairRequest, DamageReport,
    Asset, AssetCategory, User, Project,
)
from extensions import db

requests_bp = Blueprint('requests', __name__)

PRIORITIES = [('low', 'Low'), ('medium', 'Medium'), ('high', 'High')]
REPAIR_CATEGORIES = [
    ('hardware', 'Hardware'), ('software', 'Software'), ('printer', 'Printer'),
    ('network', 'Network'), ('other', 'Other'),
]
DAMAGE_TYPES = [
    ('damaged', 'Damaged Asset'), ('lost', 'Lost Asset'), ('maintenance', 'Maintenance Request'),
]
REPAIR_STATUSES = [
    'pending', 'approved', 'in_repair', 'completed', 'beyond_repair', 'rejected',
]
DAMAGE_STATUSES = [
    'pending', 'repair_required', 'completed', 'beyond_repair', 'disposed', 'rejected',
]


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role not in ('admin', 'finance'):
            abort(403)
        return f(*args, **kwargs)
    return decorated


ALLOWED_PHOTO_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}


def _save_repair_photo(file):
    if not file or not file.filename:
        return None
    filename = secure_filename(file.filename)
    if '.' not in filename:
        return None
    ext = filename.rsplit('.', 1)[1].lower()
    if ext not in ALLOWED_PHOTO_EXTENSIONS:
        return None
    if not file.mimetype or not file.mimetype.startswith('image/'):
        return None
    upload_dir = os.path.join(current_app.instance_path, 'uploads', 'repair')
    os.makedirs(upload_dir, exist_ok=True)
    rel = f"uploads/repair/{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{filename}"
    file.save(os.path.join(current_app.instance_path, rel))
    return rel


def _can_view_repair(rep):
    if rep.requested_by_id == current_user.id:
        return True
    return current_user.role in ('admin', 'finance')


def _can_delete_repair(rep):
    if current_user.role in ('admin', 'finance'):
        return True
    return rep.requested_by_id == current_user.id and rep.status == 'pending'


def _delete_repair_photo(rep):
    if not rep.photo_path:
        return
    full = os.path.join(current_app.instance_path, rep.photo_path)
    if os.path.isfile(full):
        os.remove(full)


def _repair_requests_query():
    if _show_all_requests():
        return RepairRequest.query.order_by(
            RepairRequest.status.asc(), RepairRequest.requested_at.desc()
        )
    return RepairRequest.query.filter_by(requested_by_id=current_user.id)\
        .order_by(RepairRequest.requested_at.desc())


def _can_delete_damage(report):
    if current_user.role in ('admin', 'finance'):
        return True
    return report.reported_by_id == current_user.id and report.status == 'pending'


def _damage_reports_query():
    if _show_all_requests():
        return DamageReport.query.order_by(
            DamageReport.status.asc(), DamageReport.reported_at.desc()
        )
    return DamageReport.query.filter_by(reported_by_id=current_user.id)\
        .order_by(DamageReport.reported_at.desc())


def _show_all_requests():
    """ICT review lists — admin always; finance when ?review=1."""
    if current_user.role == 'admin':
        return True
    if current_user.role == 'finance' and request.args.get('review') == '1':
        return True
    return False


def _notify_admin(subject, body):
    try:
        from email_utils import send_admin_notification
        send_admin_notification(subject, body)
    except Exception:
        pass


def _ict_review_url(endpoint, **kwargs):
    if current_user.role == 'finance':
        kwargs['review'] = 1
    return url_for(endpoint, **kwargs)


def _staff_requests_redirect():
    if current_user.is_staff_portal:
        return redirect(url_for('requests.request_status'))
    return redirect(url_for('requests.request_history'))


def _status_badge(status):
    labels = {
        'pending': '⏳ Pending', 'approved': '✓ Approved', 'rejected': '✗ Rejected',
        'in_repair': '🔧 In Repair', 'completed': '✓ Completed',
        'beyond_repair': '⚠ Beyond Repair', 'repair_required': '🔧 Repair Required',
        'disposed': '🗑 Disposed',
    }
    return labels.get(status, status.replace('_', ' ').title())


# ─────────────────────────────────────────────
#  ASSET REQUESTS
# ─────────────────────────────────────────────

@requests_bp.route('/asset-requests')
@login_required
def asset_requests():
    if _show_all_requests():
        items = AssetRequest.query.order_by(
            AssetRequest.status.asc(), AssetRequest.requested_at.desc()
        ).all()
    else:
        items = AssetRequest.query.filter_by(requested_by_id=current_user.id)\
            .order_by(AssetRequest.requested_at.desc()).all()
    categories = AssetCategory.query.order_by(AssetCategory.name).all()
    return render_template('requests/asset_requests.html',
                           requests=items, categories=categories,
                           review_mode=_show_all_requests())


@requests_bp.route('/asset-requests/new', methods=['GET', 'POST'])
@login_required
def new_asset_request():
    categories = AssetCategory.query.order_by(AssetCategory.name).all()
    countries = Project.query.filter_by(status='active').order_by(Project.name).all()

    if request.method == 'POST':
        from_str = request.form.get('date_needed_from', '')
        to_str = request.form.get('date_needed_to', '')
        try:
            date_from = date.fromisoformat(from_str) if from_str else None
            date_to = date.fromisoformat(to_str) if to_str else None
            duration = (date_to - date_from).days + 1 if date_from and date_to else None
        except ValueError:
            date_from = date_to = duration = None

        project_id = request.form.get('project_id') or None
        req = AssetRequest(
            requested_by_id=current_user.id,
            item_requested=request.form['item_requested'].strip(),
            purpose=request.form['purpose'].strip(),
            date_needed_from=date_from,
            date_needed_to=date_to,
            duration_days=duration,
            category_id=request.form.get('category_id') or None,
            project_id=int(project_id) if project_id else None,
            department=request.form.get('department', '').strip() or current_user.department,
            priority=request.form.get('priority', 'medium'),
            status='pending',
        )
        db.session.add(req)
        db.session.commit()
        _notify_admin(
            'New Asset Request',
            f'{current_user.name} requested: {req.item_requested} (Priority: {req.priority})',
        )
        flash('✓ Asset request submitted. Track status under View Request Status.', 'success')
        return redirect(url_for('requests.request_status'))

    return render_template('requests/new_asset_request.html',
                           categories=categories, countries=countries, priorities=PRIORITIES)


@requests_bp.route('/asset-requests/<int:req_id>/review', methods=['GET', 'POST'])
@login_required
@admin_required
def review_asset_request(req_id):
    req = AssetRequest.query.get_or_404(req_id)
    available = Asset.query.filter_by(assigned_to_id=None, status='active').order_by(Asset.name).all()
    suggested = [a for a in available if req.category_id and a.category_id == req.category_id] if req.category_id else available

    if request.method == 'POST':
        action = request.form.get('action')
        req.reviewed_by_id = current_user.id
        req.reviewed_at = datetime.utcnow()
        req.admin_note = request.form.get('admin_note', '').strip()

        if action == 'approve':
            asset_id = request.form.get('assigned_asset_id')
            if not asset_id:
                flash('Please select an asset to assign.', 'error')
                return render_template('requests/review_asset_request.html',
                                       req=req, suggested=suggested, available=available)
            asset = Asset.query.get_or_404(int(asset_id))
            asset.assigned_to_id = req.requested_by_id
            asset.assigned_on = date.today()
            req.assigned_asset_id = asset.id
            req.status = 'approved'
            db.session.commit()
            flash(f'✓ Request approved. {asset.tag} assigned to {req.requested_by.name}.', 'success')
        elif action == 'reject':
            req.status = 'rejected'
            db.session.commit()
            flash(f'Request from {req.requested_by.name} rejected.', 'success')
        return redirect(_ict_review_url('requests.asset_requests'))

    return render_template('requests/review_asset_request.html',
                           req=req, suggested=suggested, available=available)


@requests_bp.route('/asset-requests/<int:req_id>/cancel', methods=['POST'])
@login_required
def cancel_asset_request(req_id):
    req = AssetRequest.query.get_or_404(req_id)
    if req.requested_by_id != current_user.id and current_user.role != 'admin':
        abort(403)
    if req.status != 'pending':
        flash('Only pending requests can be cancelled.', 'error')
        return _staff_requests_redirect()
    db.session.delete(req)
    db.session.commit()
    flash('Asset request cancelled.', 'success')
    return _staff_requests_redirect()


# ─────────────────────────────────────────────
#  RETURN REQUESTS
# ─────────────────────────────────────────────

@requests_bp.route('/return-requests')
@login_required
def return_requests():
    if _show_all_requests():
        items = ReturnRequest.query.order_by(
            ReturnRequest.status.asc(), ReturnRequest.requested_at.desc()
        ).all()
    else:
        items = ReturnRequest.query.filter_by(requested_by_id=current_user.id)\
            .order_by(ReturnRequest.requested_at.desc()).all()
    return render_template('requests/return_requests.html',
                           requests=items, review_mode=_show_all_requests())


@requests_bp.route('/return-asset')
@login_required
def return_asset_picker():
    assets = Asset.query.filter_by(
        assigned_to_id=current_user.id, status='active'
    ).order_by(Asset.name).all()
    pending = {
        r.asset_id for r in ReturnRequest.query.filter_by(
            requested_by_id=current_user.id, status='pending'
        ).all()
    }
    return render_template('requests/return_picker.html', assets=assets, pending=pending)


@requests_bp.route('/return-requests/new/<int:asset_id>', methods=['GET', 'POST'])
@login_required
def new_return_request(asset_id):
    asset = Asset.query.get_or_404(asset_id)
    if asset.assigned_to_id != current_user.id:
        abort(403)

    existing = ReturnRequest.query.filter_by(
        asset_id=asset_id, requested_by_id=current_user.id, status='pending'
    ).first()
    if existing:
        flash('You already have a pending return request for this asset.', 'warning')
        return redirect(url_for('requests.return_asset_picker'))

    if request.method == 'POST':
        ret = ReturnRequest(
            asset_id=asset.id,
            requested_by_id=current_user.id,
            reason=request.form.get('reason', '').strip(),
            condition_at_return=request.form.get('condition_at_return', 'good'),
            status='pending',
        )
        db.session.add(ret)
        db.session.commit()
        _notify_admin('New Return Request', f'{current_user.name} wants to return {asset.tag}.')
        flash('✓ Return request submitted. ICT will review it shortly.', 'success')
        return redirect(url_for('requests.request_status'))

    return render_template('requests/new_return_request.html', asset=asset)


@requests_bp.route('/return-requests/<int:req_id>/review', methods=['POST'])
@login_required
@admin_required
def review_return_request(req_id):
    from models import ReturnRecord
    ret = ReturnRequest.query.get_or_404(req_id)
    action = request.form.get('action')
    ret.reviewed_by_id = current_user.id
    ret.reviewed_at = datetime.utcnow()
    ret.admin_note = request.form.get('admin_note', '').strip()

    if action == 'approve':
        record = ReturnRecord(
            asset_id=ret.asset_id,
            user_id=ret.requested_by_id,
            condition_at_return=ret.condition_at_return,
            returned_at=date.today(),
            notes=ret.reason,
            processed_by_id=current_user.id,
        )
        db.session.add(record)
        asset = Asset.query.get(ret.asset_id)
        asset.condition = ret.condition_at_return
        asset.assigned_to_id = None
        asset.assigned_on = None
        ret.status = 'approved'
        db.session.commit()
        flash(f'✓ Return approved. {asset.tag} is now back in inventory.', 'success')
    elif action == 'reject':
        ret.status = 'rejected'
        db.session.commit()
        flash('Return request rejected. Asset remains assigned.', 'success')
    return redirect(_ict_review_url('requests.return_requests'))


# ─────────────────────────────────────────────
#  REPAIR REQUESTS
# ─────────────────────────────────────────────

@requests_bp.route('/repair-requests')
@login_required
def repair_requests():
    items = _repair_requests_query().all()
    return render_template('requests/repair_requests.html',
                           requests=items, review_mode=_show_all_requests())


@requests_bp.route('/repair-requests/new', methods=['GET', 'POST'])
@login_required
def new_repair_request():
    assets = Asset.query.filter_by(
        assigned_to_id=current_user.id, status='active'
    ).order_by(Asset.name).all()
    if not assets:
        flash('You have no assigned assets to request repair for.', 'warning')
        return redirect(url_for('main.dashboard'))

    if request.method == 'POST':
        asset_id = request.form.get('asset_id')
        asset = Asset.query.get_or_404(int(asset_id))
        if asset.assigned_to_id != current_user.id:
            abort(403)
        photo_file = request.files.get('photo')
        photo = None
        if photo_file and photo_file.filename:
            photo = _save_repair_photo(photo_file)
            if photo is None:
                flash('Repair attachment must be a valid JPG, PNG, or GIF image.', 'error')
                return render_template('requests/new_repair_request.html',
                                       assets=assets, categories=REPAIR_CATEGORIES, priorities=PRIORITIES)
        rep = RepairRequest(
            asset_id=asset.id,
            requested_by_id=current_user.id,
            problem_category=request.form['problem_category'],
            description=request.form['description'].strip(),
            priority=request.form.get('priority', 'medium'),
            photo_path=photo,
            status='pending',
        )
        db.session.add(rep)
        db.session.commit()
        _notify_admin(
            'New Repair Request',
            f'{current_user.name} reported {rep.problem_category} issue on {asset.tag}.',
        )
        flash('✓ Repair request submitted.', 'success')
        return redirect(url_for('requests.request_status'))

    return render_template('requests/new_repair_request.html',
                           assets=assets, categories=REPAIR_CATEGORIES, priorities=PRIORITIES)


@requests_bp.route('/repair-requests/<int:req_id>/review', methods=['POST'])
@login_required
@admin_required
def review_repair_request(req_id):
    rep = RepairRequest.query.get_or_404(req_id)
    action = request.form.get('action')
    new_status = request.form.get('status', action)
    rep.reviewed_by_id = current_user.id
    rep.reviewed_at = datetime.utcnow()
    rep.admin_note = request.form.get('admin_note', '').strip()

    if new_status in REPAIR_STATUSES:
        rep.status = new_status
        db.session.commit()
        flash(f'Repair request updated to {_status_badge(rep.status)}.', 'success')
    return redirect(_ict_review_url('requests.repair_requests'))


@requests_bp.route('/repair-requests/<int:req_id>/attachment')
@login_required
def repair_request_attachment(req_id):
    rep = RepairRequest.query.get_or_404(req_id)
    if not _can_view_repair(rep):
        abort(403)
    if not rep.photo_path:
        abort(404)
    directory = os.path.join(current_app.instance_path, os.path.dirname(rep.photo_path))
    filename = os.path.basename(rep.photo_path)
    return send_from_directory(directory, filename)


@requests_bp.route('/repair-requests/download/pdf')
@login_required
def repair_requests_pdf():
    from pdf_utils import build_gr_pdf, build_pdf_table, scaled_col_widths, pdf_response

    items = _repair_requests_query().all()
    rows = [['Requested By', 'Asset', 'Category', 'Priority', 'Status', 'Submitted', 'Attachment', 'Description']]
    for r in items:
        rows.append([
            r.requested_by.name,
            f'{r.asset.tag} — {r.asset.name}' if r.asset else '—',
            r.problem_category.title(), r.priority.title(),
            r.status.replace('_', ' ').title(),
            r.requested_at.strftime('%d %b %Y'),
            'Yes' if r.photo_path else 'No',
            (r.description or '')[:120],
        ])

    def body(doc):
        weights = [70, 90, 50, 45, 55, 50, 45, 150]
        return [build_pdf_table(rows, scaled_col_widths(weights, doc.width))]

    return pdf_response(build_gr_pdf(body, report_title='Repair Requests'), 'gr_repair_requests.pdf')


@requests_bp.route('/repair-requests/<int:req_id>/pdf')
@login_required
def repair_request_pdf(req_id):
    from pdf_utils import build_gr_pdf, build_pdf_table, scaled_col_widths, pdf_response
    from reportlab.platypus import Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet

    rep = RepairRequest.query.get_or_404(req_id)
    if not _can_view_repair(rep):
        abort(403)

    rows = [
        ['Field', 'Value'],
        ['Requested By', rep.requested_by.name],
        ['Asset Tag', rep.asset.tag if rep.asset else '—'],
        ['Asset Name', rep.asset.name if rep.asset else '—'],
        ['Category', rep.problem_category.title()],
        ['Priority', rep.priority.title()],
        ['Status', rep.status.replace('_', ' ').title()],
        ['Submitted', rep.requested_at.strftime('%d %b %Y %H:%M')],
        ['Description', rep.description or '—'],
        ['Attachment', 'Yes — view in GR AMS' if rep.photo_path else 'None'],
        ['Admin Note', rep.admin_note or '—'],
        ['Reviewed By', rep.reviewed_by.name if rep.reviewed_by else '—'],
        ['Reviewed At', rep.reviewed_at.strftime('%d %b %Y %H:%M') if rep.reviewed_at else '—'],
    ]

    def body(doc):
        styles = getSampleStyleSheet()
        title = Paragraph(
            f'Repair Request #{rep.id} — {rep.asset.tag if rep.asset else "Asset"}',
            styles['Heading2'],
        )
        return [
            title,
            Spacer(1, 8),
            build_pdf_table(rows, scaled_col_widths([90, 220], doc.width)),
        ]

    tag = rep.asset.tag if rep.asset else f'request_{rep.id}'
    report_title = f'Repair Request — {rep.problem_category.replace("_", " ").title()}'
    return pdf_response(build_gr_pdf(body, report_title=report_title), f'repair_{tag}.pdf')


@requests_bp.route('/repair-requests/<int:req_id>/cancel', methods=['POST'])
@login_required
def cancel_repair_request(req_id):
    rep = RepairRequest.query.get_or_404(req_id)
    if rep.requested_by_id != current_user.id:
        abort(403)
    if rep.status != 'pending':
        flash('Only pending repair requests can be cancelled.', 'error')
        return _staff_requests_redirect()
    _delete_repair_photo(rep)
    db.session.delete(rep)
    db.session.commit()
    flash('Repair request cancelled.', 'success')
    return _staff_requests_redirect()


@requests_bp.route('/repair-requests/<int:req_id>/delete', methods=['POST'])
@login_required
def delete_repair_request(req_id):
    rep = RepairRequest.query.get_or_404(req_id)
    if not _can_delete_repair(rep):
        abort(403)
    is_self_cancel = (
        rep.requested_by_id == current_user.id
        and rep.status == 'pending'
        and current_user.is_staff_portal
    )
    _delete_repair_photo(rep)
    db.session.delete(rep)
    db.session.commit()
    flash(
        'Repair request cancelled.' if is_self_cancel else 'Repair request deleted.',
        'success',
    )
    if is_self_cancel:
        return _staff_requests_redirect()
    if _show_all_requests():
        return redirect(_ict_review_url('requests.repair_requests'))
    return redirect(url_for('requests.repair_requests'))


# ─────────────────────────────────────────────
#  DAMAGE REPORTS
# ─────────────────────────────────────────────

@requests_bp.route('/damage-reports')
@login_required
def damage_reports():
    items = _damage_reports_query().all()
    return render_template('requests/damage_reports.html',
                           reports=items, review_mode=_show_all_requests())


@requests_bp.route('/damage-reports/new', methods=['GET', 'POST'])
@login_required
def new_damage_report():
    assets = Asset.query.filter_by(
        assigned_to_id=current_user.id, status='active'
    ).order_by(Asset.name).all()

    if request.method == 'POST':
        asset_id = request.form.get('asset_id')
        asset = Asset.query.get(int(asset_id)) if asset_id else None
        if asset and asset.assigned_to_id != current_user.id:
            abort(403)
        report = DamageReport(
            asset_id=asset.id if asset else None,
            reported_by_id=current_user.id,
            report_type=request.form['report_type'],
            description=request.form['description'].strip(),
            priority=request.form.get('priority', 'medium'),
            status='pending',
        )
        db.session.add(report)
        db.session.commit()
        _notify_admin(
            'New Damage Report',
            f'{current_user.name} reported: {report.report_type} — {report.description[:80]}',
        )
        flash('✓ Damage report submitted.', 'success')
        return redirect(url_for('requests.request_status'))

    return render_template('requests/new_damage_report.html',
                           assets=assets, report_types=DAMAGE_TYPES, priorities=PRIORITIES)


@requests_bp.route('/damage-reports/<int:report_id>/review', methods=['POST'])
@login_required
@admin_required
def review_damage_report(report_id):
    report = DamageReport.query.get_or_404(report_id)
    new_status = request.form.get('status')
    report.reviewed_by_id = current_user.id
    report.reviewed_at = datetime.utcnow()
    report.admin_note = request.form.get('admin_note', '').strip()
    if new_status in DAMAGE_STATUSES:
        report.status = new_status
        db.session.commit()
        flash(f'Damage report updated to {_status_badge(report.status)}.', 'success')
    return redirect(_ict_review_url('requests.damage_reports'))


@requests_bp.route('/damage-reports/<int:report_id>/delete', methods=['POST'])
@login_required
def delete_damage_report(report_id):
    report = DamageReport.query.get_or_404(report_id)
    if not _can_delete_damage(report):
        abort(403)
    db.session.delete(report)
    db.session.commit()
    flash('Damage report deleted.', 'success')
    if _show_all_requests():
        return redirect(_ict_review_url('requests.damage_reports'))
    return redirect(url_for('requests.damage_reports'))


@requests_bp.route('/damage-reports/download/csv')
@login_required
def damage_reports_csv():
    if current_user.role in ('admin', 'finance'):
        items = DamageReport.query.order_by(DamageReport.reported_at.desc()).all()
    else:
        items = DamageReport.query.filter_by(reported_by_id=current_user.id)\
            .order_by(DamageReport.reported_at.desc()).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Type', 'Asset Tag', 'Asset Name', 'Reported By', 'Priority', 'Status', 'Description', 'Date'])
    for r in items:
        writer.writerow([
            r.report_type, r.asset.tag if r.asset else '—', r.asset.name if r.asset else '—',
            r.reported_by.name, r.priority, r.status, r.description,
            r.reported_at.strftime('%d %b %Y'),
        ])
    response = make_response(output.getvalue())
    response.headers['Content-Type'] = 'text/csv; charset=utf-8'
    response.headers['Content-Disposition'] = 'attachment; filename=gr_damage_reports.csv'
    return response


@requests_bp.route('/damage-reports/download/pdf')
@login_required
def damage_reports_pdf():
    from pdf_utils import build_gr_pdf, build_pdf_table, pdf_response

    if current_user.role in ('admin', 'finance'):
        items = DamageReport.query.order_by(DamageReport.reported_at.desc()).all()
    else:
        items = DamageReport.query.filter_by(reported_by_id=current_user.id)\
            .order_by(DamageReport.reported_at.desc()).all()

    rows = [['Type', 'Asset', 'Reported By', 'Priority', 'Status', 'Date', 'Description']]
    for r in items:
        rows.append([
            r.report_type.title(), r.asset.tag if r.asset else '—',
            r.reported_by.name, r.priority.title(), r.status.replace('_', ' ').title(),
            r.reported_at.strftime('%d %b %Y'), (r.description or '')[:120],
        ])

    def body(doc):
        from pdf_utils import scaled_col_widths
        weights = [50, 70, 80, 45, 55, 50, 150]
        return [build_pdf_table(rows, scaled_col_widths(weights, doc.width))]

    return pdf_response(build_gr_pdf(body, report_title='Damage Reports'), 'gr_damage_reports.pdf')


# ─────────────────────────────────────────────
#  REQUEST STATUS & HISTORY
# ─────────────────────────────────────────────

def _user_asset_requests():
    return AssetRequest.query.filter_by(requested_by_id=current_user.id).all()


def _user_return_requests():
    return ReturnRequest.query.filter_by(requested_by_id=current_user.id).all()


def _user_repair_requests():
    return RepairRequest.query.filter_by(requested_by_id=current_user.id).all()


def _user_damage_reports():
    return DamageReport.query.filter_by(reported_by_id=current_user.id).all()


@requests_bp.route('/status')
@login_required
def request_status():
    if current_user.role == 'admin':
        return redirect(url_for('main.dashboard'))

    ar = _user_asset_requests()
    rr = _user_return_requests()
    rep = _user_repair_requests()
    dmg = _user_damage_reports()

    def count(items, status):
        return len([i for i in items if i.status == status])

    stats = {
        'asset_pending': count(ar, 'pending'),
        'asset_approved': count(ar, 'approved'),
        'return_pending': count(rr, 'pending'),
        'return_approved': count(rr, 'approved'),
        'repair_pending': count(rep, 'pending'),
        'repair_active': len([r for r in rep if r.status in ('approved', 'in_repair')]),
        'damage_pending': count(dmg, 'pending'),
    }

    recent = []
    for r in ar:
        recent.append({
            'type': 'Asset Request', 'ref': r.item_requested, 'status': r.status,
            'date': r.requested_at, 'note': r.admin_note,
            'asset': r.assigned_asset.tag if r.assigned_asset else None,
            'id': r.id, 'kind': 'asset',
            'can_cancel': r.status == 'pending',
        })
    for r in rr:
        recent.append({
            'type': 'Return Request', 'ref': r.asset.tag, 'status': r.status,
            'date': r.requested_at, 'note': r.admin_note, 'asset': r.asset.tag,
            'id': r.id, 'kind': 'return', 'can_cancel': False,
        })
    for r in rep:
        recent.append({
            'type': 'Repair Request', 'ref': r.asset.tag, 'status': r.status,
            'date': r.requested_at, 'note': r.admin_note, 'asset': r.asset.tag,
            'id': r.id, 'kind': 'repair',
            'can_cancel': r.status == 'pending',
        })
    for r in dmg:
        recent.append({
            'type': 'Damage Report', 'ref': r.report_type.title(), 'status': r.status,
            'date': r.reported_at, 'note': r.admin_note,
            'asset': r.asset.tag if r.asset else None,
            'id': r.id, 'kind': 'damage', 'can_cancel': False,
        })
    recent.sort(key=lambda x: x['date'], reverse=True)

    return render_template('requests/request_status.html', stats=stats, recent=recent[:20])


@requests_bp.route('/history')
@login_required
def request_history():
    history = []
    if current_user.role == 'admin':
        for r in AssetRequest.query.order_by(AssetRequest.requested_at.desc()).all():
            history.append(_history_row('Asset Request', r.requested_by.name, r.item_requested,
                                        r.status, r.requested_at, r.admin_note,
                                        r.assigned_asset.tag if r.assigned_asset else None))
        for r in ReturnRequest.query.order_by(ReturnRequest.requested_at.desc()).all():
            history.append(_history_row('Return', r.requested_by.name, r.asset.tag,
                                        r.status, r.requested_at, r.admin_note, r.asset.tag))
        for r in RepairRequest.query.order_by(RepairRequest.requested_at.desc()).all():
            history.append(_history_row('Repair', r.requested_by.name, r.asset.tag,
                                        r.status, r.requested_at, r.admin_note, r.asset.tag))
        for r in DamageReport.query.order_by(DamageReport.reported_at.desc()).all():
            history.append(_history_row('Damage', r.reported_by.name, r.report_type.title(),
                                        r.status, r.reported_at, r.admin_note,
                                        r.asset.tag if r.asset else None))
    else:
        for r in _user_asset_requests():
            history.append(_history_row('Asset Request', current_user.name, r.item_requested,
                                        r.status, r.requested_at, r.admin_note,
                                        r.assigned_asset.tag if r.assigned_asset else None,
                                        r.id, 'asset'))
        for r in _user_return_requests():
            history.append(_history_row('Return', current_user.name, r.asset.tag,
                                        r.status, r.requested_at, r.admin_note, r.asset.tag))
        for r in _user_repair_requests():
            history.append(_history_row('Repair', current_user.name, r.asset.tag,
                                        r.status, r.requested_at, r.admin_note, r.asset.tag,
                                        r.id, 'repair'))
        for r in _user_damage_reports():
            history.append(_history_row('Damage', current_user.name, r.report_type.title(),
                                        r.status, r.reported_at, r.admin_note,
                                        r.asset.tag if r.asset else None))

    history.sort(key=lambda x: x['date'], reverse=True)
    return render_template('requests/request_history.html', history=history)


def _history_row(rtype, who, ref, status, dt, note, asset_tag, item_id=None, kind=None):
    return {
        'type': rtype, 'who': who, 'ref': ref, 'status': status,
        'date': dt, 'note': note, 'asset': asset_tag,
        'id': item_id, 'kind': kind,
        'can_cancel': kind in ('asset', 'repair') and status == 'pending',
    }
