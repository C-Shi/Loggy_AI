import json
from google.cloud import storage

def write_to_bucket(data: dict, bucket_name: str, file_name: str, content_type: str = "application/json",) -> str:
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(file_name)
    blob.upload_from_string(
        json.dumps(data, default=str),
        content_type=content_type,
    )

    return file_name
