from flask_script import Manager
from flask_migrate import Migrate, MigrateCommand
from apps import create_app, db
import os
import base64

# 创建 app，并传入配置模式：development / production / testing
app = create_app('development')

# 用Manager管理项目
manager = Manager(app)

# 添加数据库迁移命令集成
Migrate(app, db)
manager.add_command('db', MigrateCommand)


@manager.command
def generate_secret_key(length=48):
    key = os.urandom(length)
    secret_key = base64.b64encode(key)
    return secret_key


@manager.option('-n', '-name', dest="username")
@manager.option('-p', '-password', dest="password")
def createsuperuser(username, password):
    if not all([username, password]):
        print("参数不足,请指定用户名和密码")
    from apps.account.models import User
    user = User()
    user.nick_name = username
    user.mobile = username
    user.password = password
    user.is_admin = True
    try:
        db.session.add(user)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print(e)
    return "添加成功"


if __name__ == '__main__':
    manager.run()
