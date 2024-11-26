import os
import util
from dotenv import load_dotenv
from logger import ColorLogger
from constants import DIRECTORY_PATHS, PHOTOMICROGRAPH_PATHS, LEONARDO_VISION_XL

logger = ColorLogger(__name__)
dotenv_path = "../.env"
load_dotenv(dotenv_path=dotenv_path)

captioner_url = os.getenv("IMAGE_CAPTIONER_URL")

for path in DIRECTORY_PATHS:
    util.caption_images_in_directory(path, f"{captioner_url}/caption")
for path in PHOTOMICROGRAPH_PATHS:
    util.caption_images_in_directory(path, f"{captioner_url}/caption-photomicrograph")

logger.info("Captioning process for all paths complete!")

params = {}
params["modelId"] = LEONARDO_VISION_XL
params["photoReal"] = True
params["photoRealVersion"] = "v2"
params["init_strength"] = 0.6
for path in DIRECTORY_PATHS:
    util.generate_image_to_image(path, params)
for path in PHOTOMICROGRAPH_PATHS:
    util.generate_image_to_image(path, params)

logger.info("Generating AI counterparts complete!")
