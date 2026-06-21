from flask import Blueprint, render_template, request, redirect, url_for, flash, g, abort
from app.db import query, execute
from app.decorators import login_required, role_required

tickets_bp = Blueprint('tickets', __name__, url_prefix='/tickets')

@tickets_bp.route('/')
@login_required
def index():
    search = request.args.get('search', '').strip()
    status_filter = request.args.get('status', '').strip()
    priority_filter = request.args.get('priority', '').strip()
    
    sql = """
        SELECT t.*, u.username AS assignee_name, r.username AS reporter_name 
        FROM tickets t 
        LEFT JOIN users u ON t.assignee_id = u.id
        LEFT JOIN users r ON t.reporter_id = r.id
        WHERE 1=1
    """
    params = []
    
    if search:
        sql += " AND (t.title ILIKE %s OR t.description ILIKE %s)"
        params.extend([f"%{search}%", f"%{search}%"])
        
    if status_filter:
        sql += " AND t.status = %s"
        params.append(status_filter)
        
    if priority_filter:
        sql += " AND t.priority = %s"
        params.append(priority_filter)
        
    sql += " ORDER BY t.created_at DESC"
    tickets = query(sql, params)
    
    return render_template('tickets/list.html', tickets=tickets, search=search, status_filter=status_filter, priority_filter=priority_filter)

@tickets_bp.route('/<int:ticket_id>')
@login_required
def detail(ticket_id):
    ticket = query("""
        SELECT t.*, u.username AS assignee_name, r.username AS reporter_name 
        FROM tickets t
        LEFT JOIN users u ON t.assignee_id = u.id
        LEFT JOIN users r ON t.reporter_id = r.id
        WHERE t.id = %s
    """, (ticket_id,), one=True)
    
    if not ticket:
        abort(404)
        
    # Comments & Audit Log - these will be rendered by Vijay's templates
    comments = query("""
        SELECT c.*, u.username 
        FROM comments c
        JOIN users u ON c.user_id = u.id
        WHERE c.ticket_id = %s
        ORDER BY c.created_at ASC
    """, (ticket_id,))
    
    audit_log = query("""
        SELECT a.*, u.username AS changed_by_name 
        FROM audit_logs a
        LEFT JOIN users u ON a.changed_by = u.id
        WHERE a.ticket_id = %s
        ORDER BY a.changed_at DESC
    """, (ticket_id,))
    
    users = query("SELECT id, username, role FROM users ORDER BY username ASC")
    
    return render_template(
        'tickets/detail.html', 
        ticket=ticket, 
        comments=comments, 
        audit_log=audit_log,
        users=users
    )

@tickets_bp.route('/create', methods=('GET', 'POST'))
@login_required
def create():
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        priority = request.form.get('priority', 'medium')
        ticket_type = request.form.get('type', 'task')
        due_date = request.form.get('due_date') or None
        assignee_id = request.form.get('assignee_id')
        
        if not title:
            flash("Title is required.", "danger")
            return redirect(url_for('tickets.create'))
            
        if assignee_id == '':
            assignee_id = None
            
        try:
            res = execute(
                """
                INSERT INTO tickets (title, description, priority, type, due_date, assignee_id, reporter_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id
                """,
                (title, description, priority, ticket_type, due_date, assignee_id, g.user['id'])
            )
            flash("Ticket created successfully.", "success")
            return redirect(url_for('tickets.detail', ticket_id=res[0]['id']))
        except Exception as e:
            flash(f"Error creating ticket: {e}", "danger")
            
    users = query("SELECT id, username, role FROM users ORDER BY username ASC")
    return render_template('tickets/form.html', mode='create', ticket=None, users=users)

@tickets_bp.route('/<int:ticket_id>/edit', methods=('GET', 'POST'))
@login_required
def edit(ticket_id):
    ticket = query("SELECT * FROM tickets WHERE id = %s", (ticket_id,), one=True)
    if not ticket:
        abort(404)
        
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        priority = request.form.get('priority', 'medium')
        ticket_type = request.form.get('type', 'task')
        due_date = request.form.get('due_date') or None
        assignee_id = request.form.get('assignee_id')
        
        if not title:
            flash("Title is required.", "danger")
            return redirect(url_for('tickets.edit', ticket_id=ticket_id))
            
        if assignee_id == '':
            assignee_id = None
            
        try:
            execute(
                """
                UPDATE tickets 
                SET title = %s, description = %s, priority = %s, type = %s, due_date = %s, assignee_id = %s
                WHERE id = %s
                """,
                (title, description, priority, ticket_type, due_date, assignee_id, ticket_id)
            )
            flash("Ticket updated successfully.", "success")
            return redirect(url_for('tickets.detail', ticket_id=ticket_id))
        except Exception as e:
            flash(f"Error updating ticket: {e}", "danger")
            
    users = query("SELECT id, username, role FROM users ORDER BY username ASC")
    return render_template('tickets/form.html', mode='edit', ticket=ticket, users=users)

