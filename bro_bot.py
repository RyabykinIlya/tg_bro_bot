import telebot
from telebot.types import ReplyParameters, InputFile
import random
from urllib.parse import quote
import pathlib
import requests
import re
import time
import json
import os
from datetime import datetime, timedelta

bot = telebot.TeleBot(
    os.environ.get("TG_BOT_TOKEN"), parse_mode="Markdown"
)

URL = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"

OAuth = os.environ.get("YANDEX_OAUTH")
folder_id = os.environ.get("YANDEX_FOLDER_ID")
bot_name = "@bomzh_bro_bot"
audio_name = "audio.mp3"
speakers = [
    "Claribel%20Dervla",
    "Vjollca%20Johnnie",
    "Royston%20Min",
    "Viktor%20Eka",
    "Craig%20Gutsy",
    "Zofija%20Kendrick",
    "Ferran%20Simen",
]

response_categories = [
    "инвестиции",
    "финансы",
    "деньги",
    "криптовалюта",
    "биржа",
    "игры",
    "женщины",
    # "мемы",
    # "новости",
    "искусственный интеллект",
    "путешествия",
    "искусство",
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
            print("got token", self.yc_token, "expires at", self.yc_token_expires_at)

        return self.yc_token


class Dialog:
    def __init__(self):
        self.messages = []
        self.max_messages = 30
        self.config = {
            "answer": "",
            "model": "",
            "options": {},
            "tts_host": "",
        }
        self.init_messages()

    def init_messages(self):
        with open("config/messages.txt", "r") as f:
            self.messages = json.loads(f.readline().strip())
            print("load messages:", self.messages)

    def add_message(self, role, message_text):
        self.messages.extend(
            [
                {"role": role, "text": message_text},
            ]
        )

        if len(self.messages) > self.max_messages:
            self.messages.pop(0)

        with open("config/messages.txt", "w+") as f:
             f.writelines(json.dumps(self.messages))
            
        # print("messages now:", self.messages)

    def add_user_message(self, user_request):
        self.add_message("user", user_request)
        # self.messages.extend(
        #     [
        #         {"role": "user", "text": user_request},
        #     ]
        # )

        # if len(self.messages) > self.max_messages:
        #     self.messages.pop(0)

        # print("messages now:", self.messages)

    def add_dialog_message(self, user_request, ai_response):
        self.add_message("user", user_request)
        self.add_message("assistant", ai_response)
        # self.messages.extend(
        #     [
        #         {"role": "user", "text": user_request},
        #         {"role": "assistant", "text": ai_response},
        #     ]
        # )

        # if len(self.messages) > self.max_messages:
        #     self.messages.pop(0)
        #     self.messages.pop(0)

        # print("messages now:", self.messages)

    def get_messages(self):
        return self.messages


yc_token = ycToken()
dialog = Dialog()


def remove_non_russian(text):
    # Используем регулярное выражение для удаления всех символов, кроме русских букв
    cleaned_text = re.sub(r"[^а-яА-ЯёЁ\s]", "", text)
    return cleaned_text


def get_settings(type):
    with open("config/" + type + ".txt", "r") as f:
        return f.readline()


def get_model():
    with open("config/model.txt", "r") as f:
        return f.readline().strip()


def get_options():
    with open("config/options.txt", "r") as f:
        return json.loads(f.readline().strip())


def get_tts_host():
    with open("config/tts_host.txt", "r") as f:
        return f.readline().strip()


def get_random_speaker():
    return speakers[random.randint(0, len(speakers) - 1)]


def askGPT(user_text, context, dialog=[]):
    data = {}
    data["modelUri"] = f"gpt://{folder_id}/{get_model()}"
    data["completionOptions"] = get_options()  # {"temperature": 0.5, "maxTokens": 3000}
    data["messages"] = [
        {"role": "system", "text": f"{context}"},
        *dialog,
        {"role": "user", "text": f"{user_text}"},
    ]
    print(data)

    # print(">!>!>!", data["messages"])

    response = requests.post(
        URL,
        headers={
            "Accept": "application/json",
            "Authorization": f"Bearer {yc_token.get_token()}",
        },
        json=data,
    ).json()

    print("request:\t", user_text, "\nresponse:\t", response)
    response = response["result"]["alternatives"][0]["message"]["text"]

    return response


def get_alice_answer(user_text):
    response = askGPT(user_text, get_settings("answer"), dialog=dialog.get_messages())

    if (
        response.find("я не могу ничего сказать об этом") >= 0
        or response.find("есть много сайтов с информацией на эту тему") >= 0
    ):
        return (None, None)
    else:
        audio = None
        random_number = random.randint(0, 100)
        print(f"dice: {random_number}")

        if len(response) < 182 and random_number > 80:
            try:
                tts_host = get_tts_host()
                requests.get(f"{tts_host}", timeout=0.5)
                resp_tts = requests.get(
                    f"{tts_host}/api/tts?text={quote(response)}&speaker_id={get_random_speaker()}&style_wav=&language_id=ru&split-sentences=true"
                )
                with open(audio_name, "wb") as f:
                    f.write(resp_tts.content)
                # song = AudioSegment.from_wav("audio.wav")
                # song.export(audio_name, format="ogg")
                audio = True
            except requests.exceptions.ConnectionError:
                print(
                    f"__________________ host {tts_host} is not available __________________"
                )
        dialog.add_dialog_message(user_text, response)
        return (audio, response)


def categorize_message(user_text):
    category = askGPT(user_text, get_settings("categorize"))
    print(user_text, category, sep="\t")
    return category


def categorized_messages(message):
    check = (
        remove_non_russian(categorize_message(message.text)).lower()
        in response_categories
    )
    time.sleep(0.5)
    return True if check else False


@bot.message_handler(regexp=".*{0}.*".format(bot_name))
def response_any(message):
    print(">>>> mention")
    from_who = message.from_user.first_name
    msg = message.text.replace(bot_name, "")
    audio, alice_response = get_alice_answer(from_who + ":" + msg)
    if alice_response:
        if audio:
            bot.send_voice(
                message.chat.id,
                voice=InputFile(pathlib.Path(audio_name)),
                # caption="послушай, братан",
                # duration=audio.duration_seconds,
                reply_parameters=ReplyParameters(message.id, message.chat.id),
            )
        else:
            bot.reply_to(message, alice_response)


# @bot.message_handler(func=categorized_messages)
# def response_categorized(message):
#     print(">>>> categorized")
#     from_who = message.from_user.first_name
#     alice_response = get_alice_answer(from_who + ":" + message.text)
#     if alice_response:
#         bot.reply_to(message, alice_response)


@bot.message_handler(
    func=lambda message: True,
    content_types=["audio", "photo", "voice", "video", "document", "text"],
)
def handle_message(message):
    from_who = message.from_user.first_name
    user_message = from_who + ":" + message.text
    if (
        message.reply_to_message
        and message.reply_to_message.from_user.id == bot.get_me().id
    ):
        print(">>>> reply")
        audio, alice_response = get_alice_answer(user_message)
        if alice_response:
            if audio:
                bot.send_voice(
                    message.chat.id,
                    voice=InputFile(pathlib.Path(audio_name)),
                    # caption="послушай, братан",
                    # duration=audio.duration_seconds,
                    reply_parameters=ReplyParameters(message.id, message.chat.id),
                )
            else:
                bot.reply_to(message, alice_response)
    else:
        dialog.add_user_message(user_message)


bot.infinity_polling()
