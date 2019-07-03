from flask import Blueprint

admin_app = Blueprint("admin", __name__)

from . import urls
from . import models
