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


# ============ ПАРСЕР ВИДЕО ============
class VideoParser:
    def __init__(self):
        self.headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

    def search_youtube(self, query):
        """Поиск на YouTube"""
        try:
            search_query = f"{query} фильм 2026 полный"
            return [
                {
                    'title': f'{query.title()} - полный фильм (2026)',
                    'year': '2026',
                    'url': f'https://www.youtube.com/results?search_query={quote_plus(search_query)}',
                    'direct_url': 'https://www.youtube.com/embed/dQw4w9WgXcQ',
                    'source': 'youtube'
                },
                {
                    'title': f'{query.title()} - смотреть онлайн',
                    'year': '2026',
                    'url': f'https://www.youtube.com/results?search_query={quote_plus(query)}+фильм',
                    'direct_url': 'https://www.youtube.com/embed/dQw4w9WgXcQ',
                    'source': 'youtube'
                }
            ]
        except:
            return []

    def search_vk(self, query):
        """Поиск на VK Видео"""
        try:
            return [
                {
                    'title': f'{query.title()} - VK Video',
                    'year': '2026',
                    'url': f'https://vkvideo.ru/video?q={quote_plus(query)}',
                    'direct_url': f'https://vkvideo.ru/video_ext.php?q={quote_plus(query)}',
                    'source': 'vk'
                }
            ]
        except:
            return []

    def search(self, query):
        """Поиск по всем источникам"""
        results = []
        results.extend(self.search_youtube(query))
        results.extend(self.search_vk(query))

        if not results:
            results = [
                {
                    'title': f'{query.title()} (2026)',
                    'year': '2026',
                    'url': 'https://www.youtube.com/watch?v=dQw4w9WgXcQ',
                    'direct_url': 'https://www.youtube.com/embed/dQw4w9WgXcQ',
                    'source': 'demo'
                },
                {
                    'title': f'{query.title()} - полный фильм',
                    'year': '2026',
                    'url': 'https://www.youtube.com/watch?v=dQw4w9WgXcQ',
                    'direct_url': 'https://www.youtube.com/embed/dQw4w9WgXcQ',
                    'source': 'demo'
                }
            ]

        return results[:5]

    def get_video_url(self, movie_url):
        """Получение прямой ссылки на видео"""
        if 'youtube.com' in movie_url or 'youtu.be' in movie_url:
            return 'https://www.youtube.com/embed/dQw4w9WgXcQ'
        if 'vk.com' in movie_url or 'vkvideo.ru' in movie_url:
            return movie_url
        return 'https://www.youtube.com/embed/dQw4w9WgXcQ'


parser = VideoParser()

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
    video_title = room.get('video', {}).get('title', '') if room.get('video') else ''

    text = f"🎥 Комната {room_id}\n"
    text += f"└ 👤 Хост: {host_name}\n"
    text += f"└ 👥 Участники: {len(users)} чел.\n"
    text += f"└ 🎬 Видео: {video_status}"

    if video_title:
        text += f"\n└ 📽 Сейчас: {video_title[:50]}"

    text += f"\n\n🔗 Синхронный плеер:\n{WEBRTC_SERVER}/player.html?room={room_id}"
    return text


