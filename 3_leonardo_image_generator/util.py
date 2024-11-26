import os
import re
import json
import time
import requests
from PIL import Image
from logger import ColorLogger
from dotenv import load_dotenv
from collections import Counter
from collections import defaultdict
from datetime import datetime, timedelta

logger = ColorLogger(__name__)
dotenv_path = ".env"
load_dotenv(dotenv_path=dotenv_path)

API_KEY = os.getenv("API_KEY")


def generate_image_to_image(directory_path: str, params: dict):
    from analytics.main_manifest import MAIN_MANIFEST
    from analytics.images_captioned import IMAGES_CAPTIONED

    for file_name in os.listdir(directory_path):
        img_path = unix_path(directory_path, file_name)

        if not MAIN_MANIFEST.get(img_path):
            api_key = API_KEY
            headers = {
                "accept": "application/json",
                "content-type": "application/json",
                "authorization": f"Bearer {api_key}",
            }

            # Get a presigined upload image url
            get_presigned_url = "https://cloud.leonardo.ai/api/rest/v1/init-image"

            logger.info(f"Get presigned upload image URL status code")
            # Returns fields, presigned URL, and image ID for use in the next step
            response = requests.post(
                url=get_presigned_url, json={"extension": "jpg"}, headers=headers
            )

            # Extract fields, presigned URL, and image ID
            fields = json.loads(response.json()["uploadInitImage"]["fields"])
            presigned_url = response.json()["uploadInitImage"]["url"]
            image_id = response.json()["uploadInitImage"]["id"]

            real_img_path = unix_path(directory_path, file_name)
            files = {"file": open(real_img_path, "rb")}
            logger.info(f"Uploading {real_img_path} to presigned URL")
            # Headers not needed when using presigned url to upload image. Adding authorization headers may cause authentication errors.
            response = requests.post(presigned_url, data=fields, files=files)

            # Generate with prompt (caption) and Image to Image
            generation_url = "https://cloud.leonardo.ai/api/rest/v1/generations"

            height, width = adjust_dimensions(
                height=Image.open(real_img_path).height,
                width=Image.open(real_img_path).width,
                model_id=params["modelId"],
            )

            api_body = {
                "alchemy": True,
                "height": height,
                "modelId": params["modelId"],
                "num_images": 1,
                "presetStyle": "CINEMATIC",
                "prompt": IMAGES_CAPTIONED.get(real_img_path),
                "width": width,
                "init_image_id": image_id,
            }

            logger.info(f"Sending Image to Image with prompt request")
            response = requests.post(generation_url, json=api_body, headers=headers)
            if response.status_code != 200:
                logger.debug(real_img_path)
                logger.debug(IMAGES_CAPTIONED.get(real_img_path))
                logger.debug(response.content)
                logger.warning("Must wait 30 seconds to attempt prompt again")
                time.sleep(30)
                response = requests.post(generation_url, json=api_body, headers=headers)
                logger.debug(response.content)

            # Get generation of Images from Leonardo.AI
            generation_id = response.json()["sdGenerationJob"]["generationId"]
            generation_id_url = f"{generation_url}/{generation_id}"

            # Poll the Leonardo.AI API until Image is generated
            logger.info("Getting generation of images url")
            # logger.debug(response.content)
            response = poll_generation_status(
                generation_id_url=generation_id_url, headers=headers
            )

            # logger.debug(response.content)

            # Once the url(s) are received, download to directories, and update manifests
            download_generated_images(
                response=response, real_img_path_key=real_img_path
            )
        else:
            logger.warning(f"{img_path} already has an AI generated counterpart!")


def poll_generation_status(
    generation_id_url: str, headers: dict, max_attempts: int = 7, interval: int = 10
) -> str:
    """Polls the generation status API every interval seconds until max_attempts is reached or the image is ready."""
    for attempt in range(max_attempts):
        logger.info(f"Polling attempt {attempt + 1}/{max_attempts}")
        response = requests.get(generation_id_url, headers=headers)

        if response.status_code == 200:
            generation_status = response.json()["generations_by_pk"]["status"]
            if generation_status == "COMPLETE":
                return response
            elif generation_status == "FAILED":
                logger.error("Image generation failed")
                return ""

        time.sleep(interval)

    logger.warning("Max polling attempts reached without completion")


