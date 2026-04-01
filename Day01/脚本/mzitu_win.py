# -*- coding: utf-8 -*-
#!/usr/bin/python

import random
import time
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# 越多越好：用来轮换 User-Agent
MEIZI_HEADERS = [
    "Mozilla/5.0 (Windows NT 6.3; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.95 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_9_2) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/35.0.1916.153 Safari/537.36",
    "Mozilla/5.0 (Windows NT 6.1; WOW64; rv:30.0) Gecko/20100101 Firefox/30.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_9_2) AppleWebKit/537.75.14 (KHTML, like Gecko) Version/7.0.3 Safari/537.75.14",
    "Mozilla/5.0 (compatible; MSIE 10.0; Windows NT 6.2; Win64; x64; Trident/6.0)",
    "Mozilla/5.0 (Windows; U; Windows NT 5.1; it; rv:1.8.1.11) Gecko/20071127 Firefox/2.0.0.11",
    "Opera/9.25 (Windows NT 5.1; U; en)",
    "Mozilla/4.0 (compatible; MSIE 6.0; Windows NT 5.1; SV1; .NET CLR 1.1.4322; .NET CLR 2.0.50727)",
    "Mozilla/5.0 (compatible; Konqueror/3.5; Linux) KHTML/3.5.5 (like Gecko) (Kubuntu)",
    "Mozilla/5.0 (X11; U; Linux i686; en-US; rv:1.8.0.12) Gecko/20070731 Ubuntu/dapper-security Firefox/1.5.0.12",
    "Lynx/2.8.5rel.1 libwww-FM/2.14 SSL-MM/1.4.1 GNUTLS/1.2.9",
    "Mozilla/5.0 (X11; Linux i686) AppleWebKit/535.7 (KHTML, like Gecko) Ubuntu/11.04 Chromium/16.0.912.77 Chrome/16.0.912.77 Safari/535.7",
    "Mozilla/5.0 (X11; Ubuntu; Linux i686; rv:10.0) Gecko/20100101 Firefox/10.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/54.0.2840.99 Safari/537.36",
]

# 你之前的 `mzitu.com` 站点可能不可用了。
# 这里改为 Picsum（占位图片服务），提供稳定的 JSON 列表接口：/v2/list
PICSUM_BASE = "https://picsum.photos"
PICSUM_LIST_ENDPOINT = "https://picsum.photos/v2/list"

# 定义存储位置（按你的需要修改）
SAVE_PATH = Path("E:/BeautifulPictures")

DEFAULT_TIMEOUT = (5, 20)  # (连接超时, 读取超时)

# 下载配置
PAGES = 100          # 抓取多少个列表页（先小量验证是否通）
LIMIT_PER_PAGE = 10
DELAY_SECONDS = (0.8, 2.0)  # 每张图片之间随机等待，降低触发频率

# 构建会话
def build_session() -> requests.Session:
    session = requests.Session()

    # 让 session 自动做重试：网络抖动时不至于直接挂掉
    retry = Retry(
        total=5,
        connect=5,
        read=5,
        backoff_factor=0.8,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET", "HEAD"),
        raise_on_status=False,
    )
    # 挂载适配器
    adapter = HTTPAdapter(max_retries=retry)
    # 挂载适配器
    session.mount("http://", adapter)
    # 挂载适配器
    session.mount("https://", adapter)
    # 更新请求头
    session.headers.update({"User-Agent": random.choice(MEIZI_HEADERS)})
    return session

# 确保目录存在
def ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)

# 下载文件
def download_to_file(
    session: requests.Session,
    url: str,
    out_file: Path,
    referer: str,
) -> bool:
    # 如果文件已存在，跳过可大幅减少重复下载
    if out_file.exists() and out_file.stat().st_size > 0:
        return True

    # 更新请求头
    headers = {
        "User-Agent": random.choice(MEIZI_HEADERS),
        "Referer": referer,
    }

    # 确保目录存在
    out_file.parent.mkdir(parents=True, exist_ok=True)

    # stream=True 避免一次性把大文件读进内存
    with session.get(url, headers=headers, timeout=DEFAULT_TIMEOUT, stream=True) as r:
        r.raise_for_status()
        with open(out_file, "wb") as f:
            for chunk in r.iter_content(chunk_size=1024 * 64):
                if chunk:
                    f.write(chunk)

    return True

# 获取列表
def fetch_picsum_list(session: requests.Session, page: int, limit: int) -> list[dict]:
    params = {"page": page, "limit": limit}
    r = session.get(PICSUM_LIST_ENDPOINT, params=params, timeout=DEFAULT_TIMEOUT)
    r.raise_for_status()
    return r.json()

# 主函数
def main() -> None:
    session = build_session()
    ensure_dir(SAVE_PATH)
    # 打印开始下载
    print(f"Start downloading: {PICSUM_LIST_ENDPOINT} (PAGES={PAGES}, LIMIT_PER_PAGE={LIMIT_PER_PAGE})")
    # 遍历页码
    for i in range(1, PAGES + 1):
        out_dir = SAVE_PATH / f"page_{i}"
        ensure_dir(out_dir)
        # 获取列表
        try:
            items = fetch_picsum_list(session, page=i, limit=LIMIT_PER_PAGE)
        except Exception as e:
            # 打印获取列表失败
            print("Failed to fetch list. page=", i, "|", e)
            continue

        if not items:   
            # 打印列表为空
            print("Empty list. page=", i)
            continue

        # 打印列表页码和数量
        print("List page:", i, "items:", len(items))
        # 遍历列表
        for idx, item in enumerate(items, start=1):
            # Picsum 的返回一般包含：id、width、height、download_url 等字段
            img_id = str(item.get("id", idx))
            width = item.get("width", "")
            height = item.get("height", "")
            download_url = item.get("download_url")

            if not download_url:
                print("Missing download_url, skip:", img_id)
                continue

            # 以 id + 分辨率命名，避免覆盖
            suffix = "jpg"
            out_file = out_dir / f"{img_id}_{width}x{height}.{suffix}"

            time.sleep(random.uniform(*DELAY_SECONDS))
            try:
                print("Downloading:", out_file.name)
                download_to_file(
                    session=session,
                    url=download_url,
                    out_file=out_file,
                    referer=PICSUM_BASE,
                )
            except Exception as e:
                print("Download failed:", out_file.name, "|", e)


if __name__ == "__main__":
    main()
