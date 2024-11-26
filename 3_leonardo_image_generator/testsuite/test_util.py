import os
import json
import time
import requests
from PIL import Image
from dotenv import load_dotenv
from logger import ColorLogger


logger = ColorLogger(__name__)
dotenv_path = "../.env"
load_dotenv(dotenv_path=dotenv_path)

API_KEY = os.getenv("API_KEY")


def generate_image_to_image(directory_path: str, params: dict):
    from analytics.images_captioned import IMAGES_CAPTIONED

    api_key = API_KEY
    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "authorization": f"Bearer {api_key}",
    }

    get_presigned_url = "https://cloud.leonardo.ai/api/rest/v1/init-image"

    logger.info(f"Get presigned upload image URL status code")
    response = requests.post(
        url=get_presigned_url, json={"extension": "jpg"}, headers=headers
    )

    fields = json.loads(response.json()["uploadInitImage"]["fields"])
    presigned_url = response.json()["uploadInitImage"]["url"]
    image_id = response.json()["uploadInitImage"]["id"]

    real_img_path = directory_path
    files = {"file": open(real_img_path, "rb")}
    logger.info(f"Uploading {real_img_path} to presigned URL")

    response = requests.post(presigned_url, data=fields, files=files)

    generation_url = "https://cloud.leonardo.ai/api/rest/v1/generations"

    height, width = adjust_dimensions(
        Image.open(real_img_path).height,
        Image.open(real_img_path).width,
        params["modelId"],
    )
    cleaned_text = IMAGES_CAPTIONED.get(
        directory_path.removeprefix("test_api/")
    ).replace("\n", "")

    api_body = {
        "alchemy": True,
        "height": height,
        "modelId": params["modelId"],
        "num_images": 1,
        "presetStyle": "CINEMATIC",
        "prompt": cleaned_text,
        "width": width,
        "init_image_id": image_id,
    }

    logger.info(f"Sending Image to Image with prompt request")
    response = requests.post(generation_url, json=api_body, headers=headers)
    if response.status_code != 200:
        logger.warning("Must wait 30 seconds to attempt prompt again")
        time.sleep(30)
        response = requests.post(generation_url, json=api_body, headers=headers)

    # Get generation of Images from Leonardo.AI
    logger.debug(response.json())
    generation_id = response.json()["sdGenerationJob"]["generationId"]
    generation_id_url = f"{generation_url}/{generation_id}"

    # Poll the Leonardo.AI API until Image is generated
    logger.info("Getting generation of images url")
    response = poll_generation_status(
        generation_id_url=generation_id_url, headers=headers
    )

    # Once the url(s) are received, download to directories, and update manifests
    download_generated_images(
        response=response,
        real_img_path_key=real_img_path,
        download_path=directory_path,
    )


def unix_path(directory_path: str, file_name: str) -> str:
    img_path = os.path.normpath(os.path.join(directory_path, file_name))
    unix_style_file_path = img_path.replace("\\", "/")
    img_path = unix_style_file_path

    return img_path


def adjust_dimensions(height, width, model_id):
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


def download_generated_images(response, real_img_path_key: str, download_path: str):
    main_download_path = os.path.join(os.path.dirname(download_path), "AI")
    os.makedirs(main_download_path, exist_ok=True)

    first_image_downloaded = False

    for img_data in response.json()["generations_by_pk"]["generated_images"]:
        img_url = img_data["url"]
        img_name = img_url.split("/")[-1]

        if "_o" in img_name and img_name.endswith("_o.jpg"):
            img_name = img_name.replace("_o", "")

        main_img_path = unix_path(directory_path=main_download_path, file_name=img_name)

        logger.debug(f"Attempting to save to: {main_img_path}")
        if not os.path.isdir(os.path.dirname(main_img_path)):
            logger.error(f"Directory does not exist: {os.path.dirname(main_img_path)}")
            continue

        try:
            base, ext = os.path.splitext(main_img_path)
            counter = 1
            new_save_path = main_img_path

            while os.path.exists(new_save_path):
                new_save_path = f"{base}_{counter}{ext}"
                counter += 1

            response = requests.get(img_url)

            if not first_image_downloaded:
                os.makedirs(os.path.dirname(new_save_path), exist_ok=True)
                logger.debug(f"{new_save_path} is made")
                with open(new_save_path, "wb") as file:
                    file.write(response.content)
                logger.info(f"Downloaded {img_name} to main path")
                first_image_downloaded = True
        except Exception as e:
            logger.error(
                f"Failed to download {img_name}: {e} - HTTP Response: {response.status_code}"
            )


def create_new_save_path(original_img_path: str):
    """
    This is used if you are generating images with different parameters of a model since single
    images will have the same name with different parameters.
    If generating multiple images with the same parameters, create_new_save_path() is unnecessary.
    """
    base, ext = os.path.splitext(original_img_path)
    counter = 1
    new_save_path = original_img_path

    while os.path.exists(new_save_path):
        new_save_path = f"{base}_{counter}{ext}"
        counter += 1

    return new_save_path