def download_generated_images(response, real_img_path_key: str):
    from analytics.main_manifest import MAIN_MANIFEST

    main_download_path = os.path.join("AI", os.path.dirname(real_img_path_key))

    # Extract image URLs and download them
    for img_data in response.json()["generations_by_pk"]["generated_images"]:
        img_url = img_data["url"]
        img_name = img_url.split("/")[-1]

        main_img_path = unix_path(directory_path=main_download_path, file_name=img_name)

        try:
            new_save_path = get_unique_file_path(main_img_path)

            logger.debug("new_save_path created!")

            response = requests.get(img_url)

            os.makedirs(os.path.dirname(new_save_path), exist_ok=True)
            logger.debug(f"{new_save_path} is made")
            with open(new_save_path, "wb") as file:
                file.write(response.content)
            logger.info(f"Downloaded {img_name} to main path")
        except Exception as e:
            logger.debug("Path may be too long: executing windows_write")
            windows_write(new_save_path, response)

        update_dict(
            file_path="./analytics/main_manifest.py",
            key=real_img_path_key,
            value=new_save_path,
            dictionary=MAIN_MANIFEST,
        )


def caption_images_in_directory(directory_path, ai_img_captioner_url):
    from analytics.images_captioned import IMAGES_CAPTIONED

    # Iterate through each image in the directory
    directory_path = f"./{directory_path}"
    for file_name in os.listdir(directory_path):
        img_path = unix_path(directory_path, file_name)

        if not IMAGES_CAPTIONED.get(img_path):
            # Prepare image file for POST request
            with open(img_path, "rb") as image_file:
                files = {"image": image_file}
                try:
                    # Use %H:%M:%S if on a server
                    estimated_completion = (
                        datetime.now() + timedelta(minutes=3)
                    ).strftime("%I:%M:%S %p")
                    logger.info(f"Caption generating for {img_path}.")
                    logger.info(f"Estimated completion at {estimated_completion}")
                    # Make POST request to the captioning endpoint
                    response = requests.post(ai_img_captioner_url, files=files)
                    response.raise_for_status()

                    # Extract caption from JSON response
                    caption = response.json().get("caption", "")
                    update_dict(
                        file_path="./analytics/images_captioned.py",
                        key=img_path,
                        value=caption,
                        dictionary=IMAGES_CAPTIONED,
                    )
                    logger.info("Updated IMAGES_CAPTIONED dict")
                except requests.RequestException as e:
                    print(f"Error captioning {img_path}: {e}")
        else:
            logger.warning(f"{img_path} already captioned")


def adjust_dimensions(height, width, model_id):
    """
    With Leonardo alchemy enabled, 512x512 images are outputted as 896x896. If original dimensions increase, the scale multiplier goes up. For ex:

    - 512x768 images scale to 896x1344, a scale of 1.5*384 from 768.
    - 512x1080 (max on API calculator) images scale to 896x1792, a scale of 2.0*384 from 1080.
    """
    # Define bounds
    MIN_SIZE = 512
    # Leonardo Phoenix: Can use less than 512 since not a SDXL model
    if model_id == "6b645e3a-d64f-4341-a6d8-7a3690fbf042":
        MIN_SIZE = 32
    MAX_SIZE = 1536

    # Helper function to round to the nearest multiple of 8
    def round_to_nearest_multiple_of_8(value):
        return max(8, round(value / 8) * 8)

    # Adjust aspect ratio if width or height is out of bounds
    aspect_ratio = width / height

    # Scale up if height or width is less than MIN_SIZE
    if height < MIN_SIZE or width < MIN_SIZE:
        if height < width:
            height = MIN_SIZE
            width = round_to_nearest_multiple_of_8(height * aspect_ratio)
        else:
            width = MIN_SIZE
            height = round_to_nearest_multiple_of_8(width / aspect_ratio)

    # Scale down if height or width is more than MAX_SIZE
    if height > MAX_SIZE or width > MAX_SIZE:
        if height > width:
            height = MAX_SIZE
            width = round_to_nearest_multiple_of_8(height * aspect_ratio)
        else:
            width = MAX_SIZE
            height = round_to_nearest_multiple_of_8(width / aspect_ratio)

    # Ensure final dimensions are within bounds and are multiples of 8
    height = max(MIN_SIZE, min(MAX_SIZE, round_to_nearest_multiple_of_8(height)))
    width = max(MIN_SIZE, min(MAX_SIZE, round_to_nearest_multiple_of_8(width)))

    return height, width


