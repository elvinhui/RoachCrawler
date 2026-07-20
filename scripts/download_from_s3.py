import os
import boto3
from pathlib import Path

# Vercel environment variables
AWS_REGION = os.getenv("AWS_REGION")
AWS_S3_BUCKET = os.getenv("AWS_S3_BUCKET")

if not AWS_S3_BUCKET:
    print("Error: AWS_S3_BUCKET environment variable is not set. Skipping download.")
    exit(0)

s3_client = boto3.client('s3', region_name=AWS_REGION)

def download_s3_prefix(s3_prefix, local_dir):
    """
    Downloads all objects under an S3 prefix to a local directory.
    """
    local_path = Path(local_dir)
    local_path.mkdir(parents=True, exist_ok=True)
    
    print(f"Fetching from s3://{AWS_S3_BUCKET}/{s3_prefix} to {local_dir}...")
    
    # List objects
    try:
        response = s3_client.list_objects_v2(Bucket=AWS_S3_BUCKET, Prefix=s3_prefix)
        if 'Contents' not in response:
            print(f"No objects found with prefix {s3_prefix}")
            return
            
        for obj in response['Contents']:
            key = obj['Key']
            if key.endswith('/'):
                continue # Skip directories
                
            # Calculate local path
            relative_key = key[len(s3_prefix):].lstrip('/')
            file_path = local_path / relative_key
            
            # Ensure local directory exists
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            print(f"  Downloading {key} to {file_path}")
            s3_client.download_file(AWS_S3_BUCKET, key, str(file_path))
            
    except Exception as e:
        print(f"Error listing/downloading from S3: {e}")
        exit(1)

if __name__ == "__main__":
    # Download content/posts to site_payload/content/posts
    posts_dir = os.path.join(os.path.dirname(__file__), "..", "site_payload", "content", "posts")
    download_s3_prefix("content/posts/", posts_dir)
    print("Download process completed.")
