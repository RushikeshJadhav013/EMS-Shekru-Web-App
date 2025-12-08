"""
Migration script to create task_comments table with file support
Run this script to update the database schema
"""
import sqlite3

def create_and_update_table():
    conn = sqlite3.connect('attendance.db')
    cursor = conn.cursor()
    
    # Check if table exists
    cursor.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='table' AND name='task_comments'
    """)
    table_exists = cursor.fetchone() is not None
    
    if not table_exists:
        print("Creating task_comments table...")
        cursor.execute('''
            CREATE TABLE task_comments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                comment TEXT,
                file_url VARCHAR(500),
                file_name VARCHAR(255),
                file_type VARCHAR(100),
                file_size INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (task_id) REFERENCES tasks(task_id) ON DELETE CASCADE,
                FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
            )
        ''')
        print("✓ Created task_comments table with file support")
    else:
        print("task_comments table exists, adding file columns...")
        
        # Get existing columns
        cursor.execute("PRAGMA table_info(task_comments)")
        existing_columns = [row[1] for row in cursor.fetchall()]
        
        # Add file columns if they don't exist
        if 'file_url' not in existing_columns:
            try:
                cursor.execute('ALTER TABLE task_comments ADD COLUMN file_url VARCHAR(500)')
                print("✓ Added file_url column")
            except sqlite3.OperationalError as e:
                print(f"⚠ file_url: {e}")
        else:
            print("✓ file_url column already exists")
        
        if 'file_name' not in existing_columns:
            try:
                cursor.execute('ALTER TABLE task_comments ADD COLUMN file_name VARCHAR(255)')
                print("✓ Added file_name column")
            except sqlite3.OperationalError as e:
                print(f"⚠ file_name: {e}")
        else:
            print("✓ file_name column already exists")
        
        if 'file_type' not in existing_columns:
            try:
                cursor.execute('ALTER TABLE task_comments ADD COLUMN file_type VARCHAR(100)')
                print("✓ Added file_type column")
            except sqlite3.OperationalError as e:
                print(f"⚠ file_type: {e}")
        else:
            print("✓ file_type column already exists")
        
        if 'file_size' not in existing_columns:
            try:
                cursor.execute('ALTER TABLE task_comments ADD COLUMN file_size INTEGER')
                print("✓ Added file_size column")
            except sqlite3.OperationalError as e:
                print(f"⚠ file_size: {e}")
        else:
            print("✓ file_size column already exists")
    
    conn.commit()
    conn.close()
    print("\n✅ Migration completed successfully!")

if __name__ == "__main__":
    print("Setting up task_comments table with file support...")
    create_and_update_table()
