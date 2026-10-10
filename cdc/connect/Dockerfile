FROM debezium/connect:2.7.3.Final

USER root

RUN microdnf install -y curl tar gzip \
    && microdnf clean all

RUN mkdir -p /kafka/connect/debezium-jdbc

RUN curl -fSL \
    https://repo1.maven.org/maven2/io/debezium/debezium-connector-jdbc/2.7.3.Final/debezium-connector-jdbc-2.7.3.Final-plugin.tar.gz \
    -o /tmp/debezium-jdbc.tar.gz \
    && tar -xzf /tmp/debezium-jdbc.tar.gz \
       -C /kafka/connect/debezium-jdbc \
    && rm /tmp/debezium-jdbc.tar.gz