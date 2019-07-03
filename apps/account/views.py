from apps import redis_store, db
from flask import request, abort, render_template, redirect, g
from apps.utils.captcha.captcha import captcha
from apps import constants
from flask import current_app, make_response, jsonify, session
from flask.views import MethodView
from apps.utils.response_code import RET
import re
import random
from datetime import datetime
from apps.libs.yuntongxun.sms import ccp
from .models import User
from apps.news.models import Category, News
from apps.utils.common import user_login_data, login_require
from apps.utils.image_storage import storage


class GetImageCode(MethodView):

    def get(self):
        """
        生成验证码并返回
        1. 取得参数
        2. 判断参数是否有值
        3. 生成图片验证码
        4. 保存图片验证码文字到redis
        5. 返回验证码图片
        :return: 验证码图片
        """

        # 1.取得参数
        image_uuid = request.args.get("imageCodeId", None)

        # 2. 判断参数是否有值
        if not image_uuid:
            return abort(403)

        # 3. 生成图片验证码
        name, text, image = captcha.generate_captcha()

        # TODO 方便测试,记得删除
        current_app.logger.error("当前图片验证码为: {}".format(text))

        # 4. 保存图片验证码文字到redis
        try:
            redis_store.setex("imageCodeId:" + image_uuid, constants.IMAGE_CODE_REDIS_EXPIRES, text)
        except Exception as e:
            current_app.logger.error("redis保存图片验证码错误:" + str(e))
            abort(500)

        # 5. 返回验证码图片
        response = make_response(image)
        response.headers["Content-Type"] = "image/jpg"
        return response


class SendSMSCode(MethodView):

    def post(self):
        """
        发送手机验证码
        1. 取得参数:
            手机号 图片验证码 图片验证码uuid
        2. 判断参数是否有值,是否符合规则
        3. 从redis去去取图片验证码的text对比用户传来的是否一致
            如果不一致,返回验证码错误
        4. 一致,生成验证码的内容(随机数据)
        5. 发送手机验证码
        6. 保存手机验证码到redis中
        6. 返回数据,告知发送结果
        :return: 告知发送手机验证码结果
        """

        # 1.取得参数
        # params_dict = json.loads(request.data)
        params_dict = request.json

        #  1. 取得参数:
        #  手机号 图片验证码 图片验证码uuid
        phone = params_dict.get("mobile", None)
        image_code = params_dict.get("image_code", None)
        image_uuid = params_dict.get("image_code_id", None)

        # 2. 判断参数是否有值,是否符合规则
        if not all([phone, image_code, image_uuid]):
            return jsonify(errno=RET.PARAMERR, errmsg="传入参数有误")

        if not re.match(r"^1[35678]\d{9}$", phone):
            return jsonify(errno=RET.PARAMERR, errmsg="手机号格式不正确")

        try:
            frequently_sms = redis_store.get("Frequently_SMS_" + phone)
        except Exception as e:
            current_app.logger.error(e)
            return jsonify(errno=RET.DBERR, errmsg="数据查询失败")

        if frequently_sms:
            return jsonify(errno=RET.REQERR, errmsg="请求频繁")

        # 3. 从redis去去取图片验证码的text对比用户传来的是否一致
        try:
            real_image_code = redis_store.get("imageCodeId:" + image_uuid)
            redis_store.delete("imageCodeId:" + image_uuid)
        except Exception as e:
            current_app.logger.error("redis获取图片验证码错误:" + str(e))
            return jsonify(errno=RET.DBERR, errmsg="数据查询失败")

        if not real_image_code:
            return jsonify(errno=RET.NODATA, errmsg="图片验证码已过期")

        # 4. 与用户传来的数据进行对比
        if image_code.lower() != real_image_code.lower():
            return jsonify(errno=RET.DATAERR, errmsg="图片验证码输入错误")

        try:
            user = User.query.filter_by(mobile=phone).first()
        except Exception as e:
            current_app.logger.error(e)
            return jsonify(errno=RET.DBERR, errmsg="数据库查询错误")
        if user:
            # 该手机已被注册
            return jsonify(errno=RET.DATAEXIST, errmsg="该手机已被注册")

        # 5. 生成验证码的内容(随机数据)
        sms_code = "%06d" % random.randint(0, 999999)

        # TODO 方便测试,记得删除
        current_app.logger.error("当前{}手机的验证码为: {}".format(phone, sms_code))

        # 6. 发送手机验证码
        result = ccp.send_template_sms(phone, [sms_code, constants.SMS_CODE_REDIS_EXPIRES / 60], 1)

        try:
            redis_store.setex("Frequently_SMS_:" + phone, 60, 1)
        except Exception as e:
            current_app.logger.error(e)
            return jsonify(errno=RET.DBERR, errmsg="数据库查询错误")

        # 4. 保存手机验证码文字到redis
        try:
            redis_store.setex("SMS_:" + phone, constants.SMS_CODE_REDIS_EXPIRES, sms_code)
        except Exception as e:
            current_app.logger.error("redis保存手机验证码错误:" + str(e))
            return jsonify(errno=RET.DBERR, errmsg="数据库查询错误")

        if result != 0:
            current_app.logger.error("第三方发送手机验证码错误")
            return jsonify(errno=RET.SERVERERR, errmsg="发送手机验证码失败")
        return jsonify(errno=RET.OK, errmsg="发送手机验证码成功")


