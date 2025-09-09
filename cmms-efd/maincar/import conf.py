import sqlite3
from sistems import config_with_interval

def exportar_sistems_a_sqlite(config_list, db_name="intDB.db"):
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()

    for item in config_list:
        cursor.execute('''
            INSERT INTO config_interval (
                name, measurement, field, asset_id,
                attribute, db_name, time_interval, salIndex
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            item.get("name"),
            item.get("measurement"),
            item.get("field"),
            item.get("asset_id"),
            item.get("attribute"),
            item.get("db_name"),
            item.get("time_interval"),
            item.get("salIndex")  # puede ser None
        ))

    conn.commit()
    conn.close()
    print(f"[✔] Se guardaron {len(config_list)} configuraciones en '{db_name}'.")

if __name__ == "__main__":
    exportar_sistems_a_sqlite(config_with_interval)
