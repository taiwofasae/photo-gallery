from flask import Flask, render_template, request, redirect
import boto3
import json
import os
from datetime import datetime
from werkzeug.utils import secure_filename
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
s3 = boto3.client('s3')
BUCKET = os.getenv("S3_BUCKET")
BUCKET_FOLDER = os.getenv("BUCKET_FOLDER")

@app.route("/", methods=["GET", "POST"])
def upload_image():
    if request.method == "POST":
        image = request.files["image"]
        tags = request.form["tags"]
        filename = secure_filename(image.filename)
        tag_list = [tag.strip().lower() for tag in tags.split(",")]

        # Upload image
        s3.upload_fileobj(image, BUCKET, f"{BUCKET_FOLDER}images/{filename}")

        # Upload metadata
        metadata = {
            "filename": filename,
            "tags": tag_list,
            "uploaded_at": datetime.utcnow().isoformat()
        }
        metadata_filename = f"{BUCKET_FOLDER}/metadata/{os.path.splitext(filename)[0]}.json"
        s3.put_object(Body=json.dumps(metadata), Bucket=BUCKET, Key=metadata_filename)

        return redirect("/")

    return render_template("upload.html")

if __name__ == "__main__":
    app.run(debug=True)
