from . import admin_app

from .views import *

admin_app.add_url_rule('/login', view_func=AdminLoginView.as_view('login'))
admin_app.add_url_rule('/', view_func=AdminView.as_view('admin'))
admin_app.add_url_rule('/user_count', view_func=AdminUserCountView.as_view('user_count'))
admin_app.add_url_rule('/user_list', view_func=AdminUserListView.as_view('user_list'))
admin_app.add_url_rule('/news_review', view_func=AdminNewsReviewView.as_view('news_review'))
admin_app.add_url_rule('/news_review_detail',
                       view_func=AdminNewsReviewDetailView.as_view('news_review_detail'))
admin_app.add_url_rule('/news_edit',
                       view_func=AdminNewsEditView.as_view('news_edit'))
admin_app.add_url_rule('/news_edit_detail',
                       view_func=AdminNewsEditDetailView.as_view('news_edit_detail'))
admin_app.add_url_rule('/news_category',
                       view_func=AdminNewsCategoryView.as_view('news_category'))
admin_app.add_url_rule('/add_category',
                       view_func=AdminAddCategoryView.as_view('add_category'))

