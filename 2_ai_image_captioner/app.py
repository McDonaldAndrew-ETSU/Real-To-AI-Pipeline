from logger import ColorLogger
from captioning_model import Captioner
from flask import Flask, request, jsonify

logger = ColorLogger(__name__)
app = Flask(__name__)
model = Captioner(use_cache=True)

# Test
# print(model.generate_image_caption("./img/2.jpg"))


@app.route("/caption", methods=["POST"])
def caption_image():
    logger.debug("POST request received")
    if "image" not in request.files:
        logger.error("No 'image' in request")
        return "400"

    image = request.files["image"]
    caption = model.generate_image_caption(image)

    response = jsonify({"caption": caption})
    response.status_code = 200
    return response


@app.route("/caption-photomicrograph", methods=["POST"])
def caption_photomicrograph():
    logger.debug("POST request received")
    if "image" not in request.files:
        logger.error("No 'image' in request")
        return "400"

    image = request.files["image"]
    caption = model.generate_photomicrograph_caption(image)

    response = jsonify({"caption": caption})
    response.status_code = 200
    return response


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
