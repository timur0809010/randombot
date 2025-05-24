import telebot
from telebot import types
import json
import os
import random
import time
from functools import wraps
from config import ADMIN_ID, TOKEN, REF_REWARD, CHANNELS
import config
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto, InputMediaVideo

bot = telebot.TeleBot(TOKEN)

DATA_FILE = 'users.json'
CASE_COST = 25

case_items = [
    ("Мишка", 45),
    ("Роза", 45),
    ("Ракета", 9.8),
    ("Кольцо", 0.2),
]
premium_case_items = [
    ("Ракета", 60),
    ("Кольцо", 39),
    ("NFT", 1),
]

free_case_items = [
    ("Звезды", 100),  # Просто заглушка — само число будет от 0.1 до 2
]

def is_subscribed(user_id):
    for ch in CHANNELS:
        try:
            # проверяем именно по internal chat_id
            member = bot.get_chat_member(ch['id'], user_id)
            # статус “left” или “kicked” — значит отписан
            if member.status in ['left', 'kicked']:
                return False
        except Exception as e:
            # если что-то пошло не так — считаем, что не подписан
            print(f"Ошибка проверки подписки в {ch['id']}: {e}")
            return False
    return True




PROMO_FILE = 'promo.json'


def load_promos():
    if not os.path.exists(PROMO_FILE):
        with open(PROMO_FILE, 'w') as f:
            json.dump({}, f)
    with open(PROMO_FILE, 'r') as f:
        return json.load(f)

def save_promos(promos):
    with open(PROMO_FILE, 'w') as f:
        json.dump(promos, f, indent=2)


def load_data():
    if not os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'w') as f:
            json.dump({}, f)
    with open(DATA_FILE, 'r') as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f, indent=2)

def get_main_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("🎁 Открыть кейс", "⭐ Баланс")
    markup.row("👥 Партнёрская программа", "🔑 Ввести промокод")
    markup.row("💸 Вывести")
    return markup



def ensure_user_and_subscription(func):
    @wraps(func)
    def wrapper(message, *args, **kwargs):
        data = load_data()
        user_id = str(message.from_user.id)

        # Если нет пользователя — добавим его
        if user_id not in data:
            data[user_id] = {
                'balance': 0,
                'ref_by': None,
                'ref_bonus': False,
                'refs': [],
                'pending': []
            }
            save_data(data)

        # Проверка подписки
        if not is_subscribed(message.from_user.id):
            bot.send_message(message.chat.id, "❗ Сначала подпишись на каналы!", reply_markup=get_subscribe_markup())
            return  # Выходим из обработчика

        return func(message, *args, **kwargs)
    return wrapper






def get_subscribe_markup():
    markup = types.InlineKeyboardMarkup()
    for ch in CHANNELS:
        markup.add(types.InlineKeyboardButton("➕ Подписаться", url=f"https://{ch['link']}" ))
    markup.add(types.InlineKeyboardButton("✅ Проверить подписку", callback_data="check_subs"))
    return markup
@ensure_user_and_subscription
@bot.message_handler(commands=['start'])
def start(message):
    user_id = str(message.from_user.id)
    data = load_data()

    referrer_id = None
    if len(message.text.split()) > 1:
        referrer_id = message.text.split()[1]

    if user_id not in data:
        data[user_id] = {
            'balance': 0,
            'ref_by': referrer_id if referrer_id != user_id else None,
            'ref_bonus': False,
            'refs': [],
            'pending': []
        }

        if referrer_id and referrer_id in data:
            if user_id not in data[referrer_id]['pending']:
                data[referrer_id]['pending'].append(user_id)

        save_data(data)  # <-- Всегда сохраняем


    if not is_subscribed(message.from_user.id):
        bot.send_message(message.chat.id, "👋 Чтобы начать, подпишись на каналы:", reply_markup=get_subscribe_markup())
    else:
        # <- Здесь добавим проверку бонуса
        ref_by = data[user_id].get('ref_by')
        if ref_by and ref_by in data:
            ref_data = data[ref_by]

            # Если был в pending — переносим в refs
            if user_id in ref_data.get('pending', []):
                ref_data['pending'].remove(user_id)
                if user_id not in ref_data['refs']:
                    ref_data['refs'].append(user_id)

            # Если еще не получал бонус — начисляем
            if user_id in ref_data.get('refs', []) and not data[user_id].get('ref_bonus'):
                ref_data['balance'] += REF_REWARD
                data[user_id]['ref_bonus'] = True
                bot.send_message(int(ref_by), f"🎉 У тебя новый активный реферал!\nТебе начислено {REF_REWARD} ⭐")

            save_data(data)

        bot.send_message(message.chat.id, "✅ Ты уже подписан!", reply_markup=get_main_menu())


