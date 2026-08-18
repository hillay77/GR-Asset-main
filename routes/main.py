from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from models import Asset, User, Project, ReturnRecord, ReturnRequest, AssetCategory, AssetRequest, RepairRequest, DamageReport
from extensions import db
from sqlalchemy import func
from werkzeug.security import generate_password_hash, check_password_hash

main_bp = Blueprint('main', __name__)


@main_bp.route('/')
@main_bp.route('/dashboard')
@login_required
def dashboard():
    if current_user.is_staff_portal:
        my_assets = Asset.query.filter_by(
            assigned_to_id=current_user.id, status='active'
        ).all()
        my_returns = ReturnRecord.query.filter_by(
            user_id=current_user.id
        ).order_by(ReturnRecord.returned_at.desc()).all()
        total_value  = sum(float(a.price or 0) for a in my_assets)
        pending_rets = ReturnRequest.query.filter_by(
            requested_by_id=current_user.id, status='pending'
        ).all()
        pending_returns = {r.asset_id: r for r in pending_rets}
        my_asset_reqs = AssetRequest.query.filter_by(requested_by_id=current_user.id).all()
        my_repair_reqs = RepairRequest.query.filter_by(requested_by_id=current_user.id).all()
        pending_asset = len([r for r in my_asset_reqs if r.status == 'pending'])
        approved_asset = len([r for r in my_asset_reqs if r.status == 'approved'])
        pending_repair = len([r for r in my_repair_reqs if r.status == 'pending'])
        returned_count = len(my_returns)
        return render_template('dashboard_user.html',
                               my_assets=my_assets,
                               my_returns=my_returns,
                               total_value=total_value,
                               pending_returns=pending_returns,
                               pending_asset=pending_asset,
                               approved_asset=approved_asset,
                               pending_repair=pending_repair,
                               returned_count=returned_count)

    # Admin / Finance dashboard
    total_assets    = Asset.query.filter_by(status='active').count()
    total_value     = db.session.query(func.sum(Asset.price)).filter_by(status='active').scalar() or 0
    assigned        = Asset.query.filter(Asset.assigned_to_id.isnot(None), Asset.status=='active').count()
    unassigned      = total_assets - assigned
    active_projects = Project.query.filter_by(status='active').count()
    total_users     = User.query.filter_by(status='active').count()

    recent_assets = Asset.query.filter_by(status='active')\
        .order_by(Asset.created_at.desc()).limit(6).all()

    by_project = db.session.query(
        Project,
        func.count(Asset.id).label('count'),
        func.sum(Asset.price).label('total')
    ).outerjoin(Asset, Asset.project_id == Project.id)\
     .group_by(Project.id).all()

    by_condition = db.session.query(
        Asset.condition,
        func.count(Asset.id).label('count')
    ).filter_by(status='active').group_by(Asset.condition).all()

    by_category = db.session.query(
        AssetCategory.name,
        func.count(Asset.id).label('count'),
        func.sum(Asset.price).label('total')
    ).outerjoin(Asset, Asset.category_id == AssetCategory.id)\
     .group_by(AssetCategory.id)\
     .order_by(func.count(Asset.id).desc()).all()

    # Top 6 users by asset value
    by_user = db.session.query(
        User.name,
        func.count(Asset.id).label('count'),
        func.sum(Asset.price).label('total')
    ).join(Asset, Asset.assigned_to_id == User.id)\
     .filter(Asset.status == 'active')\
     .group_by(User.id)\
     .order_by(func.sum(Asset.price).desc()).limit(6).all()

    return render_template('dashboard_admin.html',
                           total_assets=total_assets,
                           total_value=total_value,
                           assigned=assigned,
                           unassigned=unassigned,
                           active_projects=active_projects,
                           total_users=total_users,
                           recent_assets=recent_assets,
                           by_project=by_project,
                           by_condition=by_condition,
                           by_category=by_category,
                           by_user=by_user)


# ─────────────────────────────────────────────
#  PROFILE — view & edit own details
# ─────────────────────────────────────────────
@main_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        name       = request.form.get('name', '').strip()
        email      = request.form.get('email', '').strip()
        department = request.form.get('department', '').strip()

        if not name:
            flash('Name cannot be empty.', 'error')
            return redirect(url_for('main.profile'))

        current_user.name       = name
        current_user.email      = email
        current_user.department = department
        db.session.commit()
        flash('✓ Profile updated successfully.', 'success')
        return redirect(url_for('main.profile'))

    my_assets = Asset.query.filter_by(
        assigned_to_id=current_user.id, status='active'
    ).all()
    return render_template('profile.html', my_assets=my_assets)


# ─────────────────────────────────────────────
#  CHANGE PASSWORD
# ─────────────────────────────────────────────
@main_bp.route('/privacy-policy')
def privacy_policy():
    return render_template('privacy_policy.html')


@main_bp.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    if request.method == 'POST':
        current_pw  = request.form.get('current_password', '')
        new_pw      = request.form.get('new_password', '')
        confirm_pw  = request.form.get('confirm_password', '')

        if not current_user.check_password(current_pw):
            flash('Current password is incorrect.', 'error')
            return redirect(url_for('main.change_password'))

        if len(new_pw) < 6:
            flash('New password must be at least 6 characters.', 'error')
            return redirect(url_for('main.change_password'))

        if new_pw != confirm_pw:
            flash('New passwords do not match.', 'error')
            return redirect(url_for('main.change_password'))

        if new_pw == current_pw:
            flash('New password must be different from your current password.', 'error')
            return redirect(url_for('main.change_password'))

        current_user.set_password(new_pw)
        db.session.commit()
        flash('✓ Password changed successfully.', 'success')
        return redirect(url_for('main.profile'))

    return render_template('change_password.html')
