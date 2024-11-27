import telegram
import config
import telebot
from telebot import types
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, timedelta
import logging
import json
import os
from telegram.ext import Updater, CommandHandler
from telebot.types import ReplyKeyboardMarkup, KeyboardButton


bot = telebot.TeleBot(config.TOKEN)



scheduler = BackgroundScheduler()

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

# Файл для хранения данных о полах решений
DECISION_DATA_FILE = 'decision_data.json'
LINKS_HISTORY_FILE = 'links_history.json'

@bot.message_handler(commands=['info'])
def send_info(message):
    info_text = (
        "👋 Привет! Вот инструкция, как отправить ссылку:\n\n"
        "1. Напиши ссылку в формате https://example.com, чтобы отправить её.\n"
        "2. Бот проверит, не превышен ли лимит на отправку ссылок. Если лимит достигнут, "
        "бот сообщит тебе, когда можно будет отправить ссылку снова.\n"
        "3. Если ссылка пройдет проверку, бот запросит дополнительную информацию, например, номер решения и/или род слова размещено.\n"
        "4. После этого твоя ссылка будет сохранена, и ты сможешь использовать её по назначению.\n\n"
        "Если у тебя возникли проблемы или вопросы, напиши администратору!"
    )
    bot.send_message(message.chat.id, info_text)



# Загрузка данных о ссылках и датах отправки
def load_links_history():
    return load_json_file(LINKS_HISTORY_FILE)

# Сохранение истории ссылок
def save_links_history(data):
    save_json_file(LINKS_HISTORY_FILE, data)

# Загрузка данных о полах
def load_decision_data():
    return load_json_file(DECISION_DATA_FILE)

# Сохранение данных о полах
def save_decision_data(data):
    save_json_file(DECISION_DATA_FILE, data)

# Загрузка данных о полах решений
decision_data = load_decision_data()


@bot.message_handler(commands=['manager_menu'])
def manager_menu(message):
    if message.chat.id != config.MANAGER_CHAT_ID:
        bot.send_message(message.chat.id, "У вас нет прав для доступа к этому меню.")
        return

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    users_button = types.KeyboardButton("Посмотреть всех пользователей")
    send_reminder_button = types.KeyboardButton("Отправить напоминание всем пользователям")
    stats_button = types.KeyboardButton("Посмотреть статистику")
    change_link_limits = types.KeyboardButton("Изменить лимиты ссылок")

    markup.add(users_button, send_reminder_button, stats_button, change_link_limits)

    bot.send_message(message.chat.id, "Выберите действие:", reply_markup=markup)

@bot.message_handler(func=lambda message: message.text == "Удалить пользователя")
def remove_user(message):
    if message.chat.id != config.MANAGER_CHAT_ID:
        bot.send_message(message.chat.id, "У вас нет прав для доступа к этому меню.")
        return

    bot.send_message(message.chat.id, "Введите ID пользователя, которого хотите удалить:")

    @bot.message_handler(func=lambda message: message.text.isdigit())
    def process_user_removal(message):
        user_id_to_remove = int(message.text)

        # Удаляем пользователя из всех списков
        if user_id_to_remove in user_data:
            del user_data[user_id_to_remove]
            save_json_file(USER_DATA_FILE, user_data)
            bot.send_message(message.chat.id, f"Пользователь {user_id_to_remove} удалён из базы данных.")
        else:
            bot.send_message(message.chat.id, "Пользователь с таким ID не найден.")

@bot.message_handler(func=lambda message: message.text == "Изменить лимиты ссылок")
def change_link_limits(message):
    if message.chat.id != config.MANAGER_CHAT_ID:
        bot.send_message(message.chat.id, "У вас нет прав для доступа к этому меню.")
        return

    bot.send_message(message.chat.id, "Введите новый лимит ссылок на пользователя (например, 6):")

    @bot.message_handler(func=lambda message: message.text.isdigit())
    def process_limit_change(message):
        new_limit = int(message.text)
        global USER_WEEKLY_LIMIT
        USER_WEEKLY_LIMIT = new_limit
        bot.send_message(message.chat.id, f"Новый лимит ссылок на пользователя: {new_limit}.")


@bot.message_handler(func=lambda message: message.text == "Отправить напоминание всем пользователям")
def send_reminder_to_all(message):
    if message.chat.id != config.MANAGER_CHAT_ID:
        bot.send_message(message.chat.id, "У вас нет прав для доступа к этому меню.")
        return

    send_daily_reminder()
    bot.send_message(message.chat.id, "Напоминание отправлено всем пользователям.")


