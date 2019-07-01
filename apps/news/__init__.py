from flask import Blueprint

news_app = Blueprint("news", __name__)

from . import urls
from . import models
