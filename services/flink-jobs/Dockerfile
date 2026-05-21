FROM flink:1.20-scala_2.12-java17

# Supprimer linux-libc-dev pour passer le scan Trivy
RUN apt-get update && \
    apt-get remove -y linux-libc-dev && \
    apt-get install -y python3 python3-pip && \
    apt-get autoremove -y && \
    rm -rf /var/lib/apt/lists/*

RUN pip3 install fastavro confluent-kafka numpy

WORKDIR /opt/flink/jobs
COPY jobs/ ./jobs/

ENV KAFKA_BROKER=kafka:9092
ENV TOPIC_DETECTIONS=detections
ENV TOPIC_EVENTS=events
ENV TOPIC_TRACKS=tracks
ENV TOPIC_KPIS=kpis
ENV STATIONARY_THRESHOLD_SEC=300
ENV MOVEMENT_THRESHOLD_PX=15.0