@bot.callback_query_handler(func=lambda call: call.data == "check_subs")
def check_subs(call):
    user_id = str(call.from_user.id)
    data = load_data()

    if is_subscribed(call.from_user.id):
        bot.answer_callback_query(call.id, "✅ Подписка подтверждена!")

        ref_by = data[user_id].get('ref_by')
        if ref_by and ref_by in data:
            ref_data = data[ref_by]
            if user_id in ref_data.get('pending', []):
                ref_data['pending'].remove(user_id)
                ref_data['refs'].append(user_id)
                ref_data['balance'] += REF_REWARD
                save_data(data)
                bot.send_message(int(ref_by), f"🎉 У тебя новый активный реферал!\nТебе начислено {REF_REWARD} ⭐")
        bot.send_message(call.message.chat.id, "🎉 Добро пожаловать!", reply_markup=get_main_menu())
    else:
        bot.answer_callback_query(call.id, "❌ Ты ещё не подписан на все каналы.")

@ensure_user_and_subscription
@bot.message_handler(func=lambda message: message.text == "⭐ Баланс")
def show_balance(message):
    data = load_data()
    user_id = str(message.from_user.id)
    bal = data[user_id]['balance']
    bot.send_message(message.chat.id, f"У тебя {bal} звёзд. За пополнением к @Kricocool")

