import functools
from flask import g, session


def to_index_class(index):
    if index == 1:
        return "first"
    elif index == 2:
        return "second"
    elif index == 3:
        return "third"
    else:
        return ""


def user_login_data(f):
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        # 获取到当前登录用户的id
        user_id = session.get("user_id")
        # 通过id获取用户信息
        user = None
        if user_id:
            from apps.account.models import User
            user = User.query.get(user_id)

        g.user = user
        return f(*args, **kwargs)

    return wrapper
