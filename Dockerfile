FROM python:3-slim

WORKDIR /opt
COPY bro_bot.py requirements.txt ./

RUN pip install -r requirements.txt

VOLUME ["/opt/config"]

CMD [ "python", "-u", "./bro_bot.py" ]