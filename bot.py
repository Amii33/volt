import sqlite3
import logging
from datetime import datetime
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup
)
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler
)

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Константы
ADMIN_CHAT_ID = 167162909  # 1016263757 Замените на ваш chat_id
BOT_TOKEN = "7816437926:AAFRf1xhZHlJvvoys4s3MBdxP-XP76x_35w"  # Ваш токен

# Состояния ConversationHandler
SELECT_DATE, ENTER_DETAILS, SELECT_LOCATION, CONFIRMATION = range(4)

# Инструкции по передвижению
LOCATION_INSTRUCTIONS = {
    "Подольск": """🚌<b>НА СКЛАД🚌</b>\n\nЕжедневно:
<b>07.00</b> Подольск, проезд Авиаторов д. 1 (парковка у ТЦ Молоток)
<b>07.20</b> Станция МЦД Подольск (пересечение улиц Железнодорожная и Рощинская, ост.Стройиндустрия) (📍<a href="https://yandex.ru/maps/213/moscow/?ll=37.566647%2C55.430322&mode=search&sll=37.567108%2C55.430408&text=55.430408%2C37.567108&utm_source=share&z=19">Точка на карте</a>📍)\n
🚌<b>ОБРАТНО🚌</b>:\n
Ежедневно:
<b>20.15</b> - д. Кучино (Домодедовский район) с 50а
<b>20.35</b> - МЦД Подольск
<b>20.45</b> - Ост. Красная горка 55.450104,37.552475
<b>20.50</b> - Подольск, остановка АТП-6
<b>20.55</b> - Подольск, пр-кт Юных Ленинцев (ост. Ново-Сырово)""",
    "Москва": """🚌<b>НА СКЛАД</b>🚌\n\nЕжедневно:
<b>07:10</b> - ст. метро Пражская (📍<a href="https://yandex.ru/maps/213/moscow/?indoorLevel=1&ll=37.608305%2C55.609292&mode=search&sll=37.607936%2C55.609226&text=55.609226%2C37.607936&utm_source=share&z=18">Точка на карте</a>📍)
<b>08:00</b> - д. Кучино (Домодедовский район)  с 50а\n
🚌<b>ОБРАТНО</b>🚌:\n
Ежедневно:
<b>20:15</b> - д. Кучино (Домодедовский район) с 50а
<b>20:50</b> - метро Аннино
<b>21:00</b> - метро Пражская (📍<a href="https://yandex.ru/maps/213/moscow/?ll=37.609883%2C55.608851&mode=search&sll=37.609728%2C55.609083&text=55.609083%2C37.609728&utm_source=share&z=18">Точка на карте</a>📍)
""",
    "Домодедово": """🚌<b>НА СКЛАД</b>🚌\n\nЕжедневно:
<b>07:20</b> - Домодедово, ост. Новая улица (в сторону Константиново) (📍<a href="https://yandex.ru/maps/10725/domodedovo/?ll=37.764505%2C55.436585&mode=search&sll=37.764605%2C55.436547&text=55.436547%2C37.764605&utm_campaign=desktop&utm_medium=search&utm_source=share&z=20">Точка на карте</a>📍)
<b>07:45</b> - д. Кучино (Домодедовский район) с 50а\n
🚌<b>ОБРАТНО</b>🚌:\n
Ежедневно:
<b>20.15</b> - д. Кучино (Домодедовский район) с50а
<b>20:30</b> - Домодедово, ост. Новая улица (в сторону Константиново) (📍<a href="https://yandex.ru/maps/10725/domodedovo/?ll=37.764505%2C55.436585&mode=search&sll=37.764605%2C55.436547&text=55.436547%2C37.764605&utm_campaign=desktop&utm_medium=search&utm_source=share&z=20">Точка на карте</a>)📍""",
    "Доберусь на личном транспорте": "🚕д. Кучино (Домодедовский район) с50а"
}

