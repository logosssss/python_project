# Python3 + Django 开发一个 Web 项目（Day06 小说示例）

## 1. 环境准备

```bash
cd E:\Python\Day06\novel
python -m pip install -r requirements.txt
```

依赖说明：

| 包 | 作用 |
|----|------|
| Django | Web 框架 |
| PyMySQL | MySQL 驱动（配合 `mysqlclient` 二选一即可） |
| DBUtils | 连接池；**DBUtils 3.x** 使用 `from dbutils.pooled_db import PooledDB`（包名小写 `dbutils`） |
| numpy | `utils/encoder.py` 若需序列化 `numpy.ndarray` 时使用（未安装时 encoder 仍支持 `bytes`） |

**必须在含 `requirements.txt` 的目录执行安装**，否则会报 `Could not open requirements file`：

```bash
cd E:\Python\Day06\novel
python -m pip install -r requirements.txt
```

若在仓库根目录 `E:\Python` 安装，请写：

```bash
python -m pip install -r Day06/novel/requirements.txt
```

### 常见导入报错

| 报错 | 处理 |
|------|------|
| `No module named 'DBUtils'` | 安装 `DBUtils` 后应使用 `from dbutils.pooled_db import PooledDB`（代码已兼容）；执行 `python -m pip install DBUtils` |
| `No module named 'django'` | `python -m pip install Django` |
| `No module named 'numpy'` | `python -m pip install numpy` 或安装完整 `requirements.txt` |
| 确认用的是否为同一 Python | 运行 `where python` / `python -V`，在 IDE 里选对解释器 |

创建项目与应用（你已建好时可跳过）：

```bash
django-admin startproject novel .
python manage.py startapp novel
```

> 当前 `Day06/novel` 目录结构是「外层工程目录 + 内层包名也叫 `novel`」，与教程里写的 `itstyle` 只是命名不同，原理一致。

## 2. 推荐目录结构（与代码一致）

```
novel/                    # 工程根（含 manage.py）
├── manage.py
├── requirements.txt
├── novel/                # Django 项目包（settings / urls / models）
│   ├── settings.py
│   ├── urls.py
│   ├── models.py
│   ├── admin.py
│   ├── wsgi.py
│   └── migrations/
├── templates/            # 模板（settings 里 DIRS 指向这里）
│   ├── novel_list.html
│   └── novel.html
├── utils/
│   ├── dbMysqlConfig.cnf # 连接池读的配置（勿提交含真实密码到公开仓库）
│   ├── mysql_DBUtils.py
│   └── encoder.py
└── view/
    └── index.py          # 视图（业务）
```

说明：`templates`、`view`、`utils` 与内层 `novel` 包并列，由 `settings.BASE_DIR` 与 `sys.path`（`manage.py` 所在目录）解析 `from view import index`。

## 3. 启动与检查

```bash
python manage.py check          # 系统检查，应无报错
python manage.py runserver      # 默认 http://127.0.0.1:8000/
python manage.py runserver 8001 # 端口被占用时换端口
```

数据库（MySQL）需已创建库、表，且 `utils/dbMysqlConfig.cnf` 与 `novel/settings.py` 中 `DATABASES` 一致。表 `novel` 至少包含视图里用到的字段：`id, title, content`。

```bash
python manage.py migrate        # 若使用 Django ORM / Admin，需执行迁移
```

## 4. URL 与视图（path，兼容 Django 4+）

**不要**再使用已移除的 `django.conf.urls.url`（Django 4.1+ 已删）。统一用 `path` / `re_path`：

```python
from django.urls import path
from django.contrib import admin
from view import index

urlpatterns = [
    path('', index.main, name='novel_home'),
    path('admin/', admin.site.urls),
    path('chapter/<int:novel_id>/', index.chapter, name='chapter'),
]
```

模板里链接推荐用**命名 URL**，避免手写路径写错或多余空格：

```django
<a href="{% url 'chapter' novel.id %}">{{ novel.title }}</a>
```

对应视图：`chapter(request, novel_id)` 中的参数名需与 `<int:novel_id>` 一致。

## 5. 配置项易错点

### 5.1 `settings.DATABASES`

- 端口关键字是 **`PORT`**，不要写成 `POST`（拼写错误会导致连库异常）。
- 使用 PyMySQL 时通常在**项目 `__init__.py`** 或 `manage.py` 同级的 `novel/__init__.py` 里执行：

  ```python
  import pymysql
  pymysql.install_as_MySQLdb()
  ```

  （若你当前环境已能连库，可保持现有方式。）

### 5.2 连接池模块

- DBUtils 3.x：`from dbutils.pooled_db import PooledDB`
- 连接池单例应赋值给**类变量** `MyPymysqlPool.__pool`，避免每取一次连接都新建池。

### 5.3 不要在 import 时就连数据库

`mysql_DBUtils` 里使用**懒加载**包装器，在第一次执行 `mysql.getAll()` 等时才创建连接池；这样在未启动 MySQL 时仍可执行 `manage.py check`、`makemigrations`。

## 6. 视图与模板注意点

- 本项目里 `mysql.getAll` / `getOne` 在无数据时可能返回 **`False`**，模板 `{% for %}` 需要列表，视图中应转为 `result or []`。
- 章节页若查无记录，应返回 404 或友好提示，避免 `novel.title` 访问 `False` 报错。
- 若数据库字段为 `bytes`，需在视图中 `.decode('utf-8')`（本项目已做兼容）。

## 7. 后台 Admin

模型注册在 **`novel/admin.py`**（与应用同包）。不要放在 `view/admin.py`，Django 不会自动加载 `view` 包下的 `admin`。

## 8. 本项目已修复问题小结

| 问题 | 处理 |
|------|------|
| `ImportError: cannot import name 'url' from 'django.conf.urls'` | 去掉 `url`，仅用 `path` |
| `settings` 里 `POST` 误写 | 改为 `PORT` |
| `ModuleNotFoundError: DBUtils` | 使用 `dbutils.pooled_db`；并安装 `requirements.txt` |
| 连接池未复用 | `MyPymysqlPool.__pool = PooledDB(...)` |
| `import` 即连 MySQL 导致 `check` 失败 | `mysql` 改为懒加载代理 |
| 列表页链接多余空格、非 reverse | 使用 `{% url 'chapter' novel.id %}` |
| 空查询 / 无章节 | 视图做空数据与 404 处理 |
| `models.W042` | `DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'` |

## 9. RESTful 风格（说明）

路由使用路径参数 `chapter/<int:novel_id>/` 即符合常见 REST 风格的一种实践；严格 REST 还会约定资源名、HTTP 方法等，学习阶段掌握「路径参数 + 视图函数入参」即可。
