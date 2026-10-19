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
  4) Когда FunPay присылает системное уведомление о новом оплаченном заказе,
      продавцу в ВК: «юзер оплатил заказ начните выполнять» + ссылка на чат.
      Сообщения покупателя на этом шаге больше не считаются оплатой.
  5) Бот сам поднимает ваши предложения (лоты) на FunPay раз в 4 часа.
  6) Бот бесконечно слушает FunPay и сам восстанавливается после сбоев сети,
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
  Локально (работает, пока включён компьютер):
      pip install FunPayAPI vk_api
      python funpay_bot.py

  Через GitHub Actions (бесплатно, без своего сервера):
      файл .github/workflows/bot.yml уже лежит в проекте — просто залейте
      репозиторий на GitHub, добавьте секреты FUNPAY_GOLDEN_KEY,
      VK_GROUP_TOKEN, VK_SELLER_ID (Settings -> Secrets and variables ->
      Actions) и включите Actions. Workflow сам запускает бота каждые
      5 часов и хранит состояние диалогов в кэше.
      ВАЖНО: репозиторий должен быть ПУБЛИЧНЫМ, иначе бесплатные минуты
      Actions кончатся меньше чем за двое суток.

=====================================================================
  ТЕКСТЫ — меняйте под себя в блоках 2 и 3, ничего не сломается.
