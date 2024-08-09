import config
import telebot
from telebot import types
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime
import logging
import json
import os

bot = telebot.TeleBot(config.TOKEN)

# Конфигурация логирования
logging.basicConfig(level=logging.INFO)

# Файлы для хранения данных
USER_DATA_FILE = 'user_data.json'
USER_LINKS_COUNT_FILE = 'user_links_count.json'
ALL_USERS_FILE = 'all_users.json'
SENT_DATA_FILE = 'sent_data.json'

# Лимиты ссылок
USER_WEEKLY_LIMIT = 6
TOTAL_WEEKLY_LIMIT = 36

# Функция для загрузки данных из JSON файла
def load_json_file(filename):
    if os.path.exists(filename):
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                data = f.read().strip()
                if not data:
                    return {}
                return json.loads(data)
        except json.JSONDecodeError as e:
            logging.error(f"Ошибка декодирования JSON в файле {filename}: {e}")
            return {}
        except IOError as e:
            logging.error(f"Ошибка чтения файла {filename}: {e}")
            return {}
    return {}

# Функция для сохранения данных в JSON файл
def save_json_file(filename, data):
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
    except IOError as e:
        logging.error(f"Ошибка записи в файл {filename}: {e}")

# Загрузка данных
user_data = load_json_file(USER_DATA_FILE)
user_links_count = load_json_file(USER_LINKS_COUNT_FILE)
all_users = set(load_json_file(ALL_USERS_FILE).keys())  # Преобразование ключей словаря в множество

# Загрузка отправленных данных
def load_sent_data():
    return load_json_file(SENT_DATA_FILE) or []

# Сохранение отправленных данных
def save_sent_data(data):
    save_json_file(SENT_DATA_FILE, data)

# Напоминание пользователям
def send_daily_reminder():
    for chat_id in list(all_users):
        try:
            bot.send_message(chat_id, "Привет! Не забудь отправить сайт на проверку сегодня!")
        except telebot.apihelper.ApiTelegramException as e:
            if e.error_code == 403:
                logging.warning(f"Пользователь {chat_id} заблокировал бота. Удаляю из списка.")
                all_users.discard(chat_id)
                save_json_file(ALL_USERS_FILE, {uid: True for uid in all_users})
            else:
                logging.error(f"Ошибка при отправке сообщения пользователю {chat_id}: {e}")

# Запуск планировщика
scheduler = BackgroundScheduler()
scheduler.add_job(send_daily_reminder, 'interval', days=1, start_date=datetime.now().replace(hour=9, minute=0, second=0))
scheduler.start()

# Обработчик команды /test_reminder
@bot.message_handler(commands=['test_reminder'])
def test_reminder(message):
    bot.send_message(message.chat.id, "Отправляю тестовое напоминание...")
    send_daily_reminder()

# Получение ссылки от пользователя
@bot.message_handler(func=lambda message: 'link' not in user_data.get(message.chat.id, {}))
def get_link(message):
    all_users.add(message.chat.id)
    save_json_file(ALL_USERS_FILE, {uid: True for uid in all_users})

    if message.chat.id not in user_data:
        user_data[message.chat.id] = {}
    user_data[message.chat.id]['link'] = message.text

    bot.send_message(message.chat.id, "Спасибо за ссылку. Теперь отправьте номер решения (формат: входит в Федеральный список экстремистских материалов под номером ####).")

def lowercase_first_char(text):
    if not text:
        return text
    return text[0].lower() + text[1:]

@bot.message_handler(func=lambda message: 'gender_selection' in user_data.get(message.chat.id, {}))
def handle_gender_selection(message):
    logging.info(f"Получен выбор пола от {message.chat.id}: {message.text}")

    gender = message.text.strip()
    valid_genders = ["размещен", "размещена", "размещено"]

    if gender not in valid_genders:
        bot.send_message(message.chat.id, "Пожалуйста, выберите корректный пол: размещен, размещена или размещено.")
        return

    decision_number = user_data[message.chat.id].pop('gender_selection', None)

    if not decision_number:
        bot.send_message(message.chat.id, "Не удалось найти номер решения. Попробуйте снова.")
        return

    user_data[message.chat.id]['gender'] = gender
    save_json_file(USER_DATA_FILE, user_data)

    sent_data = load_sent_data()
    existing_data = next((item for item in sent_data if item['decision_number'] == decision_number), None)

    logging.info(f"Данные для номера решения {decision_number}: {existing_data}")

    if existing_data:
        data_text = existing_data.get('data', '')

        final_message = (
            f"{user_data[message.chat.id].get('link', '')} "
            f"{gender} "
            f"{lowercase_first_char(data_text)}"
            f"(Включён в Федеральный список экстремистских материалов под номером {decision_number})"
        )

        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        confirm_button = types.KeyboardButton("Подтвердить")
        restart_button = types.KeyboardButton("Начать заново")
        markup.add(confirm_button, restart_button)

        bot.send_message(message.chat.id,
                         f"Вот итоговое сообщение:\n\n{final_message}\n\nВы хотите подтвердить или начать заново?",
                         reply_markup=markup)
        user_data[message.chat.id]['final_message'] = final_message
        save_json_file(USER_DATA_FILE, user_data)
    else:
        bot.send_message(message.chat.id, "Не удалось найти данные для данного номера решения. Попробуйте снова.")

