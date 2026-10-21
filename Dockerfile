ARG PYTHON_IMAGE=python:3.13-slim-bookworm
FROM ${PYTHON_IMAGE} AS web
WORKDIR /build
COPY LICENSE LICENSE
COPY vocab-data/ vocab-data/
COPY server/build_web.py server/build_web.py
COPY server/static/ server/static/
RUN python vocab-data/build.py && python server/build_web.py

FROM ${PYTHON_IMAGE} AS dependencies
WORKDIR /build
COPY server/requirements.txt requirements.txt
RUN python -m venv /opt/venv && /opt/venv/bin/pip install --no-cache-dir -r requirements.txt

FROM ${PYTHON_IMAGE} AS runtime
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 DATABASE_PATH=/data/study.db PATH=/opt/venv/bin:$PATH
WORKDIR /app
RUN groupadd --gid 10001 workbook && useradd --uid 10001 --gid 10001 --no-create-home workbook && mkdir -p /data && chown workbook:workbook /data
COPY --from=dependencies /opt/venv /opt/venv
COPY server/*.py /app/server/
COPY server/static/ /app/server/static/
COPY --from=web /build/server/web/ /app/server/web/
COPY vocab-data/study-data.json /app/vocab-data/study-data.json
COPY vocab-data/ecdict-license.txt /app/vocab-data/ecdict-license.txt
COPY LICENSE NOTICE /app/
USER 10001:10001
EXPOSE 8000
# Trusts X-Forwarded-For from any peer: only reachable through Caddy, never publish port 8000.
CMD ["python","-m","uvicorn","server.app:application","--factory","--host","0.0.0.0","--port","8000","--proxy-headers","--forwarded-allow-ips=*","--limit-concurrency","32","--no-server-header"]

FROM runtime AS test
USER root
COPY server/requirements*.txt /tmp/
RUN pip install --no-cache-dir -r /tmp/requirements-dev.txt
COPY tests/test_server.py /app/tests/test_server.py
USER 10001:10001
CMD ["python","-m","pytest","tests/test_server.py","-q"]
