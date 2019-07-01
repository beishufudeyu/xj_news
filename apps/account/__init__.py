from flask import Blueprint

account_app = Blueprint("account", __name__)

from . import urls
