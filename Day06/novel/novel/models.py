# coding:utf-8
from django.db import models


class Article(models.Model):
    """
    与 view 中 raw SQL 使用的表 `novel`（id, title, content）一致。
    """

    title = models.CharField("标题", max_length=256)
    content = models.TextField("内容", blank=True)

    class Meta:
        db_table = "novel"
        # 表已由业务/SQL 创建时设为 False，避免 migrate 再执行 CREATE TABLE
        managed = False

