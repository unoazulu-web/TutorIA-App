import sqlite3

def init_db():
    conn = sqlite3.connect("tatoeba_pairs.db")
    cursor = conn.cursor()

    # 1. Tabla FTS5 para búsqueda rápida de oraciones de Tatoeba (<10 ms)
    cursor.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS tatoeba_fts USING fts5(
            english_sentence,
            spanish_translation
        );
    """)

    # 2. Tabla para memoria de errores del estudiante y Repetición Espaciada (SRS)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS srs_memory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_error TEXT NOT NULL,
            recast_correction TEXT NOT NULL,
            cefr_level TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        );
    """)

    # Sembrado inicial de frases bilingües de Tatoeba (ejemplo representativo)
    cursor.execute("SELECT COUNT(*) FROM tatoeba_fts;")
    if cursor.fetchone()[0] == 0:
        sample_data = [
            ("I went to the market yesterday.", "Fui al mercado ayer."),
            ("Could you tell me how to get to the station?", "¿Podría decirme cómo llegar a la estación?"),
            ("I'm looking forward to working with you.", "Tengo muchas ganas de trabajar contigo."),
            ("She has been studying English for three years.", "Ella ha estado estudiando inglés durante tres años."),
            ("If I had known, I would have called you.", "Si lo hubiera sabido, te habría llamado.")
        ]
        cursor.executemany("""
            INSERT INTO tatoeba_fts (english_sentence, spanish_translation) 
            VALUES (?, ?);
        """, sample_data)
        conn.commit()

    conn.close()
    print("Base de datos tatoeba_pairs.db indexada correctamente.")

if __name__ == "__main__":
    init_db()