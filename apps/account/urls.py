from . import account_app

from .views import *

account_app.add_url_rule("/image_code", endpoint="index", view_func=get_image_code)
