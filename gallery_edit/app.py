from datetime import datetime
from flask import Flask, render_template, request, redirect
import boto3
import json
from dotenv import load_dotenv
import os
from werkzeug.utils import secure_filename

from utils import convert_heic_from_s3

load_dotenv()

app = Flask(__name__)
s3 = boto3.client('s3')
BUCKET = os.getenv("S3_BUCKET")
BUCKET_FOLDER = os.getenv("BUCKET_FOLDER")

@app.route("/heic", methods=["POST"])
def convert_heic():
    if request.method == "POST":
        image_key = request.form["heic_key"]
        # handle iphone HEIC formats
        if image_key.lower().endswith('heic'):
            print("object is of heic ext. Converting to png...")
            new_image_key = f"{os.path.splitext(image_key)[0]}.png"
            png_exists = False
            # check if png exists
            try:
                s3.head_object(Bucket=BUCKET, Key=new_image_key)
                png_exists = True
            except s3.exceptions.ClientError as e:
                if e.response['Error']['Code'] == "404":
                    pass

            if png_exists:
                print('png exists. Skipping...')
            else:
                print('png does not exist. Converting from heic to png...')
                convert_heic_from_s3(
                    bucket=BUCKET,
                    key=image_key,
                    output_format="PNG",
                    save_to_s3=True,
                    output_bucket=BUCKET,
                    output_key=new_image_key
                )
                image_key = new_image_key
            return {"OK": "Updated"}, 200
            
        return {"error": "Something's wrong"}, 400

@app.route("/", methods=["GET"])
def gallery():
    search = request.args.get("search", "").lower()
    image_entries = []

    result = s3.list_objects_v2(Bucket=BUCKET, Prefix=f"{BUCKET_FOLDER}images/")
    flag = False
    if "Contents" in result:
        for item in result["Contents"]:
            image_key = item["Key"]
            if image_key.endswith('/'):
                # Skip directories
                continue

            is_heic = False
            # handle iphone HEIC formats
            if image_key.lower().endswith('heic'):
                is_heic = True

            image_signed_path = f"https://{BUCKET}.s3.us-east-1.amazonaws.com/{image_key}"
            image_filename = image_key.split(f"{BUCKET_FOLDER}images/")[-1]
            metadata_key = f"{BUCKET_FOLDER}metadata/{os.path.splitext(image_filename)[0]}.json"
            # check if metadata exists
            try:
                obj = s3.get_object(Bucket=BUCKET, Key=metadata_key)
                metadata = json.loads(obj["Body"].read())
                if not search or search in metadata["tags"]:
                    image_entries.append((image_signed_path, metadata["tags"], image_filename, is_heic))
            except s3.exceptions.NoSuchKey as e:
                # TODO: consider excluding images with no metadata. Temporarily used as forcing metadata declaration
                image_entries.append((image_signed_path, [], image_filename, is_heic))

    return render_template("gallery.html", images=image_entries)

@app.route("/update", methods=["POST"])
def update_tags():
    if request.method == "POST":
        tags = request.form["tags"]
        filename = request.form["filename"]
        filename = secure_filename(filename)
        tag_list = [tag.strip().lower() for tag in tags.split(",")]

        # create metadata if not exists
        metadata_filename = f"{BUCKET_FOLDER}metadata/{os.path.splitext(filename)[0]}.json"
        try:
            obj = s3.get_object(Bucket=BUCKET, Key=metadata_filename)
            metadata = json.loads(obj["Body"].read())
            print("metadata:", metadata)
            # Update metadata
            metadata = {
                "filename": metadata['filename'],
                "tags": tag_list,
                "uploaded_at": metadata['uploaded_at']
            }
            s3.put_object(Body=json.dumps(metadata), Bucket=BUCKET, Key=metadata_filename)
        except s3.exceptions.NoSuchKey as e:
            metadata = {
                "filename": filename,
                "tags": tag_list,
                "uploaded_at": datetime.utcnow().isoformat()
            }
            s3.put_object(Body=json.dumps(metadata), Bucket=BUCKET, Key=metadata_filename)

        return {"OK": "Updated"}, 200

    return {"error": "Something bad happened"}, 500

if __name__ == "__main__":
    app.run(debug=True)
