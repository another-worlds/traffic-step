FROM nvidia/cuda:12.3.2-runtime-ubuntu22.04
WORKDIR /app
RUN apt-get update && apt-get install -y python3 python3-pip && rm -rf /var/lib/apt/lists/*
RUN pip3 install --no-cache-dir ultralytics torch torchvision celery redis psycopg[binary] sqlalchemy
COPY . .
CMD ["celery", "-A", "tasks", "worker", "-l", "info", "--concurrency=1"]
