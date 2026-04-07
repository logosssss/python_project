#!/usr/bin/python3

# PyMySQL 是在 Python3.x 版本中用于连接 MySQL 服务器的一个库，Python2中则使用mysqldb。
import pymysql


def get_connection():
    """
    创建并返回一个到 MySQL 的连接。
    方便在其他模块里复用。
    """
    return pymysql.connect(
        host="",
        user="",
        password="",
        database="python_test",
        charset="utf8mb4",
    )


def test_connection():
    """
    简单的启动测试：
    - 连接数据库
    - 查询 seckill 表前几条记录
    - 打印结果
    """
    db = get_connection()
    print("DB connection opened:", db)

    try:
        cursor = db.cursor()
        cursor.execute("SELECT * FROM seckill LIMIT 5")
        data = cursor.fetchall()

        print("Query result (first 5 rows):")
        for row in data:
            print(row)
    finally:
        db.close()
        print("DB connection closed.")


if __name__ == "__main__":
    # 直接运行 PyMySQL.py 时，执行一次连通性测试
    test_connection()