# Инициализация базы данных
def init_db():
    """Создает таблицы в базе данных при первом запуске."""
    with sqlite3.connect('work_bot.db') as conn:
        cursor = conn.cursor()
        
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS work_dates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL UNIQUE,
            slots INTEGER NOT NULL
        )
        ''')
        
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            phone TEXT NOT NULL,
            location TEXT NOT NULL,
            date_id INTEGER NOT NULL,
            FOREIGN KEY (date_id) REFERENCES work_dates(id),
            UNIQUE(user_id, date_id)
        )
        ''')
        
        conn.commit()

# Функции для работы с базой данных
def get_available_dates():
    """Возвращает список дат с доступными местами."""
    with sqlite3.connect('work_bot.db') as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('''
        SELECT wd.id, wd.date, wd.slots, COUNT(u.id) as booked 
        FROM work_dates wd 
        LEFT JOIN users u ON wd.id = u.date_id 
        GROUP BY wd.id 
        HAVING booked < wd.slots OR booked IS NULL
        ''')
        
        return cursor.fetchall()

def add_user_to_db(user_id, name, phone, location, date_id):
    """Добавляет пользователя в базу данных с проверкой дублирования."""
    with sqlite3.connect('work_bot.db') as conn:
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
            INSERT INTO users (user_id, name, phone, location, date_id)
            VALUES (?, ?, ?, ?, ?)
            ''', (user_id, name, phone, location, date_id))
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            # Пользователь уже записан на эту дату
            conn.rollback()
            return False

def get_date_by_id(date_id):
    """Возвращает информацию о дате по ID."""
    with sqlite3.connect('work_bot.db') as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM work_dates WHERE id = ?', (date_id,))
        return cursor.fetchone()

# Обработчики команд
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработчик команды /start."""
    dates = get_available_dates()
    
    if not dates:
        await update.message.reply_text('В настоящее время нет доступных дат для записи.')
        return ConversationHandler.END
    
    keyboard = [
        [InlineKeyboardButton(date['date'], callback_data=str(date['id']))]
        for date in dates
    ]
    
    await update.message.reply_text(
        'Выберите дату для подработки:',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return SELECT_DATE

async def select_date(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработка выбора даты."""
    query = update.callback_query
    await query.answer()
    
    date_id = int(query.data)
    context.user_data['date_id'] = date_id
    
    await query.edit_message_text(
        text="Введите ваши данные в формате:\nФИО, номер телефона\n\n"
             "Пример: Иванов Иван Иванович, +79123456789"
    )
    return ENTER_DETAILS

async def enter_details(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработка введенных пользовательских данных."""
    try:
        text = update.message.text
        name, phone = [part.strip() for part in text.split(',', 1)]
        
        if not phone.replace('+', '').isdigit():
            raise ValueError("Неверный формат телефона")
            
        context.user_data['name'] = name
        context.user_data['phone'] = phone
        
        keyboard = [
            [InlineKeyboardButton(loc, callback_data=loc)]
            for loc in LOCATION_INSTRUCTIONS.keys()
        ]
        
        await update.message.reply_text(
            'Выберите место отправления:',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return SELECT_LOCATION
        
    except Exception as e:
        logger.error(f"Ошибка ввода данных: {e}")
        await update.message.reply_text(
            'Неверный формат. Пожалуйста, введите данные в формате:\n'
            'ФИО, номер телефона\n\n'
            'Пример: Иванов Иван Иванович, +79123456789'
        )
        return ENTER_DETAILS

async def select_location(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработка выбора места отправления."""
    query = update.callback_query
    await query.answer()
    
    location = query.data
    context.user_data['location'] = location
    
    date_info = get_date_by_id(context.user_data['date_id'])
    
    confirmation_text = (
        "Пожалуйста, подтвердите ваши данные:\n\n"
        f"📅 Дата: {date_info['date']}\n"
        f"👤 ФИО: {context.user_data['name']}\n"
        f"📱 Телефон: {context.user_data['phone']}\n"
        f"📍 Место отправления: {location}\n\n"
        "Все верно?"
    )
    
    keyboard = [
        [
            InlineKeyboardButton("✅ Подтвердить", callback_data="confirm"),
            InlineKeyboardButton("❌ Отменить", callback_data="cancel")
        ]
    ]
    
    await query.edit_message_text(
        text=confirmation_text,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return CONFIRMATION

async def confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработка подтверждения или отмены."""
    query = update.callback_query
    await query.answer()
    
    if query.data == "confirm":
        user_id = update.effective_user.id
        date_id = context.user_data['date_id']
        name = context.user_data['name']
        phone = context.user_data['phone']
        location = context.user_data['location']
        
        # Пытаемся добавить пользователя
        if add_user_to_db(user_id, name, phone, location, date_id):
            date_info = get_date_by_id(date_id)
            
            success_message = (
                "✅ Вы успешно записались на подработку!\n\n"
                f"📅 Дата: {date_info['date']}\n"
                f"👤 ФИО: {name}\n"
                f"📱 Телефон: {phone}\n"
                f"📍 Место отправления: {location}\n\n"
                f"ℹ️ Инструкция: {LOCATION_INSTRUCTIONS.get(location, '')}"
            )
            
            await query.edit_message_text(
            text=success_message,
            parse_mode="HTML"  
        )
            
            if ADMIN_CHAT_ID:
                admin_message = (
                    "🆕 Новая запись на подработку:\n\n"
                    f"📅 Дата: {date_info['date']}\n"
                    f"👤 ФИО: {name}\n"
                    f"📱 Телефон: {phone}\n"
                    f"📍 Место: {location}\n"
                    f"🆔 ID пользователя: {user_id}"
                )
                await context.bot.send_message(
                    chat_id=ADMIN_CHAT_ID,
                    text=admin_message
                )
        else:
            # Если запись уже существует
            date_info = get_date_by_id(date_id)
            await query.edit_message_text(
                text=f"⚠️ Вы уже записаны на {date_info['date']}!\n"
                     "Повторная запись невозможна."
            )
    else:
        await query.edit_message_text(text="❌ Запись отменена.")
    
    return ConversationHandler.END
    

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработчик отмены."""
    await update.message.reply_text('Регистрация отменена.')
    return ConversationHandler.END

# Админ-команды
async def admin_add_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Добавление новой даты для записи."""
    if update.effective_user.id != ADMIN_CHAT_ID:
        await update.message.reply_text("⛔ У вас нет прав доступа!")
        return
    
    try:
        if len(context.args) != 2:
            raise ValueError("Неверное количество аргументов")
            
        date_str = context.args[0]
        slots = int(context.args[1])
        
        datetime.strptime(date_str, '%d.%m.%Y')
        
        with sqlite3.connect('work_bot.db') as conn:
            cursor = conn.cursor()
            
            try:
                cursor.execute('''
                INSERT INTO work_dates (date, slots) VALUES (?, ?)
                ''', (date_str, slots))
                
                conn.commit()
                await update.message.reply_text(
                    f"✅ Дата {date_str} успешно добавлена ({slots} мест)"
                )
            except sqlite3.IntegrityError:
                await update.message.reply_text(
                    f"⚠️ Дата {date_str} уже существует в базе"
                )
                
    except ValueError as e:
        logger.error(f"Ошибка добавления даты: {e}")
        await update.message.reply_text(
            "❌ Неверный формат команды.\n"
            "Используйте: /add_date ДД.ММ.ГГГГ количество_мест\n\n"
            "Пример: /add_date 15.08.2023 10"
        )

async def admin_list_dates(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает список всех дат с количеством записанных."""
    if update.effective_user.id != ADMIN_CHAT_ID:
        await update.message.reply_text("⛔ У вас нет прав доступа!")
        return
    
    with sqlite3.connect('work_bot.db') as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('''
        SELECT wd.id, wd.date, wd.slots, COUNT(u.id) as booked 
        FROM work_dates wd 
        LEFT JOIN users u ON wd.id = u.date_id 
        GROUP BY wd.id
        ''')
        
        dates = cursor.fetchall()
    
    if not dates:
        await update.message.reply_text("В базе нет доступных дат.")
        return
    
    message = "📅 Список дат и записей:\n\n"
    for date in dates:
        message += (
            f"{date['date']}:\n"
            f"  Всего мест: {date['slots']}\n"
            f"  Записано: {date['booked']}\n"
            f"  Свободно: {date['slots'] - date['booked']}\n\n"
        )
    
    await update.message.reply_text(message)

async def admin_list_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает список пользователей для конкретной даты."""
    if update.effective_user.id != ADMIN_CHAT_ID:
        await update.message.reply_text("⛔ У вас нет прав доступа!")
        return
    
    try:
        date_str = context.args[0]
        
        with sqlite3.connect('work_bot.db') as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute('''
            SELECT u.name, u.phone, u.location, u.user_id 
            FROM users u 
            JOIN work_dates wd ON u.date_id = wd.id 
            WHERE wd.date = ?
            ''', (date_str,))
            
            users = cursor.fetchall()
        
        if not users:
            await update.message.reply_text(f"На дату {date_str} нет записей.")
            return
        
        message = f"👥 Список записавшихся на {date_str}:\n\n"
        for user in users:
            message += (
                f"👤 {user['name']}\n"
                f"📱 {user['phone']}\n"
                f"📍 {user['location']}\n"
                f"🆔 {user['user_id']}\n\n"
            )
        
        await update.message.reply_text(message)
        
    except IndexError:
        await update.message.reply_text(
            "Укажите дату в формате ДД.ММ.ГГГГ\n"
            "Пример: /list_users 15.08.2023"
        )

async def admin_delete_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Удаляет дату и все связанные записи"""
    if update.effective_user.id != ADMIN_CHAT_ID:
        await update.message.reply_text("⛔ Доступ запрещен!")
        return
    
    try:
        date_str = context.args[0]  # Получаем дату из аргументов
        
        with sqlite3.connect('work_bot.db') as conn:
            cursor = conn.cursor()
            
            # 1. Находим ID даты
            cursor.execute("SELECT id FROM work_dates WHERE date = ?", (date_str,))
            date_id = cursor.fetchone()
            
            if not date_id:
                await update.message.reply_text(f"❌ Дата {date_str} не найдена")
                return
            
            # 2. Удаляем сначала связанные записи пользователей
            cursor.execute("DELETE FROM users WHERE date_id = ?", (date_id[0],))
            
            # 3. Удаляем саму дату
            cursor.execute("DELETE FROM work_dates WHERE id = ?", (date_id[0],))
            
            conn.commit()
        
        await update.message.reply_text(f"✅ Дата {date_str} и все записи удалены!")
        
    except IndexError:
        await update.message.reply_text("❌ Укажите дату в формате: /delete_date ДД.ММ.ГГГГ")
    except Exception as e:
        logger.error(f"Ошибка удаления даты: {e}")
        await update.message.reply_text("⚠️ Произошла ошибка при удалении")

# Главная функция
def main() -> None:
    """Запуск бота."""
    # Инициализация базы данных
    init_db()
    
    # Создание Application
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Обработчик диалога регистрации
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            SELECT_DATE: [CallbackQueryHandler(select_date)],
            ENTER_DETAILS: [MessageHandler(filters.TEXT & ~filters.COMMAND, enter_details)],
            SELECT_LOCATION: [CallbackQueryHandler(select_location)],
            CONFIRMATION: [CallbackQueryHandler(confirmation)]
        },
        fallbacks=[CommandHandler('cancel', cancel)],
        per_message=False  # Изменено на False для корректной работы
    )
    
    # Регистрация обработчиков
    application.add_handler(conv_handler)
    application.add_handler(CommandHandler("add_date", admin_add_date))
    application.add_handler(CommandHandler("list_dates", admin_list_dates))
    application.add_handler(CommandHandler("list_users", admin_list_users))
    application.add_handler(CommandHandler("delete_date", admin_delete_date))
    
    # Запуск бота
    application.run_polling()

if __name__ == '__main__':
    main()
