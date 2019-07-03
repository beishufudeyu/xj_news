from . import news_app

from .views import *

news_app.add_url_rule("/favicon.ico", endpoint="favicon", view_func=get_favicon)
news_app.add_url_rule("/", endpoint="index", view_func=index)
news_app.add_url_rule("/newslist", endpoint="newslist", view_func=get_news_list)
news_app.add_url_rule("/news/<int:new_id>", endpoint="new_detail", view_func=news_detail)
news_app.add_url_rule("/news/news_collect", view_func=NewCollect.as_view('news_collect'))
news_app.add_url_rule("/news/news_comment", view_func=AddNewComment.as_view('news_comment'))
news_app.add_url_rule("/news/comment_like", view_func=SetCommentLike.as_view('comment_like'))
news_app.add_url_rule("/news/followed_user", view_func=FollowedUser.as_view('followed_user'))
