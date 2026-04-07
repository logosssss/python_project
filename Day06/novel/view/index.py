from django.http import HttpResponse
from django.shortcuts import render
from utils.mysql_DBUtils import mysql


# 《星辰变》章节列表
def main(request):
    sql = "SELECT id,title FROM novel LIMIT 10;"
    result = mysql.getAll(sql)
    if not result:
        result = []
    context = {'novel_list': result}
    return render(request, 'novel_list.html', context)


# def chapter(request):
#     id = request.GET['id']
#     sql = "SELECT content FROM novel where id = %(id)s;"
#     param = {"id": id}
#     result = mysql.getOne(sql, param)
#     result['content'] = result['content'].decode('utf-8')
#     context = {}
#     context["content"] =  result['content']
#     return render(request, 'novel.html', context)

'''
单个章节
此处 novel_id 对应 urls.py 中的 <int:novel_id>
你可以访问：http://localhost:8000/chapter/1/
'''
def chapter(request, novel_id):
    sql = "SELECT title,content FROM novel where id = %(id)s;"
    param = {"id": novel_id}
    result = mysql.getOne(sql, param)
    if not result:
        return render(
            request,
            'novel.html',
            {'novel': {'title': '未找到', 'content': '没有该章节记录（请检查 id 或数据库数据）。'}},
            status=404,
        )
    title = result.get("title")
    content = result.get("content")
    if isinstance(title, bytes):
        title = title.decode("utf-8", errors="replace")
    if isinstance(content, bytes):
        content = content.decode("utf-8", errors="replace")
    context = {"novel": {"title": title, "content": content}}
    return render(request, 'novel.html', context)

