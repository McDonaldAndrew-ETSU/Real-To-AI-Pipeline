import os
import re
import ast
import json
import requests
import imagehash
import subprocess
import numpy as np
import urllib.parse
from PIL import Image
from io import BytesIO
from logger import ColorLogger
from validator import Validator
from skimage.metrics import structural_similarity
from analytics.all_links_checked_dict import ALL_LINKS_CHECKED


logger = ColorLogger("util.py")


def get_start_index(data: str, use_flickr_api: bool):
    """ """
    if use_flickr_api:
        try:
            current_page = data.get("photos", {}).get("page", [{}])
            next_page = current_page + 1
            return next_page
        except Exception as e:
            logger.error(e)
            return None
    else:
        try:
            next_page_info = data.get("queries", {}).get("nextPage", [{}])[0]
            return next_page_info.get("startIndex", None)
        except Exception as e:
            logger.error(e)
            return None


def update_dict(file_path: str, key: str, value: str, dictionary: dict):
    """
    Appends the new entry to the *_dict.py file without rewriting the entire file.
    Ensures that the python dictionary format is maintained.

    :param file_path: The file path where the *_dict.py file resides.
    :param key: The key of the entry's key-value pair.
    :param value: The value of the entry's key-value pair.
    :param dictionary: A specific dict (e.g., AVERAGE_HASHES, DIFFERENCE_HASHES, etc.).
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


def reset_all_dicts():
    """
    WARNING: DO NOT USE UNLESS YOU KNOW WHAT YOU'RE DOING
    Clears all current dictionaries.
    """
    # Reset imagehash dicts
    clear_dict("./dicts/ahash_dict.py", "AVERAGE_HASHES")
    clear_dict("./dicts/dhash_dict.py", "DIFFERENCE_HASHES")
    clear_dict("./dicts/phash_dict.py", "PERCEPTUAL_HASHES")
    clear_dict("./dicts/whash_dict.py", "WAVELET_HASHES")

    # Reset Analytics
    clear_dict("./analytics/all_links_checked_dict.py", "ALL_LINKS_CHECKED")
    clear_dict("./analytics/watchlist.py", "WATCHLIST")
    clear_dict("./analytics/criteria_success_list.py", "CRITERIA_SUCCESS_LIST")
    clear_dict("./analytics/failed_dict.py", "FAILED")
    clear_dict("./analytics/passing_dict.py", "PASSING")
    clear_dict("./analytics/scraped_image_manifest.py", "SCRAPED_IMAGE_MANIFEST")


def clear_dict(file_path: str, dict_name: str):
    """
    WARNING: DO NOT USE UNLESS YOU KNOW WHAT YOU'RE DOING

    Rewrites any specified dictionary constant file to be an empty dict.
    e.g. `DICT = {"...":"...", "...":"...", ...}` -> `DICT = {}`

    :param file_path: The file path that the *_dict.py file resides.
    :param dictionary: The name of the dictionary variable in the file.
    """
    if not os.path.exists(file_path):
        logger.error(f"{file_path} does not exist")
        return

    try:
        with open(file_path, "w") as f:
            # Write the dictionary as an empty dict
            f.write(f"{dict_name} = {{}}\n")
        logger.info(f"{dict_name} has been cleared in {file_path}")
    except Exception as e:
        logger.error(f"Failed to clear {dict_name} in {file_path}: {e}")


def check_all_links(local_image_path: str, initial_image_link: str):
    """
    The `ALL_LINKS_CHECKED` dict has the local image path for the key, with the value being the initial image link.
    This function helps with keeping track of all current image urls to ensure duplicate image urls are not used.
    Updates the `ALL_LINKS_CHECKED` dict if the initial_image_link has not been used yet.

    :param local_image_path: The local image path key that is along the lines of ./GranularImageCategories/<category>/image.jpg
    :param initial_image_link: The found image link containing the image later used to find the image origin and IS NOT the origin link.
    :returns: True if the link already exists, i.e. a duplcate. False after updating the dict.
    """
    from analytics.all_links_checked_dict import ALL_LINKS_CHECKED

    if ALL_LINKS_CHECKED.get(local_image_path):
        logger.warning(f"Duplicate link detected: {initial_image_link}")
        return True
    else:
        update_dict(
            file_path="./analytics/all_links_checked_dict.py",
            key=local_image_path,
            value=f"{initial_image_link}",
            dictionary=ALL_LINKS_CHECKED,
        )
        return False


def download_images_to_local(
    data: str, download_path: str, use_flickr_api: bool, flickr_api_key: str
):
    """
    Downloads the associated images from a list of image link paths.
    It returns an array of unique image paths to the downloaded images ensuring no duplicates.

    :param response: The image urls.
    :param download_path: The directory where the images should be downloaded
    :returns: A list of downloaded image paths.
    """
    if use_flickr_api:
        photo_array = data.get("photos", {}).get("photo", [{}])
        for p in photo_array:
            url = ""
            try:
                id = p.get("id")
                secret = p.get("secret")
                user_id = p.get("owner")
                url_o = p.get("url_o")
                if url_o:
                    url = url_o
                else:
                    server_id = p.get("server")
                    url = f"https://live.staticflickr.com/{server_id}/{id}_{secret}.jpg"

                download_image(
                    url_link=url,
                    download_path=download_path,
                    flickr_tuple=(flickr_api_key, id, secret, user_id),
                )
            except Exception as e:
                logger.error(f"Could not download {url}: {e}")
    else:
        items = data.get("items", [])
        for item in items:
            try:
                link = item.get("link")
                download_image(url_link=link, download_path=download_path)
            except Exception as e:
                logger.error(e)


def download_image(
    url_link: str, download_path: str, flickr_tuple=None, is_temp_download: bool = False
):
    """
    Downloads an image from a url image link to a download path.

    :param url_link: The image url.
    :param download_path: The path to download the image to.
    """
    try:
        parsed_url = urllib.parse.urlparse(url_link)
        file_name = os.path.basename(parsed_url.path) or f"{url_link}.jpg"

        response = get_response(url=url_link)
        img = get_image(response=response)

        os.makedirs(download_path, exist_ok=True)
        # img_path = os.path.join(download_path, file_name)
        img_path = os.path.normpath(os.path.join(download_path, file_name))
        unix_style_file_path = img_path.replace("\\", "/")
        img_path = unix_style_file_path

        hashes_exist = False
        link_exists = False
        valid_image = True

        hashes_exist = check_image_hash(pil_image=img, url_link=url_link)
        link_exists = check_all_links(
            local_image_path=img_path, initial_image_link=url_link
        )
        if not is_temp_download and not hashes_exist and not link_exists:
            all_images_path = f"AllScrapedImages/{file_name}"
            os.makedirs(os.path.dirname(all_images_path), exist_ok=True)
            write_binary(destination=all_images_path, response=response)

            metadata = get_metadata(image_path=f"../{all_images_path}")
            update_scraped_manifest(
                image_path_key=all_images_path, original_metadata=metadata
            )

            url_link = ALL_LINKS_CHECKED[img_path]
            valid_image = validate_image(
                metadata, url_link, flickr_tuple, all_images_path
            )

        if not hashes_exist and not link_exists and valid_image:
            write_binary(destination=img_path, response=response)

        return img_path
    except Exception as e:
        logger.error(f"Failed to get {url_link} - {response.status_code} - {e}")
        return


def update_scraped_manifest(image_path_key: str, original_metadata: str):
    """
    For Analytics - Maps the metadata of the image to the local downloaded image path for "./AllScrapedImages/..."
    Updates the `SCRAPED_IMAGE_MANIFEST` dict.

    :param image_path_key: Intended for the local "./AllScrapedImages/..." image path
    :param metadata_value: The metadata for the associated image from image_path_key
    """
    from analytics.scraped_image_manifest import SCRAPED_IMAGE_MANIFEST

    original_metadata.pop("Directory", None)

    update_dict(
        file_path="./analytics/scraped_image_manifest.py",
        key=image_path_key,
        value=original_metadata,
        dictionary=SCRAPED_IMAGE_MANIFEST,
    )


def validate_image(
    metadata, url_link, flickr_tuple=None, all_images_path="", needs_camera=True
):
    try:
        validator = Validator(debug_mode=True, flickr_api_key=flickr_tuple[0])
        if flickr_tuple:
            validator.current_flickr_image_id = flickr_tuple[1]
            validator.current_flickr_image_secret = flickr_tuple[2]
            validator.current_flickr_image_user_id = flickr_tuple[3]

            if validator.validate_flickr(metadata=metadata, image_path=all_images_path):
                return True
            else:
                return False
        else:
            if validator.validate(
                metadata=metadata, image_url=url_link, image_path=all_images_path
            ):
                return True
            else:
                return False
    except Exception as e:
        logger.error(e)
        return False


def write_binary(destination: str, response: requests.Response):
    """
    Writes the image in binary to a destination path using the response keeping metadata intact.

    :param destination: The destination path to write the image.
    :param response: An image url response to grab the image from.
    """
    with open(destination, "wb") as out_file:
        out_file.write(response.content)
    logger.debug(f"Image saved to {destination}")


def get_response(url: str) -> requests.Response:
    """
    Returns the response from a given url that uses spoof headers.

    :param url: The url link to make a get request to.
    :returns: The response from the request.
    """
    response = None
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36"
        }
        response = requests.get(url=url, headers=headers, stream=True)
    except Exception as e:
        logger.error(f"Could not get response: {e}")

    return response


def get_image(response: requests.Response) -> Image:
    """
    Returns a PIL Image from the response of a get request.

    :param response: The response containing the content of an image.
    :returns: The PIL Image from the link
    """
    try:
        return Image.open(BytesIO(response.content))
    except Exception as e:
        logger.error(f"Could not get image from response: {e}")
        return None


def check_image_hash(pil_image: Image, url_link: str) -> bool:
    """
    Checks a given image's hash against all images in the RealWithAI directory and all of its subdirectories to ensure no duplicates exist.

    :param pil_image: The PIL Image object of the downloaded image
    :param url_link: The link of the original image. Useful to see what links were duplicates.
    :returns: True if the image is unique, False if a duplicate is found.
    """
    from dicts.ahash_dict import AVERAGE_HASHES
    from dicts.whash_dict import WAVELET_HASHES
    from dicts.dhash_dict import DIFFERENCE_HASHES
    from dicts.phash_dict import PERCEPTUAL_HASHES

    ahash = imagehash.average_hash(pil_image)
    dhash = imagehash.dhash(pil_image)
    phash = imagehash.phash(pil_image)
    whash = imagehash.whash(pil_image)
    if (
        AVERAGE_HASHES.get(str(ahash))
        or DIFFERENCE_HASHES.get(str(dhash))
        or PERCEPTUAL_HASHES.get(str(phash))
        or WAVELET_HASHES.get(str(whash))
    ):
        logger.warning(f"Duplicate image detected: {url_link}")
        return True
    else:
        update_dict(
            file_path="./dicts/ahash_dict.py",
            key=ahash,
            value=1,
            dictionary=AVERAGE_HASHES,
        )
        update_dict(
            file_path="./dicts/dhash_dict.py",
            key=dhash,
            value=1,
            dictionary=DIFFERENCE_HASHES,
        )
        update_dict(
            file_path="./dicts/phash_dict.py",
            key=phash,
            value=1,
            dictionary=PERCEPTUAL_HASHES,
        )
        update_dict(
            file_path="./dicts/whash_dict.py",
            key=whash,
            value=1,
            dictionary=WAVELET_HASHES,
        )
        return False


def get_metadata(image_path: str) -> dict:
    """
    Uses Exif Tool by Phil Harvey to examine a downloaded image.
    The embedded metadata is recorded for Criteria Checking (see README.md)

    :param image_path: The string path of a downloaded image to examine with the EXIF Tool.
    :returns: The metadata as a dict.
    """
    try:
        result = subprocess.run(
            ["perl", "./exiftool", image_path],
            capture_output=True,
            text=True,
            cwd="./Image-ExifTool-12.96",
        )
        if result.returncode == 0 and result.stdout:
            metadata = {}
            for line in result.stdout.splitlines():
                key, _, value = line.partition(":")
                metadata[key.strip()] = value.strip()

            logger.debug("Metadata recorded")

            return metadata
        else:
            logger.warning(f"ExifTool error - {result.stderr}")
            return {}
    except Exception as e:
        logger.error(f"ExifTool error - {e}")
        return {}


def get_camera_from_metadata(metadata: dict) -> tuple[str, str, str]:
    """
    Gets the camera model from an image's metadata.

    :param metadata: The image metadata
    :returns: If available, a tuple containing the key and value for the camera model, and the camera lens.
    """
    from constants import LENS_KEYS, MODEL_KEYS

    key = None
    lens = None
    model = None

    for m in MODEL_KEYS:
        value = metadata.get(f"{m}")

        if m == "Creator Tool" and value:
            key = m
            regex = r"(?:Digital Camera\s*)?([\w\s-]+?)(?=\sVer|\sFirmware|$)"
            match = re.search(regex, value)
            model = match.group(1).strip() if match else None
            logger.debug(f"{key}: {model}")
            break

        if value:
            key = m
            model = value
            logger.debug(f"{key}: {model}")
            break

    for l in LENS_KEYS:
        value = metadata.get(f"{l}")

        if value and not model and l == "Lens Profile Filename":
            key = l
            match = re.match(r"(.+?) \((.+?)\)", value)
            model = match.group(1).strip() if match else None
            lens = match.group(2).strip() if match else None
            logger.debug(f"pulled model: {model}, pulled lens: {lens}")
            break

        if value:
            key = l
            lens = value
            logger.debug(f"{key}: {lens}")
            break

    if not model and not lens:
        logger.warning("No Model and Lens keys available in metadata")
        return None, None, None

    logger.debug(f"({key}, {model}, {lens})")
    return (key, model, lens)


def get_creator_from_metadata(metadata: dict) -> str:
    """
    Gets the creator's name from an image's metadata

    :param metadata: The image metadata
    :returns: The creator's name if available or None if not found
    """
    from constants import CREATOR_KEYS

    key = None
    creator = None

    for c in CREATOR_KEYS:
        value = metadata.get(f"{c}")

        if value:
            key = c
            creator = value
            logger.debug(f"{key}: {creator}")
            break

    if not creator:
        logger.warning("No Creator keys available in metadata")
        return None, None

    return key, creator


def get_camera_from_flickr_image(
    flickr_api_key: str,
    flickr_photo_id: str,
    flickr_photo_secret: str,
) -> str:
    """
    Validates that a camera shows in a Flickr image's metadata.
    Returns the camera from the EXIF data of the flickr image's ID using the flickr.photos.getExif method.
    """
    try:
        method_url = "https://api.flickr.com/services/rest/"
        exif_params = {
            "method": "flickr.photos.getExif",
            "api_key": flickr_api_key,
            "photo_id": flickr_photo_id,
            "secret": flickr_photo_secret,
            "format": "json",
            "nojsoncallback": 1,
        }
        response = requests.get(method_url, params=exif_params)
        data = response.json()
        camera = data.get("photo", {}).get("camera", "")
        if camera:
            logger.info("Camera found on flickr image.")
            return camera
        else:
            logger.warning("No camera available from flickr image")
            return None
    except Exception as e:
        logger.warning(f"Camera attribute is not in data: {e}")
        return False


def get_flickr_creator_url(flickr_api_key: str, flickr_user_id: str) -> str:
    """
    Returns flickr user url to find eventually find creator and then validate camera, image, and creator.
    Uses flickr.urls.getUserPhotos.
    """
    try:
        method_url = "https://api.flickr.com/services/rest/"
        user_site_params = {
            "method": "flickr.urls.getUserPhotos",
            "api_key": flickr_api_key,
            "user_id": flickr_user_id,
            "format": "json",
            "nojsoncallback": 1,
        }
        response = requests.get(method_url, params=user_site_params)
        data = response.json()
        origin_url = data.get("user", {}).get("url", "")
        if origin_url:
            logger.info("The Flickr Creator URL was found!")
            return origin_url
        else:
            logger.error("The Flickr Creator URL could not be found.")
            return False
    except Exception as e:
        logger.error(e)
        return False


def format_url(url: str) -> str:
    """Ensure the URL starts with 'https:' if it only has '//'"""
    return f"https:{url}" if url.startswith("//") else url


# CHANGE is_image_similar to make sure local image is resized to the comparison image rather than making both images resized as whichever one has the smallest dimensions
def is_image_similar(local_image_path: str, compare_url: str, threshold: float = 0.90):
    """
    Compares a locally downloaded image with an image from a URL using structural similarity scoring.

    SSIM scoring:
    - Below 85%: Images are likely visually different. Differences could be noticeable in structure, color, or detail, suggesting they are not the same image.
    - 85% - 95%: This range often indicates minor differences, such as slight edits, cropping, compression, or color adjustments. They may look similar but might not be exact copies.
    - 95% - 100%: This range generally indicates that the images are visually identical, with any differences likely being due to minor artifacts or compression rather than structural or perceptual changes.

    :param local_image: The locally downloaded image.
    :param compare_url: The image source url containing image to compare to local_image.
    :param threshold: A float designating the percentage the similarity score should meet.
    :returns: True if similarity is over the threshold, otherwise False.
    """
    try:
        compare_url = format_url(compare_url)
        response = get_response(url=compare_url)

        local_image = Image.open(local_image_path).convert("RGB")
        compare_image = Image.open(BytesIO(response.content)).convert("RGB")

        target_size = min(local_image.size, compare_image.size)
        resized_image = local_image.convert("RGB").resize(target_size)
        resized_compare_image = compare_image.convert("RGB").resize(target_size)

        min_dim = min(target_size)
        win_size = min(15, min_dim if min_dim % 2 == 1 else min_dim - 1)

        similarity_score = structural_similarity(
            np.array(resized_image),
            np.array(resized_compare_image),
            channel_axis=-1,
            win_size=win_size,
        )

        logger.debug(f"SSIM Score: {similarity_score}")

        return similarity_score >= threshold
    except Exception as e:
        logger.debug(f"Error finding similarity: {e}")
        return False


def put_creator_on_watch_or_success_list(
    origin_link: str,
    creator: str,
    is_successful: bool,
    watchlist_reasoning: str = "",
):
    """
    The `WATCHLIST` dict has the key as the creator, and the value as the list of origin image links that `failed` the criteria.
    The `CRITERIA_SUCCESS_LIST` dict has the key as the creator, and the value as the list of origin image links that `passed` the criteria.
    Dynamically updates either dict depending on is_successful param.

    :param origin_link: The image origin link that will be appended to either the `WATCHLIST` or `CRITERIA_SUCCESS_LIST`
    :param creator: The Creator responsible for the image origin link.
    :param is_successful: If False, will update the `WATCHLIST`. If True, will update the `CRITERIA_SUCCESS_LIST`
    """
    from analytics.watchlist import WATCHLIST
    from analytics.criteria_success_list import CRITERIA_SUCCESS_LIST

    try:
        watchlist_urls = WATCHLIST.get(creator)
        success_list_urls = CRITERIA_SUCCESS_LIST.get(creator)

        chosen_path = ""
        chosen_value = []
        chosen_dict = {}
        dict_name = ""
        if is_successful:
            chosen_path = "./analytics/criteria_success_list.py"
            logger.info(f"Putting '{creator}' on Success List!")
            if success_list_urls:
                success_list_urls = ast.literal_eval(success_list_urls)
                success_list_urls.append(origin_link)
                chosen_value = success_list_urls
            else:
                chosen_value = [origin_link]
            chosen_dict = CRITERIA_SUCCESS_LIST
            dict_name = "CRITERIA_SUCCESS_LIST"
        else:
            logger.info(f"Putting '{creator}' on WATCHLIST!")
            chosen_path = "./analytics/watchlist.py"
            if watchlist_urls:
                watchlist_urls = ast.literal_eval(watchlist_urls)
                watchlist_urls.append(f"{origin_link} - {watchlist_reasoning}")
                chosen_value = watchlist_urls
            else:
                chosen_value = [f"{origin_link} - {watchlist_reasoning}"]
            chosen_dict = WATCHLIST
            dict_name = "WATCHLIST"

        rewrite_dict(
            file_path=chosen_path,
            key=creator,
            value=chosen_value,
            dictionary=chosen_dict,
            dict_name=dict_name,
        )
    except Exception as e:
        logger.error(e)


def record_metadata_for_local_image(
    local_image_path: str, origin_link: str, metadata: dict, is_passing: bool
):
    """
    The `FAILED` dict has the key as the "./AllScrapedImages/local image path" and the value as its metadata with the origin link appended to it.
    The `PASSING` dict has the key as the "local image path" and the value as its metadata with the origin link appended to it.
    Similar to `update_scraped_manifest`, however, it includes the origin link within the metadata as well as organizing the entries into their associated separate dicts.
    If is_passing, the key refers to the /GranularImageCategories directory. If not, it refers to the ./AllScrapedImages directory.

    :param local_image_path: The local image path to be used for the key of the entry.
    :param origin_link: Tee origin url link of the image.
    :param metadata: The metadata to be used for the value of the entry.
    :param is_passing: If True, updates the `PASSING` dict. Otherwise updates the `FAILED` dict.
    """
    from analytics.failed_dict import FAILED
    from analytics.passing_dict import PASSING

    try:
        chosen_path = ""
        new_metadata = metadata["origin_link"] = origin_link
        chosen_dict = {}
        if is_passing:
            chosen_path = "./analytics/passing_dict.py"
            chosen_dict = PASSING
        else:
            chosen_path = "./analytics/failed_dict.py"
            chosen_dict = FAILED

        update_dict(
            file_path=chosen_path,
            key=local_image_path,
            value=new_metadata,
            dictionary=chosen_dict,
        )
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


def handle_moved_images(granular_path: str):
    from analytics.all_links_checked_dict import ALL_LINKS_CHECKED

    try:
        for root, dirs, files in os.walk(granular_path):
            for file in files:
                new_granular_filepath = os.path.normpath(os.path.join(root, file))
                new_granular_filepath = new_granular_filepath.replace("\\", "/")

                rewrite_keys(
                    new_granular_filepath,
                    file,
                    ALL_LINKS_CHECKED,
                    "./analytics/all_links_checked_dict.py",
                    "ALL_LINKS_CHECKED",
                )

        logger.info("Updated ALL_LINKS_CHECKED!")
    except Exception as e:
        logger.error(e)


def rewrite_keys(new_filepath, file, dict, dict_filepath, dict_name):
    try:
        if new_filepath not in dict:
            old_scraped_filepath = None
            for old_key, value in dict.items():
                if file in old_key.split("/")[-1]:
                    old_scraped_filepath = old_key
                    break

            if old_scraped_filepath:
                val = dict.pop(old_scraped_filepath)
                dict[new_filepath] = val

                rewrite_dict(
                    file_path=dict_filepath,
                    key=new_filepath,
                    value=val,
                    dictionary=dict,
                    dict_name=dict_name,
                )
                logger.info(f"\nUpdated:\n{old_scraped_filepath} ->\n{new_filepath}")

    except Exception as e:
        logger.error(f"rewrite() Error: {e}")


def handle_removed_images(granular_path: str):
    from analytics.all_links_checked_dict import ALL_LINKS_CHECKED

    try:
        found_keys = set()
        for root, dirs, files in os.walk(granular_path):
            for file in files:
                new_granular_filepath = os.path.normpath(os.path.join(root, file))
                new_granular_filepath = new_granular_filepath.replace("\\", "/")

                found_keys.add(new_granular_filepath)
        for key in list(ALL_LINKS_CHECKED.keys()):
            if key not in found_keys:
                value = ALL_LINKS_CHECKED[key]
                if value.startswith("(Removed or Did Not Pass)"):
                    continue
                value = "(Removed or Did Not Pass)" + value
                ALL_LINKS_CHECKED[key] = value
                rewrite_dict(
                    file_path="./analytics/all_links_checked_dict.py",
                    key=key,
                    value=value,
                    dictionary=ALL_LINKS_CHECKED,
                    dict_name="ALL_LINKS_CHECKED",
                )
                logger.info(f"Removed {key}")
        logger.info("Updated ALL_LINKS_CHECKED!")
    except Exception as e:
        logger.error(e)


def log_deepest_subdirectories_file_count(root_dir):
    # Dictionary to hold the file count for the deepest subdirectories
    subdir_file_count = {}

    # Traverse the directory tree
    for dirpath, dirnames, filenames in os.walk(root_dir):
        # If there are no more subdirectories, it's the deepest level
        if not dirnames:
            # Count the files in the deepest subdirectory
            file_count = len(filenames)
            subdir_file_count[dirpath] = file_count

    # Log the file count for each deepest subdirectory
    for subdir, count in subdir_file_count.items():
        logger.info(f"Directory: {subdir}, File Count: {count}")

    # Calculate and log the total file count across all deepest subdirectories
    total_file_count = sum(subdir_file_count.values())
    logger.info(f"Total File Count: {total_file_count}")
