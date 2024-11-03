FROM python:3-slim

WORKDIR /opt
COPY bro_bot.py .
COPY .env

RUN pip install pyTelegramBotAPI
RUN source .env


VOLUME ["/opt/config"]

CMD [ "python", "-u", "./bro_bot.py" ]