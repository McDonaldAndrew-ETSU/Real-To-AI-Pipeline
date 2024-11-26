import util
from logger import ColorLogger
from analytics.images_captioned import IMAGES_CAPTIONED
from analytics.main_manifest import MAIN_MANIFEST

logger = ColorLogger(__name__)

path = "GranularImageCategories"
logger.info(
    f"The path '{path}' contains {(util.count_files_in_directory(path, True))} images"
)

ai_path = "AI"
logger.info(
    f"The path '{ai_path}' contains {(util.count_files_in_directory(ai_path, True))} images"
)


unmatched_keys = util.find_unmatched_files(path, set(MAIN_MANIFEST.keys()))
unmatched_values = util.find_unmatched_files(ai_path, set(MAIN_MANIFEST.values()))

if unmatched_keys:
    logger.info(
        f"Unmatched files in GranularImageCategories directory: {unmatched_keys}"
    )
else:
    logger.info(
        "All files in GranularImageCategories directory are accounted for in the MAIN_MANIFEST keys."
    )

if unmatched_values:
    logger.info(f"Unmatched files in AI directory: {unmatched_values}")
else:
    logger.info(
        "All files in AI directory are accounted for in the MAIN_MANIFEST values."
    )

util.log_text_duplicate_keys("./analytics/main_manifest.py")
util.log_text_duplicate_keys("./analytics/images_captioned.py")

util.log_text_duplicate_values("./analytics/main_manifest.py")
# No need to do duplicate values for MAIN_MANIFEST since some captions are the same for similar images.
# util.log_text_duplicate_values("./analytics/images_captioned.py")
