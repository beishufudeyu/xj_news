import redis
import logging


class Config(object):
    """工程基础配置信息"""

    # 数据库配置
    SQLALCHEMY_DATABASE_URI = "mysql+pymysql://root:120609@192.168.132.11:3306/news_finance"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    # 实现请求结束之后进行数据自动提交
    SQLALCHEMY_COMMIT_ON_TEARDOWN = True

    SECRET_KEY = "j8sqO4p5k41mpKAAOPx0xdS2ig1kmtwSJzoCZPVOG3FKc4Kyqz1JEeG3I5BzKq94"
    # redis配置
    REDIS_HOST = "192.168.132.13"
    REDIS_PORT = 16379

    # flask_session的配置信息
    # 指定 session 保存到 redis 中
    SESSION_TYPE = "redis"
    # 让 cookie 中的 session_id 被加密签名处理
    SESSION_USE_SIGNER = True
    # 使用 redis 的实例
    SESSION_REDIS = redis.StrictRedis(host=REDIS_HOST, port=REDIS_PORT)
    # session 的有效期，单位是秒(1天)
    PERMANENT_SESSION_LIFETIME = 86400

    # 默认日志等级
    LOG_LEVEL = logging.DEBUG


class DevelopementConfig(Config):
    """开发模式下的配置"""
    DEBUG = True


class ProductionConfig(Config):
    """生产模式下的配置"""
    DEBUG = False
    """生产模式下的配置"""
    LOG_LEVEL = logging.ERROR


class TestingConfig(Config):
    """生产模式下的配置"""
    DEBUG = True
    TESTING = True


# 定义配置字典
config = {
    "development": DevelopementConfig,
    "production": ProductionConfig,
    'testing': TestingConfig
}
