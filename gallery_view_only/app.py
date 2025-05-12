from flask import Flask, render_template, request
import boto3
import json
from dotenv import load_dotenv
import os
load_dotenv()

app = Flask(__name__)
s3 = boto3.client('s3')
BUCKET = os.getenv("S3_BUCKET")
BUCKET_FOLDER = os.getenv("BUCKET_FOLDER")

@app.route("/", methods=["GET"])
def gallery():
    search = request.args.get("search", "").lower()
    image_entries = []

    result = s3.list_objects_v2(Bucket=BUCKET, Prefix=f"{BUCKET_FOLDER}/metadata/")
    if "Contents" in result:
        for item in result["Contents"]:
            metadata_file = item["Key"]
            obj = s3.get_object(Bucket=BUCKET, Key=metadata_file)
            metadata = json.loads(obj["Body"].read())
            # search takes only the first keyword
            if not search or search.split()[0].split(',')[0] in metadata["tags"]:
                image_url = s3.generate_presigned_url(
                    'get_object',
                    Params={'Bucket': BUCKET, 'Key': f"{BUCKET_FOLDER}images/{metadata['filename']}"},
                    ExpiresIn=3600
                )
                image_entries.append(image_url)

    return render_template("gallery.html", images=image_entries, search=search)

if __name__ == "__main__":
    app.run(debug=True, port=5001)
