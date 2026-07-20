import os
import boto3
import hashlib
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env if present
load_dotenv()

AWS_REGION = os.getenv("AWS_REGION")
AWS_S3_BUCKET = os.getenv("AWS_S3_BUCKET")

if not AWS_S3_BUCKET:
    print("Error: AWS_S3_BUCKET environment variable is not set.")
    exit(1)

# Initialize S3 client
s3_client = boto3.client('s3', region_name=AWS_REGION)

def calculate_md5(file_path):
    hash_md5 = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()

def upload_directory_to_s3(local_dir, s3_prefix=""):
    """
    Recursively uploads a directory to an S3 bucket.
    """
    local_path = Path(local_dir)
    if not local_path.exists():
        print(f"Directory {local_dir} does not exist.")
        return

    for root, dirs, files in os.walk(local_path):
        for file in files:
            if file.endswith(".md"):
                file_path = os.path.join(root, file)
                # Calculate relative path to maintain directory structure in S3
                relative_path = os.path.relpath(file_path, local_dir)
                s3_key = os.path.join(s3_prefix, relative_path).replace("\\", "/")
                
                # Check if file needs to be uploaded
                local_md5 = calculate_md5(file_path)
                try:
                    head = s3_client.head_object(Bucket=AWS_S3_BUCKET, Key=s3_key)
                    # S3 ETags for non-multipart uploads are the MD5 hash enclosed in quotes
                    s3_etag = head.get('ETag', '').strip('"')
                    if s3_etag == local_md5:
                        print(f"  Skipping {s3_key} (already up to date)")
                        continue
                except Exception as e:
                    # If it throws a 404, it means the object doesn't exist, which is fine
                    pass

                print(f"Uploading {file_path} to s3://{AWS_S3_BUCKET}/{s3_key}...")
                try:
                    s3_client.upload_file(file_path, AWS_S3_BUCKET, s3_key)
                    print(f"  Successfully uploaded {s3_key}")
                except Exception as e:
                    print(f"  Error uploading {s3_key}: {e}")

if __name__ == "__main__":
    # Upload articles from site_payload/content/posts to the 'content/posts' folder in S3
    posts_dir = os.path.join(os.path.dirname(__file__), "..", "site_payload", "content", "posts")
    upload_directory_to_s3(posts_dir, s3_prefix="content/posts")
    print("Upload process completed.")
