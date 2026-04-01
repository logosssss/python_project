# -*- coding: utf-8 -*-
"""
新笔趣阁 xbiquge.la 抓取示例。

- 单本：指定 BOOK_INDEX，只下这一本书。
- 全站（按站点「分类分页」尽量扫全）：边翻 fenlei 列表页边解析出书目录，**立刻下载**该书全部章节（全局去重，同一本书多页重复出现只下一次）。

注意：全量抓取会对目标站产生大量请求，请自行遵守法律法规与站点服务条款，仅建议学习/调试时使用，
并适当调大延时、加 --max-books 做小规模试验。
"""
from __future__ import annotations

import argparse
import json
import os
import random
import re
import time
from pathlib import Path
from urllib.parse import urljoin, urlparse

import codecs
import requests
from bs4 import BeautifulSoup

BASE = "http://www.xbiquge.la/"
# 单本书目录页示例（--mode single 时使用）
BOOK_INDEX = "http://www.xbiquge.la/5/5623/"
# 全站时，每本书保存在该目录下：SAVE_ROOT / {slug} /
SAVE_ROOT = Path("E:/xbiquge_books")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/54.0.2840.99 Safari/537.36"
    ),
    "Referer": BASE,
}

REQUEST_TIMEOUT = 20
# 章节之间随机等待（秒）
DELAY_CHAPTER = (0.4, 1.2)
# 两本书之间额外等待（秒）
DELAY_BOOK = (1.0, 3.0)
# 拉列表页之间等待（秒）
DELAY_LIST_PAGE = (0.5, 1.5)

# 实测分类 id 1～7 有效，8 起为 404
DEFAULT_FENLEI_CATEGORIES = list(range(1, 8))

STATE_FILE = Path(__file__).resolve().parent / "book_crawl_state.json"

# 用于在「整页 HTML」里判断是否存在章节式链接（不能用 ^...$ 只匹配单个 href）
FENLEI_PAGE_CHAPTER_HINT = re.compile(r"/\d+/\d+/\d+\.html", re.I)


def fetch_html(session: requests.Session, url: str) -> str:
    r = session.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
    r.raise_for_status()
    r.encoding = r.apparent_encoding or "utf-8"
    return r.text


def chapter_href_pattern():
    # /128/128223/56762546.html
    return re.compile(r"^/?(\d+)/(\d+)/(\d+)\.html$", re.I)


def book_url_from_chapter_href(href: str, base: str = BASE) -> str | None:
    href = href.strip()
    m = chapter_href_pattern().match(href)
    if not m:
        return None
    a, b, _ = m.groups()
    return urljoin(base, f"/{a}/{b}/")


def book_urls_from_listing_page(html: str, page_url: str) -> set[str]:
    """从分类列表、首页等页面中，根据章节链接反推书籍目录 URL。"""
    out: set[str] = set()
    for m in re.finditer(
        r'href=["\'](/\d+/\d+/\d+\.html)["\']',
        html,
        re.I,
    ):
        bu = book_url_from_chapter_href(m.group(1), base=page_url)
        if bu:
            out.add(bu)
    soup = BeautifulSoup(html, "html.parser")
    host = urlparse(BASE).netloc
    for a in soup.find_all("a", href=True):
        full = urljoin(page_url, a["href"].strip())
        if urlparse(full).netloc != host:
            continue
        path = urlparse(full).path
        m2 = re.match(r"/(\d+)/(\d+)/(\d+)\.html$", path, re.I)
        if m2:
            out.add(urljoin(BASE, f"/{m2.group(1)}/{m2.group(2)}/"))
    return out


def book_id_slug(book_url: str) -> str:
    """由 URL 路径生成的 id，如 /0/57/ -> 0_57（仅数字，不是书名）。"""
    path = urlparse(book_url).path.strip("/")
    return path.replace("/", "_") if path else "unknown"


def book_title_from_index_html(html: str) -> str | None:
    """从小说目录页 HTML 里解析书名（站点结构变化时可能需再改选择器）。"""
    soup = BeautifulSoup(html, "html.parser")
    h1 = soup.find("h1")
    if h1:
        t = h1.get_text(strip=True)
        if t and len(t) < 200:
            return t
    meta = soup.find("meta", property="og:title")
    if meta and meta.get("content"):
        c = meta["content"].strip()
        if c:
            return c
    meta2 = soup.find("meta", attrs={"name": "keywords"})
    if meta2 and meta2.get("content"):
        # 有的站 keywords 第一个是书名
        kw = meta2["content"].split(",")[0].strip()
        if kw and len(kw) < 80:
            return kw
    t_el = soup.find("title")
    if t_el:
        text = t_el.get_text(strip=True)
        for sep in (" - ", "——", "_", "|"):
            if sep in text:
                return text.split(sep)[0].strip()
        return text
    return None


def sanitize_dir_name(name: str) -> str:
    """Windows 目录名非法字符去掉，并限制长度。"""
    s = re.sub(r'[<>:"/\\|?*\n\r\t]', "_", name.strip())
    s = re.sub(r"_+", "_", s).strip(" .")
    if len(s) > 100:
        s = s[:100].rstrip()
    return s


