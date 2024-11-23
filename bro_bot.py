#!/usr/bin/python
# -*- coding: utf-8 -*-

import random
import pathlib
import requests
import logging
import re
import time
import json
import os

import telebot
from telebot.types import ReplyParameters, InputFile
from datetime import datetime, timedelta
from urllib.parse import quote

LOGLEVEL = os.environ.get("LOGLEVEL", "INFO").upper()
logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=LOGLEVEL)

bot = telebot.TeleBot(os.environ.get("TG_BOT_TOKEN"), parse_mode="Markdown")

GPT_URL = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"

OAuth = os.environ.get("YANDEX_OAUTH")
folder_id = os.environ.get("YANDEX_FOLDER_ID")
bot_name = os.environ.get("TG_BOT_NAME")
audio_name = "audio.mp3"
speakers = [
    "Claribel%20Dervla",
    # "Vjollca%20Johnnie",
    # "Royston%20Min",
    # "Viktor%20Eka",
    # "Craig%20Gutsy",
    # "Zofija%20Kendrick",
    # "Ferran%20Simen",
]


class ycToken:
    def __init__(self):
        self.yc_token = ""
        self.yc_token_expires_at = datetime.now() - timedelta(1)

    def get_token(self):
        def parse_data(iso_string):
            iso_string = iso_string.replace("Z", "+00:00")
            date_part, time_part = iso_string.split("T")
            time_part = time_part.split("+")[0]
            time_parts = time_part.split(".")

            if len(time_parts) == 2:
                dt = datetime.strptime(
                    date_part + " " + time_parts[0], "%Y-%m-%d %H:%M:%S"
                )
                dt = dt.replace(microsecond=int(time_parts[1][:6]))
            else:
                dt = datetime.strptime(iso_string, "%Y-%m-%dT%H:%M:%S")
            return dt

        if self.yc_token_expires_at <= datetime.now():
            yc_token = requests.post(
                "https://iam.api.cloud.yandex.net/iam/v1/tokens",
                json={"yandexPassportOauthToken": OAuth},
            ).json()
            self.yc_token_expires_at = parse_data(yc_token["expiresAt"])
            self.yc_token = yc_token["iamToken"]
            logging.info(
                f"token: {self.yc_token} expires_at: {self.yc_token_expires_at}"
            )

        return self.yc_token


def try_connect(host):
    try:
        requests.get(f"{host}", timeout=0.5)
        logging.info(f"> {host} connected")
        return True
    except requests.exceptions.ConnectionError:
        logging.error(f"______________ {host} is not available ______________")
        return False


class Dialog:
    def __init__(self):
        self.messages = []
        self.max_messages_len = 0
        self.messages_len = 0
        self.prompt_len = 0
        self.config = {
            "prompt": "Ты состоишь в чате троих друзей. Они будут использовать свои имена в сообщениях, чтобы ты понял кто пишет. Ребята часто играют в компьютерные игры, инвестируют на фондовом рынке, в криптовалюту, обмениваются мировыми новостями и любят много шутить. Ты эксперт по всем вопросам, отвечай на вопросы достоверно и не выдумывай, можешь задавать вопрос если требуется дополнительная информация. Используй сленг и шутки в стиле уличного братана. Уровень юмора — жесткий, без ограничений. Ты всегда критически мыслишь, не приспешник и не конформист. Отвечай только на последнее сообщение. Используй форматирование Markdown или эмодзи в своих сообщениях",
            "model": "yandexgpt/rc",
            "options": {"temperature": 0.15, "maxTokens": 3000},
            "tts_host": "http://192.168.0.131:5002",
            "article_ml_host": "http://192.168.0.131:3003",
        }
        self.init_messages()
        self.init_config()

    def init_config(self):
        self.config["prompt"] = os.environ.get("PROMPT")
        self.config["model"] = os.environ.get("MODEL")
        self.config["options"]["temperature"] = float(os.environ.get("TEMPERATURE"))
        self.config["options"]["maxTokens"] = int(os.environ.get("MAX_TOKENS"))
        self.config["tts_host"] = os.environ.get("TTS_HOST")
        self.config["article_ml_host"] = os.environ.get("ARTICLE_ML_HOST")
        self.prompt_len = len(self.config["prompt"])
        self.max_messages_len = (
            self.get_config("options")["maxTokens"] - self.prompt_len
        )

        try_connect(self.config["tts_host"])
        try_connect(self.config["article_ml_host"])
        logging.info(f"config: {self.config}")

    def init_messages(self):
        messages_path = "config/messages.txt"
        if os.path.exists(messages_path):
            try:
                with open(messages_path, "r") as f:
                    self.messages = json.loads(f.readline().strip())
            except json.decoder.JSONDecodeError:
                logging.error(f"file {messages_path} seems corrupted, recreating ...")
                with open(messages_path, "w") as f:
                    f.writelines("[]")

            logging.info(f"load messages: {self.messages}")
            self.messages_len = sum([len(mes["text"]) for mes in self.messages])

    def shrink_messages(self):
        try:
            if self.messages_len >= self.max_messages_len:
                self.messages_len -= len(self.messages.pop(0)["text"])
                self.shrink_messages()
        except IndexError:
            logging.error("probably PROMPT length is higher than MAX_TOKENS")

    def add_message(self, role, message_text):
        self.messages.extend(
            [
                {"role": role, "text": message_text},
            ]
        )
        self.messages_len += len(message_text)
        self.shrink_messages()

        with open("config/messages.txt", "w", encoding="utf-8") as f:
            f.writelines(json.dumps(self.messages, ensure_ascii=False))

    def add_user_message(self, user_request):
        self.add_message("user", user_request)
        logging.info(f"user message: {user_request}")

    def add_dialog_message(self, user_request, ai_response):
        self.add_message("user", user_request)
        self.add_message("assistant", ai_response)

    def get_messages(self):
        return self.messages

    def get_config(self, cfg_key):
        return self.config[cfg_key]