def unix_path(directory_path: str, file_name: str) -> str:
    img_path = os.path.normpath(os.path.join(directory_path, file_name))
    unix_style_file_path = img_path.replace("\\", "/")
    img_path = unix_style_file_path

    return img_path


def get_unique_file_path(main_image_path):
    base, ext = os.path.splitext(main_image_path)

    match = re.search(r"_(\d+)$", base)
    if match:
        counter = int(match.group(1))
        base = base[: match.start()]
    else:
        counter = 0

    while True:
        new_save_path = f"{base}_{counter}{ext}"

        if os.name == "nt" and len(os.path.abspath(new_save_path)) > 256:
            new_save_path = f"\\\\?\\{os.path.abspath(new_save_path)}"

        if not os.path.exists(new_save_path):
            new_save_path = f"{base}_{counter}{ext}"
            break

        counter += 1

    return new_save_path


def windows_write(save_path, response):
    logger.warning(f"Failed to download so using windows_write function")
    try:
        if os.name != "nt":
            raise Exception("Not on Windows.")
        windows_save_path = f"\\\\?\\{os.path.abspath(save_path)}"
        logger.debug(windows_save_path)
        os.makedirs(os.path.dirname(windows_save_path), exist_ok=True)
        with open(windows_save_path, "wb") as file:
            file.write(response.content)
    except Exception as e:
        logger.critical(
            "Some other issue other than Windows path length is causing download to Fail"
        )
        logger.critical(e)
        exit(0)


def update_dict(file_path: str, key: str, value: str, dictionary: dict):
    """
    Appends the new entry to the dict.py file without rewriting the entire file.
    Ensures that the python dictionary format is maintained.

    :param file_path: The file path where the *_dict.py file resides.
    :param key: The key of the entry's key-value pair.
    :param value: The value of the entry's key-value pair.
    :param dictionary: A specific dict
    """
    try:
        if not os.path.exists(file_path):
            logger.error(f"{file_path} does not exist")
            return

        new_entry = f'\t"{key}": {json.dumps(value)},\n'
        with open(file_path, "rb+") as f:
            f.seek(0, os.SEEK_END)

            f.seek(-1, os.SEEK_END)
            pos = f.tell()

            while pos > 0:
                f.seek(pos)
                last_char = f.read(1)
                if last_char == b"}":
                    break
                pos -= 1
                f.seek(pos)

            f.seek(pos)
            f.write(bytes(new_entry, "utf-8"))
            f.write(b"}")

        dictionary[str(key)] = value
    except Exception as e:
        logger.error(e)


