# -*- coding: utf-8 -*-
import sys
import uuid
import json
import time
import threading
from datetime import datetime
from urllib.parse import quote_plus, urlparse
import requests
from bs4 import BeautifulSoup

print("🚀 ЗАПУСК БОТА...")
print(f"🐍 Python: {sys.version_info.major}.{sys.version_info.minor}")
print("-" * 40)

# ТВОЙ ТОКЕН
BOT_TOKEN = "8414477578:AAH44JTQWDXmQl_fRsN4fIuSHBV9tYsEscQ"

try:
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
    from telegram.ext import Updater, CommandHandler, MessageHandler, CallbackQueryHandler, Filters
    from telegram.error import BadRequest

    print("✅ Telegram библиотека загружена")
except ImportError:
    import subprocess

    subprocess.check_call(
        [sys.executable, "-m", "pip", "install", "python-telegram-bot==13.15", "requests", "beautifulsoup4"])
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
    from telegram.ext import Updater, CommandHandler, MessageHandler, CallbackQueryHandler, Filters
    from telegram.error import BadRequest


# ============ ПАРСЕР LORDFILM ============
class LordFilmParser:
    def __init__(self):
        self.base_url = "https://lorldfilm2520.ru"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }

    def search(self, query):
        """Поиск фильмов на сайте"""
        try:
            search_url = f"{self.base_url}/index.php?do=search&subaction=search&q={quote_plus(query)}"
            response = requests.get(search_url, headers=self.headers, timeout=10)
            soup = BeautifulSoup(response.text, 'html.parser')

            results = []
            items = soup.select('.short-item, .movie-item, .shortstory, .film-item')

            if not items:
                items = soup.select('article, .post, .movie, .item')

            for item in items[:8]:
                try:
                    # Название
                    title_elem = item.select_one('.title a, .name a, h2 a, h3 a')
                    if not title_elem:
                        continue

                    title = title_elem.text.strip()
                    detail_url = title_elem.get('href')
                    if not detail_url.startswith('http'):
                        detail_url = self.base_url + detail_url

                    # Год
                    year = '2025'
                    year_elem = item.select_one('.year, .date, .info span')
                    if year_elem:
                        year = year_elem.text.strip()[:4]

                    # Постер
                    poster = ''
                    img_elem = item.select_one('img')
                    if img_elem:
                        poster = img_elem.get('src', '')
                        if not poster.startswith('http'):
                            poster = self.base_url + poster

                    results.append({
                        'title': title,
                        'year': year,
                        'url': detail_url,
                        'poster': poster,
                        'source': 'lordfilm'
                    })
                except:
                    continue

            return results
        except Exception as e:
            print(f"Парсер ошибка: {e}")
            return []

    def get_video_url(self, detail_url):
        """Получение прямой ссылки на видео с iframe"""
        try:
            response = requests.get(detail_url, headers=self.headers, timeout=10)
            soup = BeautifulSoup(response.text, 'html.parser')

            # Ищем iframe с видео
            iframe = soup.select_one(
                'iframe[src*="video"], iframe[src*="player"], iframe[src*="kinokrad"], iframe[src*="bazon"]')
            if iframe:
                video_url = iframe.get('src')
                if not video_url.startswith('http'):
                    video_url = self.base_url + video_url
                return video_url

            # Ищем прямые ссылки
            video_links = soup.select('a[href*=".mp4"], a[href*=".m3u8"], source[src*=".mp4"]')
            for link in video_links:
                url = link.get('href') or link.get('src')
                if url:
                    if not url.startswith('http'):
                        url = self.base_url + url
                    return url

            return None
        except:
            return None


parser = LordFilmParser()

# ============ СИНХРОНИЗАЦИЯ КОМНАТ ============
rooms = {}
room_locks = {}


def get_room_lock(room_id):
    """Получить блокировку для комнаты"""
    if room_id not in room_locks:
        room_locks[room_id] = threading.Lock()
    return room_locks[room_id]


