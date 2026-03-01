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
            file_id TEXT,
            download_count INTEGER DEFAULT 1
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS favorites (
            user_id INTEGER,
            query_key TEXT,
            UNIQUE(user_id, query_key)
        )
    ''')
    try:
        cursor.execute('ALTER TABLE cache ADD COLUMN download_count INTEGER DEFAULT 1')
    except:
        pass
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
    if result:
        cursor.execute('UPDATE cache SET download_count = download_count + 1 WHERE query = ?', (query.lower(),))
        conn.commit()
    conn.close()
    return result[0] if result else None

def add_cache(query, file_id):
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    cursor.execute('INSERT OR IGNORE INTO cache (query, file_id, download_count) VALUES (?, ?, 1)', (query.lower(), file_id))
    cursor.execute('UPDATE cache SET file_id = ? WHERE query = ?', (file_id, query.lower()))
    conn.commit()
    conn.close()

# --- ADMIN TIZIMI ---
def get_all_users():
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    cursor.execute('SELECT user_id FROM users')
    users = cursor.fetchall()
    conn.close()
    return [u[0] for u in users]

def get_stats():
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM users')
    u_count = cursor.fetchone()[0]
    cursor.execute('SELECT COUNT(*) FROM cache')
    c_count = cursor.fetchone()[0]
    conn.close()
    return u_count, c_count

def get_top_music(limit=10):
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    cursor.execute('SELECT query, download_count FROM cache WHERE query LIKE "orig_%" ORDER BY download_count DESC LIMIT ?', (limit,))
    tops = cursor.fetchall()
    conn.close()
    return tops

# --- SEVIMLILAR VA INLINE UCHUN ---
def toggle_favorite(user_id, query_key):
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    cursor.execute('SELECT 1 FROM favorites WHERE user_id = ? AND query_key = ?', (user_id, query_key))
    if cursor.fetchone():
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

def search_cache_inline(query):
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    cursor.execute('SELECT query, file_id FROM cache WHERE query LIKE ? AND query LIKE "orig_%" LIMIT 50', (f'%{query.lower()}%',))
    results = cursor.fetchall()
    conn.close()
    return results
