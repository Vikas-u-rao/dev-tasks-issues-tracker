from werkzeug.security import generate_password_hash, check_password_hash

def hash_pass(password):
    """
    Securely hashes a password using Werkzeug's default hashing algorithm.
    """
    return generate_password_hash(password)

def verify_pass(hashed_password, password):
    """
    Verifies a password against its Werkzeug hash.
    """
    return check_password_hash(hashed_password, password)
