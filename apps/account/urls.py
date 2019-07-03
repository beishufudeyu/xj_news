from . import account_app

from .views import *

account_app.add_url_rule('/image_code', view_func=GetImageCode.as_view('get_image_code'))
account_app.add_url_rule('/sms_code', view_func=SendSMSCode.as_view('send_sms_code'))
account_app.add_url_rule('/register', view_func=Register.as_view('register'))
account_app.add_url_rule('/login', view_func=Login.as_view('login'))
account_app.add_url_rule('/logout', view_func=Logout.as_view('logout'))
account_app.add_url_rule('/', view_func=UserInfo.as_view('user_info'))
account_app.add_url_rule('/base_info', view_func=UserBaseInfo.as_view('base_info'))
account_app.add_url_rule('/pic_info', view_func=UserPicInfo.as_view('pic_info'))
account_app.add_url_rule('/pass_info', view_func=UserPasswordInfo.as_view('pass_info'))
account_app.add_url_rule('/collection', view_func=UserCollectionInfo.as_view('collection'))
account_app.add_url_rule('/news_release', view_func=UserPublishInfo.as_view('news_release'))
account_app.add_url_rule('/news_list', view_func=UserNewListInfo.as_view('news_list'))
account_app.add_url_rule('/user_follow', view_func=UserFollowInfo.as_view('user_follow'))
account_app.add_url_rule('/other_info', view_func=UserOtherInfo.as_view('other_info'))
account_app.add_url_rule('/other_news_list', view_func=OtherUserNewsInfo.as_view('other_news_list'))
