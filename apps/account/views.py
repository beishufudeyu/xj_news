from apps import redis_store
from flask import request, abort
from apps.utils.captcha.captcha import captcha
from apps import constants
from flask import current_app, make_response, jsonify
from flask.views import MethodView
from apps.utils.response_code import RET
import re
import random
from apps.libs.yuntongxun.sms import CCP


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

        # 3. 从redis去去取图片验证码的text对比用户传来的是否一致
        try:
            real_image_code = redis_store.get("imageCodeId:" + image_uuid)
        except Exception as e:
            current_app.logger.error("redis获取图片验证码错误:" + str(e))
            return jsonify(errno=RET.DBERR, errmsg="数据查询失败")

        if not real_image_code:
            return jsonify(errno=RET.NODATA, errmsg="图片验证码已过期")

        # 4. 与用户传来的数据进行对比
        if image_code.lower() != real_image_code.lower():
            return jsonify(errno=RET.NODATA, errmsg="图片验证码已过期")

        # 5. 生成验证码的内容(随机数据)
        sms_code = "%06d" % random.randint(0, 999999)

        # 6. 发送手机验证码
        result = CCP.send_template_sms(phone, [sms_code, constants.SMS_CODE_REDIS_EXPIRES / 60], 1)

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
