from . import news_app

from .views import *

news_app.add_url_rule("/", endpoint="index", view_func=index)