=====================================================================
"""

import json
import logging
import os
import re
import sys
import threading
import time
import traceback

import requests
import vk_api
from bs4 import BeautifulSoup
from FunPayAPI import Account, Runner, enums, exceptions, types

# =====================================================================
#  БЛОК 1. НАСТРОЙКИ — КУДА ВСТАВЛЯТЬ ВАШИ ДАННЫЕ
#  (если заданы переменные окружения с такими же именами — код возьмёт их,
#   а то, что вписано здесь, будет проигнорировано)
# =====================================================================

# golden_key с funpay.com (см. инструкцию в шапке файла)
FUNPAY_GOLDEN_KEY = "99n9ikgvdbnfzaob9txudaqq8vue0o5d"

# токен сообщества ВК, от которого шлются уведомления
VK_GROUP_TOKEN = "vk1.a.bh7sxx4bOc4oMKyzy1DGTlDzOT3qfOGQvB_lPDNZs5-kjmWD3YgY86XWT5nUzB30i_z8qPk1DdL7fYpGBPSwwoehKSfRdHV18MVFP2ttxIF-w0eQHF45p_IWxY1tjyDAcGi7WK_B5f_82WyrJfeKseJIPrwArE7ONifEm-5FJ9-7qlj2pVEBTxJ8ZCkk0RNoXJl5b5YIdXpWem711726WA

# ваш личный id ВК (число) — кому присылать уведомления
VK_SELLER_ID = 875762552

# автоматически поднимать предложения (лоты) на FunPay
AUTO_RAISE = True

# как часто поднимать лоты, в минутах
# FunPay разрешает поднятие раз в 4 часа, поэтому 245 минут (4 ч 5 мин) — с запасом
RAISE_INTERVAL_MINUTES = 245

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
NOTIFY_PAID = "юзер оплатил заказ начните выполнять\n{link}"       # системное уведомление FunPay о новом заказе

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
#   4 — FunPay подтвердил оплату заказа (системное уведомление NEW_ORDER)

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


def _ensure_state_file():
    """Создаёт пустой файл состояния, если его ещё нет (нужно для кэша на GitHub)."""
    if not os.path.exists(STATE_FILE):
        _write_state({})


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
            # покупатель прислал ссылку/username — продавцу она уже ушла выше.
            # Оплату подтверждает только системное уведомление FunPay (NEW_ORDER),
            # поэтому стадию здесь не меняем и NOTIFY_PAID не шлём.
            pass
        # стадия 4: ответ просто ушёл продавцу, покупателю ничего не пишем
        return

    # на стадии оплаты обычное сообщение (ссылка/username) пересылаем продавцу,
    # но оплатой его не считаем: ждём системное уведомление FunPay о заказе
    if stage == 3:
        vk_notify(NOTIFY_REPLY.format(link=link, text=text))


def handle_order_event(acc, order):
    """Реакция на системное уведомление FunPay о новом заказе (покупке).

    Событие NEW_ORDER приходит от FunPay, когда покупатель оплатил заказ,
    поэтому именно оно (а не сообщение покупателя) подтверждает оплату.
    """
    if order.status != enums.OrderStatuses.PAID:
        log(f"💰 FunPay: заказ #{order.id} в статусе {order.status.name} — уведомление не нужно")
        return

    # ссылка на чат покупателя (если он писал боту), иначе — на его профиль
    link = f"https://funpay.com/users/{order.buyer_id}/"
    try:
        chat = acc.get_chat_by_name(order.buyer_username, make_request=True)
    except Exception as e:
        chat = None
        log("⚠ FunPay: не удалось найти чат покупателя —", e)

    if chat:
        link = f"https://funpay.com/chat/?node={chat.id}"
        # если покупатель уже прошёл сценарий до просьбы оплатить — закрываем диалог
        if get_stage(chat.id) == 3:
            funpay_send(acc, chat.id, MSG_DONE)
            set_stage(chat.id, 4)

    log(f"💰 FunPay: оплачен заказ #{order.id} — {order.description} "
        f"({order.price} ₽, {order.subcategory_name}), покупатель {order.buyer_username}")
    vk_notify(NOTIFY_PAID.format(link=link))
    _mark_order_seen(order.id)


# ---------- память об уже обработанных заказах ----------
def _orders_info():
    with _state_lock:
        return _read_state().get("_orders") or {}


def _orders_ready():
    return bool(_orders_info().get("ready"))


def _set_orders_ready():
    with _state_lock:
        state = _read_state()
        info = state.get("_orders") or {}
        info["ready"] = True
        state["_orders"] = info
        _write_state(state)


def _is_order_seen(order_id):
    return str(order_id) in (_orders_info().get("seen") or [])


def _mark_order_seen(order_id):
    with _state_lock:
        state = _read_state()
        info = state.get("_orders") or {}
        seen = [str(i) for i in (info.get("seen") or [])]
        if str(order_id) not in seen:
            seen.append(str(order_id))
        info["seen"] = seen[-500:]   # храним последние 500 заказов
        state["_orders"] = info
        _write_state(state)


def handle_initial_order(acc, order):
    """Заказы, которые уже существовали на момент запуска бота.

    При первом запуске просто запоминаем их, чтобы не спамить старыми
    покупками. При следующих запусках заказы, сделанные пока бот не работал,
    отсутствуют в памяти — о них уведомляем.
    """
    if not _orders_ready():
        _mark_order_seen(order.id)
        return
    if _is_order_seen(order.id):
        return
    handle_order_event(acc, order)


# ---------- подключение и главный цикл ----------
def patch_funpay_golden_seal():
    """FunPay с 2026 года требует cookie golden_seal, которой нет в FunPayAPI 1.1.0.

    Без неё сайт отвечает на /runner/: 400
    {"msg":"Необходимая cookie отсутствует или устарела. Повторите запрос.","error":1}

    Патчим Account.method: отправляем golden_seal вместе с golden_key/PHPSESSID
    и запоминаем новое значение из каждого ответа (FunPay может его обновлять).
    """
    original = Account.method
    if getattr(original, "_lisenok_golden_seal", False):
        return

    def method(self, request_method, api_method, headers, payload,
               exclude_phpsessid=False, raise_not_200=False):
        headers = dict(headers)
        parts = [f"golden_key={self.golden_key}"]
        if self.phpsessid and not exclude_phpsessid:
            parts.append(f"PHPSESSID={self.phpsessid}")
        seal = getattr(self, "_golden_seal", None)
        if seal:
            parts.append(f"golden_seal={seal}")
        headers["cookie"] = "; ".join(parts)
        if self.user_agent:
            headers["user-agent"] = self.user_agent

        link = (api_method if api_method.startswith("https://funpay.com")
                else "https://funpay.com/" + api_method)
        response = getattr(requests, request_method)(
            link, headers=headers, data=payload,
            timeout=self.requests_timeout, proxies=self.proxy or {})

        # сохраняем/обновляем golden_seal из ответа
        try:
            jar = response.cookies.get_dict()
            if jar.get("golden_seal"):
                self._golden_seal = jar["golden_seal"]
        except Exception:
            pass

        if response.status_code == 403:
            raise exceptions.UnauthorizedError(response)
        elif response.status_code != 200 and raise_not_200:
            raise exceptions.RequestFailedError(response)
        return response

    method._lisenok_golden_seal = True
    Account.method = method


def _msg_text(parser):
    """Текст сообщения: FunPay отдаёт div.chat-msg-text, старый класс — message-text."""
    node = (parser.find("div", {"class": "chat-msg-text"})
            or parser.find("div", {"class": "message-text"}))
    return node.get_text() if node else ""


def patch_funpay_parsing():
    """FunPay переименовал класс текста сообщения: message-text -> chat-msg-text.

    FunPayAPI 1.1.0 (2023) ищет старый класс, получает None и падает с
    AttributeError. Runner 3 раза повторяет запрос и сдаётся, поэтому бот
    вообще не видит сообщения покупателей. Подменяем два метода библиотеки
    на такие же, но с поиском обоих классов.
    """
    if getattr(Account, "_lisenok_text_patch", False):
        return

    def parse_messages(self, json_messages, chat_id, interlocutor_id=None,
                       interlocutor_username=None, from_id=0):
        messages = []
        ids = {self.id: self.username, 0: "FunPay"}
        badges = {}
        if interlocutor_id is not None:
            ids[interlocutor_id] = interlocutor_username
        bot_char = getattr(self, "_Account__bot_character", "\u2064")

        for i in json_messages:
            if i["id"] < from_id:
                continue
            author_id = i["author"]
            parser = BeautifulSoup(i["html"], "html.parser")

            # ник и бейдж автора, если ещё не знаем
            if (None in (ids.get(author_id), badges.get(author_id))
                    and (author_div := parser.find("div", {"class": "media-user-name"}))):
                if badges.get(author_id) is None:
                    badge = author_div.find("span")
                    badges[author_id] = badge.text if badge else 0
                if ids.get(author_id) is None:
                    author_link = author_div.find("a")
                    if author_link:
                        author = author_link.text.strip()
                        ids[author_id] = author
                        if (Account.chat_id_private(chat_id) and author_id == interlocutor_id
                                and not interlocutor_username):
                            interlocutor_username = author
                            ids[interlocutor_id] = interlocutor_username

            image_link = parser.find("a", {"class": "chat-img-link"})
            if image_link:
                image_link = image_link.get("href")
                message_text = None
            else:
                image_link = None
                if author_id == 0:   # системное сообщение FunPay
                    alert = parser.find("div", {"class": "alert alert-with-icon alert-info"})
                    message_text = alert.get_text().strip() if alert else _msg_text(parser).strip()
                else:
                    message_text = _msg_text(parser)

            by_bot = False
            if not image_link and message_text.startswith(bot_char):
                message_text = message_text.replace(bot_char, "", 1)
                by_bot = True

            message_obj = types.Message(i["id"], message_text, chat_id, interlocutor_username,
                                        None, author_id, i["html"], image_link,
                                        determine_msg_type=False)
            message_obj.by_bot = by_bot
            message_obj.type = (types.MessageTypes.NON_SYSTEM if author_id != 0
                                else message_obj.get_message_type())
            messages.append(message_obj)

        for i in messages:
            i.author = ids.get(i.author_id)
            i.chat_name = interlocutor_username
            i.badge = badges.get(i.author_id) if badges.get(i.author_id) != 0 else None
        return messages

    def send_message(self, chat_id, text=None, chat_name=None, image_id=None,
                     add_to_ignore_list=True, update_last_saved_message=False):
        if not self.is_initiated:
            raise exceptions.AccountNotInitiatedError()

        headers = {
            "accept": "*/*",
            "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
            "x-requested-with": "XMLHttpRequest",
        }
        request = {
            "action": "chat_message",
            "data": {"node": chat_id, "last_message": -1, "content": text},
        }
        bot_char = getattr(self, "_Account__bot_character", "\u2064")

        if image_id is not None:
            request["data"]["image_id"] = image_id
            request["data"]["content"] = ""
        else:
            request["data"]["content"] = f"{bot_char}{text}" if text else ""

        objects = [{
            "type": "chat_node",
            "id": chat_id,
            "tag": "00000000",
            "data": {"node": chat_id, "last_message": -1, "content": ""},
        }]
        payload = {
            "objects": json.dumps(objects),
            "request": json.dumps(request),
            "csrf_token": self.csrf_token,
        }

        response = self.method("post", "runner/", headers, payload, raise_not_200=True)
        json_response = response.json()
        if not (resp := json_response.get("response")):
            raise exceptions.MessageNotDeliveredError(response, None, chat_id)
        if (error_text := resp.get("error")) is not None:
            raise exceptions.MessageNotDeliveredError(response, error_text, chat_id)

        mes = json_response["objects"][0]["data"]["messages"][-1]
        parser = BeautifulSoup(mes["html"], "html.parser")
        if image_link := parser.find("a", {"class": "chat-img-link"}):
            image_link = image_link.get("href")
            message_text = None
        else:
            message_text = _msg_text(parser).replace(bot_char, "", 1)

        message_obj = types.Message(int(mes["id"]), message_text, chat_id, chat_name,
                                    self.username, self.id, mes["html"], image_link)
        if self.runner and isinstance(chat_id, int):
            if add_to_ignore_list:
                self.runner.mark_as_by_bot(chat_id, message_obj.id)
            if update_last_saved_message:
                self.runner.update_last_message(chat_id, message_text)
        return message_obj

    Account._Account__parse_messages = parse_messages
    Account.send_message = send_message
    Account._lisenok_text_patch = True


def connect_funpay():
    """Входит в FunPay. При ошибках сети повторяет попытки, пока не получится."""
    while True:
        try:
            acc = Account(FUNPAY_GOLDEN_KEY).get()
            log(f"✅ FunPay: вошли как {acc.username} (id {acc.id}). Бот в сети 24/7.")
            if not getattr(acc, "_golden_seal", None):
                log("⚠ FunPay: cookie golden_seal не получена — возможны ошибки 400")
            return acc
        except exceptions.AccountNotInitiatedError:
            log("❌ FunPay: golden_key не подошёл. Проверьте FUNPAY_GOLDEN_KEY в настройках.")
            return None
        except Exception as e:
            log(f"⚠ FunPay: ошибка входа ({e}) — повтор через 15 сек")
            time.sleep(15)


def refresh_session(acc):
    """Обновляет PHPSESSID и golden_seal (когда FunPay пишет, что cookie устарела)."""
    try:
        acc.get()
        log("🔄 FunPay: сессия и cookie обновлены")
        return True
    except Exception as e:
        log("⚠ FunPay: не удалось обновить сессию —", e)
        return False


def new_runner(acc):
    """Создаёт слушателя событий. Перед повторным созданием отвязывает старый."""
    acc.runner = None
    return Runner(acc)


# ---------- автоподнятие лотов ----------
def _raise_info():
    """Сохраняет время последнего/следующего поднятия в файле состояния."""
    with _state_lock:
        return _read_state().get("_raise") or {}


def _set_raise_info(**kwargs):
    with _state_lock:
        state = _read_state()
        info = state.get("_raise") or {}
        info.update(kwargs)
        state["_raise"] = info
        _write_state(state)


def my_lot_categories(acc):
    """Возвращает категории (игры), в которых у аккаунта есть обычные лоты.

    Формат: {ID категории: {"name": название, "subcategories": {ID: SubCategory}}}.
    Подкатегории нужны, чтобы поднимать только те разделы, где есть лоты.
    """
    profile = acc.get_user(acc.id)
    categories = {}
    for lot in profile.get_lots():
        sub = lot.subcategory
        if sub.type is types.SubCategoryTypes.COMMON:
            cat = categories.setdefault(sub.category.id,
                                        {"name": sub.category.name, "subcategories": {}})
            cat["subcategories"][sub.id] = sub
    return categories


def raise_all_lots(acc):
    """Поднимает лоты во всех категориях. Возвращает паузу (сек) до следующей попытки."""
    categories = my_lot_categories(acc)
    if not categories:
        log("⬆ Автоподнятие: активных лотов не найдено")
        return RAISE_INTERVAL_MINUTES * 60

    pause = 0
    for cat_id, info in categories.items():
        cat_name = info["name"]
        try:
            acc.raise_lots(cat_id, subcategories=list(info["subcategories"].values()))
            log(f"⬆ Автоподнятие: лоты подняты — {cat_name} (категория {cat_id})")
        except exceptions.RaiseError as e:
            wait = e.wait_time or 0
            log(f"⬆ Автоподнятие: {cat_name} — {e.error_message or 'поднять не удалось'}"
                + (f", повтор через {wait} сек" if wait else ""))
            pause = max(pause, wait)
        except Exception as e:
            log(f"⬆ Автоподнятие: ошибка в категории {cat_name} — {type(e).__name__}: {e}")
            pause = max(pause, 600)

    return pause or RAISE_INTERVAL_MINUTES * 60


def maybe_raise_lots(acc):
    """Вызывается из главного цикла: поднимает лоты, когда подошло время."""
    if not AUTO_RAISE:
        return
    now = time.time()
    next_ts = float(_raise_info().get("next") or 0)
    if next_ts > now:
        return
    try:
        pause = raise_all_lots(acc)
    except Exception:
        log("⬆ Автоподнятие: непредвиденная ошибка:", traceback.format_exc())
        _set_raise_info(next=time.time() + 600)
        return
    now = time.time()
    _set_raise_info(last=now, next=now + pause)
    log(f"⬆ Автоподнятие: следующая попытка через {int(pause // 60)} мин")


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    # Логи библиотеки FunPayAPI тоже выводим в консоль: при проблемах со связью
    # там будет видна причина. Для подробных трейсбеков задайте FUNPAY_DEBUG=1.
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
    if os.environ.get("FUNPAY_DEBUG") == "1":
        logging.getLogger("FunPayAPI").setLevel(logging.DEBUG)

    if _is_placeholder(FUNPAY_GOLDEN_KEY):
        print("❌ Впишите FUNPAY_GOLDEN_KEY в БЛОК 1 (или задайте переменную окружения).")
        return
    if _is_placeholder(VK_GROUP_TOKEN) or not VK_SELLER_ID:
        log("⚠ ВК: не заполнены VK_GROUP_TOKEN / VK_SELLER_ID — уведомления продавцу работать не будут.")

    # без этого патча FunPay отвечает 400 «Необходимая cookie отсутствует или устарела»
    patch_funpay_golden_seal()
    # без этого бот не видит текстовые сообщения (класс chat-msg-text)
    patch_funpay_parsing()

    acc = connect_funpay()
    if acc is None:
        return

    # состояние диалогов: если файла ещё нет — создаём, чтобы он точно попал в кэш
    _ensure_state_file()

    # На GitHub Actions одна задача живёт максимум 6 часов, поэтому workflow
    # задаёт RUN_MINUTES=330: бот сам аккуратно завершится до этого лимита,
    # а следующий запуск поднимет его снова. Локально переменная не задана —
    # бот работает без ограничений по времени.
    try:
        run_minutes = int(os.environ.get("RUN_MINUTES") or 0)
    except ValueError:
        run_minutes = 0
    if run_minutes > 0:
        def _time_to_restart():
            log(f"⏳ Лимит запуска ({run_minutes} мин) достигнут — завершаюсь, "
                f"следующий запуск поднимет бота заново")
            os._exit(0)   # код 0 = успех: workflow сохранит кэш и перезапустит бота

        timer = threading.Timer(run_minutes * 60, _time_to_restart)
        timer.daemon = True
        timer.start()
        log(f"⏱ Бот завершится сам через {run_minutes} мин (лимит GitHub Actions) "
            f"и будет перезапущен следующим запуском")

    runner = new_runner(acc)
    first_batch = True   # первый опрос: старые заказы только запоминаем
    while True:
        try:
            # Сами опрашиваем FunPay вместо runner.listen(): встроенный listen
            # прячет настоящую причину ошибки под общей фразой «Произошла ошибка
            # при получении событий». Так в лог попадает точная ошибка (код 403,
            # Unauthorized и т.п.), по которой сразу видно, что чинить.
            updates = runner.get_updates()
            events = runner.parse_updates(updates)
            for event in events:
                if event.type is enums.EventTypes.NEW_MESSAGE:
                    msg = event.message
                    if not msg or not (msg.text or "").strip():
                        continue
                    if msg.by_bot or msg.author_id in (0, acc.id):
                        continue   # свои и системные сообщения не обрабатываем
                    try:
                        handle_message(acc, msg)
                    except Exception:
                        log("Ошибка обработки сообщения:", traceback.format_exc())
                elif event.type is enums.EventTypes.NEW_ORDER:
                    # системное уведомление FunPay: покупатель оплатил заказ
                    try:
                        handle_order_event(acc, event.order)
                    except Exception:
                        log("Ошибка обработки заказа:", traceback.format_exc())
                elif event.type is enums.EventTypes.INITIAL_ORDER:
                    # заказы, существовавшие до запуска (в т.ч. сделанные,
                    # пока бот был выключен) — уведомляем только о новых
                    try:
                        handle_initial_order(acc, event.order)
                    except Exception:
                        log("Ошибка обработки старого заказа:", traceback.format_exc())

            if first_batch:
                first_batch = False
                _set_orders_ready()

            # автоподнятие лотов (не чаще раза в RAISE_INTERVAL_MINUTES)
            try:
                maybe_raise_lots(acc)
            except Exception:
                log("Ошибка автоподнятия лотов:", traceback.format_exc())
        except KeyboardInterrupt:
            raise
        except exceptions.RequestFailedError as e:
            body = ""
            try:
                body = e.response.content.decode("utf-8", "replace")
            except Exception:
                pass
            log(f"⚠ FunPay: код {e.status_code}: {body[:300]}")
            # FunPay пишет «cookie отсутствует или устарела» — обновляем сессию
            if e.status_code == 400 and "cookie" in body.lower():
                refresh_session(acc)
            time.sleep(10)
        except Exception as e:
            # runner НЕ пересоздаём: у него внутри хранится состояние чатов,
            # иначе часть сообщений можно потерять. Просто ждём и пробуем снова.
            log(f"⚠ Ошибка получения событий FunPay: {type(e).__name__}: {e}")
            time.sleep(10)
        time.sleep(REQUEST_DELAY)


if __name__ == "__main__":
    main()