class Register(MethodView):

    def post(self):
        """
        注册用户
        1. 取得参数
        2. 判断参数是否有值
        3. 取到数据库保存的真实手机验证码验证是否一致
        4. 一致,初始化User模型,创建用户
        5. 不一致,返回手机验证码错误
        6. 返回响应
        :return: 返回响应
        """

        params_dict = request.json

        #  1. 取得参数:
        #  手机号 图片验证码 图片验证码uuid
        phone = params_dict.get("mobile", None)
        sms_code = params_dict.get("sms_code", None)
        password = params_dict.get("password", None)

        # 2. 判断参数是否有值,是否符合规则
        if not all([phone, sms_code, password]):
            return jsonify(errno=RET.PARAMERR, errmsg="参数错误")

        if not re.match(r"^1[35678]\d{9}$", phone):
            return jsonify(errno=RET.PARAMERR, errmsg="手机号格式不正确")

        # 3. 取到数据库保存的真实手机验证码验证是否一致
        try:
            real_sms_code = redis_store.get("SMS_:" + phone)
        except Exception as e:
            current_app.logger.error(e)
            return jsonify(errno=RET.DBERR, errmsg="数据查询失败")

        # 数据为空,即是验证码已过期
        if not real_sms_code:
            return jsonify(errno=RET.NODATA, errmsg="手机验证码过期")

        # 判断手机验证码是否一致
        if real_sms_code != sms_code:
            return jsonify(errno=RET.DATAERR, errmsg="手机验证码输入错误")

        # 删除短信验证码
        try:
            redis_store.delete("SMS_:" + phone)
        except Exception as e:
            current_app.logger.error(e)

        # 4. 一致,初始化User模型,创建用户
        user = User()
        user.mobile = phone
        # 没有nickname,默认保存手机号
        user.nick_name = phone
        # 保存用户最后一次登录时间
        user.last_login = datetime.now()
        # 密码的处理,已经在模型中处理密码加密
        user.password = password

        # 添加到数据库
        try:
            db.session.add(user)
            db.session.commit()
        except Exception as e:
            current_app.logger.error("创建用户到数据库失败:" + str(e))
            db.session.rollback()
            return jsonify(errno=RET.DBERR, errmsg="数据库错误")

        # 登录,添加用户信息到session中
        session["user_id"] = user.id
        session["mobile"] = user.mobile
        session["nick_name"] = user.nick_name

        # 5. 返回响应
        return jsonify(errno=RET.OK, errmsg="注册成功")


