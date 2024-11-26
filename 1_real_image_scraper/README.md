## Choice of `webdriver`

- Edge is most memory efficient when compared to Chrome and Firefox

## Category image count

40 total categories.

- ### Milestone 1: 1,000 total real images / 4 main categories = 250 images
  - LandscapesEnvironments - 250 / 22 = ~ 12 images per category
  - PeopleActionsPortraits - 250 / 14 = ~ 18 images per category
  - PeopleWarTornScenery - 250 / 5 = 50 images per category
  - Photomicrographs - 250 / 6 = ~ 42 images per category

## Critera for Real Image search

- **Step** 1 : Download images from links - `image_scraper_curl.process_images() > util.download_images_to_local()`
- **Step** 2 : Use imagehash to ensure no duplicates of any image within dataset. - `util.download_image() > util.check_image_hash()`
- **Step** 3 : Download ALL images (passing or not passing), linking each to its metadata. - `util.download_image() > util.update_scraped_manifest()`
- **Step** 4 : Use Exif Tool to record image metadata (Creator, Camera, etc.) - `image_scraper_curl.process_images() > util.get_metadata`
- **Step** 5 : Record how many images were skipped in total. - `image_scraper_curl.process_images()`
- **Step** 6 : Verify Camera information (Model), if not any delete and skip the image. - `validator.validate() > _validate_camera()`
- **Step** 7 : Verify Photographer (Name) - `validator.validate() > _validate_creator()`
- **Step** 8 : Verify Image information on image origin and seeing if it exists. - `validator.validate() > __validate_image()`
- **Step** 9: Verify if Creator truly owns the image, if not, delete and skip the image. - `validator.validate() > __validate_image()`
- **Step** 10: For inconsitencies - If new authentic image does not contain THE SAME information:

  - **Step** 10.1: If the new authentic image CONTAINS THE SAME Camera model and Creator name:
    - Since the new authentic image contains the same Camera or Creator, this does not necessarily mean that the image is an imposter.
    - Therefore, replace the local image with the origin image. - `validator.validate() > __validate_image()`
  - **Step** 10.2: If the new authentic image DOES NOT contain THE SAME Camera model and Creator name:
    - Since the new authentic image does not contain the same Camera or Creator, this gives evidence towards it not being taken from a Camera or that the Creator is the owner.
    - Therefore, DELETE BOTH the origin image and local image and proceed to the next image. - `validator.validate() > __validate_image()`
    - **Step** 10.2.1: If the new authentic image DOES NOT contain THE SAME Camera model and Creator name:
      - Put Creator on a "watchlist". This means instead of excluding every photo from a photographer, it helps hold them responsible for specific images. - `validator.validate() > util.put_creator_on_watch_or_success_list()`

- **Step** 11: Put Creator on "Criteria Success List" that passes all criteria. Key = Creator, Value = List of URLS. - `validator.validate() > util.put_creator_on_watch_or_success_list()`
- **Step** 12: Record metadata, and link url to it (1 for passing images, 1 for not). - `validator.validate() > util.record_metadata_for_local_image()`
- **Step** 13: Record how many images passed all criteria. - `image_scraper_curl.process_images()`
- **Step** 14: Do steps 1-13 until each image category meets its threshold of images. - `image_scraper_curl.process_images()`
