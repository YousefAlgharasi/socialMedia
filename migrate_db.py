import sqlite3
from app.config import STORAGE_DIR

def migrate():
    db_path = STORAGE_DIR / 'scheduler.db'
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    columns_to_add = [
        ("avatar_url", "VARCHAR(500)"),
        ("followers_count", "VARCHAR(50) DEFAULT '0'"),
        ("views_count", "VARCHAR(50) DEFAULT '0'"),
        ("posts_count", "VARCHAR(50) DEFAULT '0'"),
        ("credentials_json", "TEXT")
    ]

    for col_name, col_type in columns_to_add:
        try:
            cur.execute(f"ALTER TABLE accounts ADD COLUMN {col_name} {col_type};")
            print(f"Added column {col_name}")
        except Exception as e:
            print(f"Column {col_name} already exists or error: {e}")

    conn.commit()
    conn.close()
    print("Migration finished!")

if __name__ == "__main__":
    migrate()