def rewrite_dict(
    file_path: str, key: str, value: list, dictionary: dict, dict_name: str
):
    """
    Adds or updates an entry in the specified dictionary file by rewriting the entire file.
    Ensures that only one entry for the key is present, avoiding duplicate keys.

    :param file_path: The file path of the *_dict.py file.
    :param key: The key of the entry's key-value pair to add or update.
    :param value: The value of the entry's key-value pair, can be a string or list.
    :param dictionary: The dictionary in memory (e.g., CRITERIA_SUCCESS_LIST or WATCHLIST).
    :param dict_name: The name of the dictionary in the file (e.g., "CRITERIA_SUCCESS_LIST").

    Note: This function rewrites the entire dictionary file. If the key exists, it updates
    the value in place; if not, it adds the new key-value pair. The dictionary format is preserved.
    """
    try:
        if not os.path.exists(file_path):
            logger.error(f"{file_path} does not exist")
            return

        if isinstance(value, list):
            value = str(value)  # Convert list to string format

        # Update the dictionary in memory
        dictionary[key] = value

        # Write the updated dictionary back to the file
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(dict_name)
            f.write(" = {\n")
            for key, value in dictionary.items():
                f.write(f'\t"{key}": {json.dumps(value, ensure_ascii=False)},\n')
            f.write("}\n")
    except Exception as e:
        logger.error(e)


def convert_tif_to_jpg(folder_path):
    # Loop through all files in the folder
    for filename in os.listdir(folder_path):
        if filename.endswith(".tif"):
            # Open the .tiff image
            tiff_image_path = os.path.join(folder_path, filename)
            with Image.open(tiff_image_path) as img:
                # Convert the image to RGB (necessary for JPG format)
                rgb_img = img.convert("RGB")

                # Create the new filename with .jpg extension
                jpg_image_path = os.path.join(
                    folder_path, f"{os.path.splitext(filename)[0]}.jpg"
                )

                # Save the image as .jpg
                rgb_img.save(jpg_image_path, "JPEG")

            print(f"Converted {filename} to .jpg")

    print("Conversion complete.")


def count_files_in_directory(directory_path, include_subdirectories=False):
    if not os.path.isdir("GranularImageCategories"):
        logger.error("GranularImageCategories does not exist")
        return

    file_count = 0

    # Use os.walk to optionally include subdirectories
    if include_subdirectories:
        for root, _, files in os.walk(directory_path):
            file_count += len(files)
    else:
        # Only count files in the specified directory, not subdirectories
        file_count = len(
            [
                f
                for f in os.listdir(directory_path)
                if os.path.isfile(os.path.join(directory_path, f))
            ]
        )

    return file_count


def write_dict(file_path: str, dictionary: dict, dict_name: str):
    """Rewrites dict if removing entries"""
    try:
        if not os.path.exists(file_path):
            logger.error(f"{file_path} does not exist")
            return

        # Write the updated dictionary back to the file
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(dict_name)
            f.write(" = {\n")
            for key, value in dictionary.items():
                f.write(f'\t"{key}": {json.dumps(value, ensure_ascii=False)},\n')
            f.write("}\n")
    except Exception as e:
        logger.error(e)


def find_unmatched_files(directory_path, keys_or_values):
    """Find files in the GranularImageCategories or AI directories not present in MAIN_MANIFEST keys or values"""
    unmatched_files = []

    for root, _, files in os.walk(directory_path):
        for file in files:
            # Construct the full file path
            full_path = unix_path(root, file)
            # Check if this file path is not in the manifest values
            if full_path not in keys_or_values:
                unmatched_files.append(full_path)

    return unmatched_files


def log_text_duplicate_keys(file_path):
    """Logs any duplicate key"""
    # Read the file as a string
    with open(file_path, "r") as f:
        content = f.read()

    # Extract keys using a regular expression
    keys = re.findall(r"\"(.*?)\":", content)

    # Find duplicate keys
    duplicates = [key for key, count in Counter(keys).items() if count > 1]

    if duplicates:
        logger.warning(f"Duplicate keys found in {file_path}: {duplicates}")
    else:
        logger.info(f"No duplicate keys found in {file_path}")


def log_text_duplicate_values(file_path):
    """Logs any duplicate values"""
    # Read the file as a string
    with open(file_path, "r") as f:
        content = f.read()

    # Extract values using a regular expression
    values = re.findall(r':\s*"(.*?)"', content)

    # Find duplicate values
    duplicates = [value for value, count in Counter(values).items() if count > 1]

    if duplicates:
        logger.warning(f"Duplicate values found in {file_path}: {duplicates}")
    else:
        logger.info(f"No duplicate values found in {file_path}")
