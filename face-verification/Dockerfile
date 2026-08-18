# Build context must be the repo root, not this directory - this service
# depends on the sibling Face_Verification_Test/face_verification_package/
# package (see src/faceverify/pipeline.py). e.g.:
#   docker build -f face-verification/Dockerfile -t penta-face-verification .
FROM python:3.12-slim

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends libpq-dev gcc libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY face-verification/requirements.txt ./face-verification/requirements.txt
RUN pip install --no-cache-dir -r face-verification/requirements.txt

COPY face-verification/src ./face-verification/src
COPY Face_Verification_Test/face_verification_package/face_verification ./Face_Verification_Test/face_verification_package/face_verification

WORKDIR /app/face-verification
ENV PYTHONPATH=/app/face-verification/src

EXPOSE 8002

CMD ["uvicorn", "faceverify.api:app", "--host", "0.0.0.0", "--port", "8002"]
