import os
import json
import util
import requests
from datetime import datetime
from logger import ColorLogger
from analytics.all_links_checked_dict import ALL_LINKS_CHECKED


logger = ColorLogger("image_scraper_curl.py")


class ImageScraperCurl:
    def __init__(
        self,
        path: str,
        query: str,
        google_cse_api_key: str,
        custom_search_engine_id: str,
        flickr_api_key: str,
        tags: str,
        image_threshold: int,
        images_per_iteration: int,
        use_flickr_api: bool,
    ):
        """Scrapes images"""
        self.START_TRACKER = 1
        self.IMAGE_THRESHOLD = image_threshold
        self.PROCESSED_COUNT = 0
        self.IMAGES_SKIPPED = 0
        self.DURATION = 0

        self.path = path
        self.query = query

        self.use_flickr_api = use_flickr_api

        self.cse_url = f"https://www.googleapis.com/customsearch/v1?key={google_cse_api_key}&cx={custom_search_engine_id}"
        self.flickr_api_key = flickr_api_key
        self.tags = tags
        self.images_per_iteration = images_per_iteration

    def __query_CSE(self) -> str:
        """
        A query is sent as a curl request to the Custom Search Engine.

        :returns: A JSON formatted string of the search results
        """
        q = self.query
        rights = "cc_nonderived,cc_attribute,cc_noncommercial"
        url = f"{self.cse_url}&q={q}&rights={rights}&searchType=image&start={self.START_TRACKER}"

        try:
            response = requests.get(url)
            if response.status_code == 200:
                json_string = response.json()
                pretty_json = json.dumps(json_string, indent=4)
                logger.debug(pretty_json)

                self.START_TRACKER = util.get_start_index(response=json_string)
                logger.debug(f"Next page starts at: {self.START_TRACKER}")

                return json_string
            else:
                logger.error(f"{response.status_code} - {response.text}")
                return ""
        except Exception as e:
            logger.error(e)
            return ""

    def query_flickr(self) -> str:
        """
        A search query is sent as a curl request to the Flickr API.

        :returns: A JSON formatted string of the search results
        """
        query = self.query
        method_url = "https://api.flickr.com/services/rest/"
        search_params = {
            "method": "flickr.photos.search",
            "api_key": self.flickr_api_key,
            "tags": self.tags,  # A comma-delimited list of tags. Photos with one or more of the tags listed will be returned. You can exclude results that match a term by prepending it with a - character.
            # "tag_mode": "all",             # Either 'any' for an OR combination of tags, or 'all' for an AND combination. Defaults to 'any' if not specified.
            "text": f"{query}",  # A free text search. Photos who's title, description or tags contain the text will be returned. You can exclude results that match a term by prepending it with a - character.
            # "license",                     # The license id for photos (for possible values see the flickr.photos.licenses.getInfo method). Multiple licenses may be comma-separated.
            "sort": "relevance",  # Sort by relevance instead of the possible values: date-posted-asc, date-posted-desc, date-taken-asc, date-taken-desc, interestingness-desc, interestingness-asc, and relevance
            "safe_search": 1,  # Safe search setting: 1 for safe. 2 for moderate. 3 for restricted. (Please note: Un-authed calls can only see Safe content.)
            "content_types": 0,  # (singular version "content_type" is DEPRECATED) Comma-separated list of content types to return. If used in conjunction with video_content_types, this is applied to only photos. If video_content_types is not specified, this filter will apply to all media types
            "media": "photos",  # Filter results by media type. Possible values are all (default), photos or videos
            "extras": "license, date_upload, date_taken, url_o",  # A comma-delimited list of extra information to fetch for each returned record. Currently supported fields are: description, license, date_upload, date_taken, owner_name, icon_server, original_format, last_update, geo, tags, machine_tags, o_dims, views, media, path_alias, url_sq, url_t, url_s, url_q, url_m, url_n, url_z, url_c, url_l, url_o
            "per_page": self.images_per_iteration,  # Number of photos to return per page. If this argument is omitted, it defaults to 100. The maximum allowed value is 500.
            "page": self.START_TRACKER,  # The page of results to return. If this argument is omitted, it defaults to 1.
            # Below are not method specific
            "format": "json",  # Request JSON response
            "nojsoncallback": 1,  # Exclude the JSON callback (cleaner response)
        }

        try:
            response = requests.get(method_url, params=search_params)

            if response.status_code == 200:
                data = response.json()

                self.START_TRACKER = util.get_start_index(data, self.use_flickr_api)
                logger.debug(f"Next page starts at: {self.START_TRACKER}")

                return data
            else:
                logger.error(f"{response.status_code} - {response.text}")
                return ""
        except Exception as e:
            logger.error(e)
            return ""

    def process_images(self):
        """
        Processes images until the threshold is reached
        """
        processing_time = datetime.now()
        i = 0
        while self.PROCESSED_COUNT < self.IMAGE_THRESHOLD:
            data = ""
            if self.use_flickr_api:
                data = self.query_flickr()
            else:
                data = self.__query_CSE()

            path = self.path
            util.download_images_to_local(
                data=data,
                download_path=f"./{path}",
                use_flickr_api=self.use_flickr_api,
                flickr_api_key=self.flickr_api_key,
            )

            self.PROCESSED_COUNT = len(os.listdir(f"./{path}"))
            self.IMAGES_SKIPPED = len(ALL_LINKS_CHECKED) - self.PROCESSED_COUNT

            end_iteration = datetime.now()
            self.DURATION = end_iteration - processing_time
            logger.info(
                f"{path} - Iteration {i}  - Valid: {self.PROCESSED_COUNT} - Skipped: {self.IMAGES_SKIPPED} - Duration: {self.DURATION}"
            )
            i = i + 1


if __name__ == "__main__":
    pass
    # Tests imagehash python module
    # from PIL import Image

    # for file_name in os.listdir("./test/imagehash"):
    #     file_path = os.path.join("./test/imagehash", file_name)
    #     image = Image.open(file_path)
    #     bool = util.check_image_hash(image, file_path)

    # for file_name in os.listdir("./Landscapes and Environments/Dunes"):
    #     file_path = os.path.join("../Landscapes and Environments/Dunes", file_name)
    #     logger.info(util.get_metadata(image_path=file_path))
