"""爬虫服务 — 封装 DrissionPage 爬虫逻辑，支持后台线程执行"""

import os
import time
import threading
from datetime import datetime

import pandas as pd

# 延迟导入，避免未安装 DrissionPage 时影响整个系统
_browser_lock = threading.Lock()


def _run_crawler(app, task_id, jd_url, brand_id, max_pages=10):
    """在后台线程中执行爬虫任务"""
    with app.app_context():
        from app import db
        from app.models.task import CrawlerTask
        from app.models.comment import Comment
        from app.services import analyze_text

        task = CrawlerTask.query.get(task_id)
        if not task:
            return

        task.status = 'running'
        task.start_time = datetime.now()
        db.session.commit()

        try:
            from DrissionPage import ChromiumPage, ChromiumOptions

            # 配置浏览器
            options = ChromiumOptions()
            user_data_path = os.path.join(os.getcwd(), 'chrome_user_data')
            options.set_paths(user_data_path=user_data_path)
            options.set_argument('--disable-blink-features=AutomationControlled')
            options.set_argument('--disable-infobars')
            options.set_argument('--disable-gpu')
            options.set_argument('--disable-dev-shm-usage')
            options.set_pref('excludeSwitches', ['enable-automation'])
            options.set_pref('useAutomationExtension', False)

            with _browser_lock:
                page = ChromiumPage(options)

                try:
                    page.get(jd_url)
                    time.sleep(5)

                    # 开始监听评论 API
                    page.listen.start('api.m.jd.com/client.action')

                    # 点击"全部评价"
                    try:
                        page.ele("全部评价").click()
                    except Exception:
                        try:
                            page.ele("商品评价").click()
                        except Exception:
                            pass

                    processed_ids = set()
                    total_saved = 0
                    empty_rounds = 0

                    for page_num in range(max_pages * 3):
                        try:
                            res = page.listen.wait(timeout=15)

                            if res and hasattr(res, 'response') and hasattr(res.response, 'body'):
                                data = res.response.body
                                comments = _extract_comments(data, processed_ids)

                                if comments:
                                    saved = _save_to_db(db, comments, brand_id, task_id)
                                    total_saved += saved
                                    empty_rounds = 0

                                    # 更新任务进度
                                    task.total_count = total_saved
                                    db.session.commit()
                                else:
                                    empty_rounds += 1
                            else:
                                empty_rounds += 1

                            # 连续3次没有新数据就尝试翻页
                            if empty_rounds >= 3:
                                try:
                                    next_btn = page.ele('下一页')
                                    if next_btn:
                                        next_btn.click()
                                        time.sleep(2)
                                        empty_rounds = 0
                                    else:
                                        break
                                except Exception:
                                    break

                        except Exception as e:
                            print(f"[爬虫] 处理响应出错: {e}")
                            time.sleep(3)

                        time.sleep(1)

                finally:
                    try:
                        page.quit()
                    except Exception:
                        pass

            # 完成
            task.status = 'completed'
            task.total_count = total_saved
            task.end_time = datetime.now()
            db.session.commit()
            print(f"[爬虫] 任务#{task_id} 完成，共采集 {total_saved} 条评论")

        except ImportError:
            task.status = 'failed'
            task.error_msg = '未安装 DrissionPage，请运行: pip install DrissionPage'
            task.end_time = datetime.now()
            db.session.commit()

        except Exception as e:
            task.status = 'failed'
            task.error_msg = str(e)[:500]
            task.end_time = datetime.now()
            db.session.commit()
            print(f"[爬虫] 任务#{task_id} 失败: {e}")


def _extract_comments(data, processed_ids):
    """从京东 API 响应中提取评论"""
    comments = []
    try:
        for floor in data.get('result', {}).get('floors', []):
            if floor.get('mId') == 'commentlist-list' and 'data' in floor:
                for item in floor['data']:
                    if 'commentInfo' not in item:
                        continue
                    info = item['commentInfo']
                    cid = info.get('commentId', '')

                    if cid in processed_ids:
                        continue

                    color = ''
                    model = ''
                    for attr in info.get('wareAttribute', []):
                        if '颜色' in attr:
                            color = attr.get('颜色', '')
                        elif '型号' in attr:
                            model = attr.get('型号', '')

                    comments.append({
                        'comment_id': str(cid),
                        'comment_time': info.get('commentDate', ''),
                        'content': info.get('commentData', ''),
                        'score': info.get('commentScore', 5),
                        'user_nickname': info.get('userNickName', ''),
                        'color': color,
                        'model': model,
                    })
                    processed_ids.add(cid)
    except Exception as e:
        print(f"[爬虫] 解析评论出错: {e}")
    return comments


def _save_to_db(db, comments, brand_id, task_id):
    """将评论保存到数据库并执行情感分析"""
    from app.models.comment import Comment
    from app.services import analyze_text

    saved = 0
    for c in comments:
        # 检查是否已存在
        if Comment.query.filter_by(comment_id=c['comment_id']).first():
            continue

        # 情感分析
        result = analyze_text(c['content'])

        # 解析时间
        ct = None
        if c['comment_time']:
            try:
                ct = pd.to_datetime(c['comment_time'])
            except Exception:
                pass

        comment = Comment(
            brand_id=brand_id,
            comment_id=c['comment_id'],
            comment_time=ct,
            content=c['content'],
            cleaned_content=result['cleaned_content'],
            score=c['score'],
            user_nickname=c['user_nickname'],
            color=c['color'] if len(c.get('color', '')) < 100 else '',
            model=c['model'] if len(c.get('model', '')) < 100 else '',
            sentiment_score=result['sentiment_score'],
            sentiment_label=result['sentiment_label'],
            keywords=result['keywords'],
        )
        db.session.add(comment)
        saved += 1

    if saved > 0:
        db.session.commit()
    return saved


def start_crawler_task(app, task_id, jd_url, brand_id, max_pages=10):
    """启动后台爬虫线程"""
    t = threading.Thread(
        target=_run_crawler,
        args=(app, task_id, jd_url, brand_id, max_pages),
        daemon=True,
        name=f'crawler-task-{task_id}',
    )
    t.start()
    return t
