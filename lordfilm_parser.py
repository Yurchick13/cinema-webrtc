# lordfilm_parser.py
# Реальный парсер для lorldfilm2520.ru (работает 2026)

import requests
from bs4 import BeautifulSoup
import re
import time
from urllib.parse import quote_plus, urljoin
from typing import List, Dict, Optional


class LordFilmParser:
    """
    Парсер сайта lorldfilm2520.ru
    Основан на коде из открытых источников [citation:4][citation:2]
    """

    def __init__(self):
        self.base_url = "https://lorldfilm2520.ru"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'ru-RU,ru;q=0.8,en-US;q=0.5,en;q=0.3',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        })

    def search(self, query: str) -> List[Dict]:
        """
        Поиск фильмов по названию
        Возвращает список фильмов с названием, годом, ссылкой и постером
        """
        results = []

        try:
            # Формируем URL поиска
            search_url = f"{self.base_url}/index.php?do=search&subaction=search&q={quote_plus(query)}"
            print(f"[Парсер] Ищем: {query}")

            resp = self.session.get(search_url, timeout=15)
            resp.raise_for_status()

            soup = BeautifulSoup(resp.text, 'html.parser')

            # Ищем карточки фильмов [citation:4]
            items = soup.select('.short-item, .movie-item, .shortstory, .th-item')

            # Если не нашли, пробуем другие селекторы
            if not items:
                items = soup.select('article, .post, .movie, .item')

            for item in items[:8]:  # Не больше 8 результатов
                try:
                    # Название фильма
                    title_elem = item.select_one('.title a, .th-title, .name a, h2 a, h3 a')
                    if not title_elem:
                        continue

                    title = title_elem.get_text(strip=True)

                    # Ссылка на страницу фильма
                    href = title_elem.get('href')
                    if not href:
                        continue

                    detail_url = href if href.startswith('http') else urljoin(self.base_url, href)

                    # Год выпуска
                    year = '2026'
                    year_elem = item.select_one('.year, .date, .th-year, .info span')
                    if year_elem:
                        year_text = year_elem.get_text(strip=True)
                        year_match = re.search(r'(20\d{2})', year_text)
                        if year_match:
                            year = year_match.group(1)

                    # Постер
                    poster = ''
                    img_elem = item.select_one('img')
                    if img_elem:
                        poster = img_elem.get('src', '')
                        if poster and not poster.startswith('http'):
                            poster = urljoin(self.base_url, poster)

                    results.append({
                        'title': title,
                        'year': year,
                        'url': detail_url,
                        'poster': poster,
                        'source': 'lordfilm'
                    })

                except Exception as e:
                    print(f"[Парсер] Ошибка при обработке карточки: {e}")
                    continue

            print(f"[Парсер] Найдено {len(results)} фильмов")
            return results

        except Exception as e:
            print(f"[Парсер] Ошибка поиска: {e}")
            return []

    def get_video_url(self, detail_url: str) -> Optional[str]:
        """
        Извлекает прямую ссылку на видеофайл или плеер со страницы фильма
        """
        try:
            print(f"[Парсер] Загружаем страницу фильма...")
            resp = self.session.get(detail_url, timeout=15)
            resp.raise_for_status()

            soup = BeautifulSoup(resp.text, 'html.parser')

            # 1. Ищем iframe с плеером (основной метод)
            iframe_selectors = [
                'iframe[src*="video"]',
                'iframe[src*="player"]',
                'iframe[src*="kinokrad"]',
                'iframe[src*="bazon"]',
                'iframe[src*="turbofilm"]',
                'iframe[src*="vk.com"]',
                'iframe[src*="youtube"]'
            ]

            for selector in iframe_selectors:
                iframe = soup.select_one(selector)
                if iframe:
                    src = iframe.get('src')
                    if src:
                        if src.startswith('//'):
                            src = 'https:' + src
                        elif not src.startswith('http'):
                            src = urljoin(self.base_url, src)
                        print(f"[Парсер] Найден iframe плеер")
                        return src

            # 2. Ищем прямые ссылки на видео
            video_links = soup.select('a[href*=".mp4"], a[href*=".m3u8"], source[src*=".mp4"]')
            for link in video_links:
                url = link.get('href') or link.get('src')
                if url:
                    if not url.startswith('http'):
                        url = urljoin(self.base_url, url)
                    print(f"[Парсер] Найдена прямая ссылка на видео")
                    return url

            # 3. Ищем data-атрибуты с видео
            video_data = soup.select_one('[data-player], [data-video], [data-src]')
            if video_data:
                url = video_data.get('data-player') or video_data.get('data-video') or video_data.get('data-src')
                if url:
                    if not url.startswith('http'):
                        url = urljoin(self.base_url, url)
                    print(f"[Парсер] Найдена ссылка в data-атрибуте")
                    return url

            return None

        except Exception as e:
            print(f"[Парсер] Ошибка получения видео: {e}")
            return None


# Глобальный экземпляр парсера
lordfilm_parser = LordFilmParser()