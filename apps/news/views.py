from flask import render_template, request, jsonify, g, abort
from apps.utils.response_code import RET
from flask import current_app, session
from .models import News, Category, Comment, CommentLike
from apps import constants, db
from apps.utils.common import user_login_data
from flask.views import MethodView
from apps.account.models import User


def get_favicon():
    return current_app.send_static_file("news/favicon.ico")


@user_login_data
def index():
    # 右侧的新闻排行
    hot_news = []
    try:
        hot_news = News.query.order_by(News.clicks.desc()).limit(constants.CLICK_RANK_MAX_NEWS)
    except Exception as e:
        current_app.logger.error(e)

    # 遍历对象列表,将对象字典添加到列表中
    hot_news_dict_li = []
    for new in hot_news:
        hot_news_dict_li.append(new.to_basic_dict())

    # 获取新闻分类数据
    categories = Category.query.all()
    # 定义列表保存分类数据
    categories_dicts = []

    for category in categories:
        # 拼接内容
        categories_dicts.append(category.to_dict())

    data = {
        "user_info": g.user.to_dict() if g.user else None,
        "hot_news_dict_li": hot_news_dict_li,
        "categories": categories_dicts
    }

    return render_template('news/index.html', data=data)


def get_news_list():
    """
    获取指定分类的新闻列表
    1. 获取参数
    2. 校验参数
    3. 查询数据
    4. 返回数据
    :return:
    """

    # 1. 获取参数
    cid = request.args.get("cid", "1")
    page = request.args.get("page", '1')
    per_page = request.args.get("per_page", constants.HOME_PAGE_MAX_NEWS)

    # 2. 校验参数
    try:
        cid = int(cid)
        page = int(page)
        per_page = int(per_page)
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.PARAMERR, errmsg="参数错误")

    # 3. 查询数据并分页
    filters = [News.status == 0]

    # 如果分类id不为1，那么添加分类id的过滤
    # 查询的不是最新的数据
    if cid != 1:
        filters.append(News.category_id == cid)
    try:
        # 过滤分类,按时间排序,进行分页
        paginate = News.query.filter(*filters).order_by(News.create_time.desc()).paginate(page, per_page, False)
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg="数据查询失败")

    # 获取查询出来的数据
    items = paginate.items
    # 获取到总页数
    total_page = paginate.pages
    current_page = paginate.page

    # 遍历已分页的数据,转换成字典并返回
    news_li = []
    for news in items:
        news_li.append(news.to_basic_dict())

    # 4. 返回数据
    return jsonify(errno=RET.OK, errmsg="OK", totalPage=total_page, currentPage=current_page, newsList=news_li,
                   cid=cid)


@user_login_data
def news_detail(new_id):
    news = None
    try:
        news = News.query.get(new_id)
    except Exception as e:
        current_app.logger.error(e)
        abort(404)

    if not news:
        # 返回数据未找到的页面
        abort(404)

    news.clicks += 1

    # 获取当前新闻的评论
    comments = []
    try:
        comments = Comment.query.filter(Comment.news_id == new_id).order_by(Comment.create_time.desc()).all()
    except Exception as e:
        current_app.logger.error(e)

    # 查询当前用户在当前新闻里点赞了哪些评论
    comment_like_ids = []
    if g.user:
        # 如果当前用户已登录
        try:
            comment_ids = [comment.id for comment in comments]
            if len(comment_ids) > 0:
                # 取到当前用户在当前新闻的所有评论点赞的记录
                comment_likes = CommentLike.query.filter(CommentLike.comment_id.in_(comment_ids),
                                                         CommentLike.user_id == g.user.id).all()
                # 取出记录中所有的评论id
                comment_like_ids = [comment_like.comment_id for comment_like in comment_likes]
        except Exception as e:
            current_app.logger.error(e)

    comment_list = []
    for item in comments:
        comment_dict = item.to_dict()
        comment_dict["is_like"] = False
        # 判断用户是否点赞该评论
        if g.user and item.id in comment_like_ids:
            comment_dict["is_like"] = True
        comment_list.append(comment_dict)

    # 当前登录用户是否关注当前新闻作者
    is_followed = False
    # 判断用户是否收藏过该新闻
    is_collected = False
    if g.user:
        if news in g.user.collection_news:
            is_collected = True
        if news.user.followers.filter(User.id == g.user.id).count() > 0:
            is_followed = True

    hot_news = []
    try:
        hot_news = News.query.order_by(News.clicks.desc()).limit(constants.CLICK_RANK_MAX_NEWS)
    except Exception as e:
        current_app.logger.error(e)

    # 遍历对象列表,将对象字典添加到列表中
    hot_news_dict_li = []
    for new in hot_news:
        hot_news_dict_li.append(new.to_basic_dict())

    data = {
        "user_info": g.user.to_dict() if g.user else None,
        "hot_news_dict_li": hot_news_dict_li,
        "news": news.to_dict(),
        "is_collected": is_collected,
        "comments": comment_list,
        "is_followed": is_followed
    }
    return render_template("news/detail.html", data=data)


