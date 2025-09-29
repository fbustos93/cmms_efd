import sqlite3
def createDB(db_name="intDB.db"):
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS efd_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    measurement TEXT NOT NULL,
    field TEXT NOT NULL,
    value REAL NOT NULL,
    asset_id TEXT NOT NULL,
    timestamp TEXT NOT NULL
)

    ''')
    conn.commit()
    conn.close()
    print(f"base de datos creada'{db_name}' creada")

if __name__== "__main__":
    createDB()