class Login(MethodView):
    def post(self):
        """
        1. 获取参数和判断是否有值
        2. 从数据库查询出指定的用户
        3. 校验密码
        4. 保存用户登录状态
        5. 返回结果
        :return:
        """

        # 1. 获取参数和判断是否有值
        json_data = request.json

        mobile = json_data.get("mobile", None)
        password = json_data.get("password", None)

        if not all([mobile, password]):
            # 参数不全
            return jsonify(errno=RET.PARAMERR, errmsg="参数不全")

        # 2. 从数据库查询出指定的用户
        try:
            user = User.query.filter_by(mobile=mobile).first()
        except Exception as e:
            current_app.logger.error(e)
            return jsonify(errno=RET.DBERR, errmsg="查询数据错误")

        if not user:
            return jsonify(errno=RET.USERERR, errmsg="用户不存在")

        # 3. 校验密码
        if not user.check_password(password):
            return jsonify(errno=RET.PWDERR, errmsg="用户名或密码错误")

        # 4. 保存用户登录状态
        session["user_id"] = user.id
        session["nick_name"] = user.nick_name
        session["mobile"] = user.mobile

        # 记录用户最后一次登录时间
        user.last_login = datetime.now()

        # 保存已在SQLALCHEMY_COMMIT_ON_TEARDOWN配置自动提交

        # 5. 登录成功
        return jsonify(errno=RET.OK, errmsg="OK")


class Logout(MethodView):
    decorators = [login_require, user_login_data]

    def get(self):
        session.pop('user_id', None)
        session.pop('nick_name', None)
        session.pop('mobile', None)
        # 返回结果
        return redirect("/")


# def logout():
#     """
#     清除session中的对应登录之后保存的信息
#     :return:
#     """
#     session.pop('user_id', None)
#     session.pop('nick_name', None)
#     session.pop('mobile', None)
#
#     # 返回结果
#     return redirect("/")


class UserInfo(MethodView):
    decorators = [login_require, user_login_data]

    def get(self):
        return render_template('news/user.html', data={"user_info": g.user.to_dict()})


class UserBaseInfo(MethodView):
    decorators = [login_require, user_login_data]

    def get(self):
        return render_template('news/user_base_info.html', data={"user_info": g.user.to_dict()})

    def post(self):
        user = g.user
        if not user:
            return jsonify(errno=RET.SESSIONERR, errmsg="用户未登录")
        # 2. 获取到传入参数
        data_dict = request.json
        nick_name = data_dict.get("nick_name")
        gender = data_dict.get("gender")
        signature = data_dict.get("signature")
        if not all([nick_name, gender, signature]):
            return jsonify(errno=RET.PARAMERR, errmsg="参数有误")

        if gender not in (['MAN', 'WOMAN']):
            return jsonify(errno=RET.PARAMERR, errmsg="性别参数有误")

        # 3. 更新并保存数据
        user.nick_name = nick_name
        user.gender = gender
        user.signature = signature

        # 将 session 中保存的数据进行实时更新
        session["nick_name"] = nick_name

        # 4. 返回响应
        return jsonify(errno=RET.OK, errmsg="更新成功")


class UserPicInfo(MethodView):
    decorators = [login_require, user_login_data]

    def get(self):
        return render_template('news/user_pic_info.html', data={"user_info": g.user.to_dict()})

    def post(self):
        user = g.user
        if not user:
            return jsonify(errno=RET.SESSIONERR, errmsg="用户未登录")
        # 1. 获取到上传的文件
        try:
            avatar_file = request.files.get("avatar").read()
        except Exception as e:
            current_app.logger.error(e)
            return jsonify(errno=RET.PARAMERR, errmsg="读取文件出错")

        # 2. 再将文件上传到七牛云
        try:
            url = storage(avatar_file)
        except Exception as e:
            current_app.logger.error(e)
            return jsonify(errno=RET.THIRDERR, errmsg="上传图片错误")

        # 3. 将头像信息更新到当前用户的模型中
        # 设置用户模型相关数据
        user.avatar_url = url

        # 4. 返回上传的结果<avatar_url>
        return jsonify(errno=RET.OK, errmsg="OK", data={"avatar_url": constants.QINIU_DOMIN_PREFIX + url})