def broadcast_to_room(bot, room_id, command, data=None):
    """Отправить команду всем в комнате кроме хоста"""
    if room_id not in rooms:
        return

    room = rooms[room_id]
    host_id = room.get('host')

    for user in room.get('users', []):
        user_id = user.get('id')
        if user_id and user_id != host_id:
            try:
                if command == 'play':
                    bot.send_message(
                        chat_id=user_id,
                        text=f"🎬 Хост запустил видео!\n\n{room.get('video', {}).get('url', '')}",
                        reply_markup=InlineKeyboardMarkup([[
                            InlineKeyboardButton("▶️ Смотреть синхронно", url=room.get('video', {}).get('url', ''))
                        ]])
                    )
                elif command == 'video':
                    bot.send_message(
                        chat_id=user_id,
                        text=f"🎥 В комнате загружено новое видео!\n\n{data}",
                        reply_markup=InlineKeyboardMarkup([[
                            InlineKeyboardButton("▶️ Смотреть", url=data)
                        ]])
                    )
            except:
                pass


# ============ КОМАНДЫ БОТА ============
def start(update, context):
    """Старт"""
    update.message.reply_text(
        "🎬 LordFilm Cinema Bot\n\n"
        "🔍 /search [название] - поиск на lordfilm\n"
        "👥 /room - создать комнату\n"
        "🔑 /join [ID] - войти в комнату\n"
        "🎥 /video [ID] [URL] - загрузить видео в комнату\n"
        "📹 Отправь ссылку - смотреть одному\n\n"
        f"✅ Парсинг lordfilm2520.ru | Python 3.10"
    )


