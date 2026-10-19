# -*- coding: utf-8 -*-
"""
Lisenok-FunPay — бот для FunPay с уведомлениями продавцу в ВК. Работает 24/7.

=====================================================================
  ЧТО ДЕЛАЕТ БОТ
=====================================================================
  1) Покупатель пишет в любой чат FunPay — бот отвечает приветствием
     и инструкцией (+от / +позвать).
  2) Покупатель пишет «+от <текст>» — продавцу в ВК уходит сообщение:
         ответ от пользователя <ссылка на чат>, (<текст>)
     а покупателю бот отвечает по шагам покупки:
         1-й «+от» -> «вам нужен сразу готовый и рабочий бот или файл с кодом?..»
         2-й «+от» -> «всё, что осталось — оплатить заказ и прислать ссылку/username»
  3) Покупатель пишет «+позвать» — покупателю: «продавец скоро придёт, ожидайте 2-3 мин»,
     продавцу в ВК: «вас вызывают (<ссылка на чат>)».
  4) После того как покупателя попросили оплатить, он присылает ссылку/username —
     продавцу в ВК: «юзер оплатил заказ начните выполнять».
  5) Бот бесконечно слушает FunPay и сам восстанавливается после сбоев сети,
     поэтому работает круглосуточно, пока запущен.

=====================================================================
  КУДА ЧТО ВСТАВЛЯТЬ (2 способа — выберите любой)
=====================================================================
  Способ 1 — локально: впишите свои 3 значения в блок НАСТРОЙКИ ниже.

  Способ 2 — для GitHub / хостинга (рекомендуется):
     задайте переменные окружения с именами:
         FUNPAY_GOLDEN_KEY
         VK_GROUP_TOKEN
         VK_SELLER_ID
     Код подхватит их автоматически (они важнее того, что вписано в код).
     Либо создайте рядом файл .env (образец — .env.example).

  ВАЖНО: не заливайте реальные ключи в ПУБЛИЧНЫЙ репозиторий GitHub!
  Для хостинга используйте переменные окружения, для локального запуска — .env
  (он уже добавлен в .gitignore).

  Где взять данные:
    FUNPAY_GOLDEN_KEY — зайдите на funpay.com под своим аккаунтом,
        нажмите F12 -> вкладка Application/Приложение -> Cookies ->
        https://funpay.com -> строка golden_key -> скопируйте столбец Value.
    VK_GROUP_TOKEN — Управление сообществом -> Работа с API -> Создать ключ
        доступа. Права: «Сообщения сообщества» и «Отправлять сообщения».
        Потом в сообществе включите «Сообщения сообщества».
    VK_SELLER_ID — ваш личный id ВК (число). Узнать: откройте vk.com/ваш_ник,
        в адресной строке будет vk.com/id123456789 — нужно число 123456789.

  Чтобы сообщество могло писать вам в ЛС: откройте сообщество из своего ВК,
  нажмите «Написать сообщение» и отправьте туда любое сообщение —
  после этого бот сможет слать вам уведомления.

=====================================================================
  УСТАНОВКА И ЗАПУСК
=====================================================================
  pip install FunPayAPI vk_api
  python funpay_bot.py

=====================================================================
  ТЕКСТЫ — меняйте под себя в блоках 2 и 3, ничего не сломается.
=====================================================================
"""

import json
import os
import re
import sys
import threading
import time
import traceback

import vk_api
from FunPayAPI import Account, Runner, enums, exceptions

# =====================================================================
#  БЛОК 1. НАСТРОЙКИ — КУДА ВСТАВЛЯТЬ ВАШИ ДАННЫЕ
#  (если заданы переменные окружения с такими же именами — код возьмёт их,
#   а то, что вписано здесь, будет проигнорировано)
# =====================================================================

# golden_key с funpay.com (см. инструкцию в шапке файла)
FUNPAY_GOLDEN_KEY = "ВСТАВЬТЕ_СЮДА_GOLDEN_KEY"

# токен сообщества ВК, от которого шлются уведомления
VK_GROUP_TOKEN = "ВСТАВЬТЕ_СЮДА_ТОКЕН_СООБЩЕСТВА"

# ваш личный id ВК (число) — кому присылать уведомления
VK_SELLER_ID = 0

# =====================================================================
#  БЛОК 2. СООБЩЕНИЯ ДЛЯ ПОКУПАТЕЛЯ (текст можно менять)
# =====================================================================

MSG_HELLO = (
    "Привет! Для покупки услуги мне нужно знать, какой именно бот вам нужен.\n"
    "Распишите, что именно вам нужно в боте, для каких услуг и что в него добавить.\n"
    "Для ответа используйте +от (ваш текст)\n"
    "Чтобы позвать продавца, используйте +позвать"
)

