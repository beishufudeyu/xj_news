from apps import redis_store, db
from flask import request, abort, render_template, redirect, g, current_app, make_response, jsonify, session, url_for
from apps.utils.captcha.captcha import captcha
from apps import constants
from apps.account.models import User
from flask.views import MethodView
from apps.utils.response_code import RET
import re
import random
from datetime import datetime
from apps.libs.yuntongxun.sms import ccp
from apps.news.models import Category, News
from apps.utils.common import admin_login_require, admin_user_login_data, is_login_to_admin
from apps.utils.image_storage import storage
import time
from datetime import timedelta


class AdminLoginView(MethodView):
    decorators = [is_login_to_admin, admin_user_login_data]

    def get(self):
        return render_template("admin/login.html")

    def post(self):
        # 取到登录的参数
        username = request.form.get("username")
        password = request.form.get("password")
        if not all([username, password]):
            return render_template('admin/login.html', errmsg="参数不足")

        try:
            user = User.query.filter(User.mobile == username, User.is_admin == 1).first()
        except Exception as e:
            current_app.logger.error(e)
            return render_template('admin/login.html', errmsg="数据查询失败")

        if not user:
            return render_template('admin/login.html', errmsg="用户不存在")

        if not user.check_password(password):
            return render_template('admin/login.html', errmsg="密码错误")

        if not user.is_admin:
            return render_template('admin/login.html', errmsg="用户权限错误")

        session["user_id"] = user.id
        session["nick_name"] = user.nick_name
        session["mobile"] = user.mobile
        session["is_admin"] = True

        # TODO 跳转到后台管理主页,暂未实现
        return redirect(url_for("admin.admin"))


class AdminView(MethodView):
    decorators = [admin_login_require, admin_user_login_data]

    def get(self):
        user = g.admin_user
        return render_template("admin/index.html", user=user.to_dict())


class AdminUserCountView(MethodView):
    """
    # 月新增数：获取到本月第1天0点0分0秒的时间对象，然后查询最后一次登录比其大的所有数据
    # 日新增数：获取到当日0点0分0秒时间对象，然后查询最后一次登录比其大的所有数据
    # 图表查询：遍历查询数据每一天的数据(当前天数，减去某些天)
    """
    decorators = [admin_login_require, admin_user_login_data]

    def get(self):
        # 查询总人数
        total_count = 0
        try:
            total_count = User.query.filter(User.is_admin == 0).count()
        except Exception as e:
            current_app.logger.error(e)

        # 查询月新增数
        mon_count = 0
        now = time.localtime()
        try:
            mon_begin = '%d-%02d-01' % (now.tm_year, now.tm_mon)
            mon_begin_date = datetime.strptime(mon_begin, '%Y-%m-%d')
            mon_count = User.query.filter(User.is_admin == 0, User.create_time >= mon_begin_date).count()
        except Exception as e:
            current_app.logger.error(e)

        # 查询日新增数
        day_count = 0
        day_begin = '%d-%02d-%02d' % (now.tm_year, now.tm_mon, now.tm_mday)
        day_begin_date = datetime.strptime(day_begin, '%Y-%m-%d')
        try:
            day_count = User.query.filter(User.is_admin == 0, User.create_time > day_begin_date).count()
        except Exception as e:
            current_app.logger.error(e)

        # 查询图表信息
        # 获取到当天00:00:00时间
        now = datetime.now().strftime('%Y-%m-%d')
        begin_today_date = datetime.strptime(now, '%Y-%m-%d')
        # 定义空数组，保存数据
        active_date = []
        active_count = []

        # 依次添加数据，再反转
        for i in range(0, 31):
            # 取到某一天的0.0分
            begin_date = begin_today_date - timedelta(days=i)
            # 取到某一天的前一天的0.0分
            end_date = begin_today_date - timedelta(days=(i - 1))
            # 所有天数添加到active_date列表中
            active_date.append(begin_date.strftime('%Y-%m-%d'))
            count = 0
            try:
                count = User.query.filter(User.is_admin == 0, User.last_login >= day_begin,
                                          User.last_login < end_date).count()
            except Exception as e:
                current_app.logger.error(e)
            active_count.append(count)

        active_date.reverse()
        active_count.reverse()

        data = {"total_count": total_count, "mon_count": mon_count, "day_count": day_count, "active_date": active_date,
                "active_count": active_count}

        return render_template('admin/user_count.html', data=data)