@bot.message_handler(func=lambda message: message.text == "Посмотреть статистику")
def show_statistics(message):
    if message.chat.id != config.MANAGER_CHAT_ID:
        bot.send_message(message.chat.id, "У вас нет прав для доступа к этому меню.")
        return

    total_users = len(all_users)
    total_links_sent = sum(user_links_count.values())
    bot.send_message(message.chat.id,
                     f"Статистика:\nВсего пользователей: {total_users}\nВсего отправленных ссылок: {total_links_sent}")






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

# Обновлённая функция для планировщика
def send_daily_reminder():
    global all_users
    for chat_id in list(all_users):
        try:
            bot.send_message(chat_id, "Привет! Не забудь отправить сайт на проверку сегодня!")
        except telebot.apihelper.ApiTelegramException as e:
            if e.error_code == 403:  # Пользователь заблокировал бота
                logging.warning(f"Пользователь {chat_id} заблокировал бота. Удаляю из списка.")
                all_users.discard(chat_id)
                save_json_file(ALL_USERS_FILE, {uid: True for uid in all_users})
            else:
                logging.error(f"Ошибка при отправке сообщения пользователю {chat_id}: {e}")

scheduler.add_job(
    send_daily_reminder,
    'interval',
    days=1,
    start_date=(datetime.now() if datetime.now().hour < 9 else datetime.now().replace(hour=9) + timedelta(days=1))
)
scheduler.start()

# Обработчик команды /test_reminder
@bot.message_handler(commands=['test_reminder'])
def test_reminder(message):
    bot.send_message(message.chat.id, "Отправляю тестовое напоминание...")
    send_daily_reminder()

from datetime import datetime, timedelta

# Проверка, можно ли отправить ссылку
def can_send_link(user_id, link):
    links_history = load_links_history()

    # Если ссылка уже была отправлена, проверяем дату
    if link in links_history:
        last_sent = datetime.strptime(links_history[link], "%Y-%m-%d %H:%M:%S")
        days_since_last_sent = (datetime.now() - last_sent).days
        if days_since_last_sent < 90:  # Если прошло меньше 90 дней
            # Считаем, когда можно будет снова отправить ссылку
            next_send_date = last_sent + timedelta(days=90)
            return False, last_sent, next_send_date
    return True, None, None



# Сохранение новой ссылки с датой отправки
def save_link(user_id, link):
    links_history = load_links_history()
    links_history[link] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")  # Сохраняем текущую дату и время
    save_links_history(links_history)


import re

# Обработчик для получения ссылок
@bot.message_handler(func=lambda message: 'link' not in user_data.get(message.chat.id, {}))
def get_link(message):
    if message.text.startswith("http"):  # Проверка, если это ссылка
        all_users.add(message.chat.id)
        save_json_file(ALL_USERS_FILE, {uid: True for uid in all_users})

        link = message.text.strip()

        # Проверка на корректность ссылки
        url_pattern = re.compile(r'^(https?://[^\s]+)$')
        if not url_pattern.match(link):
            bot.send_message(message.chat.id, "Пожалуйста, отправьте действительную ссылку (например, https://example.com).")
            return

        # Проверка, можно ли отправить ссылку
        can_send, last_sent_date, next_send_date = can_send_link(message.chat.id, link)
        if not can_send:  # Если ссылка не может быть отправлена
            last_sent_date_str = last_sent_date.strftime("%d %B %Y")  # Дата последней отправки
            next_send_date_str = next_send_date.strftime("%d %B %Y")  # Дата следующей отправки

            # Переводим месяцы на русский
            months = {
                'January': 'января', 'February': 'февраля', 'March': 'марта', 'April': 'апреля',
                'May': 'мая', 'June': 'июня', 'July': 'июля', 'August': 'августа', 'September': 'сентября',
                'October': 'октября', 'November': 'ноября', 'December': 'декабря'
            }

            # Заменяем английские месяцы на русские
            last_sent_date_str = last_sent_date_str.replace(last_sent_date.strftime("%B"),
                                                            months[last_sent_date.strftime("%B")])
            next_send_date_str = next_send_date_str.replace(next_send_date.strftime("%B"),
                                                            months[next_send_date.strftime("%B")])

            bot.send_message(message.chat.id,
                             f"Эта ссылка была отправлена {last_sent_date_str}. Вы сможете отправить её снова {next_send_date_str}.")
            return

        if message.chat.id not in user_data:
            user_data[message.chat.id] = {}

        user_data[message.chat.id]['link'] = link
        save_json_file(USER_DATA_FILE, user_data)

        # Сохраняем ссылку
        save_link(message.chat.id, link)

        bot.send_message(message.chat.id, "Спасибо за ссылку. Теперь отправьте номер решения (в формате: ####).")