MSG_AFTER_FIRST = (
    "Вам нужен сразу готовый и рабочий бот или вам нужен файл, где будет сам код бота?\n"
    "Для ответа используйте +от\n"
    "Чтобы позвать продавца, используйте: +позвать"
)

MSG_PAY = (
    "Всё, что вам осталось, — это оплатить заказ и прислать ссылку на аккаунт "
    "или ваш username"
)

MSG_SELLER_CALLED = "Продавец скоро придёт, ожидайте 2-3 мин"

# ответ покупателю, когда его данные отправлены продавцу
# (поставьте MSG_DONE = "" — и бот в этот момент писать покупателю не будет)
MSG_DONE = "Спасибо! Передал продавцу, он приступит к выполнению."

# подсказка, если «+от» написали без текста
MSG_NEED_TEXT = "Напишите ваш ответ после +от. Например: +от хочу бота для фанпей"

# =====================================================================
#  БЛОК 3. УВЕДОМЛЕНИЯ ПРОДАВЦУ В ВК (текст можно менять)
#  {link} — ссылка на чат покупателя, {text} — ответ покупателя
# =====================================================================

NOTIFY_REPLY = "ответ от пользователя {link}, ({text})"           # на каждый «+от»
NOTIFY_CALL = "вас вызывают ({link})"                              # на «+позвать»
NOTIFY_PAID = "юзер оплатил заказ начните выполнять\n{link}"       # когда прислали username/ссылку

# =====================================================================
#  СЛУЖЕБНАЯ ЧАСТЬ — менять не нужно
# =====================================================================

STATE_FILE = "funpay_state.json"   # стадии диалогов (переживают перезапуск бота)
LOG_FILE = "funpay_bot.log"        # лог работы (на хостинге удобно смотреть)
REQUEST_DELAY = 4                  # как часто проверять новые сообщения (в секундах)


