from flask import render_template
from flask import current_app, session
from apps.account.models import User


def get_favicon():
    return current_app.send_static_file("news/favicon.ico")


def index():
    # 获取到当前登录用户的id
    user_id = session.get("user_id", None)
    # 通过id获取用户信息
    user = None
    if user_id:
        try:
            user = User.query.get(user_id)
        except Exception as e:
            current_app.logger.error(e)

    data = {"user_info": user.to_dict() if user else None}

    return render_template('news/index.html', data=data)