def lowercase_first_char(text):
    if not text:
        return text
    return text[0].lower() + text[1:]

# Обновлённая функция для обработки выбора пола
# Обновлённая функция для обработки выбора пола
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

    # Сохраняем пол в decision_data
    decision_data[decision_number] = gender
    save_decision_data(decision_data)

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


# Обработчик кнопки "Подтвердить", "Начать заново" или "Изменить пол"
@bot.message_handler(func=lambda message: message.text in ["Подтвердить", "Начать заново", "Изменить пол"])
def handle_confirmation(message):
    markup = types.ReplyKeyboardRemove()  # Удаление клавиатуры

    if message.text == "Подтвердить":
        final_message = user_data[message.chat.id].get('final_message', '')

        try:
            # Отправляем сообщение в канал
            bot.send_message(-4223848296, final_message)
        except telebot.apihelper.ApiTelegramException as e:
            logging.error(f"Ошибка при отправке сообщения в канал: {e}")
            bot.send_message(message.chat.id, "Ошибка при отправке данных. Попробуйте позже.", reply_markup=markup)
            return

        bot.send_message(message.chat.id, "Данные обновлены и отправлены.", reply_markup=markup)
        user_data[message.chat.id] = {}
        save_json_file(USER_DATA_FILE, user_data)

    elif message.text == "Начать заново":
        bot.send_message(message.chat.id, "Процесс начинается заново. Отправьте номер решения ещё раз.", reply_markup=markup)
        user_data[message.chat.id] = {}
        save_json_file(USER_DATA_FILE, user_data)

    elif message.text == "Изменить пол":
        # Запрашиваем пол заново
        ask_for_gender(message)

        # Убираем старое значение пола
        user_data[message.chat.id].pop('gender', None)
        save_json_file(USER_DATA_FILE, user_data)