class UserPasswordInfo(MethodView):
    decorators = [login_require, user_login_data]

    def get(self):
        return render_template('news/user_pass_info.html')

    def post(self):
        user = g.user
        if not user:
            return jsonify(errno=RET.SESSIONERR, errmsg="用户未登录")
        # 1. 获取到传入参数
        data_dict = request.json
        old_password = data_dict.get("old_password")
        new_password = data_dict.get("new_password")

        if not all([old_password, new_password]):
            return jsonify(errno=RET.PARAMERR, errmsg="参数有误")

        # 2. 获取当前登录用户的信息
        if not user.check_passowrd(old_password):
            return jsonify(errno=RET.PWDERR, errmsg="原密码错误")

        # 更新数据
        user.password = new_password
        try:
            db.session.commit()
        except Exception as e:
            current_app.logger.error(e)
            db.session.rollback()
            return jsonify(errno=RET.DBERR, errmsg="保存数据失败")

        return jsonify(errno=RET.OK, errmsg="保存成功")


class UserCollectionInfo(MethodView):
    decorators = [login_require, user_login_data]

    def get(self):
        user = g.user
        # 获取页数
        p = request.args.get("p", 1)
        try:
            p = int(p)
        except Exception as e:
            current_app.logger.error(e)
            p = 1

        collections = []
        current_page = 1
        total_page = 1
        try:
            # 进行分页数据查询
            paginate = user.collection_news.paginate(p, constants.USER_COLLECTION_MAX_NEWS, False)
            # 获取分页数据
            collections = paginate.items
            # 获取当前页
            current_page = paginate.page
            # 获取总页数
            total_page = paginate.pages
        except Exception as e:
            current_app.logger.error(e)

        # 收藏列表
        collection_dict_li = []
        for news in collections:
            collection_dict_li.append(news.to_basic_dict())

        data = {"total_page": total_page, "current_page": current_page, "collections": collection_dict_li}
        return render_template('news/user_collection.html', data=data)


class UserPublishInfo(MethodView):
    decorators = [login_require, user_login_data]

    def get(self):
        user = g.user
        categories = []
        try:
            # 获取所有的分类数据
            categories = Category.query.all()
        except Exception as e:
            current_app.logger.error(e)

        # 定义列表保存分类数据
        categories_dicts = []

        for category in categories:
            # 获取字典
            cate_dict = category.to_dict()
            # 拼接内容
            categories_dicts.append(cate_dict)

        # 移除`最新`分类
        categories_dicts.pop(0)
        # 返回内容
        return render_template('news/user_news_release.html', data={"categories": categories_dicts})

    def post(self):
        user = g.user
        if not user:
            return jsonify(errno=RET.SESSIONERR, errmsg="用户未登录")

        # POST 提交，执行发布新闻操作
        # 1. 获取要提交的数据
        title = request.form.get("title")
        source = "个人发布"
        digest = request.form.get("digest")
        content = request.form.get("content")
        index_image = request.files.get("index_image")
        category_id = request.form.get("category_id")
        # 1.1 判断数据是否有值
        if not all([title, source, digest, content, index_image, category_id]):
            return jsonify(errno=RET.PARAMERR, errmsg="参数有误")

        try:
            category_id = int(category_id)
        except Exception as e:
            current_app.logger.error(e)
            return jsonify(errno=RET.PARAMERR, errmsg="参数有误")

        key = "https://beishufudeyu.github.io/images/%E5%88%86%E5%B8%83%E5%BC%8F%E7%89%88%E6%9C%AC%E6%8E%A7%E5%88%B6.png"
        if index_image is not None:
            # 2. 将标题图片上传到七牛
            try:
                index_image_data = index_image.read()
                key = storage(index_image_data)
            except Exception as e:
                current_app.logger.error(e)
                return jsonify(errno=RET.THIRDERR, errmsg="上传图片错误")

        # 3. 初始化新闻模型，并设置相关数据
        news = News()
        news.title = title
        news.digest = digest
        news.source = source
        news.content = content
        if index_image:
            news.index_image_url = constants.QINIU_DOMIN_PREFIX + key
        else:
            news.index_image_url = key
        news.category_id = category_id
        news.user_id = g.user.id
        # 1代表待审核状态
        news.status = 1

        # 4. 保存到数据库
        try:
            db.session.add(news)
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(e)
            return jsonify(errno=RET.DBERR, errmsg="保存数据失败")
        # 5. 返回结果
        return jsonify(errno=RET.OK, errmsg="发布成功，等待审核")


