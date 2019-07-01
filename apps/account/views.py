from apps import redis_store
from flask import request, abort
from apps.utils.captcha.captcha import captcha
from apps import constants
from flask import current_app, make_response


def get_image_code():
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