# Функция для запроса пола
def ask_for_gender(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    male_button = types.KeyboardButton("размещен")
    female_button = types.KeyboardButton("размещена")
    neutral_button = types.KeyboardButton("размещено")
    markup.add(male_button, female_button, neutral_button)

    bot.send_message(message.chat.id, "Выберите новый пол: размещен, размещена или размещено.", reply_markup=markup)

@bot.message_handler(func=lambda message: message.text in ["размещен", "размещена", "размещено"])
def handle_gender_change(message):
    # Получаем выбранный пол
    new_gender = message.text.strip()

    # Обновляем пол в данных пользователя
    user_data[message.chat.id]['gender'] = new_gender
    save_json_file(USER_DATA_FILE, user_data)

    # Получаем номер решения
    decision_number = user_data[message.chat.id].get('decision_number')
    if not decision_number:
        bot.send_message(message.chat.id, "Не удалось найти номер решения. Попробуйте заново.")
        return

    # Получаем данные для этого номера решения
    sent_data = load_sent_data()
    existing_data = next((item for item in sent_data if item['decision_number'] == decision_number), None)

    if not existing_data:
        bot.send_message(message.chat.id, "Не удалось найти данные для этого номера решения. Попробуйте снова.")
        return

    # Формируем итоговое сообщение
    final_message = (
        f"{user_data[message.chat.id].get('link', '')} "
        f"{new_gender} "
        f"{lowercase_first_char(existing_data.get('data', ''))}"
        f"(Включён в Федеральный список экстремистских материалов под номером {decision_number})"
    )

    # Сохраняем итоговое сообщение для последующего использования
    user_data[message.chat.id]['final_message'] = final_message
    save_json_file(USER_DATA_FILE, user_data)

    # Отправляем сообщение с итоговым текстом и кнопками для подтверждения
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    confirm_button = types.KeyboardButton("Подтвердить")
    restart_button = types.KeyboardButton("Начать заново")
    change_gender_button = types.KeyboardButton("Изменить пол")
    markup.add(confirm_button, restart_button, change_gender_button)

    bot.send_message(
        message.chat.id,
        f"Вот итоговое сообщение:\n\n{final_message}\n\nВы хотите подтвердить или начать заново? Если нужно, вы можете изменить пол.",
        reply_markup=markup
    )
@bot.message_handler(func=lambda message: message.text == "Изменить пол")
def prompt_for_gender_change(message):
    # Предлагаем снова выбрать пол
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    button1 = types.KeyboardButton("размещен")
    button2 = types.KeyboardButton("размещена")
    button3 = types.KeyboardButton("размещено")
    markup.add(button1, button2, button3)

    bot.send_message(message.chat.id, "Выберите новый пол: размещен, размещена или размещено.", reply_markup=markup)





# Функция для получения пола решения из файла (если он был сохранён)
def get_gender_from_decision_data(decision_number):
    return decision_data.get(decision_number)


@bot.message_handler(func=lambda message: 'decision_number' not in user_data.get(message.chat.id, {}) and 'gender_selection' not in user_data.get(message.chat.id, {}))
def get_decision_number(message):
    decision_text = message.text.strip()

    # Проверяем, что введённый текст - это цифры и длина корректная
    if not decision_text.isdigit() or len(decision_text) < 1:
        bot.send_message(message.chat.id, "Пожалуйста, введите корректный номер решения.")
        return

    sent_data = load_sent_data()
    existing_data = next((item for item in sent_data if item['decision_number'] == decision_text), None)

    if not existing_data:
        bot.send_message(message.chat.id, "Не удалось найти данные для этого номера решения. Попробуйте снова.")
        return

    # Сохраняем номер решения
    user_data[message.chat.id]['decision_number'] = decision_text
    save_json_file(USER_DATA_FILE, user_data)

    # Проверяем, есть ли пол в данных для этого номера решения
    gender = get_gender_from_decision_data(decision_text)

    if gender:
        # Если пол уже есть, формируем итоговое сообщение
        final_message = (
            f"{user_data[message.chat.id].get('link', '')} "
            f"{gender} "
            f"{existing_data.get('data', '').lower()}"
            f"(Включён в Федеральный список экстремистских материалов под номером {decision_text})"
        )

        # Отправляем сообщение с итоговым текстом и кнопками для подтверждения
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        confirm_button = types.KeyboardButton("Подтвердить")
        restart_button = types.KeyboardButton("Начать заново")
        change_gender_button = types.KeyboardButton("Изменить пол")
        markup.add(confirm_button, restart_button, change_gender_button)

        bot.send_message(
            message.chat.id,
            f"Вот итоговое сообщение:\n\n{final_message}\n\nВы хотите подтвердить или начать заново? Если нужно, вы можете изменить пол.",
            reply_markup=markup
        )

        # Сохраняем итоговое сообщение для последующего использования
        user_data[message.chat.id]['final_message'] = final_message
        save_json_file(USER_DATA_FILE, user_data)

    else:
        # Если пол ещё не выбран, запрашиваем его
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        male_button = types.KeyboardButton("размещен")
        female_button = types.KeyboardButton("размещена")
        neutral_button = types.KeyboardButton("размещено")
        markup.add(male_button, female_button, neutral_button)

        data_preview = existing_data.get('data', '').lower()
        bot.send_message(
            message.chat.id,
            f"Данные: {data_preview}\n\nВыберите пол: размещен, размещена или размещено.",
            reply_markup=markup
        )

        user_data[message.chat.id]['gender_selection'] = decision_text
        save_json_file(USER_DATA_FILE, user_data)


# Обработчик кнопки "Подтвердить", "Начать заново" или "Изменить пол"
@bot.message_handler(func=lambda message: message.text in ["Подтвердить", "Начать заново", "Изменить пол"])
def handle_confirmation(message):
    markup = types.ReplyKeyboardRemove()  # Удаление клавиатуры

    if message.text == "Подтвердить":
        final_message = user_data[message.chat.id].get('final_message', '')

        try:
            # Отправляем сообщение в канал
            bot.send_message(-4223848296, final_message)
        except telebot.apihelper.ApiTelegramException as e:
            logging.error(f"Ошибка при отправке сообщения в канал: {e}")
            bot.send_message(message.chat.id, "Ошибка при отправке данных. Попробуйте позже.", reply_markup=markup)
            return

        bot.send_message(message.chat.id, "Данные обновлены и отправлены.", reply_markup=markup)
        user_data[message.chat.id] = {}
        save_json_file(USER_DATA_FILE, user_data)

    elif message.text == "Начать заново":
        bot.send_message(message.chat.id, "Процесс начинается заново. Отправьте номер решения ещё раз.", reply_markup=markup)
        user_data[message.chat.id] = {}
        save_json_file(USER_DATA_FILE, user_data)

    elif message.text == "Изменить пол":
        # Запрашиваем пол заново
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        male_button = types.KeyboardButton("размещен")
        female_button = types.KeyboardButton("размещена")
        neutral_button = types.KeyboardButton("размещено")
        markup.add(male_button, female_button, neutral_button)

        bot.send_message(message.chat.id, "Выберите новый пол: размещен, размещена или размещено.", reply_markup=markup)
        user_data[message.chat.id].pop('gender', None)  # Убираем старое значение пола
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
