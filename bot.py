# -*- coding: utf-8 -*-
import sys
import uuid
import threading
from datetime import datetime
from urllib.parse import quote_plus
import requests
from bs4 import BeautifulSoup

print("🚀 ЗАПУСК CINEMA PARTY BOT")
print(f"🐍 Python: {sys.version_info.major}.{sys.version_info.minor}")
print("-" * 50)

# ============ КОНФИГУРАЦИЯ ============
BOT_TOKEN = "8414477578:AAH44JTQWDXmQl_fRsN4fIuSHBV9tYsEscQ"
WEBRTC_SERVER = "https://cinema-webrtc-production.up.railway.app"

try:
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    from telegram.ext import Updater, CommandHandler, MessageHandler, CallbackQueryHandler, Filters

    print("✅ Telegram SDK загружен")
except ImportError:
    import subprocess

    subprocess.check_call(
        [sys.executable, "-m", "pip", "install", "python-telegram-bot==13.15", "requests", "beautifulsoup4"])
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    from telegram.ext import Updater, CommandHandler, MessageHandler, CallbackQueryHandler, Filters


# ============ ПАРСЕР LORDFILM ============
class LordFilmParser:
    def __init__(self):
        self.base_url = "https://lorldfilm2520.ru"
        self.headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

    def search(self, query):
        try:
            search_url = f"{self.base_url}/index.php?do=search&subaction=search&q={quote_plus(query)}"
            response = requests.get(search_url, headers=self.headers, timeout=10)
            soup = BeautifulSoup(response.text, 'html.parser')
            results = []
            items = soup.select('.short-item, .movie-item, .shortstory, .film-item, article, .post')

            for item in items[:8]:
                try:
                    title_elem = item.select_one('.title a, .name a, h2 a, h3 a')
                    if not title_elem:
                        continue
                    title = title_elem.text.strip()
                    detail_url = title_elem.get('href')
                    if not detail_url.startswith('http'):
                        detail_url = self.base_url + detail_url

                    year = '2025'
                    year_elem = item.select_one('.year, .date, .info span')
                    if year_elem:
                        year = year_elem.text.strip()[:4]

                    results.append({'title': title, 'year': year, 'url': detail_url})
                except:
                    continue
            return results
        except:
            return []

    def get_video_url(self, detail_url):
        try:
            response = requests.get(detail_url, headers=self.headers, timeout=10)
            soup = BeautifulSoup(response.text, 'html.parser')
            iframe = soup.select_one('iframe[src*="video"], iframe[src*="player"], iframe[src*="kinokrad"]')
            if iframe:
                return iframe.get('src')
            return None
        except:
            return None


parser = LordFilmParser()

# ============ КОМНАТЫ ============
rooms = {}
room_locks = {}


def get_room_lock(room_id):
    if room_id not in room_locks:
        room_locks[room_id] = threading.Lock()
    return room_locks[room_id]


def get_room_info_text(room_id, username=None):
    """Генерирует текст информации о комнате (БЕЗ MARKDOWN)"""
    room = rooms.get(room_id, {})
    users = room.get('users', [])
    host_id = room.get('host')
    host_name = "Неизвестно"

    for u in users:
        if u['id'] == host_id:
            host_name = u['username']
            break

    video_status = "✅ Есть" if room.get('video') else "❌ Нет"

    return (
        f"🎥 Комната {room_id}\n"
        f"└ 👤 Хост: {host_name}\n"
        f"└ 👥 Участники: {len(users)} чел.\n"
        f"└ 🎬 Видео: {video_status}\n\n"
        f"🔗 Синхронный плеер:\n{WEBRTC_SERVER}/player.html?room={room_id}"
    )