yc_token = ycToken()
dialog = Dialog()


def get_random_speaker():
    return speakers[random.randint(0, len(speakers) - 1)]


def askGPT(user_text, context, msgs):
    data = {}
    data["modelUri"] = f"gpt://{folder_id}/{dialog.get_config('model')}"
    data["completionOptions"] = dialog.get_config("options")
    data["messages"] = [
        {"role": "system", "text": f"{context}"},
        *msgs,
        {"role": "user", "text": f"{user_text}"},
    ]
    logging.info(data)

    response = requests.post(
        GPT_URL,
        headers={
            "Accept": "application/json",
            "Authorization": f"Bearer {yc_token.get_token()}",
        },
        json=data,
    ).json()

    logging.info(f"request: {user_text} response: {response}")
    response = response["result"]["alternatives"][0]["message"]["text"]

    return response


def get_alice_answer(user_text):
    response = askGPT(
        user_text, dialog.get_config("prompt"), msgs=dialog.get_messages()
    )

    if (
        response.find("я не могу ничего сказать об этом") >= 0
        or response.find("есть много сайтов с информацией на эту тему") >= 0
    ):
        logging.info("can not speak")
        return (None, "Я не хочу об этом говорить, братан")
    else:
        audio = None
        random_number = random.randint(0, 100)
        logging.info(f"dice: {random_number}")

        if len(response) < 182 and random_number > 80:
            tts_host = dialog.get_config("tts_host")
            if try_connect(tts_host):
                resp_tts = requests.get(
                    f"{tts_host}/api/tts?text={quote(response)}&speaker_id={get_random_speaker()}&style_wav=&language_id=ru&split-sentences=true"
                )
                with open(audio_name, "wb") as f:
                    f.write(resp_tts.content)
                audio = True
        dialog.add_dialog_message(user_text, response)
        return (audio, response)


def request_article_summary(url):
    article_ml_host = dialog.get_config("article_ml_host")
    if try_connect(article_ml_host):
        response = requests.get(
            f"{article_ml_host}/summarize/article_from_url?url={url}"
        )

    if response.status_code == 200:
        return response.text
    else:
        raise AttributeError


def get_user_message(message):
    from_who = message.from_user.first_name
    logging.debug(f"> content_type: {message.content_type}")
    if message.content_type in ["photo", "document", "video", "audio"]:
        message_test = getattr(message, "caption", None)
        if not message_test:
            return None
        user_message = from_who + ":" + message_test
    else:
        user_message = from_who + ":" + message.text

    return user_message.replace(bot_name, "")


def process_url(message):
    for entity_type in ["caption_entities", "entities"]:
        entities = getattr(message, entity_type)
        if entities:
            for entity in entities:
                try:
                    if entity.type == "url":
                        url = message.text[entity.offset : entity.offset + entity.length]
                        summary = request_article_summary(url)
                        bot.reply_to(message, summary)
                        dialog.add_user_message(
                            message.from_user.first_name + ": " + summary
                        )
                        return True
                    elif entity.type == "text_link":
                        summary = request_article_summary(entity.url)
                        bot.reply_to(message, summary)
                        dialog.add_user_message(
                            message.from_user.first_name + ": " + summary
                        )
                        return True
                except (AttributeError, ConnectionError) as err:
                    logging.error(err)
                    continue


def response_to_user(message):
    process_url(message)

    user_message = get_user_message(message)
    if not user_message:
        return

    audio, alice_response = get_alice_answer(user_message)

    if alice_response:
        if audio:
            bot.send_voice(
                message.chat.id,
                voice=InputFile(pathlib.Path(audio_name)),
                reply_parameters=ReplyParameters(message.id, message.chat.id),
            )
        else:
            bot.reply_to(message, alice_response)


@bot.message_handler(regexp=".*{0}.*".format(bot_name))
def response_any(message):
    logging.info(">>>> mention")
    response_to_user(message)


@bot.message_handler(
    func=lambda message: True,
    content_types=["audio", "photo", "video", "document", "text"],
)
def handle_message(message):
    if (
        message.reply_to_message
        and message.reply_to_message.from_user.id == bot.get_me().id
    ):
        logging.info(">>>> reply")
        response_to_user(message)
    else:
        if not process_url(message):
            user_message = get_user_message(message)
            if user_message:
                dialog.add_user_message(user_message)


bot.infinity_polling()
