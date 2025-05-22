import sqlite3
from datetime import datetime

def init_db():
    """Создает базу данных и таблицы, если их нет."""
    conn = sqlite3.connect('work_bot.db')
    cursor = conn.cursor()
    
    # Таблица с датами подработки
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS work_dates (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT NOT NULL,
        slots INTEGER NOT NULL,
        UNIQUE(date)
    )
    ''')
    
    # Таблица с пользователями
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        phone TEXT NOT NULL,
        location TEXT NOT NULL,
        date_id INTEGER NOT NULL,
        FOREIGN KEY (date_id) REFERENCES work_dates(id)
    )
    ''')
    
    conn.commit()
    conn.close()

init_db()  # Инициализация при запуске