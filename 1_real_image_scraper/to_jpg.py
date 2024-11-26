from PIL import Image
import os
from logger import ColorLogger


logger = ColorLogger("image_scraper_curl.py")

# Folder path where the .tiff images are stored
folder_paths = [
    "GranularImageCategories/Photomicrographs/Bacteria",
    "GranularImageCategories/Photomicrographs/Cells/CancerCells",
    "GranularImageCategories/Photomicrographs/Cells/HealthyCells",
    "GranularImageCategories/Photomicrographs/Fungi",
    "GranularImageCategories/Photomicrographs/Parasites",
    "GranularImageCategories/Photomicrographs/Viruses",
]

# Loop through all files in the folder
for p in folder_paths:
    for filename in os.listdir(p):
        if filename.lower().endswith((".tif", ".tiff", ".dib", ".png")):
            # Open the .tiff image
            tiff_image_path = os.path.join(p, filename)
            img = Image.open(tiff_image_path)

            # Convert the image to RGB (necessary for JPG format)
            rgb_img = img.convert("RGB")

            # Create the new filename with .jpg extension
            jpg_image_path = os.path.join(p, f"{os.path.splitext(filename)[0]}.jpg")

            # Save the image as .jpg
            rgb_img.save(jpg_image_path, "JPEG")

            # Close the image file
            img.close()

            logger.info(f"Converted {filename} to .jpg")

            # Remove the original .tiff file
            os.remove(tiff_image_path)
            logger.info(f"Deleted original {filename}")

    logger.info("Conversion and cleanup complete.")
