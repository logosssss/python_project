#!/usr/bin/python3
# mysql-connector 是 MySQL 官方提供的驱动器。
import mysql.connector  # pyright: ignore[reportMissingImports]


def get_connection():
    """
    创建并返回一个到 MySQL 的连接。
    方便在其他模块里复用。
    """
    return mysql.connector.connect(
        host="39.108.59.205",
        user="jp",
        password="jp2016JP",  # 官方驱动推荐使用 password 参数名
        database="python_test",
    )


def test_connection():
    """
    简单的启动测试：
    - 连接数据库
    - 查询 seckill 表前几条记录
    - 打印结果
    """
    db = get_connection()
    print("DB connection opened (mysql-connector):", db)

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
    # 直接运行 MySqlConnector.py 时，执行一次连通性测试
    test_connection()