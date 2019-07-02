from flask import render_template, request, jsonify
from apps.utils.response_code import RET
from flask import current_app, session
from apps.account.models import User
from .models import News, Category
from apps import constants


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
        "user_info": user.to_dict() if user else None,
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
    filters = []

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