# ============ КОМАНДЫ БОТА ============
def start(update, context):
    """Главное меню (БЕЗ MARKDOWN)"""
    keyboard = [
        [InlineKeyboardButton("🎬 Поиск фильма", switch_inline_query_current_chat="")],
        [InlineKeyboardButton("👥 Создать комнату", callback_data="menu_create_room")],
        [InlineKeyboardButton("❓ Помощь", callback_data="menu_help")]
    ]

    update.message.reply_text(
        "🎬 LordFilm Cinema Party\n\n"
        "Смотри фильмы с друзьями синхронно!\n"
        "Без регистрации, без задержек, бесплатно.\n\n"
        "👇 Выбери действие:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


def search_command(update, context):
    """Поиск фильмов (БЕЗ MARKDOWN)"""
    query = ' '.join(context.args) if context.args else ''

    if not query:
        update.message.reply_text(
            "🔍 Поиск фильмов\n\n"
            "Введи название после команды:\n"
            "/search дюна\n"
            "/search аватар\n"
            "/search гарри поттер"
        )
        return

    msg = update.message.reply_text("🔍 Ищем на lordfilm2520.ru... ⏳")

    try:
        results = parser.search(query)

        if not results:
            msg.edit_text("❌ Ничего не найдено\n\nПопробуй другое название.")
            return

        keyboard = []
        for i, movie in enumerate(results[:5]):
            keyboard.append([
                InlineKeyboardButton(
                    f"🎬 {movie['title'][:35]} ({movie['year']})",
                    callback_data=f"movie_{i}"
                )
            ])

        keyboard.append([InlineKeyboardButton("🔍 Новый поиск", switch_inline_query_current_chat="")])

        context.user_data['search_results'] = results

        msg.edit_text(
            f"✅ Найдено {len(results)} фильмов\n\n"
            f"Первый: {results[0]['title']}",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    except Exception as e:
        msg.edit_text(f"❌ Ошибка поиска: {e}")


def room_command(update, context):
    """Быстрое создание комнаты"""
    create_room(update, context)


def create_room(update, context, custom_room_id=None):
    """Создание комнаты (БЕЗ MARKDOWN)"""
    try:
        room_id = custom_room_id or str(uuid.uuid4())[:6].upper()
        user_id = str(update.effective_user.id)
        username = update.effective_user.first_name or "User"

        with get_room_lock(room_id):
            if room_id not in rooms:
                rooms[room_id] = {
                    'users': [],
                    'video': None,
                    'host': user_id,
                    'created_at': datetime.now().isoformat()
                }

            if user_id not in [u['id'] for u in rooms[room_id]['users']]:
                rooms[room_id]['users'].append({'id': user_id, 'username': username})
            rooms[room_id]['host'] = user_id

        webrtc_url = f"{WEBRTC_SERVER}/player.html?room={room_id}"

        keyboard = [
            [InlineKeyboardButton("🎬 Искать фильм", switch_inline_query_current_chat="")],
            [InlineKeyboardButton("🌐 Открыть плеер", url=webrtc_url)],
            [
                InlineKeyboardButton("👥 Пригласить", callback_data=f"invite_{room_id}"),
                InlineKeyboardButton("📋 ID комнаты", callback_data=f"show_id_{room_id}")
            ],
            [InlineKeyboardButton("🔄 Обновить", callback_data=f"refresh_{room_id}")]
        ]

        message_text = get_room_info_text(room_id, username)

        if hasattr(update, 'callback_query') and update.callback_query:
            update.callback_query.edit_message_text(
                message_text,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        else:
            update.message.reply_text(
                message_text,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )

        return room_id

    except Exception as e:
        error_msg = f"❌ Ошибка создания комнаты: {e}"
        if hasattr(update, 'callback_query') and update.callback_query:
            update.callback_query.edit_message_text(error_msg)
        else:
            update.message.reply_text(error_msg)


def join_command(update, context):
    """Вход в комнату (БЕЗ MARKDOWN)"""
    try:
        room_id = context.args[0].upper() if context.args else None

        if not room_id:
            update.message.reply_text(
                "🔑 Вход в комнату\n\n"
                "Используй: /join ABC123\n"
                "Где ABC123 — ID комнаты"
            )
            return

        if room_id not in rooms:
            update.message.reply_text(
                "❌ Комната не найдена\n\n"
                "Проверь ID или создай новую: /room"
            )
            return

        user_id = str(update.effective_user.id)
        username = update.effective_user.first_name or "User"

        with get_room_lock(room_id):
            if user_id not in [u['id'] for u in rooms[room_id]['users']]:
                rooms[room_id]['users'].append({'id': user_id, 'username': username})

        webrtc_url = f"{WEBRTC_SERVER}/player.html?room={room_id}"

        keyboard = [
            [InlineKeyboardButton("🌐 Открыть плеер", url=webrtc_url)],
            [InlineKeyboardButton("🔄 Обновить", callback_data=f"refresh_{room_id}")]
        ]

        update.message.reply_text(
            get_room_info_text(room_id, username),
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

        if rooms[room_id].get('host') and rooms[room_id]['host'] != user_id:
            try:
                context.bot.send_message(
                    chat_id=rooms[room_id]['host'],
                    text=f"👥 {username} присоединился к комнате {room_id}"
                )
            except:
                pass

    except Exception as e:
        update.message.reply_text(f"❌ Ошибка: {e}")


def handle_message(update, context):
    """Обработка ссылок"""
    text = update.message.text.strip()

    if text.startswith(('http://', 'https://')):
        keyboard = [
            [InlineKeyboardButton("▶️ Смотреть сейчас", url=text)],
            [InlineKeyboardButton("👥 Смотреть в комнате", callback_data="quick_room")]
        ]
        update.message.reply_text(
            "✅ Видео готово!",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        context.user_data['current_video'] = text


# ============ ОБРАБОТЧИК КНОПОК ============
def button_callback(update, context):
    query = update.callback_query
    user_id = str(update.effective_user.id)
    username = update.effective_user.first_name or "User"

    data = query.data

    # ---------- ГЛАВНОЕ МЕНЮ ----------
    if data == "menu_create_room":
        create_room(update, context)
        return

    elif data == "menu_help":
        keyboard = [
            [InlineKeyboardButton("🎬 Поиск", switch_inline_query_current_chat="")],
            [InlineKeyboardButton("👥 Комната", callback_data="menu_create_room")],
            [InlineKeyboardButton("◀️ Назад", callback_data="menu_back")]
        ]
        query.edit_message_text(
            "❓ Помощь\n\n"
            "🔍 Поиск — /search название\n"
            "   Или просто нажми кнопку поиска\n\n"
            "👥 Комната — /room\n"
            "   Создай комнату и пригласи друзей\n\n"
            "🔑 Вход — /join ID\n"
            "   Войди в чужую комнату\n\n"
            "🌐 Плеер — открывается автоматически\n\n"
            "📱 LordFilm парсер — ищет реальные фильмы",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    elif data == "menu_back":
        # Возврат в главное меню
        keyboard = [
            [InlineKeyboardButton("🎬 Поиск фильма", switch_inline_query_current_chat="")],
            [InlineKeyboardButton("👥 Создать комнату", callback_data="menu_create_room")],
            [InlineKeyboardButton("❓ Помощь", callback_data="menu_help")]
        ]
        query.edit_message_text(
            "🎬 LordFilm Cinema Party\n\n"
            "Смотри фильмы с друзьями синхронно!\n"
            "Без регистрации, без задержек, бесплатно.\n\n"
            "👇 Выбери действие:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    elif data == "quick_room":
        room_id = create_room(update, context)
        if room_id and context.user_data.get('current_video'):
            rooms[room_id]['video'] = {'url': context.user_data['current_video']}
        return

    # ---------- УПРАВЛЕНИЕ КОМНАТАМИ ----------
    if data.startswith('invite_'):
        room_id = data.split('_')[1]
        webrtc_url = f"{WEBRTC_SERVER}/player.html?room={room_id}"

        invite_text = (
            f"🔗 Приглашение в комнату {room_id}\n\n"
            f"1️⃣ Введи команду:\n/join {room_id}\n\n"
            f"2️⃣ Или открой плеер:\n{webrtc_url}\n\n"
            f"👥 Участников: {len(rooms.get(room_id, {}).get('users', []))}"
        )

        query.message.reply_text(invite_text)
        query.answer("✅ Ссылка отправлена")
        return

    elif data.startswith('show_id_'):
        room_id = data.split('_')[2]
        query.answer(f"ID комнаты: {room_id}", show_alert=False)
        return

    elif data.startswith('refresh_'):
        room_id = data.split('_')[1]
        if room_id in rooms:
            webrtc_url = f"{WEBRTC_SERVER}/player.html?room={room_id}"
            keyboard = [
                [InlineKeyboardButton("🎬 Искать фильм", switch_inline_query_current_chat="")],
                [InlineKeyboardButton("🌐 Открыть плеер", url=webrtc_url)],
                [
                    InlineKeyboardButton("👥 Пригласить", callback_data=f"invite_{room_id}"),
                    InlineKeyboardButton("📋 ID", callback_data=f"show_id_{room_id}")
                ],
                [InlineKeyboardButton("🔄 Обновить", callback_data=f"refresh_{room_id}")]
            ]

            query.edit_message_text(
                get_room_info_text(room_id, username),
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        query.answer("🔄 Обновлено")
        return

    # ---------- ВЫБОР ФИЛЬМА ----------
    if data.startswith('movie_'):
        try:
            idx = int(data.split('_')[1])
            results = context.user_data.get('search_results', [])

            if idx < len(results):
                movie = results[idx]
                msg = query.edit_message_text("⏳ Загружаю видео с LordFilm...")

                video_url = parser.get_video_url(movie['url'])

                if video_url:
                    context.user_data['current_video'] = video_url

                    keyboard = [
                        [InlineKeyboardButton("▶️ Смотреть", url=video_url)],
                        [InlineKeyboardButton("👥 В комнату", callback_data="quick_room")],
                        [InlineKeyboardButton("🔍 Новый поиск", switch_inline_query_current_chat="")]
                    ]

                    msg.edit_text(
                        f"🎬 {movie['title']} ({movie['year']})\n\n✅ Видео загружено!",
                        reply_markup=InlineKeyboardMarkup(keyboard)
                    )
                else:
                    msg.edit_text(
                        "❌ Не удалось загрузить видео\n\n"
                        "Попробуй другой фильм или источник."
                    )
        except Exception as e:
            query.edit_message_text(f"❌ Ошибка: {e}")
        return

    query.answer()


def error_handler(update, context):
    """Глобальный обработчик ошибок"""
    try:
        print(f"⚠️ Ошибка: {context.error}")
    except:
        pass


# ============ ЗАПУСК ============
print("✅ Инициализация бота...")
print("✅ Парсер LordFilm загружен")
print(f"🖥 WebRTC сервер: {WEBRTC_SERVER}")
print("✅ Режим: БЕЗ MARKDOWN (ошибки исправлены)")

try:
    updater = Updater(BOT_TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler('start', start))
    dp.add_handler(CommandHandler('search', search_command))
    dp.add_handler(CommandHandler('room', room_command))
    dp.add_handler(CommandHandler('join', join_command))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))
    dp.add_handler(CallbackQueryHandler(button_callback))
    dp.add_error_handler(error_handler)

    print("✅ Бот готов к работе!")
    print("📱 Напиши @cinema_party_bot в Telegram")
    print("-" * 50)
    print("⏳ Запуск...")
    print("-" * 50)

    updater.start_polling()
    updater.idle()

except Exception as e:
    print(f"❌ Критическая ошибка: {e}")
    import traceback

    traceback.print_exc()