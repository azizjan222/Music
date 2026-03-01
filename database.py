import sqlite3

def init_db():
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            lang TEXT DEFAULT NULL,
            vip_status INTEGER DEFAULT 0
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS cache (
            query TEXT PRIMARY KEY,
            file_id TEXT
        )
    ''')
    conn.commit()
    conn.close()

def add_user(user_id):
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    cursor.execute('INSERT OR IGNORE INTO users (user_id) VALUES (?)', (user_id,))
    conn.commit()
    conn.close()

def set_lang(user_id, lang):
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET lang = ? WHERE user_id = ?', (lang, user_id))
    conn.commit()
    conn.close()

def get_lang(user_id):
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    cursor.execute('SELECT lang FROM users WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result and result[0] else None

def get_cache(query):
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    cursor.execute('SELECT file_id FROM cache WHERE query = ?', (query.lower(),))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else None

def add_cache(query, file_id):
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    cursor.execute('INSERT OR REPLACE INTO cache (query, file_id) VALUES (?, ?)', (query.lower(), file_id))
    conn.commit()
    conn.close()
