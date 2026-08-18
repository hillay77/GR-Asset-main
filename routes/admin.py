from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user
from models import AssetCategory, Project, Vendor, Asset
from extensions import db
from functools import wraps

admin_bp = Blueprint('admin', __name__)


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'admin':
            abort(403)
        return f(*args, **kwargs)
    return decorated


# ── Categories ─────────────────────────────────────────────────────────────
@admin_bp.route('/categories')
@login_required
@admin_required
def categories():
    cats = AssetCategory.query.order_by(AssetCategory.name).all()
    return render_template('admin/categories.html', cats=cats)


@admin_bp.route('/categories/new', methods=['POST'])
@login_required
@admin_required
def category_new():
    code = request.form['code'].strip().upper()
    if AssetCategory.query.filter_by(code=code).first():
        flash('Category code already exists.', 'error')
        return redirect(url_for('admin.categories'))
    cat = AssetCategory(
        name=request.form['name'].strip(),
        code=code,
        description=request.form.get('description', '').strip()
    )
    db.session.add(cat)
    db.session.commit()
    flash('Category added.', 'success')
    return redirect(url_for('admin.categories'))


@admin_bp.route('/categories/<int:cat_id>/edit', methods=['POST'])
@login_required
@admin_required
def category_edit(cat_id):
    cat = AssetCategory.query.get_or_404(cat_id)
    cat.name        = request.form['name'].strip()
    cat.code        = request.form['code'].strip().upper()
    cat.description = request.form.get('description', '').strip()
    db.session.commit()
    flash('Category updated.', 'success')
    return redirect(url_for('admin.categories'))


@admin_bp.route('/categories/<int:cat_id>/delete', methods=['POST'])
@login_required
@admin_required
def category_delete(cat_id):
    cat = AssetCategory.query.get_or_404(cat_id)
    if cat.assets.count() > 0:
        flash('Cannot delete: category has assets assigned.', 'error')
        return redirect(url_for('admin.categories'))
    db.session.delete(cat)
    db.session.commit()
    flash('Category deleted.', 'success')
    return redirect(url_for('admin.categories'))


# ── Projects / Countries ─────────────────────────────────────────────────────
@admin_bp.route('/projects')
@admin_bp.route('/countries', endpoint='countries')
@login_required
@admin_required
def projects():
    projects = Project.query.order_by(Project.name).all()
    return render_template('admin/projects.html', projects=projects)


@admin_bp.route('/projects/new', methods=['POST'])
@admin_bp.route('/countries/new', methods=['POST'], endpoint='countries_new')
@login_required
@admin_required
def project_new():
    code = request.form['code'].strip().upper()
    if Project.query.filter_by(code=code).first():
        flash('Country code already exists.', 'error')
        return redirect(url_for('admin.countries'))
    proj = Project(
        code=code,
        name=request.form['name'].strip(),
        description=request.form.get('description', '').strip(),
        year=request.form.get('year', '').strip(),
        status=request.form.get('status', 'active')
    )
    db.session.add(proj)
    db.session.commit()
    flash('Project added.', 'success')
    return redirect(url_for('admin.projects'))


@admin_bp.route('/projects/<int:proj_id>/edit', methods=['POST'])
@admin_bp.route('/countries/<int:proj_id>/edit', methods=['POST'], endpoint='countries_edit')
@login_required
@admin_required
def project_edit(proj_id):
    proj = Project.query.get_or_404(proj_id)
    proj.code        = request.form['code'].strip().upper()
    proj.name        = request.form['name'].strip()
    proj.description = request.form.get('description', '').strip()
    proj.year        = request.form.get('year', '').strip()
    proj.status      = request.form.get('status', proj.status)
    db.session.commit()
    flash('Country updated.', 'success')
    return redirect(url_for('admin.countries'))


@admin_bp.route('/projects/<int:proj_id>/delete', methods=['POST'])
@admin_bp.route('/countries/<int:proj_id>/delete', methods=['POST'], endpoint='countries_delete')
@login_required
@admin_required
def project_delete(proj_id):
    proj = Project.query.get_or_404(proj_id)
    if proj.assets.count() > 0:
        flash('Cannot delete: country has assets assigned.', 'error')
        return redirect(url_for('admin.countries'))
    db.session.delete(proj)
    db.session.commit()
    flash('Country deleted.', 'success')
    return redirect(url_for('admin.countries'))


# ── Vendors ────────────────────────────────────────────────────────────────
@admin_bp.route('/vendors')
@login_required
@admin_required
def vendors():
    vendors = Vendor.query.order_by(Vendor.name).all()
    return render_template('admin/vendors.html', vendors=vendors)


@admin_bp.route('/vendors/new', methods=['POST'])
@login_required
@admin_required
def vendor_new():
    vendor = Vendor(
        name=request.form['name'].strip(),
        contact=request.form.get('contact', '').strip(),
        email=request.form.get('email', '').strip(),
        address=request.form.get('address', '').strip()
    )
    db.session.add(vendor)
    db.session.commit()
    flash('Vendor added.', 'success')
    return redirect(url_for('admin.vendors'))


@admin_bp.route('/vendors/<int:vendor_id>/edit', methods=['POST'])
@login_required
@admin_required
def vendor_edit(vendor_id):
    v = Vendor.query.get_or_404(vendor_id)
    v.name    = request.form['name'].strip()
    v.contact = request.form.get('contact', '').strip()
    v.email   = request.form.get('email', '').strip()
    v.address = request.form.get('address', '').strip()
    db.session.commit()
    flash('Vendor updated.', 'success')
    return redirect(url_for('admin.vendors'))


@admin_bp.route('/vendors/<int:vendor_id>/delete', methods=['POST'])
@login_required
@admin_required
def vendor_delete(vendor_id):
    v = Vendor.query.get_or_404(vendor_id)
    if v.assets.count() > 0:
        flash('Cannot delete: vendor has supplied assets.', 'error')
        return redirect(url_for('admin.vendors'))
    db.session.delete(v)
    db.session.commit()
    flash('Vendor deleted.', 'success')
    return redirect(url_for('admin.vendors'))
