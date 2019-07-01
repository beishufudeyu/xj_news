from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from redis import StrictRedis
from flask_wtf.csrf import CSRFProtect
from flask_session import Session
from config import config
import logging
from logging.handlers import RotatingFileHandler

# 初始化db对象,flask扩展中基本上都有init_app()函数去初始化app
db = SQLAlchemy()

# redis_store = None  # type: StrictRedis
redis_store: StrictRedis = None


def setup_log(log_level):
    """配置日志"""

    # 设置日志的记录等级
    logging.basicConfig(level=log_level)  # 调试debug级
    # 创建日志记录器，指明日志保存的路径、每个日志文件的最大大小、保存的日志文件个数上限
    file_log_handler = RotatingFileHandler("logs/log", maxBytes=1024 * 1024 * 100, backupCount=10)
    # 创建日志记录的格式 日志等级 输入日志信息的文件名 行数 日志信息
    formatter = logging.Formatter('%(levelname)s %(filename)s:%(lineno)d %(message)s')
    # 为刚创建的日志记录器设置日志记录格式
    file_log_handler.setFormatter(formatter)
    # 为全局的日志工具对象（flask app使用的）添加日志记录器
    logging.getLogger().addHandler(file_log_handler)


def create_app(config_name):
    """通过传入不同的配置名字，初始化其对应配置的应用实例"""

    app = Flask(__name__)

    log_level = config[config_name].LOG_LEVEL

    # 配置项目日志
    setup_log(log_level)

    # 配置
    app.config.from_object(config[config_name])
    # 配置数据库
    db.init_app(app)
    # 配置redis
    global redis_store
    redis_store = StrictRedis(host=config[config_name].REDIS_HOST, port=config[config_name].REDIS_PORT,
                              decode_responses=False)
    # 开启csrf保护
    CSRFProtect(app)
    # 设置session保存位置
    Session(app)

    from .account import account_app
    app.register_blueprint(account_app, url_prefix="/user")

    from .news import news_app
    app.register_blueprint(news_app)

    return app
