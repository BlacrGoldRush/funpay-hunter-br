import os
import requests
from bs4 import BeautifulSoup
from flask import Flask, jsonify
import threading
import time
import logging
from datetime import datetime
import re

# Создаем Flask приложение
app = Flask(__name__)

# ================= НАСТРОЙКИ =================
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8353596700:AAGGBzOlnQZepaq0lnXys4KlQNKozJpXq7A")
CHAT_ID = os.environ.get("CHAT_ID", "5316017487")

# Ссылки на Black Russia
FUNPAY_URLS = {
    "валюта": "https://funpay.com/chips/186/",
    "аккаунты": "https://funpay.com/lots/1442/"
}

# Настройки
CHECK_INTERVAL = 300  # 5 минут
MAX_PRICE = 10000

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Глобальные переменные
monitor_running = False
monitor_thread = None
seen_items = []

# ================= ФУНКЦИИ =================

def send_telegram(message):
    """Отправляет сообщение в Telegram"""
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        payload = {
            'chat_id': CHAT_ID,
            'text': message,
            'parse_mode': 'HTML'
        }
        response = requests.post(url, data=payload, timeout=10)
        if response.status_code == 200:
            logger.info("✅ Сообщение отправлено")
            return True
        else:
            logger.error(f"❌ Ошибка Telegram: {response.status_code}")
            return False
    except Exception as e:
        logger.error(f"❌ Ошибка отправки: {e}")
        return False

def parse_funpay(url, category):
    """Парсит страницу FunPay"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
        }
        
        logger.info(f"🔍 Парсинг {category}...")
        response = requests.get(url, headers=headers, timeout=15)
        
        if response.status_code != 200:
            logger.error(f"❌ Ошибка {response.status_code}")
            return []
        
        # Парсим HTML
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Ищем товары разными способами
        items = []
        
        # Способ 1: Ищем все ссылки с текстом о цене
        for link in soup.find_all('a', href=True):
            text = link.get_text(strip=True)
            # Если есть "руб" или "₽" в тексте
            if ('руб' in text.lower() or '₽' in text) and len(text) < 150:
                # Ищем цену
                price_match = re.search(r'(\d{3,})\s*(руб|₽|р\.)', text, re.IGNORECASE)
                if price_match:
                    price = int(price_match.group(1))
                    if price <= MAX_PRICE:
                        # Формируем полную ссылку
                        href = link['href']
                        full_link = f"https://funpay.com{href}" if href.startswith('/') else href
                        
                        # Создаем заголовок
                        title = text.split('руб')[0].strip() if 'руб' in text.lower() else text[:50]
                        
                        items.append({
                            'id': f"{title}_{price}_{category}",
                            'title': title[:80],
                            'price': price,
                            'link': full_link,
                            'category': category
                        })
        
        logger.info(f"✅ Найдено {len(items)} товаров в {category}")
        return items
        
    except Exception as e:
        logger.error(f"❌ Ошибка парсинга: {e}")
        return []

def monitor_loop():
    """Основной цикл мониторинга"""
    global monitor_running, seen_items
    
    logger.info("🚀 Запуск мониторинга...")
    send_telegram("🤖 <b>FunPay Hunter запущен!</b>\nНачинаю мониторинг Black Russia...")
    
    while monitor_running:
        try:
            current_time = datetime.now().strftime("%H:%M:%S")
            logger.info(f"🔍 Проверка в {current_time}")
            
            new_items = []
            
            # Проверяем все категории
            for category, url in FUNPAY_URLS.items():
                items = parse_funpay(url, category)
                
                for item in items:
                    if item['id'] not in seen_items:
                        new_items.append(item)
                        seen_items.append(item['id'])
            
            # Отправляем уведомления о новых товарах
            if new_items:
                logger.info(f"🎯 Найдено новых: {len(new_items)}")
                send_telegram(f"🎯 <b>Найдено {len(new_items)} новых предложений!</b>")
                
                for i, item in enumerate(new_items[:3], 1):
                    message = f"""
🏆 <b>ПРЕДЛОЖЕНИЕ #{i}</b>

📦 {item['title']}
💰 {item['price']} руб.
🎮 {item['category']}

🔗 <a href="{item['link']}">КУПИТЬ</a>
                    """
                    send_telegram(message)
                    time.sleep(1)
            
            # Ждем перед следующей проверкой
            logger.info(f"😴 Следующая проверка через {CHECK_INTERVAL//60} минут...")
            time.sleep(CHECK_INTERVAL)
            
        except Exception as e:
            logger.error(f"❌ Ошибка в мониторинге: {e}")
            time.sleep(60)
    
    logger.info("🛑 Мониторинг остановлен")

# ================= ВЕБ-РОУТЫ =================

@app.route('/')
def home():
    """Главная страница"""
    return """
    <h1>🤖 FunPay Hunter для Black Russia</h1>
    <p>Бот для мониторинга выгодных предложений на FunPay</p>
    <p><a href="/start">▶️ Запустить мониторинг</a></p>
    <p><a href="/stop">⏹️ Остановить мониторинг</a></p>
    <p><a href="/status">📊 Статус</a></p>
    <p><a href="/health">❤️ Проверка работы</a></p>
    """

@app.route('/start')
def start_monitor():
    """Запускает мониторинг"""
    global monitor_running, monitor_thread
    
    if not monitor_running:
        monitor_running = True
        monitor_thread = threading.Thread(target=monitor_loop, daemon=True)
        monitor_thread.start()
        return "✅ Мониторинг запущен!"
    return "⚠️ Мониторинг уже запущен"

@app.route('/stop')
def stop_monitor():
    """Останавливает мониторинг"""
    global monitor_running
    monitor_running = False
    return "⏹️ Мониторинг остановлен"

@app.route('/status')
def status():
    """Статус бота"""
    return jsonify({
        'status': 'running' if monitor_running else 'stopped',
        'bot_token': 'установлен' if BOT_TOKEN else 'не установлен',
        'chat_id': CHAT_ID,
        'time': datetime.now().strftime("%H:%M:%S")
    })

@app.route('/health')
def health():
    """Проверка работы"""
    return "✅ OK", 200

# ================= ЗАПУСК =================

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
