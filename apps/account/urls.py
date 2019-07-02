from . import account_app

from .views import *

account_app.add_url_rule('/image_code', view_func=GetImageCode.as_view('get_image_code'))
account_app.add_url_rule('/sms_code', view_func=SendSMSCode.as_view('send_sms_code'))
account_app.add_url_rule('/register', view_func=Register.as_view('register'))
account_app.add_url_rule('/login', view_func=Login.as_view('login'))
account_app.add_url_rule('/logout', view_func=logout, endpoint="logout")
