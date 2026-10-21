FROM apache/airflow:2.10.4-python3.12

COPY airflow/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

COPY src /opt/gazette/src
COPY migrations /opt/gazette/migrations

ENV PYTHONPATH=/opt/gazette/src

