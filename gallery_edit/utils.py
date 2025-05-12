import boto3
from io import BytesIO
from pillow_heif import register_heif_opener
from PIL import Image

# Register HEIC format
register_heif_opener()

s3 = boto3.client("s3")

def convert_heic_from_s3(bucket, key, output_format="PNG", save_to_s3=False, output_bucket=None, output_key=None):
    # Download S3 object into memory
    response = s3.get_object(Bucket=bucket, Key=key)
    heic_bytes = response['Body'].read()

    # Open image from bytes
    image = Image.open(BytesIO(heic_bytes))

    # Convert and prepare output
    output_buffer = BytesIO()
    if output_format.upper() == "JPEG":
        image = image.convert("RGB")
        image.save(output_buffer, format="JPEG", quality=95, optimize=True)
    elif output_format.upper() == "PNG":
        image.save(output_buffer, format="PNG", optimize=True)
    else:
        raise ValueError("Unsupported format. Use 'PNG' or 'JPEG'.")

    output_buffer.seek(0)

    if save_to_s3:
        if not output_bucket or not output_key:
            raise ValueError("Output S3 bucket and key must be provided.")
        s3.upload_fileobj(output_buffer, output_bucket, output_key)
        print(f"Uploaded converted image to s3://{output_bucket}/{output_key}")
        return f"s3://{output_bucket}/{output_key}"
    else:
        return output_buffer  # You can use this buffer to save locally or return as HTTP response


def generate_thumbnail(source_bucket, source_key, target_bucket=None, target_key=None, size=(200, 200)):
    # Download image from S3
    response = s3.get_object(Bucket=source_bucket, Key=source_key)
    image_data = response['Body'].read()

    # Open image with Pillow
    image = Image.open(BytesIO(image_data))
    image.thumbnail(size)

    # Save thumbnail to memory
    buffer = BytesIO()
    image_format = image.format or 'JPEG'
    image.save(buffer, format=image_format)
    buffer.seek(0)

    # Determine where to upload
    if not target_bucket:
        target_bucket = source_bucket
    if not target_key:
        key_parts = source_key.rsplit('.', 1)
        suffix = f"_thumbnail.{key_parts[-1]}"
        target_key = f"{key_parts[0]}{suffix}" if len(key_parts) > 1 else f"{source_key}_thumbnail"

    # Upload thumbnail back to S3
    s3.upload_fileobj(buffer, target_bucket, target_key)
    print(f"Thumbnail saved to s3://{target_bucket}/{target_key}")