from flask import Blueprint, render_template, request, redirect, url_for, flash, session, g
from app.db import query, execute
from app.security import hash_pass, verify_pass

auth_bp = Blueprint('auth', __name__)

@auth_bp.before_app_request
def load_logged_in_user():
    """
    Runs before every request to load the logged-in user's details into the `g` context.
    """
    user_id = session.get('user_id')
    if user_id is None:
        g.user = None
    else:
        # Load user details from the database
        g.user = query("SELECT id, username, email, role FROM users WHERE id = %s", (user_id,), one=True)
        # Fallback if user doesn't exist anymore
        if not g.user:
            session.clear()

@auth_bp.route('/register', methods=('GET', 'POST'))
def register():
    if g.user:
        return redirect(url_for('dashboard.index'))
        
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        role = request.form.get('role', 'developer') # Default role is developer
        
        error = None
        if not username:
            error = 'Username is required.'
        elif not email:
            error = 'Email is required.'
        elif not password:
            error = 'Password is required.'
        
        if error is None:
            try:
                hashed_pw = hash_pass(password)
                execute(
                    "INSERT INTO users (username, email, password, role) VALUES (%s, %s, %s, %s)",
                    (username, email, hashed_pw, role)
                )
                flash("Registration successful. Please log in.", "success")
                return redirect(url_for('auth.login'))
            except Exception as e:
                # Typically unique constraint violations (e.g. duplicate username/email)
                error = f"Registration failed. Username or email might already be registered."
                
        flash(error, 'danger')
        
    return render_template('auth/register.html')

@auth_bp.route('/login', methods=('GET', 'POST'))
def login():
    if g.user:
        return redirect(url_for('dashboard.index'))
        
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        
        user = query("SELECT * FROM users WHERE username = %s", (username,), one=True)
        
        if user and verify_pass(user['password'], password):
            session.clear()
            session['user_id'] = user['id']
            flash(f"Welcome back, {user['username']}!", "success")
            return redirect(url_for('dashboard.index'))
            
        flash("Invalid username or password.", "danger")
        
    return render_template('auth/login.html')

@auth_bp.route('/logout')
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for('auth.login'))
