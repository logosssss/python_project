# 使用 PyMySQL 冒充 MySQLdb，供 Django ORM 连接 MySQL
try:
    import pymysql

    pymysql.install_as_MySQLdb()
except ImportError:
    pass
