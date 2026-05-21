FROM flink:1.18.1-scala_2.12-java11

RUN apt-get update && apt-get install -y python3 python3-pip && \
    pip3 install apache-flink==1.18.1

WORKDIR /opt/flink/jobs
COPY jobs/ ./jobs/

ENV KAFKA_BROKER=kafka:9092
ENV TOPIC_DETECTIONS=detections
ENV TOPIC_EVENTS=events
ENV TOPIC_TRACKS=tracks
ENV TOPIC_KPIS=kpis
ENV STATIONARY_THRESHOLD_SEC=300
ENV MOVEMENT_THRESHOLD_PX=15.0
