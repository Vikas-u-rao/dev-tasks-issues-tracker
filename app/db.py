import os
from flask import g, current_app
import psycopg2
import psycopg2.pool
import psycopg2.extras

db_pool = None

def init_pool(app):
    """
    Initializes a ThreadedConnectionPool for PostgreSQL.
    """
    global db_pool
    database_url = app.config.get("DATABASE_URL") or os.getenv("DATABASE_URL")
    if not database_url:
        raise ValueError("DATABASE_URL is not set in application config or environment variables.")
    
    # Initialize the connection pool
    db_pool = psycopg2.pool.ThreadedConnectionPool(
        minconn=1,
        maxconn=20,
        dsn=database_url
    )
    
    # Register teardown function to clean up database connections
    app.teardown_appcontext(close_db)

def get_db():
    """
    Retrieves a connection from the pool and stores it in Flask's application context `g`.
    Reusable within a single request context.
    """
    if 'db_conn' not in g:
        if db_pool is None:
            raise RuntimeError("Database connection pool is not initialized. Call init_pool(app) first.")
        g.db_conn = db_pool.getconn()
    return g.db_conn

def close_db(exception=None):
    """
    Returns the request's connection back to the pool on request context teardown.
    """
    db_conn = g.pop('db_conn', None)
    if db_conn is not None:
        db_pool.putconn(db_conn)

def query(sql, params=None, one=False):
    """
    Executes a SELECT query and returns the results as dictionaries.
    """
    conn = get_db()
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(sql, params or ())
        if one:
            return cur.fetchone()
        return cur.fetchall()

def execute(sql, params=None):
    """
    Executes an INSERT, UPDATE, or DELETE query, commits the changes, 
    and returns any results (e.g. for RETURNING clauses).
    """
    conn = get_db()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params or ())
            conn.commit()
            try:
                # If there are returned rows (e.g. RETURNING clause)
                if cur.description:
                    return cur.fetchall()
            except psycopg2.ProgrammingError:
                pass
            return None
    except Exception as e:
        conn.rollback()
        raise e
