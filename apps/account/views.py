from apps import redis_store, db
from flask import request, abort
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
        # try:
        #     db.session.commit()
        # except Exception as e:
        #     current_app.logger.error(e)
        # 5. 登录成功
        return jsonify(errno=RET.OK, errmsg="OK")


def logout():
    """
    清除session中的对应登录之后保存的信息
    :return:
    """
    session.pop('user_id', None)
    session.pop('nick_name', None)
    session.pop('mobile', None)

    # 返回结果
    return jsonify(errno=RET.OK, errmsg="OK")