@ensure_user_and_subscription
@bot.message_handler(func=lambda message: message.text == "🎁 Открыть кейс")
def choose_case(message):
    if not is_subscribed(message.from_user.id):
        bot.send_message(message.chat.id, "👋 Чтобы начать, подпишись на каналы:", reply_markup=get_subscribe_markup())
    else:
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🎁 Стандарт (25 ⭐)", callback_data="case_standard"))
        markup.add(types.InlineKeyboardButton("💎 Премиум (100 ⭐)", callback_data="case_premium"))
        markup.add(types.InlineKeyboardButton("🆓 Бесплатный (раз в 24ч)", callback_data="case_free"))
        bot.send_message(message.chat.id, "Выбери кейс для открытия:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("case_"))
def show_case_info(call):
    user_id = str(call.from_user.id)
    data = load_data()
    case_type = call.data.split("_")[1]

    if case_type == "standard":
        items = case_items
        cost = 25
    elif case_type == "premium":
        items = premium_case_items
        cost = 100
    elif case_type == "free":
        items = free_case_items
        cost = 0
    else:
        bot.answer_callback_query(call.id, "Неизвестный кейс.")
        return

    # Проверка баланса для обычных кейсов
    if case_type != "free" and data[user_id]["balance"] < cost:
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, f"Недостаточно звёзд. Нужно {cost} ⭐.")
        return

    # Для free — проверка времени
    if case_type == "free":
        last_open = data[user_id].get("last_free", 0)
        if time.time() - last_open < 86400:
            hours = int((86400 - (time.time() - last_open)) // 3600)
            minutes = int((86400 - (time.time() - last_open)) % 3600 // 60)
            bot.answer_callback_query(call.id)
            bot.send_message(call.message.chat.id, f"🕒 Фри-кейс можно открыть через {hours}ч {minutes}м.")
            return

    drop_list = "\n".join([f"• {item} — {chance}%" for item, chance in items])
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🧨 Открыть", callback_data=f"open_{case_type}"))
    bot.edit_message_text(
        f"<b>{'Бесплатный' if case_type=='free' else case_type.capitalize()} кейс</b>\n"
        f"Стоимость: {cost} ⭐\n\n"
        f"Шансы выпадения:\n{drop_list}",
        call.message.chat.id,
        call.message.message_id,
        parse_mode="HTML",
        reply_markup=markup
    )



@bot.callback_query_handler(func=lambda call: call.data.startswith("open_"))
def open_selected_case(call):
    user_id = str(call.from_user.id)
    chat_id = call.message.chat.id
    data = load_data()

    case_type = call.data.split("_")[1]

    if case_type == "standard":
        items = case_items
        cost = 25
    elif case_type == "premium":
        items = premium_case_items
        cost = 100
    elif case_type == "free":
        items = free_case_items
        cost = 0
    else:
        bot.answer_callback_query(call.id, "Ошибка с типом кейса.")
        return

    if case_type != "free" and data[user_id]['balance'] < cost:
        bot.answer_callback_query(call.id)
        bot.send_message(chat_id, f"Недостаточно звёзд. Нужно {cost} ⭐.")
        return

    if case_type == "free":
        last = data[user_id].get("last_free", 0)
        if time.time() - last < 86400:
            bot.answer_callback_query(call.id)
            bot.send_message(chat_id, "❗ Этот кейс можно открывать раз в 24 часа.")
            return
        data[user_id]["last_free"] = time.time()

    else:
        data[user_id]['balance'] -= cost

    save_data(data)

    # "Анимация"
    msg = bot.send_message(chat_id, "🔓 Открываем кейс...")
    time.sleep(1)
    bot.edit_message_text("🟦🟦🟦🟦🟦\n🎉 Готово!", chat_id, msg.message_id)

    # Розыгрыш
    roll = random.uniform(0, 100)
    cumulative = 0
    drop = None
    for item, chance in items:
        cumulative += chance
        if roll <= cumulative:
            drop = item
            break

    # Фри-кейс: звёзды на баланс
    if case_type == "free":
        stars = round(random.uniform(0.1, 2), 2)
        data[user_id]['balance'] += stars
        save_data(data)
        bot.send_message(chat_id, f"🎉 Тебе выпало <b>{stars} ⭐</b>!", parse_mode="HTML")
    else:
        user_display = f"@{call.from_user.username} (id:{call.from_user.id})" if call.from_user.username else f"id:{call.from_user.id}"
        bot.send_message(chat_id, f"🎁 Ты получил: <b>{drop}</b>!", parse_mode="HTML")
        bot.send_message(ADMIN_ID, f"📬 Заявка на вывод:\nПользователь: {user_display}\nДроп: {drop}")




@bot.message_handler(commands=['add'])
def add_balance(message):
    if message.from_user.id != ADMIN_ID:
        return
    parts = message.text.split()
    if len(parts) != 3:
        bot.send_message(message.chat.id, "Используй: /add user_id сумма")
        return
    uid, amount = parts[1], int(parts[2])
    data = load_data()
    if uid in data:
        data[uid]['balance'] += amount
        save_data(data)
        bot.send_message(message.chat.id, f"✅ {amount} звёзд добавлено пользователю {uid}.")
    else:
        bot.send_message(message.chat.id, "Пользователь не найден.")


@ensure_user_and_subscription
@bot.message_handler(func=lambda msg: msg.text == "👥 Партнёрская программа")
def partners(msg):
    user_id = str(msg.from_user.id)
    data = load_data()

    ref_link = f"https://t.me/{bot.get_me().username}?start={user_id}"
    refs = data[user_id].get('refs', [])
    ref_by = data[user_id].get('ref_by')

    text = f"👥 <b>Партнёрская программа</b>\n\n"
    text += f"🔗 Твоя ссылка: <code>{ref_link}</code>\n"
    text += f"👤 Приглашено: {len(refs)} пользователей\n"
    text += f"🎲Награда за реферала: {config.REF_REWARD}"

    if ref_by:
        ref_user = data.get(ref_by)
        if ref_user:
            text += f"📌 Вас пригласил: "
            if ref_by in data:
                username = f"@{ref_by}"  # default
                if bot.get_chat(ref_by).username:
                    username = f"@{bot.get_chat(ref_by).username}"
                text += f"{username} (id:{ref_by})"
            else:
                text += f"id:{ref_by}"

    bot.send_message(msg.chat.id, text, parse_mode='HTML')

@bot.message_handler(commands=['refs'])
def refs_command(message):
    user_id = str(message.from_user.id)
    if len(message.text.strip().split()) > 1:
        user_id = message.text.strip().split()[1]

    try:
        with open("users.json", "r", encoding="utf-8") as f:
            users = json.load(f)

        if user_id not in users:
            bot.send_message(message.chat.id, "Пользователь не найден.")
            return

        refs = users[user_id].get("refs", [])

        if not refs:
            bot.send_message(message.chat.id, "У пользователя нет рефералов.")
            return

        status_lines = []

        for ref_id in refs:
            all_ok = True
            for sponsor in config.CHANNELS:
                try:
                    member = bot.get_chat_member(sponsor["id"], ref_id)
                    if member.status in ["left", "kicked"]:
                        all_ok = False
                        break
                except Exception:
                    all_ok = False
                    break
            status = "✅" if all_ok else "❌"
            status_lines.append(f"{ref_id} {status}")

        result = "\n".join(status_lines)
        bot.send_message(message.chat.id, f"Рефералы пользователя {user_id}:\n\n{result}")

    except Exception as e:
        bot.send_message(message.chat.id, f"Ошибка: {e}")




@ensure_user_and_subscription
@bot.message_handler(func=lambda message: message.text == "🔑 Ввести промокод")
def ask_promo_code(message):
    bot.send_message(message.chat.id, "✉️ Введите промокод:")
    bot.register_next_step_handler(message, handle_promo_code)

def handle_promo_code(message):
    promo = message.text.strip()
    user_id = str(message.from_user.id)

    if not os.path.exists("promo.json"):
        with open("promo.json", "w") as f:
            json.dump({}, f)

    with open("promo.json", "r") as f:
        promos = json.load(f)

    if promo not in promos:
        bot.send_message(message.chat.id, "❌ Промокод не найден.")
        return

    data = load_data()
    user_data = data.get(user_id)

    if not user_data:
        bot.send_message(message.chat.id, "⚠️ Пользователь не найден.")
        return

    if 'used_promos' not in user_data:
        user_data['used_promos'] = []

    if promo in user_data['used_promos']:
        bot.send_message(message.chat.id, "❌ Вы уже использовали этот промокод.")
        return

    promo_info = promos[promo]

    if promo_info['uses_left'] <= 0:
        bot.send_message(message.chat.id, "❌ Лимит активаций промокода исчерпан.")
        return

    if user_data.get('referrals', 0) < promo_info['min_refs']:
        bot.send_message(
            message.chat.id,
            f"❌ У вас недостаточно рефералов. Нужно минимум {promo_info['min_refs']}."
        )
        return

    # Применяем награду
    user_data['balance'] += promo_info['reward']
    user_data['used_promos'].append(promo)
    promo_info['uses_left'] -= 1

    # Сохраняем
    save_data(data)
    with open("promo.json", "w") as f:
        json.dump(promos, f, indent=2)

    bot.send_message(
        message.chat.id,
        f"✅ Промокод активирован! Начислено {promo_info['reward']} ⭐"
    )



@bot.message_handler(commands=['addpromo'])
def add_promo(message):
    if message.from_user.id != ADMIN_ID:
        return

    parts = message.text.split()
    if len(parts) != 5:
        bot.send_message(
            message.chat.id,
            "Используй: /addpromo код звёзды активаций мин_рефералов\nПример: /addpromo PROMO123 50 10 2"
        )
        return

    code = parts[1]
    reward = int(parts[2])
    uses_left = int(parts[3])
    min_refs = int(parts[4])

    if not os.path.exists("promo.json"):
        with open("promo.json", "w") as f:
            json.dump({}, f)

    with open("promo.json", "r") as f:
        promos = json.load(f)

    promos[code] = {
        "reward": reward,
        "uses_left": uses_left,
        "min_refs": min_refs
    }

    with open("promo.json", "w") as f:
        json.dump(promos, f, indent=2)

    bot.send_message(
        message.chat.id,
        f"✅ Промокод '{code}' добавлен: {reward} ⭐, {uses_left} активаций, минимум {min_refs} рефералов."
    )

@bot.message_handler(commands=['dump'])
def dump_file(message):
    if message.from_user.id != ADMIN_ID:
        return
    try:
        with open(DATA_FILE, 'rb') as f:
            bot.send_document(message.chat.id, f)
    except Exception as e:
        bot.send_message(message.chat.id, f"Ошибка при отправке файла: {e}")



@bot.message_handler(commands=['reward'])
def change_ref_reward(message):
    if message.from_user.id != ADMIN_ID:
        return
    msg = bot.send_message(message.chat.id, f"Текущая награда за реферала: {config.REF_REWARD}\n\nВведите новое значение:")
    bot.register_next_step_handler(msg, set_new_ref_reward)

def set_new_ref_reward(message):
    try:
        new_reward = float(message.text)

        # Обновляем в config модуле
        config.REF_REWARD = new_reward

        # Перезаписываем файл config.py
        with open('config.py', 'r', encoding='utf-8') as f:
            lines = f.readlines()

        with open('config.py', 'w', encoding='utf-8') as f:
            for line in lines:
                if line.startswith('ref_reward'):
                    f.write(f'ref_reward = {new_reward}\n')
                else:
                    f.write(line)

        bot.send_message(message.chat.id, f"Новая награда за реферала установлена: {new_reward}")

    except ValueError:
        bot.send_message(message.chat.id, "Ошибка: введите целое число.")
















post_content = {}
awaiting_post = {}
awaiting_buttons = {}

@bot.message_handler(commands=['post'])
def start_posting(message):
    if message.from_user.id != ADMIN_ID:
        return
    msg = bot.send_message(message.chat.id, "Что вы хотите разослать? Отправьте сообщение (можно с медиа):")
    awaiting_post[message.chat.id] = True
    bot.register_next_step_handler(msg, handle_post_content)

def handle_post_content(message):
    if message.chat.id not in awaiting_post:
        return
    post_content[message.chat.id] = message
    awaiting_post.pop(message.chat.id)

    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("Да", callback_data="add_buttons"),
               InlineKeyboardButton("Нет", callback_data="no_buttons"))
    bot.send_message(message.chat.id, "Хотите ли вы добавить inline-кнопки?", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data in ["add_buttons", "no_buttons"])
def process_button_choice(call):
    chat_id = call.message.chat.id
    if call.data == "add_buttons":
        awaiting_buttons[chat_id] = []
        msg = bot.send_message(chat_id, "Отправьте кнопки в формате: Текст кнопки + ссылка\n\nКогда закончите, напишите `Готово`.")
        bot.register_next_step_handler(msg, collect_buttons)
    else:
        send_post(chat_id)

def collect_buttons(message):
    chat_id = message.chat.id
    if message.text.lower() == "готово":
        send_post(chat_id, with_buttons=True)
        return

    try:
        text, url = message.text.split('+')
        awaiting_buttons[chat_id].append(InlineKeyboardButton(text.strip(), url=url.strip()))
        msg = bot.send_message(chat_id, "Кнопка добавлена. Добавьте ещё или напишите `Готово`.")
        bot.register_next_step_handler(msg, collect_buttons)
    except:
        msg = bot.send_message(chat_id, "Неверный формат. Пожалуйста, используйте: Текст кнопки + ссылка")
        bot.register_next_step_handler(msg, collect_buttons)

def send_post(chat_id, with_buttons=False):
    message = post_content.get(chat_id)
    keyboard = None

    if with_buttons and awaiting_buttons.get(chat_id):
        markup = InlineKeyboardMarkup()
        markup.add(*awaiting_buttons[chat_id])
        keyboard = markup

    # Получаем список всех пользователей
    with open("users.json", "r", encoding="utf-8") as f:
        users = json.load(f)

    for user_id in users:
        try:
            if message.content_type == 'text':
                bot.send_message(user_id, message.text, reply_markup=keyboard)
            elif message.content_type in ['photo', 'video']:
                media = message.photo[-1].file_id if message.content_type == 'photo' else message.video.file_id
                send_func = bot.send_photo if message.content_type == 'photo' else bot.send_video
                caption = message.caption if message.caption else ""
                send_func(user_id, media, caption=caption, reply_markup=keyboard)
        except Exception as e:
            print(f"Не удалось отправить сообщение пользователю {user_id}: {e}")

    post_content.pop(chat_id, None)
    awaiting_buttons.pop(chat_id, None)
    bot.send_message(chat_id, "Рассылка завершена.")




@bot.message_handler(func=lambda message: message.text == '💸 Вывести')
def show_withdraw_options(message):
    if not is_subscribed(message.from_user.id):
        bot.send_message(message.chat.id, "👋 Чтобы начать, подпишись на каналы:", reply_markup=get_subscribe_markup())
    else:
        keyboard = telebot.types.InlineKeyboardMarkup()
        keyboard.add(
            telebot.types.InlineKeyboardButton("25", callback_data="withdraw_25"),
            telebot.types.InlineKeyboardButton("50", callback_data="withdraw_50"),
            telebot.types.InlineKeyboardButton("100", callback_data="withdraw_100"),
        )
        bot.send_message(message.chat.id, "Выберите сумму для вывода:", reply_markup=keyboard)


@bot.callback_query_handler(func=lambda call: call.data.startswith('withdraw_'))
def handle_withdraw(call):
    amount = int(call.data.split('_')[1])
    user_id = str(call.from_user.id)
    users = load_data()  # твоя функция загрузки users.json

    if user_id not in users:
        bot.answer_callback_query(call.id, "Вы не зарегистрированы.")
        return

    balance = users[user_id].get('balance', 0)

    if balance < amount:
        bot.answer_callback_query(call.id, f"Недостаточно средств для вывода {amount}. Ваш баланс: {balance}")
        return

    # Списываем баланс
    users[user_id]['balance'] = balance - amount
    save_data(users)  # твоя функция сохранения users.json

    bot.answer_callback_query(call.id, f"Вывод {amount} принят. Ожидайте обработки.")
    bot.send_message(call.message.chat.id, f"Вы успешно запросили вывод {amount}.")

    # Отправляем заявку админу
    admin_msg = f"Заявка на вывод:\nПользователь: @{call.from_user.username or call.from_user.id}\nID: {user_id}\nСумма: {amount}"
    bot.send_message(ADMIN_ID, admin_msg)





bot.infinity_polling()
