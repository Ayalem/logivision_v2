FROM flink:1.20-scala_2.12-java17

# Install Python and dependencies
RUN apt-get update && apt-get install -y python3 python3-pip && \
    ln -s /usr/bin/python3 /usr/bin/python && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /opt/flink/jobs

# Copy requirements first for layer caching
COPY pyproject.toml .
RUN pip3 install fastavro confluent-kafka numpy

# Copy job code
COPY jobs/ ./jobs/

# Flink configuration for checkpoints to MinIO
RUN echo "state.backend: rocksdb" >> /opt/flink/conf/flink-conf.yaml && \
    echo "state.checkpoints.dir: s3p://checkpoints/flink" >> /opt/flink/conf/flink-conf.yaml && \
    echo "execution.checkpointing.interval: 60s" >> /opt/flink/conf/flink-conf.yaml && \
    echo "execution.checkpointing.min-pause-between-checkpoints: 30s" >> /opt/flink/conf/flink-conf.yaml && \
    echo "s3.endpoint: http://minio:9000" >> /opt/flink/conf/flink-conf.yaml && \
    echo "s3.access-key: ${MINIO_ACCESS_KEY:-minioadmin}" >> /opt/flink/conf/flink-conf.yaml && \
    echo "s3.secret-key: ${MINIO_SECRET_KEY:-minioadmin}" >> /opt/flink/conf/flink-conf.yaml

ENV FLINK_PARALLELISM=2
ENV KAFKA_BROKER=kafka:9092
ENV ZONES_JSON='{"zone_entree":[[0,0],[200,0],[200,300],[0,300]],"zone_stockage":[[200,0],[500,0],[500,300],[200,300]]}'

ENTRYPOINT ["python3", "-m", "jobs.detection_enrichment"]
