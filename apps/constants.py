import os

# 图片验证码Redis有效期， 单位：秒
IMAGE_CODE_REDIS_EXPIRES = 300

YUNTONGXIN_ACCOUNTSID = os.getenv("YUNTONGXIN_ACCOUNTSID", None)
# 说明：主账号，登陆云通讯网站后，可在"控制台-应用"中看到开发者主账号ACCOUNT SID

# 说明：主账号Token，登陆云通讯网站后，可在控制台-应用中看到开发者主账号AUTH TOKEN
YUNTONGXIN_ACCOUNTTOEKN = os.getenv("YUNTONGXIN_ACCOUNTTOEKN", None)

# 请使用管理控制台首页的APPID或自己创建应用的APPID
YUNTONGXIN_APPID = os.getenv("YUNTONGXIN_APPID", None)

# 短信验证码Redis有效期，单位：秒
SMS_CODE_REDIS_EXPIRES = 300

# 七牛空间域名
QINIU_DOMIN_PREFIX = "http://oyucyko3w.bkt.clouddn.com/"

# 首页展示最多的新闻数量
HOME_PAGE_MAX_NEWS = 10

# 用户的关注每一页最多数量
USER_FOLLOWED_MAX_COUNT = 4

# 用户收藏最多新闻数量
USER_COLLECTION_MAX_NEWS = 10

# 其他用户每一页最多新闻数量
OTHER_NEWS_PAGE_MAX_COUNT = 10

# 点击排行展示的最多新闻数据
CLICK_RANK_MAX_NEWS = 10

# 管理员页面用户每页多最数据条数
ADMIN_USER_PAGE_MAX_COUNT = 10

# 管理员页面新闻每页多最数据条数
ADMIN_NEWS_PAGE_MAX_COUNT = 10
