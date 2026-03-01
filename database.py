import sqlite3

def init_db():
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, lang TEXT DEFAULT NULL)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS cache (
                        query TEXT PRIMARY KEY, 
                        file_id TEXT, 
                        title TEXT, 
                        download_count INTEGER DEFAULT 1)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS favorites (user_id INTEGER, query_key TEXT, UNIQUE(user_id, query_key))''')
    conn.commit()
    conn.close()

def add_user(user_id):
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    cursor.execute('INSERT OR IGNORE INTO users (user_id) VALUES (?)', (user_id,))
    conn.commit()
    conn.close()

def get_stats():
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM users')
    u_count = cursor.fetchone()[0]
    cursor.execute('SELECT COUNT(*) FROM cache')
    c_count = cursor.fetchone()[0]
    conn.close()
    return u_count, c_count

def get_all_users():
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    cursor.execute('SELECT user_id FROM users')
    users = [row[0] for row in cursor.fetchall()]
    conn.close()
    return users

def add_cache(query, file_id, title):
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    cursor.execute('INSERT OR REPLACE INTO cache (query, file_id, title) VALUES (?, ?, ?)', (query.lower(), file_id, title))
    conn.commit()
    conn.close()

def get_cache(query):
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    cursor.execute('SELECT file_id FROM cache WHERE query = ?', (query.lower(),))
    result = cursor.fetchone()
    if result:
        cursor.execute('UPDATE cache SET download_count = download_count + 1 WHERE query = ?', (query.lower(),))
        conn.commit()
    conn.close()
    return result[0] if result else None

def get_top_songs(limit=10):
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    cursor.execute('SELECT title, query FROM cache ORDER BY download_count DESC LIMIT ?', (limit,))
    tops = cursor.fetchall()
    conn.close()
    return tops

def toggle_favorite(user_id, query_key):
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    cursor.execute('SELECT 1 FROM favorites WHERE user_id = ? AND query_key = ?', (user_id, query_key))
    exists = cursor.fetchone()
    if exists:
        cursor.execute('DELETE FROM favorites WHERE user_id = ? AND query_key = ?', (user_id, query_key))
        res = False
    else:
        cursor.execute('INSERT INTO favorites (user_id, query_key) VALUES (?, ?)', (user_id, query_key))
        res = True
    conn.commit()
    conn.close()
    return res

def get_favorites(user_id):
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    cursor.execute('SELECT query_key FROM favorites WHERE user_id = ?', (user_id,))
    favs = [row[0] for row in cursor.fetchall()]
    conn.close()
    return favs