@tickets_bp.route('/<int:ticket_id>/assign', methods=('POST',))
@login_required
def assign(ticket_id):
    ticket = query("SELECT * FROM tickets WHERE id = %s", (ticket_id,), one=True)
    if not ticket:
        abort(404)
        
    new_assignee_id = request.form.get('assignee_id')
    if new_assignee_id == '':
        new_assignee_id = None
    else:
        new_assignee_id = int(new_assignee_id)
        
    # Enforce assignment RBAC rules
    if g.user['role'] == 'reporter':
        # Reporters cannot assign tickets
        flash("Reporters are not authorized to assign tickets.", "danger")
        return redirect(url_for('tickets.detail', ticket_id=ticket_id))
        
    elif g.user['role'] == 'developer':
        # Developers can only self-assign
        if new_assignee_id is not None and new_assignee_id != g.user['id']:
            flash("Developers can only assign tickets to themselves.", "danger")
            return redirect(url_for('tickets.detail', ticket_id=ticket_id))
            
    # If role is manager, they can assign to anyone (or if developers self-assign)
    try:
        execute(
            "UPDATE tickets SET assignee_id = %s WHERE id = %s",
            (new_assignee_id, ticket_id)
        )
        flash("Ticket assignee updated successfully.", "success")
    except Exception as e:
        flash(f"Database error: {e}", "danger")
        
    return redirect(url_for('tickets.detail', ticket_id=ticket_id))

@tickets_bp.route('/<int:ticket_id>/status', methods=('POST',))
@login_required
def update_status(ticket_id):
    ticket = query("SELECT * FROM tickets WHERE id = %s", (ticket_id,), one=True)
    if not ticket:
        abort(404)
        
    new_status = request.form.get('status')
    
    # Enforce 'closed' transition only for manager
    if new_status == 'closed' and g.user['role'] != 'manager':
        flash("Only managers can close tickets.", "danger")
        return redirect(url_for('tickets.detail', ticket_id=ticket_id))
        
    try:
        # We need to set the current user who changed the state so our audit log can reference it.
        # But wait, our trigger fn_log_status_change runs on the database side and has no access to Flask's context.
        # So we update the ticket status AND changed_by on audit logs.
        # Wait, the trigger creates the audit log record automatically, but changed_by is set to NULL by default.
        # To populate changed_by, we can update the status AND then update the newly created audit log entry
        # or we can do it inside a SQL transaction.
        # Better yet, let's execute UPDATE tickets SET status = %s.
        execute("UPDATE tickets SET status = %s WHERE id = %s", (new_status, ticket_id))
        
        # Now update the audit log record that was created by the trigger to set changed_by!
        execute(
            """
            UPDATE audit_logs 
            SET changed_by = %s 
            WHERE ticket_id = %s AND changed_by IS NULL 
            ORDER BY changed_at DESC LIMIT 1
            """,
            (g.user['id'], ticket_id)
        )
        flash("Ticket status updated successfully.", "success")
    except Exception as e:
        # Check database trigger exception
        err_msg = str(e)
        if "A developer must be assigned" in err_msg:
            flash("Cannot start progress: A developer must be assigned first.", "danger")
        elif "Invalid status transition" in err_msg:
            flash("Invalid ticket status transition.", "danger")
        else:
            flash(f"Error updating status: {e}", "danger")
            
    return redirect(url_for('tickets.detail', ticket_id=ticket_id))

@tickets_bp.route('/<int:ticket_id>/delete', methods=('POST', 'GET'))
@role_required('manager')
def delete(ticket_id):
    execute("DELETE FROM tickets WHERE id = %s", (ticket_id,))
    flash("Ticket deleted successfully.", "success")
    return redirect(url_for('tickets.index'))
