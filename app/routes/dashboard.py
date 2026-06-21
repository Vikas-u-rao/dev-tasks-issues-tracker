from flask import Blueprint, render_template, g
from app.db import query
from app.decorators import login_required

dashboard_bp = Blueprint('dashboard', __name__)

@dashboard_bp.route('/')
@login_required
def index():
    # 1. Total Open
    total_open = query("SELECT COUNT(*) FROM tickets WHERE status = 'open'", one=True)['count']
    
    # 2. Critical Unresolved
    critical_unresolved = query(
        "SELECT COUNT(*) FROM tickets WHERE priority = 'critical' AND status NOT IN ('resolved', 'closed')",
        one=True
    )['count']
    
    # 3. Resolved this Week
    resolved_this_week = query(
        "SELECT COUNT(*) FROM tickets WHERE status = 'resolved' AND updated_at >= date_trunc('week', NOW())",
        one=True
    )['count']
    
    # 4. User Active (Devs only or user's assigned active tickets)
    user_active = 0
    if g.user:
        user_active = query(
            "SELECT COUNT(*) FROM tickets WHERE assignee_id = %s AND status NOT IN ('resolved', 'closed')",
            (g.user['id'],),
            one=True
        )['count']
        
    # Get active workload summary from the SQL View
    workload_summary = query("SELECT * FROM v_workload_summary ORDER BY active_tickets DESC")
    
    # Get overdue tickets from the SQL View
    overdue_tickets = query("SELECT * FROM v_overdue_tickets ORDER BY due_date ASC")

    return render_template(
        'dashboard/index.html',
        total_open=total_open,
        critical_unresolved=critical_unresolved,
        resolved_this_week=resolved_this_week,
        user_active=user_active,
        workload_summary=workload_summary,
        overdue_tickets=overdue_tickets
    )
