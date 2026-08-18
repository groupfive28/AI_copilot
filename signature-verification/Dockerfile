# Build context must be the repo root, not this directory - see
# face-verification/Dockerfile for the same reasoning (this one doesn't
# depend on a sibling package, but kept consistent for the build command):
#   docker build -f signature-verification/Dockerfile -t penta-signature-verification .
FROM python:3.12-slim

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends libpq-dev gcc libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY signature-verification/requirements.txt ./signature-verification/requirements.txt
RUN pip install --no-cache-dir -r signature-verification/requirements.txt

COPY signature-verification/src ./signature-verification/src

WORKDIR /app/signature-verification
ENV PYTHONPATH=/app/signature-verification/src

EXPOSE 8003

CMD ["uvicorn", "sigverify.api:app", "--host", "0.0.0.0", "--port", "8003"]
