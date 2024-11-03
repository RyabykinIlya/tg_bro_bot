# tg_bro_bot

Build
```bash
docker build -t bro_bot_audio:v1 --platform linux/arm64 .
```

Run
```bash
docker run -d --name tg_bro_bot -v ./config:/opt/config --env-file .env --restart unless-stopped bro_bot_audio:v1
```