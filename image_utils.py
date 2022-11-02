from base64 import b64encode
from urllib.parse import quote


def convert_jpg_to_png(file):
    pass


def get_image_data_url(image_path, extension="png"):
    with open(image_path, 'rb') as f:
        data = b64encode(f.read())
    return 'data:image/{};base64,{}'.format(extension, quote(data))