class NewCollect(MethodView):
    decorators = [user_login_data]

    def post(self):
        user = g.user
        json_data = request.json
        news_id = json_data.get("news_id")
        action = json_data.get("action")

        if not user:
            return jsonify(errno=RET.SESSIONERR, errmsg="用户未登录")

        if not news_id:
            return jsonify(errno=RET.PARAMERR, errmsg="参数错误")

        if action not in ("collect", "cancel_collect"):
            return jsonify(errno=RET.PARAMERR, errmsg="参数错误")

        try:
            news = News.query.get(news_id)
        except Exception as e:
            current_app.logger.error(e)
            return jsonify(errno=RET.DBERR, errmsg="查询数据失败")

        if not news:
            return jsonify(errno=RET.NODATA, errmsg="新闻数据不存在")

        if action == "collect":
            user.collection_news.append(news)
        else:
            user.collection_news.remove(news)

        try:
            db.session.commit()
        except Exception as e:
            current_app.logger.error(e)
            db.session.rollback()
            return jsonify(errno=RET.DBERR, errmsg="保存失败")
        return jsonify(errno=RET.OK, errmsg="操作成功")


class AddNewComment(MethodView):
    decorators = [user_login_data]

    def post(self):
        user = g.user
        if not user:
            return jsonify(errno=RET.SESSIONERR, errmsg="用户未登录")
        # 获取参数
        data_dict = request.json
        news_id = data_dict.get("news_id")
        comment_str = data_dict.get("comment")
        parent_id = data_dict.get("parent_id")

        if not all([news_id, comment_str]):
            return jsonify(errno=RET.PARAMERR, errmsg="参数不足")

        try:
            news = News.query.get(news_id)
        except Exception as e:
            current_app.logger.error(e)
            return jsonify(errno=RET.DBERR, errmsg="查询数据失败")

        if not news:
            return jsonify(errno=RET.NODATA, errmsg="该新闻不存在")

        # 初始化模型，保存数据
        comment = Comment()
        comment.user_id = user.id
        comment.news_id = news_id
        comment.content = comment_str
        if parent_id:
            comment.parent_id = parent_id

        # 保存到数据库
        try:
            db.session.add(comment)
            db.session.commit()
        except Exception as e:
            current_app.logger.error(e)
            return jsonify(errno=RET.DBERR, errmsg="保存评论数据失败")

        # 返回响应
        return jsonify(errno=RET.OK, errmsg="评论成功", data=comment.to_dict())


class SetCommentLike(MethodView):
    """评论点赞"""
    decorators = [user_login_data]

    def post(self):
        if not g.user:
            return jsonify(errno=RET.SESSIONERR, errmsg="用户未登录")

        # 获取参数
        comment_id = request.json.get("comment_id")
        news_id = request.json.get("news_id")
        action = request.json.get("action")

        # 判断参数
        if not all([comment_id, news_id, action]):
            return jsonify(errno=RET.PARAMERR, errmsg="参数错误")

        if action not in ("add", "remove"):
            return jsonify(errno=RET.PARAMERR, errmsg="参数错误")

        # 查询评论数据
        try:
            comment = Comment.query.get(comment_id)
        except Exception as e:
            current_app.logger.error(e)
            return jsonify(errno=RET.DBERR, errmsg="查询数据失败")

        if not comment:
            return jsonify(errno=RET.NODATA, errmsg="评论数据不存在")

        if action == "add":
            comment_like = CommentLike.query.filter_by(comment_id=comment_id, user_id=g.user.id).first()
            if not comment_like:
                comment_like = CommentLike()
                comment_like.comment_id = comment_id
                comment_like.user_id = g.user.id
                db.session.add(comment_like)
                # 增加点赞条数
                comment.like_count += 1

        else:
            # 删除点赞数据
            comment_like = CommentLike.query.filter_by(comment_id=comment_id, user_id=g.user.id).first()
            if comment_like:
                db.session.delete(comment_like)
                # 减小点赞条数
                comment.like_count -= 1

        try:
            db.session.commit()
        except Exception as e:
            current_app.logger.error(e)
            db.session.rollback()
            return jsonify(errno=RET.DBERR, errmsg="操作失败")
        return jsonify(errno=RET.OK, errmsg="操作成功")


class FollowedUser(MethodView):
    decorators = [user_login_data]

    def post(self):
        """关注/取消关注用户"""
        if not g.user:
            return jsonify(errno=RET.SESSIONERR, errmsg="用户未登录")

        user_id = request.json.get("user_id")
        action = request.json.get("action")

        if not all([user_id, action]):
            return jsonify(errno=RET.PARAMERR, errmsg="参数错误")

        if action not in ("follow", "unfollow"):
            return jsonify(errno=RET.PARAMERR, errmsg="参数错误")

        # 查询到关注的用户信息
        try:
            target_user = User.query.get(user_id)
        except Exception as e:
            current_app.logger.error(e)
            return jsonify(errno=RET.DBERR, errmsg="查询数据库失败")

        if not target_user:
            return jsonify(errno=RET.NODATA, errmsg="未查询到用户数据")

        # 根据不同操作做不同逻辑
        if action == "follow":
            if target_user.followers.filter(User.id == g.user.id).count() > 0:
                return jsonify(errno=RET.DATAEXIST, errmsg="当前已关注")
            target_user.followers.append(g.user)
        else:
            if target_user.followers.filter(User.id == g.user.id).count() > 0:
                target_user.followers.remove(g.user)

        # 保存到数据库
        try:
            db.session.commit()
        except Exception as e:
            current_app.logger.error(e)
            return jsonify(errno=RET.DBERR, errmsg="数据保存错误")

        return jsonify(errno=RET.OK, errmsg="操作成功")