class UserNewListInfo(MethodView):
    decorators = [login_require, user_login_data]

    def get(self):
        user = g.user

        p = request.args.get("p", 1)
        try:
            p = int(p)
        except Exception as e:
            current_app.logger.error(e)
            p = 1

        news_li = []
        current_page = 1
        total_page = 1
        try:
            paginate = News.query.filter(News.user_id == user.id).paginate(p, constants.USER_COLLECTION_MAX_NEWS, False)
            # 获取当前页数据
            news_li = paginate.items
            # 获取当前页
            current_page = paginate.page
            # 获取总页数
            total_page = paginate.pages
        except Exception as e:
            current_app.logger.error(e)

        news_dict_li = []

        for news_item in news_li:
            news_dict_li.append(news_item.to_review_dict())
        data = {"news_list": news_dict_li, "total_page": total_page, "current_page": current_page}
        return render_template('news/user_news_list.html', data=data)


class UserFollowInfo(MethodView):
    decorators = [login_require, user_login_data]

    def get(self):
        user = g.user
        # 获取页数
        p = request.args.get("p", 1)
        try:
            p = int(p)
        except Exception as e:
            current_app.logger.error(e)
            p = 1

        user = g.user

        follows = []
        current_page = 1
        total_page = 1
        try:
            paginate = user.followed.paginate(p, constants.USER_FOLLOWED_MAX_COUNT, False)
            # 获取当前页数据
            follows = paginate.items
            # 获取当前页
            current_page = paginate.page
            # 获取总页数
            total_page = paginate.pages
        except Exception as e:
            current_app.logger.error(e)

        user_dict_li = []

        for follow_user in follows:
            user_dict_li.append(follow_user.to_dict())
        data = {"users": user_dict_li, "total_page": total_page, "current_page": current_page}
        return render_template('news/user_follow.html', data=data)


class UserOtherInfo(MethodView):
    decorators = [login_require, user_login_data]

    def get(self):
        user = g.user
        """查看其他用户信息"""
        # 获取其他用户id
        user_id = request.args.get("id")
        if not user_id:
            abort(404)
        # 查询用户模型
        other = None
        try:
            other = User.query.get(user_id)
        except Exception as e:
            current_app.logger.error(e)
        if not other:
            abort(404)

        # 判断当前登录用户是否关注过该用户
        is_followed = False
        if g.user:
            if other.followers.filter(User.id == user.id).count() > 0:
                is_followed = True

        # 组织数据，并返回
        data = {
            "user_info": user.to_dict(),
            "other_info": other.to_dict(),
            "is_followed": is_followed
        }
        return render_template('news/other.html', data=data)


class OtherUserNewsInfo(MethodView):
    decorators = [user_login_data, ]

    def get(self):
        # 获取页数
        p = request.args.get("p", 1)
        user_id = request.args.get("user_id")
        try:
            p = int(p)
        except Exception as e:
            current_app.logger.error(e)
            return jsonify(errno=RET.PARAMERR, errmsg="参数错误")

        if not all([p, user_id]):
            return jsonify(errno=RET.PARAMERR, errmsg="参数错误")

        try:
            user = User.query.get(user_id)
        except Exception as e:
            current_app.logger.error(e)
            return jsonify(errno=RET.DBERR, errmsg="数据查询错误")

        if not user:
            return jsonify(errno=RET.NODATA, errmsg="用户不存在")

        try:
            paginate = News.query.filter(News.user_id == user.id).paginate(p, constants.OTHER_NEWS_PAGE_MAX_COUNT,
                                                                           False)
            # 获取当前页数据
            news_li = paginate.items
            # 获取当前页
            current_page = paginate.page
            # 获取总页数
            total_page = paginate.pages
        except Exception as e:
            current_app.logger.error(e)
            return jsonify(errno=RET.DBERR, errmsg="数据查询错误")

        news_dict_li = []

        for news_item in news_li:
            news_dict_li.append(news_item.to_review_dict())
        data = {"news_list": news_dict_li, "total_page": total_page, "current_page": current_page}
        return jsonify(errno=RET.OK, errmsg="OK", data=data)
