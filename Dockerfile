FROM python:3.11-slim

# System deps for SimpleITK image IO (PNG/JPEG/TIFF, NIfTI)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libjpeg62-turbo libpng16-16 zlib1g libtiff6 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY oct_harmonize ./oct_harmonize
COPY README.md .

# Default entrypoint -> python -m oct_harmonize.main ...
ENTRYPOINT ["python", "-m", "oct_harmonize.main"]
