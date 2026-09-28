FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY cleaner.py shortlinks.py notify.py bot.py ./

RUN useradd --system --no-create-home linx && mkdir /data && chown linx /data
USER linx

# Per-user notification settings (SQLite). Mount a volume here to keep them across rebuilds.
ENV LINX_DATA_DIR=/data
VOLUME /data

# DISCORD_TOKEN, FIX_X_LINKS and SUPPRESS_ORIGINAL_EMBEDS come from the environment.
CMD ["python", "bot.py"]
