import os
import time
import torch
from PIL import Image
from logger import ColorLogger
from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig

logger = ColorLogger(__name__)


class Captioner:
    def __init__(self, use_cache: bool = True) -> None:
        start = time.time()
        if use_cache:
            os.environ["HF_HUB_OFFLINE"] = "1"
            self.model = AutoModelForCausalLM.from_pretrained(
                "./cache", local_files_only=True, trust_remote_code=True
            )
            self.model
            self.tokenizer = AutoTokenizer.from_pretrained(
                "./cache", local_files_only=True, trust_remote_code=True
            )
        else:
            self.bnb_cfg = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_compute_dtype=torch.float16,
                llm_int8_skip_modules=["mm_projector", "vision_model"],
            )
            logger.info("Created configurations")
            self.model_id = "./llama-3-vision-alpha-hf"
            self.model = AutoModelForCausalLM.from_pretrained(
                self.model_id,
                trust_remote_code=True,
                torch_dtype=torch.float16,
                quantization_config=self.bnb_cfg,
            )
            logger.info("Loaded model")
            self.tokenizer = AutoTokenizer.from_pretrained(
                self.model_id, use_fast=True, trust_remote_code=True
            )
            logger.info("Loaded tokenizer")

            self.model.save_pretrained("./cache")
            self.tokenizer.save_pretrained("./cache")
            logger.info("Model and Tokenizer saved to cache directory")
        end = time.time()
        elapsed = end - start
        logger.info(
            f"Captioner initialized in {elapsed:.2f} seconds - Awaiting image request"
        )

    def generate_image_caption(self, image_path):
        start = time.time()
        img = Image.open(image_path)
        logger.info(f"Image received! Captioning image...this may take some time...")
        caption = self.tokenizer.decode(
            self.model.answer_question(
                img, "Describe the image in detail", self.tokenizer
            ),
            skip_special_tokens=True,
        )
        end = time.time()
        elapsed = end - start
        logger.info(f"Generated caption in {elapsed:.2f} seconds")

        return caption

    def generate_photomicrograph_caption(self, image_path):
        start = time.time()
        img = Image.open(image_path)
        logger.info(f"Image received! Captioning image...this may take some time...")
        caption = self.tokenizer.decode(
            self.model.answer_question(
                img, "Describe the Photomicrograph image in detail", self.tokenizer
            ),
            skip_special_tokens=True,
        )
        end = time.time()
        elapsed = end - start
        logger.info(f"Generated caption in {elapsed:.2f} seconds")

        return caption
