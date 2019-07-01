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
    print(secret_key)
    return secret_key


if __name__ == '__main__':
    manager.run()
