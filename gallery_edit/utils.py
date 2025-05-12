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