def _load_dotenv(path):
    """Мини-читалка файла .env: строки вида ИМЯ=значение."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, val = line.split("=", 1)
                key, val = key.strip(), val.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = val
    except FileNotFoundError:
        pass
    except Exception:
        pass


_load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

# переменные окружения имеют приоритет над значениями из блока 1
FUNPAY_GOLDEN_KEY = os.environ.get("FUNPAY_GOLDEN_KEY") or FUNPAY_GOLDEN_KEY
VK_GROUP_TOKEN = os.environ.get("VK_GROUP_TOKEN") or VK_GROUP_TOKEN
try:
    VK_SELLER_ID = int(os.environ.get("VK_SELLER_ID") or VK_SELLER_ID)
except (TypeError, ValueError):
    pass


def log(*args):
    """Печать в консоль + запись в файл funpay_bot.log."""
    text = time.strftime("[%d.%m.%Y %H:%M:%S] ") + " ".join(str(a) for a in args)
    try:
        print(text, flush=True)
    except Exception:
        pass
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(text + "\n")
    except Exception:
        pass


def _is_placeholder(value):
    return (not value) or ("ВСТАВЬТЕ" in str(value))


# ---------- стадии диалога ----------
#   0 — новых сообщений от покупателя ещё не было (бот не здоровался)
#   1 — поздоровались, ждём первый «+от»
#   2 — спросили «готовый бот или код?», ждём второй «+от»
#   3 — попросили оплатить и прислать ссылку/username
#   4 — данные переданы продавцу

_state_lock = threading.Lock()


def _read_state():
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _write_state(state):
    tmp = STATE_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=1)
    os.replace(tmp, STATE_FILE)


def get_stage(chat_id):
    with _state_lock:
        try:
            return int(_read_state().get(str(chat_id), 0))
        except Exception:
            return 0


def set_stage(chat_id, stage):
    with _state_lock:
        state = _read_state()
        state[str(chat_id)] = int(stage)
        _write_state(state)


# ---------- ВК ----------
_vk_api = None
_vk_lock = threading.Lock()


def get_vk():
    global _vk_api
    with _vk_lock:
        if _vk_api is None:
            _vk_api = vk_api.VkApi(token=VK_GROUP_TOKEN).get_api()
        return _vk_api


def vk_notify(text):
    """Отправляет уведомление продавцу в ВК от имени сообщества."""
    if _is_placeholder(VK_GROUP_TOKEN) or not VK_SELLER_ID:
        log("⚠ ВК: не заполнены VK_GROUP_TOKEN / VK_SELLER_ID — уведомление пропущено")
        return
    try:
        get_vk().messages.send(peer_id=VK_SELLER_ID, message=text[:4000], random_id=0)
        log("→ ВК продавцу:", text.replace("\n", " ")[:150])
    except Exception as e:
        log("❌ ВК: не удалось отправить уведомление —", e)


# ---------- FunPay ----------
def funpay_send(acc, chat_id, text):
    """Отправляет сообщение покупателю в чат FunPay."""
    if not text:
        return
    try:
        acc.send_message(chat_id, text)
        log("→ FunPay:", text.replace("\n", " ")[:150])
    except Exception as e:
        log("❌ FunPay: не удалось отправить сообщение —", e)


RE_OT = re.compile(r"^\+от\b\s*(.*)$", re.I | re.S)
RE_CALL = re.compile(r"^\+позвать\b", re.I)


def handle_message(acc, msg):
    """Обрабатывает одно новое сообщение покупателя из чата FunPay."""
    chat_id = msg.chat_id
    text = (msg.text or "").strip()
    if not text:
        return
    link = f"https://funpay.com/chat/?node={chat_id}"
    log(f"← FunPay [{msg.chat_name or chat_id}] {msg.author or ''}: {text[:120]}")

    # «+позвать» работает на любой стадии
    if RE_CALL.match(text):
        funpay_send(acc, chat_id, MSG_SELLER_CALLED)
        vk_notify(NOTIFY_CALL.format(link=link))
        return

    stage = get_stage(chat_id)

    # первое сообщение в чате — здороваемся
    if stage == 0:
        funpay_send(acc, chat_id, MSG_HELLO)
        stage = 1
        set_stage(chat_id, stage)

    m = RE_OT.match(text)
    if m:
        body = (m.group(1) or "").strip()   # всё, что после «+от»
        if not body:
            funpay_send(acc, chat_id, MSG_NEED_TEXT)
            return
        # каждый ответ покупателя пересылаем продавцу в ВК
        vk_notify(NOTIFY_REPLY.format(link=link, text=body))
        if stage == 1:
            funpay_send(acc, chat_id, MSG_AFTER_FIRST)
            set_stage(chat_id, 2)
        elif stage == 2:
            funpay_send(acc, chat_id, MSG_PAY)
            set_stage(chat_id, 3)
        elif stage == 3:
            # это ссылка на аккаунт / username, присланные через «+от»
            vk_notify(NOTIFY_PAID.format(link=link))
            funpay_send(acc, chat_id, MSG_DONE)
            set_stage(chat_id, 4)
        # стадия 4: ответ просто ушёл продавцу, покупателю ничего не пишем
        return

    # на стадии оплаты любое сообщение (ссылка/username) считаем передачей заказа
    if stage == 3:
        vk_notify(NOTIFY_PAID.format(link=link))
        funpay_send(acc, chat_id, MSG_DONE)
        set_stage(chat_id, 4)


# ---------- подключение и главный цикл ----------
def connect_funpay():
    """Входит в FunPay. При ошибках сети повторяет попытки, пока не получится."""
    while True:
        try:
            acc = Account(FUNPAY_GOLDEN_KEY).get()
            log(f"✅ FunPay: вошли как {acc.username} (id {acc.id}). Бот в сети 24/7.")
            return acc
        except exceptions.AccountNotInitiatedError:
            log("❌ FunPay: golden_key не подошёл. Проверьте FUNPAY_GOLDEN_KEY в настройках.")
            return None
        except Exception as e:
            log(f"⚠ FunPay: ошибка входа ({e}) — повтор через 15 сек")
            time.sleep(15)


def new_runner(acc):
    """Создаёт слушателя событий. Перед повторным созданием отвязывает старый."""
    acc.runner = None
    return Runner(acc)


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    if _is_placeholder(FUNPAY_GOLDEN_KEY):
        print("❌ Впишите FUNPAY_GOLDEN_KEY в БЛОК 1 (или задайте переменную окружения).")
        return
    if _is_placeholder(VK_GROUP_TOKEN) or not VK_SELLER_ID:
        log("⚠ ВК: не заполнены VK_GROUP_TOKEN / VK_SELLER_ID — уведомления продавцу работать не будут.")

    acc = connect_funpay()
    if acc is None:
        return

    runner = None
    while True:
        try:
            if runner is None:
                runner = new_runner(acc)
            # listen опрашивает FunPay каждые REQUEST_DELAY секунд и сам глотает
            # ошибки сети — поэтому бот работает круглосуточно без падений
            for event in runner.listen(requests_delay=REQUEST_DELAY, ignore_exceptions=True):
                if event.type is not enums.EventTypes.NEW_MESSAGE:
                    continue
                msg = event.message
                if not msg or not (msg.text or "").strip():
                    continue
                if msg.by_bot or msg.author_id == acc.id:
                    continue   # свои сообщения не обрабатываем
                try:
                    handle_message(acc, msg)
                except Exception:
                    log("Ошибка обработки сообщения:", traceback.format_exc())
        except Exception:
            log("⚠ Слушатель упал, перезапуск через 10 сек:", traceback.format_exc())
            runner = None
            time.sleep(10)


if __name__ == "__main__":
    main()
