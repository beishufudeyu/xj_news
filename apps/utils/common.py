import functools
from flask import g, session, redirect, current_app, abort, jsonify
from .response_code import RET


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


def login_require(f):
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        # 获取到当前登录用户
        user = g.user
        if not user:
            return redirect("/")
        return f(*args, **kwargs)

    return wrapper


def logging_error(text):
    current_app.logger.error(text)


def redis_set_ex(key, timeout, value, error):
    from apps import redis_store
    try:
        redis_store.setex(key, timeout, value)
    except Exception as e:
        logging_error(error + str(e))
        return abort(500)
    return None


def redis_get_ex(key):
    from apps import redis_store
    try:
        value = redis_store.get(key)
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg="数据查询失败")
    return value


def redis_del_ex(key):
    from apps import redis_store
    try:
        redis_store.delete(key)
    except Exception as e:
        current_app.logger.error("redis获取图片验证码错误:" + str(e))
    return jsonify(errno=RET.DBERR, errmsg="数据查询失败")