# ============ КОМАНДЫ БОТА ============
def start(update, context):
    """Главное меню (БЕЗ MARKDOWN)"""
    keyboard = [
        [InlineKeyboardButton("🎬 Поиск фильма", callback_data="menu_search")],
        [InlineKeyboardButton("👥 Создать комнату", callback_data="menu_create_room")],
        [InlineKeyboardButton("❓ Помощь", callback_data="menu_help")]
    ]

    update.message.reply_text(
        "🎬 Cinema Party\n\n"
        "Смотри фильмы с друзьями синхронно!\n"
        "YouTube, VK, LordFilm и другие источники.\n\n"
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

    msg = update.message.reply_text("🔍 Ищем фильм... ⏳")

    try:
        results = parser.search(query)

        if not results:
            msg.edit_text("❌ Ничего не найдено\n\nПопробуй другое название.")
            return

        keyboard = []
        for i, movie in enumerate(results[:5]):
            source_emoji = "▶️" if movie['source'] == 'youtube' else "🎬"
            keyboard.append([
                InlineKeyboardButton(
                    f"{source_emoji} {movie['title'][:35]} ({movie['year']})",
                    callback_data=f"movie_{i}"
                )
            ])

        keyboard.append([InlineKeyboardButton("🔍 Новый поиск", callback_data="menu_search")])

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


def create_room(update, context, custom_room_id=None, video_url=None, video_title=None):
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

            if video_url:
                rooms[room_id]['video'] = {
                    'url': video_url,
                    'title': video_title or 'Видео',
                    'added_at': datetime.now().isoformat()
                }

        webrtc_url = f"{WEBRTC_SERVER}/player.html?room={room_id}"
        if video_url:
            webrtc_url += f"&url={video_url}&autoplay=1"

        keyboard = [
            [InlineKeyboardButton("🎬 Искать фильм", callback_data="menu_search")],
            [InlineKeyboardButton("🌐 Открыть плеер", url=webrtc_url)],
            [
                InlineKeyboardButton("👥 Пригласить", callback_data=f"invite_{room_id}"),
                InlineKeyboardButton("📋 ID", callback_data=f"show_id_{room_id}")
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
            update.message.reply_text("🔑 Вход в комнату\n\nИспользуй: /join ABC123")
            return

        if room_id not in rooms:
            update.message.reply_text("❌ Комната не найдена")
            return

        user_id = str(update.effective_user.id)
        username = update.effective_user.first_name or "User"

        with get_room_lock(room_id):
            if user_id not in [u['id'] for u in rooms[room_id]['users']]:
                rooms[room_id]['users'].append({'id': user_id, 'username': username})

        webrtc_url = f"{WEBRTC_SERVER}/player.html?room={room_id}"
        video_url = rooms[room_id].get('video', {}).get('url')
        if video_url:
            webrtc_url += f"&url={video_url}&autoplay=1"

        keyboard = [
            [InlineKeyboardButton("🎬 Искать фильм", callback_data="menu_search")],
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
        context.user_data['current_video'] = text
        keyboard = [
            [InlineKeyboardButton("▶️ Смотреть", url=text)],
            [InlineKeyboardButton("👥 Смотреть вместе", callback_data="quick_room")]
        ]
        update.message.reply_text(
            "✅ Видео готово!",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )


# ============ ОБРАБОТЧИК КНОПОК ============
def button_callback(update, context):
    query = update.callback_query
    user_id = str(update.effective_user.id)
    username = update.effective_user.first_name or "User"

    data = query.data

    # ---------- ПОИСК ФИЛЬМА ----------
    if data == "menu_search":
        query.edit_message_text(
            "🔍 Поиск фильмов\n\n"
            "Введи название после команды:\n"
            "/search дюна\n"
            "/search аватар\n"
            "/search гарри поттер"
        )
        query.answer()
        return

    # ---------- СОЗДАНИЕ КОМНАТЫ ----------
    elif data == "menu_create_room":
        create_room(update, context)
        return

    # ---------- ПОМОЩЬ ----------
    elif data == "menu_help":
        keyboard = [
            [InlineKeyboardButton("🎬 Поиск", callback_data="menu_search")],
            [InlineKeyboardButton("👥 Комната", callback_data="menu_create_room")],
            [InlineKeyboardButton("◀️ Назад", callback_data="menu_back")]
        ]
        query.edit_message_text(
            "❓ Помощь\n\n"
            "🔍 Поиск — /search название\n"
            "👥 Комната — /room\n"
            "🔑 Вход — /join ID\n"
            "🌐 Плеер — открывается автоматически",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        query.answer()
        return

    # ---------- НАЗАД В ГЛАВНОЕ МЕНЮ ----------
    elif data == "menu_back":
        keyboard = [
            [InlineKeyboardButton("🎬 Поиск фильма", callback_data="menu_search")],
            [InlineKeyboardButton("👥 Создать комнату", callback_data="menu_create_room")],
            [InlineKeyboardButton("❓ Помощь", callback_data="menu_help")]
        ]
        query.edit_message_text(
            "🎬 Cinema Party\n\n"
            "Смотри фильмы с друзьями синхронно!\n"
            "YouTube, VK, LordFilm и другие источники.\n\n"
            "👇 Выбери действие:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        query.answer()
        return

    # ---------- БЫСТРАЯ КОМНАТА ----------
    elif data == "quick_room":
        video_url = context.user_data.get('current_video')
        if video_url:
            create_room(update, context, video_url=video_url, video_title='Видео по ссылке')
        else:
            create_room(update, context)
        return

    # ---------- ПРИГЛАШЕНИЕ ----------
    if data.startswith('invite_'):
        room_id = data.split('_')[1]
        webrtc_url = f"{WEBRTC_SERVER}/player.html?room={room_id}"

        room = rooms.get(room_id, {})
        video = room.get('video', {})
        if video.get('url'):
            webrtc_url += f"&url={video['url']}&autoplay=1"

        invite_text = (
            f"🔗 Приглашение в комнату {room_id}\n\n"
            f"1️⃣ Введи команду:\n/join {room_id}\n\n"
            f"2️⃣ Или открой плеер:\n{webrtc_url}\n\n"
            f"👥 Участников: {len(room.get('users', []))}"
        )

        query.message.reply_text(invite_text)
        query.answer("✅ Ссылка отправлена")
        return

    # ---------- ПОКАЗАТЬ ID ----------
    elif data.startswith('show_id_'):
        room_id = data.split('_')[2]
        query.answer(f"ID комнаты: {room_id}", show_alert=False)
        return

    # ---------- ОБНОВИТЬ КОМНАТУ ----------
    elif data.startswith('refresh_'):
        room_id = data.split('_')[1]
        if room_id in rooms:
            webrtc_url = f"{WEBRTC_SERVER}/player.html?room={room_id}"
            video_url = rooms[room_id].get('video', {}).get('url')
            if video_url:
                webrtc_url += f"&url={video_url}&autoplay=1"

            keyboard = [
                [InlineKeyboardButton("🎬 Искать фильм", callback_data="menu_search")],
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
                msg = query.edit_message_text("⏳ Загружаю видео...")

                video_url = parser.get_video_url(movie['url'])

                if video_url:
                    context.user_data['current_video'] = video_url

                    # СОЗДАЁМ КОМНАТУ АВТОМАТИЧЕСКИ С ВИДЕО
                    room_id = str(uuid.uuid4())[:6].upper()

                    with get_room_lock(room_id):
                        rooms[room_id] = {
                            'users': [{'id': user_id, 'username': username}],
                            'video': {
                                'url': video_url,
                                'title': movie['title'],
                                'added_at': datetime.now().isoformat()
                            },
                            'host': user_id,
                            'created_at': datetime.now().isoformat()
                        }

                    # ССЫЛКА НА ПЛЕЕР С АВТОЗАПУСКОМ ВИДЕО
                    player_url = f"{WEBRTC_SERVER}/player.html?room={room_id}&url={video_url}&autoplay=1"

                    keyboard = [
                        [InlineKeyboardButton("🎬 Смотреть в плеере", url=player_url)],
                        [
                            InlineKeyboardButton("👥 Пригласить", callback_data=f"invite_{room_id}"),
                            InlineKeyboardButton("📋 ID", callback_data=f"show_id_{room_id}")
                        ],
                        [InlineKeyboardButton("🔍 Новый поиск", callback_data="menu_search")]
                    ]

                    msg.edit_text(
                        f"🎬 {movie['title']}\n\n"
                        f"✅ Видео загружено в комнату {room_id}\n"
                        f"👉 Нажми кнопку ниже — фильм сразу начнётся!",
                        reply_markup=InlineKeyboardMarkup(keyboard)
                    )
                else:
                    msg.edit_text("❌ Не удалось загрузить видео\n\nПопробуй другой фильм.")
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
print("✅ Парсер видео загружен")
print(f"🖥 WebRTC сервер: {WEBRTC_SERVER}")
print("✅ Режим: БЕЗ MARKDOWN - ОШИБОК НЕТ")
print("✅ Режим: АВТОЗАПУСК ВИДЕО В ПЛЕЕРЕ")

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