def resolve_book_folder_name(
    save_root: Path,
    book_url: str,
    index_html: str,
    folder_by_id: bool,
) -> str:
    """
    决定磁盘上的书籍文件夹名。
    - folder_by_id=True：始终用 URL 数字 id（如 0_57）。
    - 否则：优先用书名号；解析不到则退回 id。
    同名目录若已是本书（见 .book_source_url），继续用该名；否则加 _id 区分不同书。
    """
    bid = book_id_slug(book_url)
    if folder_by_id:
        return bid
    title = book_title_from_index_html(index_html)
    base = sanitize_dir_name(title) if title else ""
    if not base:
        return bid
    target = save_root / base
    marker = target / ".book_source_url"
    if target.is_dir():
        try:
            if marker.is_file() and marker.read_text(encoding="utf-8").strip() == book_url:
                return base
        except OSError:
            pass
        if base != bid:
            return f"{base}_{bid}"
        return bid
    return base


BOOK_URL_MARKER = ".book_source_url"


def chapter_links_from_index(html: str, index_url: str) -> list[tuple[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    list_div = soup.find("div", id="list")
    if not list_div:
        return []

    book_path = urlparse(index_url).path.rstrip("/")
    seen: set[str] = set()
    out: list[tuple[str, str]] = []

    for a in list_div.find_all("a", href=True):
        href = a["href"].strip()
        if not href or href.startswith("javascript:"):
            continue
        full = urljoin(index_url, href)
        path = urlparse(full).path
        if book_path and not path.startswith(book_path + "/"):
            continue
        if full in seen:
            continue
        seen.add(full)
        title = (a.get_text(strip=True) or "untitled").replace("?", "").replace("/", "_")
        if not title:
            continue
        out.append((title, full))

    return out


def get_chapter_content(session: requests.Session, chapter_url: str) -> str:
    html = fetch_html(session, chapter_url)
    soup = BeautifulSoup(html, "html.parser")
    divs = soup.find_all("div", id="content")
    if not divs:
        return ""
    text = divs[0].get_text()
    return text.replace("\xa0" * 4, "\n").strip()


def write_txt(path: Path, content: str, encoding: str = "utf-8") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with codecs.open(path, "w", encoding=encoding) as f:
        f.write(content)


def load_state() -> set[str]:
    if not STATE_FILE.is_file():
        return set()
    try:
        data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        return set(data.get("done_books", []))
    except (json.JSONDecodeError, OSError):
        return set()


def save_state(done: set[str]) -> None:
    STATE_FILE.write_text(
        json.dumps({"done_books": sorted(done)}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def download_one_book(
    session: requests.Session,
    book_url: str,
    save_dir: Path,
    *,
    index_html: str | None = None,
) -> None:
    save_dir.mkdir(parents=True, exist_ok=True)
    marker = save_dir / BOOK_URL_MARKER
    try:
        if not marker.is_file():
            marker.write_text(book_url.strip(), encoding="utf-8")
    except OSError:
        pass
    print("  目录页:", book_url)
    if index_html is None:
        index_html = fetch_html(session, book_url)
    chapters = chapter_links_from_index(index_html, book_url)
    print("  章节数:", len(chapters))

    for i, (title, url) in enumerate(chapters, 1):
        try:
            safe_title = re.sub(r'[<>:"/\\|?*]', "_", title)
            out_path = save_dir / f"{safe_title}.txt"
            if out_path.is_file() and out_path.stat().st_size > 0:
                continue
            body = get_chapter_content(session, url)
            if not body:
                print(f"    [{i}/{len(chapters)}] 跳过(无正文): {title}")
                continue
            print(f"    [{i}/{len(chapters)}] {title}")
            write_txt(out_path, body + "\n", "utf-8")
        except Exception as e:
            print(f"    [{i}/{len(chapters)}] 错误 {title}: {e}")
        time.sleep(random.uniform(*DELAY_CHAPTER))


def crawl_fenlei_streaming_download(
    session: requests.Session,
    save_root: Path,
    categories: list[int],
    max_pages_per_category: int,
    empty_page_limit: int,
    max_books: int,
    use_state: bool,
    done: set[str],
    folder_by_id: bool,
) -> int:
    """
    边翻 fenlei 分页边下载：每页解析出的书目录 URL，若全局未见则立即 download_one_book。
    返回本轮已计入「开始下载」的书本数（--use-state 下跳过已记录的不计入；单本失败仍会计数）。
    """
    seen_books: set[str] = set()
    downloaded_count = 0

    def reached_limit() -> bool:
        return bool(max_books) and downloaded_count >= max_books

    for cat in categories:
        if reached_limit():
            break
        print(f"\n=== 分类 fenlei/{cat}_*.html（边翻边下）===")
        empty_run = 0
        for page in range(1, max_pages_per_category + 1):
            if reached_limit():
                print(f"已达 --max-books={max_books}，停止")
                break
            list_url = urljoin(BASE, f"fenlei/{cat}_{page}.html")
            try:
                time.sleep(random.uniform(*DELAY_LIST_PAGE))
                html = fetch_html(session, list_url)
            except requests.HTTPError as e:
                if e.response is not None and e.response.status_code == 404:
                    print(f"  页 {page}: 404，结束该分类")
                    break
                print(f"  页 {page}: HTTP 错误 {e}，跳过")
                empty_run += 1
                if empty_run >= empty_page_limit:
                    break
                continue
            except OSError as e:
                print(f"  页 {page}: 请求失败 {e}")
                empty_run += 1
                if empty_run >= empty_page_limit:
                    break
                continue

            if not FENLEI_PAGE_CHAPTER_HINT.search(html):
                empty_run += 1
                print(f"  页 {page}: 无章节链接模式，empty_run={empty_run}")
                if empty_run >= empty_page_limit:
                    break
                continue

            empty_run = 0
            found = book_urls_from_listing_page(html, list_url)
            to_try = [u for u in sorted(found) if u not in seen_books]
            for u in to_try:
                seen_books.add(u)

            started_this_page = 0
            skipped_done = 0
            skipped_dup = len(found) - len(to_try)

            hit_limit = False
            for book_url in to_try:
                if reached_limit():
                    print(f"已达 --max-books={max_books}，停止")
                    hit_limit = True
                    break
                if use_state and book_url in done:
                    skipped_done += 1
                    continue

                index_html = fetch_html(session, book_url)
                folder_name = resolve_book_folder_name(
                    save_root, book_url, index_html, folder_by_id
                )
                book_dir = save_root / folder_name
                downloaded_count += 1
                started_this_page += 1
                print(
                    f"\n>>> 第 {downloaded_count} 本（列表页 cat={cat} p={page}） "
                    f"{folder_name}"
                )
                try:
                    download_one_book(
                        session, book_url, book_dir, index_html=index_html
                    )
                except Exception as e:
                    print(f"  本书失败: {e}")

                if use_state:
                    done.add(book_url)
                    save_state(done)

                time.sleep(random.uniform(*DELAY_BOOK))

            print(
                f"  页 {page}: 本页链接 {len(found)} 本，"
                f"新 ID {len(to_try)}，跳过重复 {skipped_dup}，"
                f"跳过已记录 {skipped_done}，本页开始下载 {started_this_page} 本，"
                f"累计已下 {downloaded_count} 本",
            )

            if hit_limit:
                return downloaded_count

        print(f"  分类 {cat} 结束，累计已下载 {downloaded_count} 本")

    return downloaded_count


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="xbiquge.la 单本 / 全站(分类分页) 抓取")
    p.add_argument(
        "--mode",
        choices=("single", "all"),
        default="single",
        help="single=只抓 BOOK_INDEX；all=按 fenlei 分页边翻边下载",
    )
    p.add_argument("--book", default=BOOK_INDEX, help="单本模式下的书籍目录页 URL")
    p.add_argument("--out", default=str(SAVE_ROOT), help="保存根目录")
    p.add_argument(
        "--categories",
        default=",".join(str(x) for x in DEFAULT_FENLEI_CATEGORIES),
        help="全站模式下 fenlei 分类 id，逗号分隔，默认 1-7",
    )
    p.add_argument(
        "--max-pages",
        type=int,
        default=800,
        help="每个分类最多翻页数（防止无限循环，可按需加大）",
    )
    p.add_argument(
        "--empty-pages",
        type=int,
        default=5,
        help="连续多少页没有章节链接模式则停止该分类",
    )
    p.add_argument(
        "--max-books",
        type=int,
        default=0,
        help="最多抓取多少本书（0 表示不限制，慎用）",
    )
    p.add_argument(
        "--use-state",
        action="store_true",
        help="将已完成的书籍目录 URL 记入 book_crawl_state.json，下次跳过",
    )
    p.add_argument(
        "--folder-by-id",
        action="store_true",
        help="书籍保存文件夹用 URL 数字 id（如 0_57），不用解析出来的书名",
    )
    return p.parse_args()


def main() -> None:
    args = parse_args()
    save_root = Path(args.out)
    save_root.mkdir(parents=True, exist_ok=True)

    session = requests.Session()
    done = load_state() if args.use_state else set()

    if args.mode == "single":
        book_url = args.book.rstrip("/") + "/"
        index_html = fetch_html(session, book_url)
        folder_name = resolve_book_folder_name(
            save_root, book_url, index_html, args.folder_by_id
        )
        download_one_book(
            session, book_url, save_root / folder_name, index_html=index_html
        )
        return

    # --- all books：边翻 fenlei 边下载 ---
    cats = [int(x.strip()) for x in args.categories.split(",") if x.strip()]
    total = crawl_fenlei_streaming_download(
        session,
        save_root=save_root,
        categories=cats,
        max_pages_per_category=args.max_pages,
        empty_page_limit=args.empty_pages,
        max_books=args.max_books,
        use_state=args.use_state,
        done=done,
        folder_by_id=args.folder_by_id,
    )
    print(f"\n本轮结束，累计下载完成 {total} 本书（受 --max-books / 分类翻页上限影响）")


if __name__ == "__main__":
    main()
