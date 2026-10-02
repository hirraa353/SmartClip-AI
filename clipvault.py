from flask import Flask, render_template, jsonify, request
import pyperclip
import sqlite3
import threading
import time
import re
from datetime import datetime

app = Flask(__name__)

# --- 1. DATABASE SETUP ---
def init_db():
    conn = sqlite3.connect('clipboard_history.db', check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS clips (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content TEXT,
            category TEXT,
            timestamp TEXT
        )
    ''')
    conn.commit()
    return conn

# --- 2. SMART TAGGING ---
def classify_content(text):
    text = text.strip()
    
    email_pattern = r'^[\w\.-]+@[\w\.-]+\.\w+(\s+[\w\.-]+@[\w\.-]+\.\w+)*$'
    phone_pattern = r'^\+?[\d\s\-\(\)]{7,15}$'
    
    if re.match(r'^https?:\/\/\S+', text): 
        return "URL"
    elif re.match(email_pattern, text): 
        return "Email"
    elif re.match(r'^#([A-Fa-f0-9]{6}|[A-Fa-f0-9]{3})$', text): 
        return "Hex Color"
    elif any(char in text for char in ['{', '}', ';', 'def ', 'function ', 'import ']): 
        return "Code"
    elif text.isdigit(): 
        return "Number"
    elif re.match(phone_pattern, text): 
        return "Contact Number"
    else: 
        return "Plain Text"

# --- 3. BACKGROUND MONITOR (Fixed for Duplicates) ---
def monitor_clipboard():
    conn = init_db()
    cursor = conn.cursor()
    print("ClipVault is monitoring the clipboard...")
    while True:
        try:
            current_value = pyperclip.paste()
            if current_value.strip() != "":
                # Check the database to see if this was just saved
                cursor.execute("SELECT content FROM clips ORDER BY id DESC LIMIT 1")
                row = cursor.fetchone()
                last_value = row[0] if row else ""
                
                if current_value != last_value:
                    category = classify_content(current_value)
                    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    cursor.execute("INSERT INTO clips (content, category, timestamp) VALUES (?, ?, ?)", 
                                   (current_value, category, timestamp))
                    conn.commit()
            time.sleep(1)
        except Exception:
            time.sleep(1)

# --- 4. WEB ROUTES ---
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/clips')
def get_clips():
    category = request.args.get('category', 'All')
    search = request.args.get('search', '')
    
    conn = init_db()
    cursor = conn.cursor()
    
    query = "SELECT id, category, timestamp, content FROM clips WHERE 1=1"
    params = []
    
    if category != 'All':
        query += " AND category = ?"
        params.append(category)
    if search:
        query += " AND content LIKE ?"
        params.append('%' + search + '%')
        
    query += " ORDER BY id DESC LIMIT 100"
    
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    
    clips = [{"id": r[0], "category": r[1], "timestamp": r[2], "content": r[3]} for r in rows]
    return jsonify(clips)

@app.route('/api/clear', methods=['POST'])
def clear_history():
    conn = init_db()
    conn.execute("DELETE FROM clips")
    conn.commit()
    conn.close()
    return jsonify({"status": "success"})

# --- 5. START THE APP ---
if __name__ == "__main__":
    monitor_thread = threading.Thread(target=monitor_clipboard, daemon=True)
    monitor_thread.start()
    
    print("ClipVault Server started! Open http://127.0.0.1:5000 in your browser.")
    app.run(debug=False, port=5000)