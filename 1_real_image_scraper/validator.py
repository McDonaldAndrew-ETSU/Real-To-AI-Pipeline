import os
import re
import util
import tempfile
from PIL import Image
from bs4 import BeautifulSoup
from datetime import datetime
from logger import ColorLogger
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support.expected_conditions import element_to_be_clickable


DATE_PATTERN = re.compile(r"\b\w{3} \d{1,2}, 20\d{2}\b")


logger = ColorLogger("validator.py")


class Validator:
    def __init__(self, debug_mode: bool, flickr_api_key: str):
        self.opt = webdriver.EdgeOptions()
        if not debug_mode:
            self.opt.add_argument("--headless=new")
            self.opt.add_experimental_option(
                "prefs", {"profile.managed_default_content_settings.javascript": 2}
            )
        self.driver = webdriver.Edge(options=self.opt)

        self.flickr_api_key = flickr_api_key
        self.current_flickr_image_id = ""
        self.current_flickr_image_secret = ""
        self.current_flickr_image_user_id = ""

    def validate_flickr(
        self,
        metadata: dict,
        image_path: str,
    ) -> bool:
        """"""
        try:
            flickr_creator_url = util.get_flickr_creator_url(
                flickr_api_key=self.flickr_api_key,
                flickr_user_id=self.current_flickr_image_user_id,
            )
            if not flickr_creator_url:
                return False
            image_origin_url = f"{flickr_creator_url}{self.current_flickr_image_id}"

            creator = self.__get_and_validate_creator_on_flickr_page(
                flickr_page=flickr_creator_url
            )
            if not creator:
                return False

            camera = util.get_camera_from_flickr_image(
                flickr_api_key=self.flickr_api_key,
                flickr_photo_id=self.current_flickr_image_id,
                flickr_photo_secret=self.current_flickr_image_secret,
            )
            if not camera:
                self.update_analytics(
                    origin=image_origin_url,
                    creator=creator,
                    is_successful=False,
                    image_path=image_path,
                    metadata=metadata,
                    watchlist_reasoning="Reason: No camera listed within image metadata.",
                )
                return False

            if not self.__validate_camera_flickr(
                image_origin_url=image_origin_url, camera=camera
            ):
                self.update_analytics(
                    origin=image_origin_url,
                    creator=creator,
                    is_successful=False,
                    image_path=image_path,
                    metadata=metadata,
                    watchlist_reasoning="Reason: Camera could not be validated on flickr page.",
                )
                return False

            if not self.__validate_image_flickr(
                origin_url=image_origin_url, local_image_path=image_path
            ):
                self.update_analytics(
                    origin=image_origin_url,
                    creator=creator,
                    is_successful=False,
                    image_path=image_path,
                    metadata=metadata,
                    watchlist_reasoning="Reason: Image downloaded is not visually the same image on Creator page based on SSIM scoring.",
                )
                return False

            self.update_analytics(
                origin=image_origin_url,
                creator=creator,
                is_successful=True,
                image_path=image_path,
                metadata=metadata,
            )

            return True
        except Exception as e:
            logger.error(e)

    def validate(self, metadata: dict, image_url: str, image_path: str) -> bool:
        """
        Uses Selenium web drivers to validate an image's metadata, specifically regarding the origin of an image,
        if the image was taken on a camera, and if it was truly taken by a photographer.
        - A camera model, creator, and origin are required within the metadate to follow the following criteria. If not available, return _False_.
        - The creator and the image must be contained on the image origin's page. Otherwise, return _False_.
        - The image's metadata must also match the origin's metadata, or at least contain the creator and the camera. Otherwise, return _False_
            - If _False_ that means it is classified as an imposter image and is not used.
        - If criteria passes, the image is recorded and the Creator is put on the `CRITERIA_SUCCESS_LIST` along with their list of passing image origin urls.
            - The local path of the image is recorded and its metadata (with image origin link) is put on the `PASSING_METADATA` dict.
        - If criteria fails, the image is recorded and the Creator is put on the `WATCHLIST` along with their list of failed image origin urls.
            - The local path of the image (within './AllScrapedImages/' since it will not be used for training) is recorded and its metadata (with image origin link) is put on the `METADATA` dict.

        :param metadata: The metadata of the image.
        :param image_url: The initial url of the image.
        :param image_path: The local image path.
        :returns: True if all criteria passes. Otherwise False
        """
        camera_key, model, lens = util.get_camera_from_metadata(metadata=metadata)
        if not model:
            return False

        self.driver = webdriver.Edge(options=self.opt)
        if not self.__validate_camera(camera_model=model):
            return False

        creator_key, creator = util.get_creator_from_metadata(metadata=metadata)
        if not creator:
            return False

        origin = self.__get_image_origin_url(image_url=image_url)
        if not origin:
            return False

        if not self.__validate_creator_selenium(origin_url=origin, creator=creator):
            if not self.__validate_string_bs4(image_origin_url=origin, s=creator):
                return False

        success = True
        if not self.__validate_image(
            origin_url=origin,
            local_image_path=image_path,
            local_metadata=metadata,
            camera_key=camera_key,
            creator_key=creator_key,
        ):
            success = False

        if success:
            logger.debug("Criteria was successful")

        util.put_creator_on_watch_or_success_list(
            origin_link=origin, creator=creator, is_successful=success
        )

        util.record_metadata_for_local_image(
            local_image_path=image_path,
            origin_link=origin,
            metadata=metadata,
            is_passing=success,
        )

        self.driver.close()
        return success

    def __get_image_origin_url(self, image_url: str) -> str:
        """
        Uses Google Reverse Image search to find the origin url of an image.

        :param image_url: The image's url to find the url of where it originated from.
        :returns: A url string to the origin of the image or False if no origin can be found.
        """
        try:
            self.driver.get("https://www.google.com/")
            google_lens = self.__wait(By.XPATH, "//*[@aria-label='Search by image']")
            google_lens.click()

            paste_image_link = self.__wait(
                By.XPATH, "//*[@placeholder='Paste image link']"
            )
            paste_image_link.send_keys(f"{image_url}")

            search = self.__wait(By.XPATH, "//*[text()='Search']")
            search.click()

            find_image_source = self.__wait(By.XPATH, "//*[text()='Find image source']")
            find_image_source.click()

            origin = self.__find_oldest_date_link()

            return origin
        except Exception as e:
            logger.error(f"Error getting origin: {e}")
            return False

    def __validate_camera(self, camera_model: str) -> bool:
        """
        Validates if camera exists on Google.

        :param camera_tuple: The Camera Model.
        :returns: True if camera exists or False if it does not.
        """
        try:
            self.driver.get("https://www.google.com/")
            search = self.__wait(By.ID, "APjFqb")
            search.send_keys(f"{camera_model}")
            search.send_keys(Keys.ENTER)

            rhs_title = self.__wait(
                By.XPATH, f"//*[@aria-level='2'][@data-attrid='title'][@role='heading']"
            )
            squished_rhs_title = re.sub(r"\s+", "", rhs_title.text.lower())
            squished_camera_model = re.sub(r"\s+", "", camera_model.lower())
            logger.debug(f"{squished_rhs_title}, {squished_camera_model}")
            if squished_camera_model not in squished_rhs_title:
                logger.warning(
                    f"'{camera_model}' is not remniscient of a camera on Google."
                )
                return False

            logger.info(f"'{camera_model}' is validated on Google!")
            return True
        except Exception as e:
            logger.warning(f"Could not validate '{camera_model}' on Google.")
            return False

    def __validate_creator_selenium(self, origin_url: str, creator: str) -> bool:
        """
        Valdates if the creator exists on the proposed image's origin page.

        :param origin_link: The url of the image's origin.
        :param creator: The name of the creator.
        :returns: True if creator, image, and if the images metadata matches. Otherwise False.
        """
        try:
            self.driver.get(origin_url)
            titled = creator.title()
            upper = creator.upper()
            possible_elements = self.driver.find_elements(
                By.XPATH,
                f"//*[contains(text(), '{creator}') or contains(text(), '{titled}') or contains(text(), '{upper}')]",
            )

            squished_creator = re.sub(r"\s+", "", creator.lower())
            for element in possible_elements:
                squished_element_text = re.sub(r"\s+", "", element.text.lower())
                if squished_creator in squished_element_text:
                    logger.info(f"Creator '{creator}' found on page.")
                    return True

            logger.warning(f"Creator '{creator}' not found on the page.")
            return False
        except Exception as e:
            logger.error(e)
            return False

    def __validate_camera_flickr(self, image_origin_url: str, camera: str) -> bool:
        """
        Goes to image origin (The Flickr creator's page).
        Finds and returns the posted link to the camera that leads to the Flickr camera database.
        This validates that the camera listed in the image's metadata is the same one on the page.
        """
        try:
            self.driver.get(image_origin_url)
            camera_anchor = self.__wait(By.XPATH, f".//a[contains(text(), '{camera}')]")
            href = camera_anchor.get_attribute("href")
            if href:
                logger.info("Camera is Validated on Flickr and in image Metadata!")
                return True
            else:
                logger.warning("Camera could not be validated on flickr page")
                return False
        except Exception as e:
            logger.error("Camera could not be validated on flickr page")
            return False

    def __validate_string_bs4(self, image_origin_url: str, s: str) -> bool:
        try:
            # Load the page
            self.driver.get(image_origin_url)
            html = self.driver.page_source
            logger.info(html)
            soup = BeautifulSoup(html, "html.parser")

            # Prepare variations of the creator's name
            titled = s.title()
            upper = s.upper()
            squished_creator = re.sub(r"\s+", "", s.lower())

            # Find all tags containing the creator's name in any form
            possible_elements = soup.find_all(
                lambda tag: tag.string
                and (
                    (s in tag.string) or (titled in tag.string) or (upper in tag.string)
                )
            )

            for element in possible_elements:
                squished_element_text = re.sub(r"\s+", "", element.get_text().lower())
                if squished_creator in squished_element_text:
                    logger.info(f"String '{s}' found on page!")
                    return True

            logger.warning(f"String '{s}' not found on the page.")
            return False
        except Exception as e:
            logger.error(e)
            return False

    def __validate_image_flickr(self, origin_url: str, local_image_path: str):
        try:
            self.driver.get(origin_url)
            main_photo = self.__wait(By.XPATH, "//img[@class='main-photo']")
            img_src = main_photo.get_attribute("src")
            if util.is_image_similar(
                local_image_path=local_image_path, compare_url=img_src
            ):
                logger.info(
                    "Image Validated! Image is visually identical! Image ID refers to the same image."
                )
                return True

            logger.warning(
                "Image not visually identical. Image ID do not refer to the same image. Image not Valid."
            )
            return False
        except Exception as e:
            logger.error(f"Error validating metadata: {e}")
            return False

    def __validate_image(
        self,
        origin_url: str,
        local_image_path: str,
        local_metadata: dict,
        camera_key: str,
        creator_key: str,
    ):
        """
        Validates if an image on the origin page matches a local image by comparing similarity and metadata.
        - Is metadata the same?
            - Yes: Validated! Return True, Keep local image, Delete temporary origin image.
            - No : Does origin image contain camera and creator?
                - Yes: Validated! Return True, Delete local image, Replace it with origin image.
                - No : Imposter! Return False, Delete local image, do not keep origin image since
                        creator & camera were not in origin image on proposed creator's page,
                        therefore unable to verify if local or origin image is from creator.

        :param origin_url: URL of the origin page where the image is expected to be found.
        :param local_image_path: Local path of the local image for validation.
        :param local_metadata: Metadata dictionary of the local image.
        :param camera_key: Key to identify camera metadata.
        :param creator_key: Key to identify creator metadata.
        :returns: True if image passes above criteria, False otherwise.
        """
        try:
            self.driver.get(origin_url)
            local_image = Image.open(fp=local_image_path)
            images_on_page = self.driver.find_elements(By.TAG_NAME, "img")
            with tempfile.TemporaryDirectory() as temp_dir:
                for img_element in images_on_page:
                    img_src = img_element.get_attribute("src")
                    if util.is_image_similar(image=local_image, compare_url=img_src):
                        logger.info("Image similarity found.")
                        temp_image_path = util.download_image(
                            url_link=img_src,
                            download_path=temp_dir,
                            is_temp_download=True,
                        )
                        src_metadata = util.get_metadata(image_path=temp_image_path)

                        logger.info(f"LOCAL Meta: {src_metadata}")
                        logger.info(f"Source Metadata: {src_metadata}")

                        ignored_keys = {
                            "File Name",
                            "Directory",
                            "File Size",
                            "File Modification Date/Time",
                            "File Access Date/Time",
                            "File Inode Change Date/Time",
                            "File Permissions",
                        }

                        filtered_local_metadata = {
                            k: v
                            for k, v in local_metadata.items()
                            if k not in ignored_keys
                        }
                        filtered_src_metadata = {
                            k: v
                            for k, v in src_metadata.items()
                            if k not in ignored_keys
                        }

                        if filtered_local_metadata == filtered_src_metadata:
                            logger.info("Images have identical metadata. Validated!")
                            return True
                        elif (
                            local_metadata[camera_key] == src_metadata[camera_key]
                            and local_metadata[creator_key] == src_metadata[creator_key]
                        ):
                            logger.info(
                                "Images do not have identical metadata, but Origin contains camera & creator info. Validated! - Replacing local image with temp image (origin)"
                            )
                            os.replace(temp_image_path, local_image_path)
                            return True
                        else:
                            logger.warning(
                                "Origin image is an Imposter! Missing required camera and creator. - Removing local image due to inability of verifying if creator owns it."
                            )
                            os.remove(local_image_path)
                            return False

                logger.warning("No matching image found on the origin page.")
                return False
        except Exception as e:
            logger.error(f"Error validating metadata: {e}")
            return False

    def __wait(self, by: By, value: str) -> tuple[str, str]:
        """
        Waits for Selenium WebElement object to be clickable.

        :param elem: The WebElement object
        :returns bool: WebElement or False if the WebElement is clickable
        """
        try:
            elem = WebDriverWait(self.driver, 5).until(
                element_to_be_clickable((by, value))
            )
            return elem
        except Exception as e:
            logger.warning(f"Element ({by}, {value}) does not exist")
            return None

    def __find_oldest_date_link(self) -> str:
        """
        Finds the url link associated with oldest date on the Google Reverse Image Lookup > "Find image source" page.
        Parses the DATE_PATTERN matched date string into a datetime object.
        If this date is older than the current oldest, update it, and find the closest element link associated.

        :returns: Url of oldest date link or None if not found.
        """
        try:
            optional_more_button = self.__wait(
                By.XPATH, "//*[text()='More exact matches']"
            )
            if optional_more_button:
                self.__scroll_to_element(element=optional_more_button)
                optional_more_button.click()

            date_elements = self.__find_deepest_date_elements()
            logger.debug(f"Date Elements Count: {len(date_elements)}")

            oldest_date = None
            oldest_date_link = None

            for date in date_elements:
                match = DATE_PATTERN.search(date.text)
                if match:
                    date_obj = datetime.strptime(match.group(), "%b %d, %Y")
                    if oldest_date is None or date_obj < oldest_date:
                        oldest_date = date_obj
                        oldest_date_link = date.find_element(
                            By.XPATH, "./ancestor::*[@role='link']"
                        )
                        logger.debug(f"Oldest date: {oldest_date}")

            if oldest_date_link:
                href = oldest_date_link.get_attribute("href")
                # origin_link = self.__get_new_page(url=href)
                return href
            else:
                ul_element = self.__wait(
                    by=By.XPATH, value="//ul[@aria-label='All results list']"
                )
                li_element = ul_element.find_element(By.XPATH, ".//li")
                oldest_date_link = li_element.find_element(
                    By.XPATH, "//*[@role='link']"
                )
                href = oldest_date_link.get_attribute("href")
                # origin_link = self.__get_new_page(url=href)
                return href
        except Exception as e:
            logger.warning(f"No valid date links found: {e}")
            return None

    def __find_deepest_date_elements(self) -> list[tuple[str, str]]:
        """
        Recursively finds the deepest date for the Google Reverse Image Lookup > "Find image source" page.

        :returns: A list of the deepest date elements from an image's "Find image source" page.
        """
        deepest_date_elements = []
        elements = self.driver.find_elements(
            By.XPATH, "//div[contains(text(), ', 20')]"
        )
        for elem in elements:
            logger.debug(elem.text)
            deepest_date = self.__get_deepest(element=elem, pattern=DATE_PATTERN)
            if deepest_date:
                deepest_date_elements.append(deepest_date)

        logger.debug("Finished finding deepest date element")
        return deepest_date_elements

    def __get_deepest(self, element: tuple[str, str], pattern: str) -> tuple[str, str]:
        """
        Recursive function to find the deepest child of a parent element.
        If no children, check if the element's text matches a regular expression pattern.
        If there are children, recursively search and return the deepest matching child.

        :param element: The Web Element that has children elements.
        :param pattern: The regular expression pattern for the element's text to match. e.g. `re.compile(r"\b\w{3} \d{1,2}, 20\d{2}\b")`
        :returns: The first deepest child Web Element that matches the pattern.
        """
        children = element.find_elements(By.XPATH, "./*")
        if not children:
            if pattern.search(element.text):
                return element
            return None
        for child in children:
            result = self.__get_deepest_date_element(child, pattern)
            if result:
                return result
        return None

    def __scroll_to_element(self, element: tuple[str, str]):
        """
        Scrolls to element so the Selenium driver can 'see' it.

        :param element: The Web Element to scroll to.
        """
        try:
            self.driver.execute_script("arguments[0].scrollIntoView();", element)
        except Exception as e:
            logger.error(f"Could not scroll to element: {e}")

    def __get_and_validate_creator_on_flickr_page(self, flickr_page: str):
        try:
            self.driver.get(flickr_page)
            heading = self.__wait(By.XPATH, "//h1[@class='truncate']")
            creator_name = heading.text
            if creator_name:
                logger.info("Creator name found and Validated on Flickr page!")
                return creator_name
            else:
                logger.error(
                    "Creator name could not be identified on Flickr page. Creator is not Validated."
                )
                return False
        except Exception as e:
            logger.error(e)
            return False

    def update_analytics(
        self,
        origin: str,
        creator: str,
        is_successful: bool,
        image_path: str,
        metadata: dict,
        watchlist_reasoning: str = "",
    ):
        try:
            util.put_creator_on_watch_or_success_list(
                origin_link=origin,
                creator=creator,
                is_successful=is_successful,
                watchlist_reasoning=watchlist_reasoning,
            )

            util.record_metadata_for_local_image(
                local_image_path=image_path,
                origin_link=origin,
                metadata=metadata,
                is_passing=is_successful,
            )
        except Exception as e:
            logger.error(e)


if __name__ == "__main__":
    validator = Validator(debug_mode=True)
    # validator.validate_camera("Canon EOS 5D Mark II")
    # validator.validate_camera("ILCE-7RM3")
    # validator.validate_camera("DiMAGE Z2")
    # validator.validate_camera("HERO7 Black")
    # validator.validate_camera("X-T3")

    # os.remove("./AllScrapedImages")
    # os.remove("./GranularImageCategories")
    # util.reset_all_dicts()
    # url = "https://www.theilluminatinglens.com/wp-content/uploads/2022/02/20220127MesquiteDunes-10.jpg"
    # path = "./test/validator/20220127MesquiteDunes-10.jpg"
    # metadata = util.get_metadata(image_path=f".{path}")
    # validator.validate(metadata=metadata, image_url=url, image_path=path)