class AdminUserListView(MethodView):
    """
    按用户最后一次登录倒序分页展示用户列表
    """
    decorators = [admin_login_require, admin_user_login_data]

    def get(self):
        # 获取参数
        page = request.args.get("p", 1)
        try:
            page = int(page)
        except Exception as e:
            current_app.logger.error(e)
            page = 1

        # 设置变量默认值
        users = []
        current_page = 1
        total_page = 1

        # 查询数据
        try:
            paginate = User.query.filter(User.is_admin == 0).order_by(User.last_login.desc()).paginate(page,
                                                                                                       constants.ADMIN_USER_PAGE_MAX_COUNT,
                                                                                                       False)
            users = paginate.items
            current_page = paginate.page
            total_page = paginate.pages
        except Exception as e:
            current_app.logger.error(e)

        # 将模型列表转成字典列表
        users_list = []
        for user in users:
            users_list.append(user.to_admin_dict())

        context = {"total_page": total_page, "current_page": current_page, "users": users_list}
        return render_template('admin/user_list.html',
                               data=context)


class AdminNewsReviewView(MethodView):
    decorators = [admin_login_require, admin_user_login_data]

    def get(self):
        # 获取参数
        page = request.args.get("p", 1)
        keywords = request.args.get("keywords", "")
        try:
            page = int(page)
        except Exception as e:
            current_app.logger.error(e)
            page = 1

        news_list = []
        current_page = 1
        total_page = 1

        try:
            filters = [News.status != 0]
            # 如果有关键词
            if keywords:
                # 添加关键词的检索选项
                filters.append(News.title.contains(keywords))
            # 查询
            paginate = News.query.filter(*filters) \
                .order_by(News.create_time.desc()) \
                .paginate(page, constants.ADMIN_NEWS_PAGE_MAX_COUNT, False)

            news_list = paginate.items
            current_page = paginate.page
            total_page = paginate.pages
        except Exception as e:
            current_app.logger.error(e)

        news_dict_list = []
        for news in news_list:
            news_dict_list.append(news.to_review_dict())

        context = {"total_page": total_page, "current_page": current_page, "news_list": news_dict_list}

        return render_template('admin/news_review.html', data=context)


class AdminNewsReviewDetailView(MethodView):
    decorators = [admin_login_require, admin_user_login_data]

    def get(self):
        news_id = request.args.get("news_id")

        # 获取新闻id
        if not news_id:
            return render_template('admin/news_review_detail.html', data={"errmsg": "未查询到此新闻"})

        # 通过id查询新闻
        news = None
        try:
            news = News.query.get(news_id)
        except Exception as e:
            current_app.logger.error(e)

        if not news:
            return render_template('admin/news_review_detail.html', data={"errmsg": "未查询到此新闻"})

        # 返回数据
        data = {"news": news.to_dict()}
        return render_template('admin/news_review_detail.html', data=data)

    def post(self):
        # 执行审核操作

        # 1.获取参数
        news_id = request.json.get("news_id")
        action = request.json.get("action")

        # 2.判断参数
        if not all([news_id, action]):
            return jsonify(errno=RET.PARAMERR, errmsg="参数错误")
        if action not in ("accept", "reject"):
            return jsonify(errno=RET.PARAMERR, errmsg="参数错误")
        news = None
        try:
            # 3.查询新闻
            news_id = int(news_id)
            news = News.query.get(news_id)
        except Exception as e:
            current_app.logger.error(e)

        if not news:
            return jsonify(errno=RET.NODATA, errmsg="未查询到数据")

        # 4.根据不同的状态设置不同的值
        if action == "accept":
            news.status = 0
        else:
            # 拒绝通过，需要获取原因
            reason = request.json.get("reason")
            if not reason:
                return jsonify(errno=RET.PARAMERR, errmsg="请填写拒绝原因")
            news.reason = reason
            news.status = -1

        # 保存数据库
        try:
            db.session.commit()
        except Exception as e:
            current_app.logger.error(e)
            db.session.rollback()
            return jsonify(errno=RET.DBERR, errmsg="数据保存失败")
        return jsonify(errno=RET.OK, errmsg="操作成功")


class AdminNewsEditView(MethodView):
    decorators = [admin_login_require, admin_user_login_data]

    def get(self):
        page = request.args.get("p", 1)
        keywords = request.args.get("keywords", None)
        try:
            page = int(page)
        except Exception as e:
            current_app.logger.error(e)
            page = 1

        news_list = []
        current_page = 1
        total_page = 1

        try:
            filters = [News.status == 0]
            # 如果有关键词
            if keywords:
                # 添加关键词的检索选项
                filters.append(News.title.contains(keywords))

            # 查询
            paginate = News.query.filter(*filters) \
                .order_by(News.create_time.desc()) \
                .paginate(page, constants.ADMIN_NEWS_PAGE_MAX_COUNT, False)

            news_list = paginate.items
            current_page = paginate.page
            total_page = paginate.pages
        except Exception as e:
            current_app.logger.error(e)

        news_dict_list = []
        for news in news_list:
            news_dict_list.append(news.to_basic_dict())

        context = {"total_page": total_page, "current_page": current_page, "news_list": news_dict_list}

        return render_template('admin/news_edit.html', data=context)


