from datetime import datetime
import streamlit as st
import boto3
import json
import os
from dotenv import load_dotenv

from utils import convert_heic_from_s3

# Load environment variables
load_dotenv()

S3_REGION = os.getenv("S3_REGION", "us-east-1")
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")

BUCKET = os.getenv("S3_BUCKET")
BUCKET_FOLDER = os.getenv("BUCKET_FOLDER")

# S3 client
s3 = boto3.client(
    "s3",
    region_name=S3_REGION,
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
)

def list_images(bucket_folder):
    response = s3.list_objects_v2(Bucket=BUCKET, Prefix=f"{bucket_folder}images/")
    return [obj["Key"] for obj in response.get("Contents", [])]
    # return [obj["Key"] for obj in response.get("Contents", []) if obj["Key"].lower().endswith((".jpg", ".jpeg", ".png"))]

def get_metadata(bucket_folder, image_key):
    base_name = os.path.splitext(os.path.basename(image_key))[0]
    meta_key = f"{bucket_folder}metadata/{base_name}.json"
    try:
        meta_obj = s3.get_object(Bucket=BUCKET, Key=meta_key)
        return json.loads(meta_obj["Body"].read()), meta_key
    except s3.exceptions.ClientError:
        return {"tags": []}, meta_key

def update_metadata(meta_key, filename, tags):
    metadata = {
            "filename": filename,
            "tags": [tag.strip() for tag in tags.split(",")],
            "uploaded_at": datetime.utcnow().isoformat()
        }
    s3.put_object(
        Bucket=BUCKET,
        Key=meta_key,
        Body=json.dumps(metadata),
        ContentType="application/json"
    )

def key_exists(s3_key):
    try:
        s3.head_object(Bucket=BUCKET, Key=s3_key)
        return True
    except s3.exceptions.ClientError as e:
        if e.response['Error']['Code'] == "404":
            pass
    return False

# Set Streamlit to use a wide layout
st.set_page_config(layout="wide")

# Streamlit UI
st.title("📸 S3 Image Gallery")



if 'bucket_folder' not in st.session_state:
    st.session_state.bucket_folder = BUCKET_FOLDER

bucket_folder = st.session_state.bucket_folder

if "all_images" not in st.session_state:
    st.session_state.all_images = list_images(bucket_folder)

all_images = st.session_state.all_images
images = all_images

if "index" not in st.session_state:
    st.session_state.index = 0


# Sidebar for refreshing the list of images
with st.sidebar:
    st.session_state.bucket_folder = st.text_input('Bucket folder', value=bucket_folder)
    if st.button("Refresh Image List"):
        st.session_state.all_images = list_images(bucket_folder)
        st.session_state.index = 0

# Sidebar for filtering by extension
with st.sidebar:
    if "extensions" not in st.session_state:
        # Extract unique extensions from the image list
        st.session_state.extensions = list(set(os.path.splitext(img)[1].lower() for img in all_images if "." in img))
    
    selected_extension = st.selectbox("Filter by Extension", ["All"] + st.session_state.extensions,
                                      on_change=lambda: st.session_state.update({'index':0}))

    if selected_extension != "All":
        images = [img for img in all_images if img.lower().endswith(selected_extension)]



if images:
    image_key = images[st.session_state.index]
    st.write(image_key)
    image_filename = image_key.split(f'{bucket_folder}images/')[-1]
    
    if image_key.lower().endswith('heic'):
        png_image_key = f"{os.path.splitext(image_key)[0]}.png"
        if st.button('Convert to png'):
            with st.spinner('converting...'):
                convert_heic_from_s3(
                        bucket=BUCKET,
                        key=image_key,
                        output_format="PNG",
                        save_to_s3=True,
                        output_bucket=BUCKET,
                        output_key=png_image_key
                    )
                st.success('conversion done.')
        if key_exists(png_image_key):
            st.write(f'PNG key exists: {png_image_key}')

    col1, col2 = st.columns([4,7])

    with col1:
        url = s3.generate_presigned_url("get_object", Params={"Bucket": BUCKET, "Key": image_key}, ExpiresIn=3600)
        st.image(url)

    with col2:
        col1, col2, col3 = st.columns(3)
        with col1:
            if st.button("Previous") and st.session_state.index > 0:
                st.session_state.index -= 1
                st.rerun()
        with col2:
            st.write(f"{st.session_state.index + 1} of {len(images)}")
        with col3:
            if st.button("Next") and st.session_state.index < len(images) - 1:
                st.session_state.index += 1
                st.rerun()
                
        metadata, meta_key = get_metadata(bucket_folder, image_key)
        st.write('**Metadata:**')
        st.json(metadata)
        tags = st.text_input("Tags (comma-separated)", value=", ".join(metadata.get("tags", [])))

        if st.button("Update Tags"):
            update_metadata(meta_key, filename=metadata.get('filename', image_filename), tags=tags)
            st.success("Tags updated!")
            st.rerun()

        
else:
    st.write("No images found in the S3 bucket.")
