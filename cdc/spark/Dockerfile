FROM python:3.11-slim-bookworm

RUN apt-get update \
    && apt-get install -y --no-install-recommends openjdk-17-jre-headless ca-certificates \
    && rm -rf /var/lib/apt/lists/*

ENV JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64
ENV PATH="${JAVA_HOME}/bin:${PATH}"
ENV PIP_NO_CACHE_DIR=1

RUN python -m pip install --no-cache-dir --upgrade pip \
        && python -m pip install --no-cache-dir pyspark==3.5.5 notebook

WORKDIR /opt/spark-app

COPY ingest.py /opt/spark-app/ingest.py
CMD ["python", "/opt/spark-app/ingest.py"]