class AdminNewsEditDetailView(MethodView):
    decorators = [admin_login_require, admin_user_login_data]

    def get(self):
        """新闻编辑详情"""

        # 获取参数
        news_id = request.args.get("news_id")

        if not news_id:
            abort(404)

        try:
            news_id = int(news_id)
        except Exception as e:
            return render_template('admin/news_edit_detail.html', data={"errmsg": "参数错误"})

        # 查询新闻
        news = None
        try:
            news = News.query.get(news_id)
        except Exception as e:
            current_app.logger.error(e)

        if not news:
            return render_template('admin/news_edit_detail.html', data={"errmsg": "未查询到此新闻"})

        # 查询分类的数据
        categories = Category.query.all()
        categories_li = []
        for category in categories:
            c_dict = category.to_dict()
            c_dict["is_selected"] = False
            if category.id == news.category_id:
                c_dict["is_selected"] = True
            categories_li.append(c_dict)
        # 移除`最新`分类
        categories_li.pop(0)

        data = {"news": news.to_dict(), "categories": categories_li}
        return render_template('admin/news_edit_detail.html', data=data)

    def post(self):
        news_id = request.form.get("news_id")
        title = request.form.get("title")
        digest = request.form.get("digest")
        content = request.form.get("content")
        index_image = request.files.get("index_image")
        category_id = request.form.get("category_id")
        # 1.1 判断数据是否有值
        if not all([title, digest, content, category_id]):
            return jsonify(errno=RET.PARAMERR, errmsg="参数有误")

        news = None
        try:
            news = News.query.get(news_id)
        except Exception as e:
            current_app.logger.error(e)
        if not news:
            return jsonify(errno=RET.NODATA, errmsg="未查询到新闻数据")

        # 1.2 尝试读取图片
        if index_image:
            try:
                index_image = index_image.read()
            except Exception as e:
                current_app.logger.error(e)
                return jsonify(errno=RET.PARAMERR, errmsg="参数有误")

            # 2. 将标题图片上传到七牛
            try:
                key = storage(index_image)
            except Exception as e:
                current_app.logger.error(e)
                return jsonify(errno=RET.THIRDERR, errmsg="上传图片错误")
            news.index_image_url = constants.QINIU_DOMIN_PREFIX + key
        # 3. 设置相关数据
        news.title = title
        news.digest = digest
        news.content = content
        news.category_id = category_id

        # 4. 保存到数据库
        try:
            db.session.commit()
        except Exception as e:
            current_app.logger.error(e)
            db.session.rollback()
            return jsonify(errno=RET.DBERR, errmsg="保存数据失败")
        # 5. 返回结果
        return jsonify(errno=RET.OK, errmsg="编辑成功")


class AdminNewsCategoryView(MethodView):
    decorators = [admin_login_require, admin_user_login_data]

    def get(self):
        # 获取所有的分类数据
        categories = Category.query.all()
        # 定义列表保存分类数据
        categories_dicts = []

        for category in categories:
            # 获取字典
            cate_dict = category.to_dict()
            # 拼接内容
            categories_dicts.append(cate_dict)

        categories_dicts.pop(0)
        # 返回内容
        return render_template('admin/news_type.html', data={"categories": categories_dicts})


class AdminAddCategoryView(MethodView):
    decorators = [admin_login_require, admin_user_login_data]

    def post(self):
        """修改或者添加分类"""

        category_id = request.json.get("id")
        category_name = request.json.get("name")
        if not category_name:
            return jsonify(errno=RET.PARAMERR, errmsg="参数错误")
        # 判断是否有分类id
        if category_id:
            try:
                category = Category.query.get(category_id)
            except Exception as e:
                current_app.logger.error(e)
                return jsonify(errno=RET.DBERR, errmsg="查询数据失败")

            if not category:
                return jsonify(errno=RET.NODATA, errmsg="未查询到分类信息")

            category.name = category_name
        else:
            # 如果没有分类id，则是添加分类
            category = Category()
            category.name = category_name
            db.session.add(category)

        try:
            db.session.commit()
        except Exception as e:
            current_app.logger.error(e)
            db.session.rollback()
            return jsonify(errno=RET.DBERR, errmsg="保存数据失败")
        return jsonify(errno=RET.OK, errmsg="保存数据成功")
