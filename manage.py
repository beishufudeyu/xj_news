from flask_script import Manager
from flask_migrate import Migrate, MigrateCommand
from apps import create_app, db

# 创建 app，并传入配置模式：development / production / testing
app = create_app('development')

# 用Manager管理项目
manager = Manager(app)

# 添加数据库迁移命令集成
Migrate(app, db)
manager.add_command('db', MigrateCommand)

if __name__ == '__main__':
    manager.run()
