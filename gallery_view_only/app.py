from flask import Flask, jsonify, render_template, request
import boto3
import json
from dotenv import load_dotenv
import os

from flask_caching import Cache
load_dotenv()

app = Flask(__name__)
s3 = boto3.client('s3')
BUCKET = os.getenv("S3_BUCKET")
BUCKET_FOLDER = os.getenv("BUCKET_FOLDER")

app.config["CACHE_TYPE"] = "SimpleCache"
app.config["CACHE_DEFAULT_TIMEOUT"] = 300
cache = Cache(app)

@app.route('/clear-cache', methods=["POST"])
def clear_cache():
    cache.clear()
    return jsonify({"status": "success", "message": "Cache cleared."})


@app.route("/", methods=["GET"])
@cache.cached(query_string=True)
def gallery():
    print('cache miss!')
    search = request.args.get("search", "").lower()
    image_entries = []

    result = s3.list_objects_v2(Bucket=BUCKET, Prefix=f"{BUCKET_FOLDER}metadata/")
    if "Contents" in result:
        for item in result["Contents"]:
            metadata_file = item["Key"]
            obj = s3.get_object(Bucket=BUCKET, Key=metadata_file)
            metadata = json.loads(obj["Body"].read())
            filename = metadata['filename']
            # search takes only the first keyword
            if not search or search.split()[0].split(',')[0] in metadata["tags"]:
                # image_url = s3.generate_presigned_url(
                #     'get_object',
                #     Params={'Bucket': BUCKET, 'Key': f"{BUCKET_FOLDER}images/{filename}"},
                #     ExpiresIn=3600
                # )
                image_url = f"https://{BUCKET}.s3.us-east-1.amazonaws.com/{BUCKET_FOLDER}images/{filename}"
                thumbnail_url = f"https://{BUCKET}.s3.us-east-1.amazonaws.com/{BUCKET_FOLDER}thumbnails/{filename}"
                image_entries.append((image_url, thumbnail_url))

    return render_template("gallery.html", images=image_entries, search=search)

if __name__ == "__main__":
    app.run(debug=True, port=5001)
