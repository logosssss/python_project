"""
兼容 MySQL 5.7 的 Django 数据库后端。

Django 4.2 自带的 django.db.backends.mysql 将最低版本设为 MySQL 8，
连接 5.7 时会报 NotSupportedError。此处继承官方后端，仅去掉该版本下限检查。

若已升级到 MySQL 8+，可把 settings 里 ENGINE 改回 django.db.backends.mysql。
"""
from django.db.backends.mysql.base import DatabaseWrapper as MySQLDatabaseWrapper
from django.db.backends.mysql import features as mysql_features
from django.utils.functional import cached_property


class DatabaseFeatures(mysql_features.DatabaseFeatures):
    @cached_property
    def minimum_database_version(self):
        return None


class DatabaseWrapper(MySQLDatabaseWrapper):
    features_class = DatabaseFeatures
