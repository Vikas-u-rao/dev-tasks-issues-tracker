import os
import psycopg2
from dotenv import load_dotenv
from app.security import hash_pass

# Load environment variables from .env file
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

def seed_db():
    if not DATABASE_URL:
        print("DATABASE_URL environment variable is not set in .env")
        return

    try:
        # Connect to PostgreSQL database
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        
        print("Connected to database. Seeding users...")
        
        # Define users to seed
        users_to_seed = [
            ("dev_vikas", "vikas@example.com", "password123", "developer"),
            ("mgr_vijay", "vijay@example.com", "password123", "manager"),
            ("rep_reporter", "reporter@example.com", "password123", "reporter")
        ]
        
        for username, email, password, role in users_to_seed:
            hashed_password = hash_pass(password)
            cursor.execute(
                "INSERT INTO users (username, email, password, role) VALUES (%s, %s, %s, %s) ON CONFLICT (username) DO NOTHING",
                (username, email, hashed_password, role)
            )
            print(f"Seeded user: {username} as {role}")
            
        conn.commit()
        cursor.close()
        conn.close()
        print("Database seeding completed successfully.")
    except Exception as e:
        print(f"Error during seeding: {e}")

if __name__ == "__main__":
    seed_db()
