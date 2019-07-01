from flask import render_template
from flask import current_app


def get_favicon():
    return current_app.send_static_file("news/favicon.ico")


def index():
    return render_template("news/index.html")
