# 📘 Developer Issue & Task Tracker — Step-by-Step Implementation Manual

This document is the master step-by-step implementation guide for building the **Enterprise Software Issue & Task Tracker** using Flask + raw PostgreSQL (`psycopg2`, no ORM) + Bootstrap 5. It contains full descriptions and code structures for every file so you and your Vijay can build and understand it.

---

## 🛠️ Step 1: Database Schema (`sql/01_schema.sql`)
*Target File*: `sql/01_schema.sql` (Vikas's Task)

This file sets up the foundation of the relational database.

### 1.1 Custom ENUM Types
Instead of text strings, we use database-level Enums to enforce data integrity:
```sql
CREATE TYPE user_role AS ENUM ('developer', 'manager', 'reporter');
CREATE TYPE ticket_status AS ENUM ('open', 'in_progress', 'in_review', 'resolved', 'closed');
CREATE TYPE ticket_priority AS ENUM ('low', 'medium', 'high', 'critical');
CREATE TYPE ticket_type AS ENUM ('bug', 'feature', 'task');
```

### 1.2 Table Definitions & Constraints
1. **`users`**: Unique usernames and emails. The password column must be `VARCHAR(256)` because Werkzeug password hashes are ~160+ characters.
2. **`tickets`**:
   * Uses `ticket_status`, `ticket_priority`, and `ticket_type` enums.
   * `assignee_id` is a foreign key pointing to `users(id)`. Uses `ON DELETE SET NULL` so deleting a user does not delete the ticket (it just becomes unassigned).
   * `reporter_id` is a foreign key pointing to `users(id)`. Uses `ON DELETE CASCADE`.
   * `parent_ticket_id` is a self-referential foreign key pointing to `tickets(id)` to allow subtasks.
3. **`comments`**: Links to `tickets` and `users`. Uses `ON DELETE CASCADE` so deleting a ticket cleans up all comments.
4. **`tags`**: Stores unique tag names (e.g., `bug`, `refactor`).
5. **`ticket_tags`**: Many-to-many join table linking `tickets` and `tags` via composite primary key `(ticket_id, tag_id)`.
6. **`audit_logs`**: Logs status updates for historical timelines.

### 1.3 Performance Indexes
Add indexes to columns filtered or joined on in queries:
```sql
CREATE INDEX idx_tickets_status ON tickets(status);
CREATE INDEX idx_tickets_assignee ON tickets(assignee_id);
CREATE INDEX idx_comments_ticket ON comments(ticket_id);
CREATE INDEX idx_audit_ticket ON audit_logs(ticket_id);
```

---

## 🔄 Step 2: Database State Machine & Triggers (`sql/02_triggers.sql`)
*Target File*: `sql/02_triggers.sql` (Vikas's Task)

We enforce the business logic of ticket states and audit logging directly inside the database using PL/pgSQL triggers.

### 2.1 State Transition Trigger
A `BEFORE UPDATE` trigger checks if the transition is legal before allowing the update:
* `open` ➔ `in_progress` (Requires `assignee_id IS NOT NULL`)
* `in_progress` ➔ `in_review` or `open`
* `in_review` ➔ `resolved` or `in_progress`
* `resolved` ➔ `closed`
* `closed` ➔ `open` (Allowed; role verification is done in Flask)

```sql
CREATE OR REPLACE FUNCTION fn_enforce_ticket_transition()
RETURNS TRIGGER AS $$
BEGIN
    -- Only check if status changed
    IF OLD.status IS DISTINCT FROM NEW.status THEN
        IF OLD.status = 'open' AND NEW.status = 'in_progress' AND NEW.assignee_id IS NULL THEN
            RAISE EXCEPTION 'A developer must be assigned to start progress.';
        ELSIF OLD.status = 'open' AND NEW.status = 'in_progress' THEN
            -- OK
        ELSIF OLD.status = 'in_progress' AND NEW.status IN ('in_review', 'open') THEN
            -- OK
        ELSIF OLD.status = 'in_review' AND NEW.status IN ('resolved', 'in_progress') THEN
            -- OK
        ELSIF OLD.status = 'resolved' AND NEW.status = 'closed' THEN
            -- OK
        ELSIF OLD.status = 'closed' AND NEW.status = 'open' THEN
            -- OK (Flask will check if current user is manager)
        ELSE
            RAISE EXCEPTION 'Invalid status transition from % to %', OLD.status, NEW.status;
        END IF;
    END IF;
    
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_ticket_transition
BEFORE UPDATE ON tickets
FOR EACH ROW
EXECUTE FUNCTION fn_enforce_ticket_transition();
```

### 2.2 Audit Logging Trigger
An `AFTER UPDATE` trigger automatically records status changes:
```sql
CREATE OR REPLACE FUNCTION fn_log_status_change()
RETURNS TRIGGER AS $$
BEGIN
    IF OLD.status IS DISTINCT FROM NEW.status THEN
        INSERT INTO audit_logs (ticket_id, action, old_value, new_value)
        VALUES (NEW.id, 'status_change', OLD.status::text, NEW.status::text);
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_log_status_change
AFTER UPDATE ON tickets
FOR EACH ROW
EXECUTE FUNCTION fn_log_status_change();
```

---

## 📊 Step 3: SQL Views & Seeding (`sql/03_views.sql` & `seed.py`)
*Target Files*: `sql/03_views.sql`, `seed.py` (Vikas's Tasks)

### 3.1 SQL Views
1. **`v_workload_summary`**:
   ```sql
   CREATE OR REPLACE VIEW v_workload_summary AS
   SELECT u.id, u.username, u.role,
          COUNT(t.id) AS total_tickets,
          COUNT(t.id) FILTER (WHERE t.status != 'closed' AND t.status != 'resolved') AS active_tickets
   FROM users u
   LEFT JOIN tickets t ON u.id = t.assignee_id
   GROUP BY u.id, u.username, u.role;
   ```
2. **`v_overdue_tickets`**:
   ```sql
   CREATE OR REPLACE VIEW v_overdue_tickets AS
   SELECT * FROM tickets
   WHERE due_date < CURRENT_DATE AND status NOT IN ('resolved', 'closed');
   ```

### 3.2 User Seeder (`seed.py`)
This script inserts users with encrypted password hashes:
* Use `werkzeug.security.generate_password_hash` to encrypt passwords.
* Query structure:
  ```python
  hashed_password = generate_password_hash("password123")
  cursor.execute(
      "INSERT INTO users (username, email, password, role) VALUES (%s, %s, %s, %s) ON CONFLICT (username) DO NOTHING",
      ("dev_vikas", "vikas@example.com", hashed_password, "developer")
  )
  ```

---

## 🐍 Step 4: Flask Connection Pooling (`app/db.py`)
*Target File*: `app/db.py` (Vikas's Task)

We manage database connections concurrently without using an ORM.

### 4.1 Threaded Connection Pool
Initialize a pool at app startup using `psycopg2.pool.ThreadedConnectionPool`:
* **`init_pool(app)`**: Creates the connection pool using configuration parameters.
* **`get_db()`**: Fetches a single connection from the pool and stores it in Flask's request context `g.db_conn` (so it's shared during a single HTTP request).
* **`close_db(exception)`**: Runs automatically on teardown to return the connection back to the pool.

### 4.2 Raw SQL Helper Functions
Create convenience helpers to write clean Python:
* **`query(sql, params=None, one=False)`**: Executes a `SELECT` query, converting the output into dictionaries using `psycopg2.extras.RealDictCursor`.
* **`execute(sql, params=None)`**: Executes `INSERT`, `UPDATE`, or `DELETE` statements, commits the changes, and returns fetched results (e.g. for `RETURNING` clauses).

---

## 🔒 Step 5: Sessions & RBAC Decorators (`app/decorators.py`)
*Target File*: `app/decorators.py` (Vikas's Task)

Secure routes by wrapping handlers.

### 5.1 Login Required
```python
from functools import wraps
from flask import session, redirect, url_for, flash, g

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash("Please log in to access this page.", "warning")
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function
```

### 5.2 Role-Based Access Control (RBAC)
```python
def role_required(*roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not g.user or g.user['role'] not in roles:
                flash("You are not authorized to access this resource.", "danger")
                return redirect(url_for('dashboard.index'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator
```

---

## 🔐 Step 6: Authentication Blueprint (`app/auth.py`)
*Target File*: `app/auth.py` (Vikas's Task)

Implement register, login, and session teardown:
* **Register**: GET renders form, POST reads inputs, hashes the password, and runs `INSERT INTO users`.
* **Login**: GET renders form, POST verifies password hash via `check_password_hash`. If match, saves `session['user_id'] = user['id']`.
* **Session Loader**: Run a `@auth_bp.before_app_request` middleware to load `g.user` on every page request.

---

## 🎟️ Step 7: Core Views & Dashboard (`app/routes/` & templates)
*Target Files*: `app/routes/dashboard.py`, `app/routes/tickets.py` (Vikas's Tasks)

### 7.1 Dashboard KPIs
The landing page running at `/` executes these aggregated queries:
1. Total Open: `SELECT COUNT(*) FROM tickets WHERE status = 'open'`
2. Critical Unresolved: `SELECT COUNT(*) FROM tickets WHERE priority = 'critical' AND status NOT IN ('resolved', 'closed')`
3. Resolved this Week: `SELECT COUNT(*) FROM tickets WHERE status = 'resolved' AND updated_at >= date_trunc('week', NOW())`
4. User Active (Devs only): `SELECT COUNT(*) FROM tickets WHERE assignee_id = %s AND status NOT IN ('resolved', 'closed')`

### 7.2 Ticket Filtering & RBAC CRUD
* **Ticket List**: Query `SELECT t.*, u.username AS assignee_name FROM tickets t LEFT JOIN users u ON t.assignee_id = u.id` with parameters for search and page offsets.
* **Assign Ticket**:
  * Managers: Assign to anyone.
  * Developers: Self-assign only (`assignee_id = g.user['id']`).
  * Reporters: Blocked.
* **Delete Ticket**: Only allow if `g.user['role'] == 'manager'`.

---

## 👥 Step 8: Vijay Tasks (Detailed Implementation)

Vijay is responsible for coding the comment routes, editing forms, user profile pages, and ticket detail views.

### 📝 Step 8.1: Comments Backend & Database Logic
* **Target File**: `app/routes/comments.py`
* **Goal**: Enable comments on tickets, ensuring secure addition and deletion rules.

#### Step-by-Step Backend Flow:
1. **`add_comment(ticket_id)`**:
   * Retrieve the comment body text: `body = request.form.get("body", "").strip()`
   * Validate that the comment is not empty. If empty, flash an error message (`flash("Comment cannot be empty.", "danger")`) and redirect back to `tickets.detail`.
   * Insert the comment into the database:
     ```sql
     INSERT INTO comments (ticket_id, user_id, body) VALUES (%s, %s, %s)
     ```
     *Params*: `ticket_id`, `g.user["id"]` (logged-in user), and `body`.
   * Redirect back to the ticket detail page.
2. **`delete_comment(ticket_id, comment_id)`**:
   * Retrieve the comment first to check ownership:
     ```sql
     SELECT * FROM comments WHERE id = %s AND ticket_id = %s
     ```
   * Enforce security rules: A comment can only be deleted if:
     * The logged-in user is the author of the comment (`comment["user_id"] == g.user["id"]`), OR
     * The logged-in user has the `manager` role (`g.user["role"] == "manager"`).
     * If neither condition is met, raise a `403 Forbidden` error using Flask's `abort(403)`.
   * Execute the delete:
     ```sql
     DELETE FROM comments WHERE id = %s
     ```
   * Redirect back to the ticket detail page.

---

### 📂 Step 8.2: Ticket Creation & Editing Form
* **Target File**: `app/templates/tickets/form.html`
* **Goal**: Build a unified Form template for both creating new tickets and editing existing ones.

#### Step-by-Step Frontend Layout:
1. **Form Configuration**:
   * Determine the action dynamically:
     * If `mode == 'edit'`, the action is `url_for('tickets.edit', ticket_id=ticket.id)`.
     * If `mode == 'create'`, the action is `url_for('tickets.create')`.
2. **Fields**:
   * **Title**: Text input, `name="title"`, marked as `required`. Pre-populate with `{{ ticket.title if mode == 'edit' else '' }}`.
   * **Description**: Textarea, `name="description"`. Pre-populate between the tags with `{{ ticket.description if mode == 'edit' else '' }}`.
   * **Priority**: Dropdown `<select name="priority">`. Options: `low`, `medium`, `high`, `critical`. Mark the option as `selected` if it matches `ticket.priority`.
   * **Type**: Dropdown `<select name="type">`. Options: `bug`, `feature`, `task`. Mark option as `selected` if it matches `ticket.type`.
   * **Due Date**: Date input, `name="due_date"`. Pre-populate with `{{ ticket.due_date if mode == 'edit' and ticket.due_date else '' }}`.

---

### 👤 Step 8.3: User Profile Page
* **Target File**: `app/routes/profile.py` & `app/templates/profile.html`
* **Goal**: Display logged-in user details and query their ticket involvement metrics.

#### Step-by-Step Backend Flow:
1. Write a SQL query counting the tickets where the user is either the assignee or the reporter:
   ```sql
   SELECT
       COUNT(*)                                              AS total_tickets,
       COUNT(*) FILTER (WHERE status = 'open')               AS open_tickets,
       COUNT(*) FILTER (WHERE status = 'in_progress')        AS in_progress,
       COUNT(*) FILTER (WHERE status = 'resolved')           AS resolved,
       COUNT(*) FILTER (WHERE status = 'closed')             AS closed
   FROM tickets
   WHERE reporter_id = %s OR assignee_id = %s
   ```
2. Run this query using `query(sql, (g.user["id"], g.user["id"]), one=True)`.
3. Pass the resulting dictionary to the template: `render_template("profile.html", stats=user_stats)`.

#### Step-by-Step Template Layout:
1. **User Profile Card**: Display user properties stored in the `current_user` object:
   * Username: `{{ current_user.username }}`
   * Email: `{{ current_user.email }}`
   * Role: `{{ current_user.role | capitalize }}` (styled with a custom Bootstrap badge)
2. **Stats Panel**: Display statistics from the `stats` dictionary (`stats.total_tickets`, `stats.open_tickets`, `stats.in_progress`, etc.) using progress bars or cards to show work distribution.

---

### 🔍 Step 8.4: Ticket Detail Page
* **Target File**: `app/templates/tickets/detail.html`
* **Goal**: Render the full details of a ticket, its comments, its status change history (audit log), and allow interactions.

#### Step-by-Step Template Layout:
1. **Ticket Details Card**:
   * Render title, description, created/updated timestamps, and due date.
   * Render status and priority badges using the color palettes from the README.
2. **Action Controls (RBAC-aware)**:
   * **Assignee Dropdown**: A dropdown allowing managers to assign the ticket to *any* user, developers to self-assign, and reporters to see only the current assignee text.
   * **Status Dropdown**: Allows changing ticket status. Options should follow the transition state machine. Changes submit to `POST /tickets/<id>/status`.
   * **Edit/Delete Buttons**: Only visible to users authorized to edit or delete the ticket (e.g. managers can delete, developer/reporter cannot).
3. **Comments Section**:
   * Loop through comments: `{% for comment in comments %}`.
   * Display comment author, date, and body text.
   * If the logged-in user is the author or is a manager, show a "Delete" button that forms POSTs to `/tickets/<ticket_id>/comments/<comment_id>/delete`.
   * Display a clean textarea form at the bottom submitting to `POST /tickets/<ticket_id>/comments/` to add new comments.
4. **Audit Log / Activity History**:
   * Loop through the audit logs list: `{% for log in audit_log %}`.
   * Render a clean list or timeline detailing:
     * User who made the change (`log.changed_by_name`)
     * Action performed (`log.action`)
     * Old value (`log.old_value`) and New value (`log.new_value`)
     * Date of the event (`log.created_at`)
