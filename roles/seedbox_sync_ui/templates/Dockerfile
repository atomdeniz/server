FROM python:{{ seedbox_sync_ui_version }}

# openssh-client: the app shells out to `ssh` to tail the seedbox log.
# Same pattern as the media_cleanup script — no paramiko dependency.
RUN apt-get update \
 && apt-get install -y --no-install-recommends openssh-client \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .

RUN adduser --disabled-password --gecos "" appuser \
 && mkdir -p /app/.ssh \
 && chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

# Single worker so the background poller thread is unique.
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "1", "--threads", "4", "app:app"]