def search_command(update, context):
    """Поиск фильмов на lordfilm"""
    query = ' '.join(context.args) if context.args else ''

    if not query:
        update.message.reply_text("🔍 /search название фильма")
        return

    msg = update.message.reply_text("🔍 Ищем на lordfilm2520.ru...")

    try:
        results = parser.search(query)

        if not results:
            msg.edit_text("❌ Ничего не найдено на lordfilm")
            return

        keyboard = []
        for i, movie in enumerate(results[:5]):
            btn_text = f"🎬 {movie['title'][:30]} ({movie['year']})"
            keyboard.append([
                InlineKeyboardButton(btn_text, callback_data=f"lord_{i}")
            ])

        context.user_data['lord_results'] = results
        msg.edit_text(
            f"✅ Найдено на lordfilm2520.ru:\n\nПервый фильм — {results[0]['title']}",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    except Exception as e:
        msg.edit_text(f"❌ Ошибка: {e}")


def room_command(update, context):
    """Создать комнату"""
    try:
        room_id = context.args[0] if context.args else str(uuid.uuid4())[:6].upper()
        user_id = str(update.effective_user.id)
        username = update.effective_user.first_name or "User"

        if room_id not in rooms:
            rooms[room_id] = {
                'users': [],
                'video': None,
                'host': user_id,
                'created_at': datetime.now().isoformat()
            }

        with get_room_lock(room_id):
            if user_id not in [u['id'] for u in rooms[room_id]['users']]:
                rooms[room_id]['users'].append({'id': user_id, 'username': username})
            rooms[room_id]['host'] = user_id

        keyboard = [
            [InlineKeyboardButton("🔍 Поиск фильма", switch_inline_query_current_chat="")],
            [InlineKeyboardButton("👥 Пригласить", callback_data=f"invite_{room_id}")]
        ]

        update.message.reply_text(
            f"🎥 Комната {room_id}\n"
            f"👤 Хост: {username}\n"
            f"👥 Участников: {len(rooms[room_id]['users'])}\n\n"
            f"🔗 Пригласить: /join {room_id}",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    except Exception as e:
        update.message.reply_text(f"❌ Ошибка: {e}")


def join_command(update, context):
    """Войти в комнату"""
    try:
        room_id = context.args[0] if context.args else None

        if not room_id:
            update.message.reply_text("❌ /join ID_комнаты")
            return

        if room_id not in rooms:
            update.message.reply_text("❌ Комната не найдена")
            return

        user_id = str(update.effective_user.id)
        username = update.effective_user.first_name or "User"

        with get_room_lock(room_id):
            if user_id not in [u['id'] for u in rooms[room_id]['users']]:
                rooms[room_id]['users'].append({'id': user_id, 'username': username})

        room = rooms[room_id]
        host_name = "Неизвестно"
        for u in room['users']:
            if u['id'] == room.get('host'):
                host_name = u['username']
                break

        video_text = ""
        if room.get('video'):
            video_text = f"\n🎬 Видео загружено: ✅"

        update.message.reply_text(
            f"✅ Вошли в комнату {room_id}\n"
            f"👤 Хост: {host_name}\n"
            f"👥 Участников: {len(room['users'])}{video_text}"
        )

        # Уведомить хоста
        if room.get('host'):
            try:
                context.bot.send_message(
                    chat_id=room['host'],
                    text=f"👥 {username} вошел в комнату {room_id}"
                )
            except:
                pass

    except Exception as e:
        update.message.reply_text(f"❌ Ошибка: {e}")


def video_command(update, context):
    """Загрузить видео в комнату"""
    try:
        if not context.args or len(context.args) < 2:
            update.message.reply_text("🎥 /video ID_комнаты URL")
            return

        room_id = context.args[0].upper()
        url = context.args[1]

        if room_id not in rooms:
            update.message.reply_text("❌ Комната не найдена")
            return

        user_id = str(update.effective_user.id)
        if rooms[room_id].get('host') != user_id:
            update.message.reply_text("❌ Только хост может загружать видео")
            return

        rooms[room_id]['video'] = {
            'url': url,
            'time': 0,
            'playing': False,
            'added_by': user_id,
            'added_at': datetime.now().isoformat()
        }

        update.message.reply_text(f"✅ Видео загружено в комнату {room_id}")

        # Оповестить всех в комнате
        broadcast_to_room(context.bot, room_id, 'video', url)

    except Exception as e:
        update.message.reply_text(f"❌ Ошибка: {e}")


def handle_message(update, context):
    """Обработка ссылок"""
    try:
        text = update.message.text.strip()

        if text.startswith(('http://', 'https://')):
            context.user_data['current_video'] = text
            keyboard = [[InlineKeyboardButton("▶️ Смотреть", url=text)]]
            update.message.reply_text(
                "✅ Видео готово!",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
    except Exception as e:
        update.message.reply_text(f"❌ Ошибка: {e}")


def button_callback(update, context):
    """Обработка кнопок"""
    try:
        query = update.callback_query
        query.answer()

        if query.data.startswith('lord_'):
            idx = int(query.data.split('_')[1])
            results = context.user_data.get('lord_results', [])

            if idx < len(results):
                movie = results[idx]

                # Получаем видео ссылку
                msg = query.edit_message_text("⏳ Загружаем видео с lordfilm...")
                video_url = parser.get_video_url(movie['url'])

                if video_url:
                    context.user_data['current_video'] = video_url

                    keyboard = [
                        [InlineKeyboardButton("▶️ Смотреть сейчас", url=video_url)],
                        [InlineKeyboardButton("👥 Смотреть в комнате", callback_data=f"to_room_{video_url[:50]}")]
                    ]

                    msg.edit_text(
                        f"🎬 {movie['title']} ({movie['year']})\n\n✅ Видео загружено!",
                        reply_markup=InlineKeyboardMarkup(keyboard)
                    )
                else:
                    msg.edit_text("❌ Не удалось загрузить видео с lordfilm")

        elif query.data.startswith('invite_'):
            room_id = query.data.split('_')[1]
            query.edit_message_text(
                f"🔗 Приглашение в комнату:\n/join {room_id}"
            )

    except Exception as e:
        print(f"Button error: {e}")
        try:
            query.edit_message_text(f"❌ Ошибка: {e}")
        except:
            pass


def error_handler(update, context):
    """Глобальный обработчик ошибок"""
    try:
        print(f"⚠️ Ошибка: {context.error}")
    except:
        pass


# ============ ЗАПУСК ============
print("✅ Инициализация бота...")
print("✅ Парсер LordFilm загружен")
print("✅ Система комнат с синхронизацией готова")

try:
    updater = Updater(BOT_TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler('start', start))
    dp.add_handler(CommandHandler('search', search_command))
    dp.add_handler(CommandHandler('room', room_command))
    dp.add_handler(CommandHandler('join', join_command))
    dp.add_handler(CommandHandler('video', video_command))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))
    dp.add_handler(CallbackQueryHandler(button_callback))
    dp.add_error_handler(error_handler)

    print("✅ Бот готов к работе!")
    print("📱 Напиши @cinema_party_bot в Telegram")
    print("-" * 40)
    print("⏳ Запуск...")
    print("-" * 40)

    updater.start_polling()
    updater.idle()

except Exception as e:
    print(f"❌ Ошибка: {e}")
    import traceback

    traceback.print_exc()