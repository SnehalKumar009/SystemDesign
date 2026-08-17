FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# System deps for PyMuPDF wheels are bundled; nothing extra needed for slim.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src ./src
COPY run.py config.yaml ./

# Runtime data/output are mounted as volumes; create mount points.
RUN mkdir -p SOURCE data output

ENTRYPOINT ["python", "run.py"]
CMD ["all"]
