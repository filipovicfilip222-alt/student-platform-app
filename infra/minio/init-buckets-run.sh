#!/bin/sh
set -e

MINIO_ALIAS="local"
MINIO_URL="http://minio:9000"

echo "Waiting for MinIO to be ready..."
until mc alias set "$MINIO_ALIAS" "$MINIO_URL" "$MINIO_ACCESS_KEY" "$MINIO_SECRET_KEY" > /dev/null 2>&1; do
  echo "MinIO not ready yet, retrying in 3s..."
  sleep 3
done
echo "MinIO is ready."

create_bucket() {
  BUCKET=$1
  if mc ls "$MINIO_ALIAS/$BUCKET" > /dev/null 2>&1; then
    echo "Bucket '$BUCKET' already exists, skipping."
  else
    mc mb "$MINIO_ALIAS/$BUCKET"
    echo "Bucket '$BUCKET' created."
  fi
}

create_bucket "appointment-files"
create_bucket "professor-avatars"
create_bucket "bulk-imports"
create_bucket "document-requests"

# Postavi anonymous read policy za avatar bucket (javni pristup avatarima)
mc anonymous set download "$MINIO_ALIAS/professor-avatars"
echo "Anonymous download policy set for 'professor-avatars'."

# Ostali bucketi su private (pristup samo kroz presigned URL-ove)
mc anonymous set none "$MINIO_ALIAS/appointment-files"
mc anonymous set none "$MINIO_ALIAS/bulk-imports"
mc anonymous set none "$MINIO_ALIAS/document-requests"
echo "Private policy confirmed for appointment-files, bulk-imports, document-requests."

echo ""
echo "MinIO bucket initialization complete."
echo "Buckets:"
mc ls "$MINIO_ALIAS"