@bot.message_handler(func=lambda message: message.text in ["Подтвердить", "Начать заново"])
def handle_confirmation(message):
    if message.text == "Подтвердить":
        final_message = user_data[message.chat.id].get('final_message', '')

        try:
            bot.send_message('-4223848296', final_message)
        except telebot.apihelper.ApiTelegramException as e:
            logging.error(f"Ошибка при отправке сообщения в канал: {e}")
            bot.send_message(message.chat.id, "Произошла ошибка при отправке данных. Пожалуйста, попробуйте позже.")
            return

        bot.send_message(message.chat.id, "Данные обновлены и отправлены.")

        sent_data = load_sent_data()
        sent_data.append({
            'decision_number': user_data[message.chat.id].get('decision_number', ''),
            'data': user_data[message.chat.id].get('data', '').lower(),
            'gender': user_data[message.chat.id].get('gender', '')
        })
        save_sent_data(sent_data)

        user_data[message.chat.id] = {}
        save_json_file(USER_DATA_FILE, user_data)

    elif message.text == "Начать заново":
        bot.send_message(message.chat.id, "Процесс начинается заново. Пожалуйста, отправьте номер решения еще раз.")
        user_data[message.chat.id] = {}
        save_json_file(USER_DATA_FILE, user_data)

@bot.message_handler(func=lambda message: 'decision_number' not in user_data.get(message.chat.id, {}) and 'gender_selection' not in user_data.get(message.chat.id, {}))
def get_decision_number(message):
    decision_text = message.text.strip()

    if not decision_text.isdigit() or len(decision_text) < 1:
        bot.send_message(message.chat.id, "Пожалуйста, введите корректный номер решения.")
        return

    sent_data = load_sent_data()
    existing_data = next((item for item in sent_data if item['decision_number'] == decision_text), None)

    if existing_data:
        if not existing_data.get('gender'):
            markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
            male_button = types.KeyboardButton("размещен")
            female_button = types.KeyboardButton("размещена")
            neutral_button = types.KeyboardButton("размещено")
            markup.add(male_button, female_button, neutral_button)

            bot.send_message(message.chat.id,
                             "Выберите пол: размещен, размещена или размещено.",
                             reply_markup=markup)

            user_data[message.chat.id]['gender_selection'] = decision_text
            save_json_file(USER_DATA_FILE, user_data)
            return

        gender = existing_data.get('gender', '')
        final_message = (
            f"{user_data[message.chat.id].get('link', '')} "
            f"{gender} "
            f"{existing_data.get('data', '').lower()}"
            f"(Включён в Федеральный список экстремистских материалов под номером {decision_text})"
        )
        try:
            bot.send_message('-4223848296', final_message)
        except telebot.apihelper.ApiTelegramException as e:
            logging.error(f"Ошибка при отправке сообщения в канал: {e}")
            bot.send_message(message.chat.id, "Произошла ошибка при отправке данных. Пожалуйста, попробуйте позже.")
            return

        bot.send_message(message.chat.id,
                         "Данные с таким номером решения уже были отправлены ранее. Отчёт готов и отправлен.")

        user_data[message.chat.id] = {}
        save_json_file(USER_DATA_FILE, user_data)
        return

    user_data[message.chat.id]['decision_number'] = decision_text

    if message.chat.id not in user_links_count:
        user_links_count[message.chat.id] = 0

    user_links_count[message.chat.id] += 1

    data_text = user_data[message.chat.id].get('data', '').lower()

    def capitalize_first_char(text):
        if not text:
            return text
        return text[0].upper() + text[1:]

    final_message = (
        f"{user_data[message.chat.id]['link']} "
        f"{user_data[message.chat.id].get('gender', '')} "
        f"{capitalize_first_char(data_text)}"
        f"(Включён в Федеральный список экстремистских материалов под номером {user_data[message.chat.id]['decision_number']})"
    )

    try:
        bot.send_message('-4223848296', final_message)
    except telebot.apihelper.ApiTelegramException as e:
        logging.error(f"Ошибка при отправке сообщения в канал: {e}")
        bot.send_message(message.chat.id, "Произошла ошибка при отправке данных. Пожалуйста, попробуйте позже.")
        return

    save_json_file(USER_DATA_FILE, user_data)
    save_json_file(USER_LINKS_COUNT_FILE, user_links_count)

    sent_data = load_sent_data()
    sent_data.append({
        'decision_number': decision_text,
        'data': user_data[message.chat.id].get('data', '').lower(),
        'gender': user_data[message.chat.id].get('gender', '')
    })
    save_sent_data(sent_data)

    user_links = user_links_count[message.chat.id]
    if user_links >= USER_WEEKLY_LIMIT:
        bot.send_message(message.chat.id, f"Вы достигли лимита в {USER_WEEKLY_LIMIT} ссылок на этой неделе. Молодец!")
    else:
        remaining = USER_WEEKLY_LIMIT - user_links
        bot.send_message(message.chat.id, f"Вы отправили {user_links} ссылок. Осталось {remaining}.")

    total_links_sent = sum(user_links_count.values())
    if total_links_sent >= TOTAL_WEEKLY_LIMIT:
        bot.send_message(message.chat.id, f"Всего отправлено {TOTAL_WEEKLY_LIMIT} ссылок на этой неделе. Все молодцы!")
    else:
        remaining = TOTAL_WEEKLY_LIMIT - total_links_sent
        bot.send_message(message.chat.id, f"Всего отправлено {total_links_sent} ссылок. Осталось {remaining}.")

    user_data[message.chat.id] = {}
    save_json_file(USER_DATA_FILE, user_data)

# Запуск бота
if __name__ == "__main__":
    try:
        bot.polling(none_stop=True)
    except telebot.apihelper.ApiTelegramException as e:
        logging.error(f'Ошибка API Telegram: {e}')
    except ConnectionError as e:
        logging.error(f'Ошибка соединения: {e}')
    except Exception as r:
        logging.error(f'Непредвиденная ошибка: {r}')
    finally:
        logging.info("Здесь всё закончилось")
