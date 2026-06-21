import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

def init_db():
    if not DATABASE_URL:
        print("DATABASE_URL is not set in .env")
        return
        
    try:
        print("Connecting to database...")
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        
        sql_files = [
            'sql/01_schema.sql',
            'sql/02_triggers.sql',
            'sql/03_views.sql'
        ]
        
        for file_path in sql_files:
            if os.path.exists(file_path):
                print(f"Executing SQL file: {file_path}...")
                with open(file_path, 'r', encoding='utf-8') as f:
                    sql = f.read()
                    cursor.execute(sql)
                conn.commit()
            else:
                print(f"Warning: File {file_path} not found.")
                
        print("Database schema initialization complete.")
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"Error initializing database: {e}")

if __name__ == '__main__':
    init_db()
