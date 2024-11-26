import test_util
from logger import ColorLogger
from constants import MODELS, PROMPT_MAGIC, INIT_STRENGTHS, TEST_IMAGE_PATHS

logger = ColorLogger(__name__)


for image_path in TEST_IMAGE_PATHS:
    params = {}
    for model in MODELS:
        params["modelId"] = model
        if model == "6b645e3a-d64f-4341-a6d8-7a3690fbf042":
            name = "Leonardo Phoenix"
        elif model == "b24e16ff-06e3-43eb-8d33-4416c2d75876":
            name = "Leonardo Lightning XL"
        elif model == "aa77f04e-3eec-4034-9c07-d0f619684628":
            name = "Leonardo Kino XL"
            params["photoReal"] = True
            params["photoRealVersion"] = "v2"
        elif model == "5c232a9e-9061-4777-980a-ddc8e65647c6":
            name = "Leonardo Vision XL"
            params["photoReal"] = True
            params["photoRealVersion"] = "v2"
        for prompt_magic in PROMPT_MAGIC:
            if prompt_magic and name in ["Leonardo Kino XL", "Leonardo Vision XL"]:
                continue

            if prompt_magic:
                # Leonardo.AI: "Activating Prompt Magic will automatically deactivate PhotoReal.
                # This is an intentional design choice to optimize the performance of both pipelines"
                # https://intercom.help/leonardo-ai/en/articles/8280769-prompt-magic-v3
                # Leonardo.AI: "We suggest trying values between 0.3 and 0.4 for optimal results."
                # https://intercom.help/leonardo-ai/en/articles/8067649-getting-started#h_f6867e5f41
                params["promptMagic"] = prompt_magic
                params["promptMagicStrength"] = 0.3
                params["promptMagicVersion"] = "v2"
            for init_strength in INIT_STRENGTHS:
                params["init_strength"] = init_strength
                if name in ["Leonardo Kino XL", "Leonardo Vision XL"] and prompt_magic:
                    continue

                photoReal = params.get("photoReal", "False")
                info = f"Model: {name} - Init Strength: {init_strength} - PromptMagic: {prompt_magic} - PhotoReal: {photoReal}"
                logger.info(info)

                test_util.generate_image_to_image(image_path, params)
