from datetime import datetime
import streamlit as st
import boto3
import json
import os
from dotenv import load_dotenv

from utils import convert_heic_from_s3, generate_thumbnail

# Load environment variables
load_dotenv()

S3_REGION = os.getenv("S3_REGION", "us-east-1")
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")

BUCKET = os.getenv("S3_BUCKET")
BUCKET_FOLDER = os.getenv("BUCKET_FOLDER")

IMAGES_FOLDER = 'images/'
THUMBNAIL_FOLDER = 'thumbnails/'
METADATA_FOLDER = 'metadata/'

# S3 client
s3 = boto3.client(
    "s3",
    region_name=S3_REGION,
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
)

def extract_filename_from_s3key(s3key):
    return os.path.splitext(os.path.basename(s3key))[0]

def list_images(bucket_folder):
    response = s3.list_objects_v2(Bucket=BUCKET, Prefix=f"{bucket_folder}{IMAGES_FOLDER}")
    return [obj["Key"] for obj in response.get("Contents", [])]
    # return [obj["Key"] for obj in response.get("Contents", []) if obj["Key"].lower().endswith((".jpg", ".jpeg", ".png"))]

def get_metadata(bucket_folder, image_key):
    filename = extract_filename_from_s3key(image_key)
    meta_key = f"{bucket_folder}{METADATA_FOLDER}{filename}.json"
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

images = st.session_state.all_images

if "index" not in st.session_state:
    st.session_state.index = 0

if "extensions" not in st.session_state:
    st.session_state.extensions = []


# Sidebar for refreshing the list of images
with st.sidebar:
    st.session_state.bucket_folder = st.text_input('Bucket folder', value=bucket_folder)
    if st.button("Refresh Image List"):
        st.session_state.all_images = []
        st.session_state.all_images = list_images(bucket_folder)
        st.session_state.index = 0
        st.rerun()

# Sidebar for filtering by extension
with st.sidebar:
    all_images = st.session_state.all_images

    st.session_state.extensions = list(set(os.path.splitext(img)[1].lower() for img in all_images if "." in img))
    
    selected_extension = st.selectbox("Filter by Extension", ["All"] + st.session_state.extensions,
                                      on_change=lambda: st.session_state.update({'index':0}))

    if selected_extension != "All":
        images = [img for img in all_images if img.lower().endswith(selected_extension)]

    st.markdown('---')

    if st.button("Convert all HEIC to PNG"):
        n_images = len(images)
        progress_bar = st.progress(0, 'Conversion')
        status_text = st.empty()
        with st.spinner(f'converting {n_images} images...'):
            for index, image_key in enumerate(images):
                status_text.text(f"{index+1}/{n_images}...")
                progress_bar.progress(index/n_images)
                if image_key.endswith('/'):
                    # skip folders
                    continue
                if image_key.lower().endswith('heic'):
                    png_image_key = f"{os.path.splitext(image_key)[0]}.png"
                    if not key_exists(png_image_key):
                        convert_heic_from_s3(
                                bucket=BUCKET,
                                key=image_key,
                                output_format="PNG",
                                save_to_s3=True,
                                output_bucket=BUCKET,
                                output_key=png_image_key
                            )
                    else:
                        print(f'file exists: {png_image_key}')
    
    st.markdown('---')

    jpeg_path = st.text_input('JPEG path', value=f'{IMAGES_FOLDER}', key='jpeg-path')
    # jpeg_quality = st.number_input('JPEG quality', value=95, key='jpeg-quality', step=1)
    st.write(f'Full path: {bucket_folder}{jpeg_path}')
    if st.button("Convert all HEIC to JPEG"):
        n_images = len(images)
        progress_bar = st.progress(0, 'Conversion')
        status_text = st.empty()
        with st.spinner(f'converting {n_images} images...'):
            for index, image_key in enumerate(images):
                status_text.text(f"{index+1}/{n_images}...")
                progress_bar.progress(index/n_images)
                if image_key.endswith('/'):
                    continue
                if image_key.lower().endswith('heic'):
                    filename = extract_filename_from_s3key(image_key)
                    jpeg_image_key = f"{bucket_folder}{jpeg_path}{filename}.jpeg"
                    if not key_exists(jpeg_image_key):
                        # print(f"saving to '{jpeg_image_key}'")
                        convert_heic_from_s3(
                                bucket=BUCKET,
                                key=image_key,
                                output_format="JPEG",
                                save_to_s3=True,
                                output_bucket=BUCKET,
                                output_key=jpeg_image_key,
                                # quality=jpeg_quality
                            )
                    else:
                        print(f'file exists: {jpeg_image_key}')
    st.markdown('---')
    if st.button("Generate thumbnails of all PNG"):
        n_images = len(images)
        progress_bar = st.progress(0, 'thumbnails')
        status_text = st.empty()
        with st.spinner(f'converting {n_images} images...'):
            for index, image_key in enumerate(images):
                status_text.text(f"{index+1}/{n_images}...")
                progress_bar.progress(index/n_images)
                if image_key.endswith('/'):
                    continue
                if image_key.lower().endswith('png'):
                    image_filename = extract_filename_from_s3key(image_key)
                    thumbnail_image_key = f"{bucket_folder}{THUMBNAIL_FOLDER}{image_filename}.png"
                    if not key_exists(thumbnail_image_key):
                        generate_thumbnail(
                            source_bucket=BUCKET,
                            source_key=image_key,
                            target_bucket=BUCKET,
                            target_key=thumbnail_image_key,
                            size=(300, 300)
                        )
                    else:
                        print(f'thumbnail exists: {thumbnail_image_key}')



if images:
    image_key = images[st.session_state.index]
    st.write(image_key)
    image_filename = image_key.split(f'{bucket_folder}{IMAGES_FOLDER}')[-1]
    
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
        with st.columns([4,1,5])[1]:
            input_index = st.number_input(f'of {len(images)}', min_value=1, 
                                        value=(st.session_state.index+1),
                                        label_visibility='hidden')
            if input_index:
                st.session_state.index = int(input_index)-1
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
