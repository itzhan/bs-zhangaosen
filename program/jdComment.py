from DrissionPage import ChromiumPage, ChromiumOptions
import os
import time
import pandas as pd
import json

# 创建浏览器设置
options = ChromiumOptions()
user_data_path = os.path.join(os.getcwd(), 'chrome_user_data')
options.set_paths(user_data_path=user_data_path)
# 反自动化检测设置
options.set_argument('--disable-blink-features=AutomationControlled')
options.set_argument('--disable-infobars')
# 使用set_pref方法设置首选项
options.set_pref('excludeSwitches', ['enable-automation'])
options.set_pref('useAutomationExtension', False)
# 性能设置
options.set_argument('--disable-gpu')
options.set_argument('--disable-dev-shm-usage')
# 设置端口
# options.set_local_port(9222)  # 使用固定端口，可以重用浏览器

#开始操作
page = ChromiumPage(options)

page.get('https://item.jd.com/100142456646.html')
time.sleep(5)
page.listen.start('api.m.jd.com/client.action')
page.ele("全部评价").click()

# 用于存储已处理的评论ID，避免重复
processed_comment_ids = set()
csv_filename = 'comments_data_pandas.csv'

# 如果CSV文件已存在，加载已有的评论ID
if os.path.exists(csv_filename):
    try:
        existing_df = pd.read_csv(csv_filename, encoding='utf-8-sig')
        processed_comment_ids = set(existing_df['评论ID'].tolist())
        print(f"加载了已有的 {len(processed_comment_ids)} 条评论记录")
    except Exception as e:
        print(f"加载已有数据时出错: {e}")

def extract_comments_from_response(data):
    """从响应数据中提取评论信息"""
    comments = []
    try:
        for floor in data['result']['floors']:
            if floor.get('mId') == 'commentlist-list' and 'data' in floor:
                for comment_item in floor['data']:
                    if 'commentInfo' in comment_item:
                        comment_info = comment_item['commentInfo']
                        comment_id = comment_info['commentId']
                        
                        # 检查是否已处理过此评论
                        if comment_id in processed_comment_ids:
                            continue
                        
                        # 提取商品颜色和尺寸
                        color = None
                        size = None
                        for attr in comment_info.get('wareAttribute', []):
                            if '颜色' in attr:
                                color = attr['颜色']
                            elif '型号' in attr:
                                size = attr['型号']
                        
                        # 构建评论信息字典
                        comment = {
                            '评论ID': comment_id,
                            '评论时间': comment_info['commentDate'],
                            '评论内容': comment_info['commentData'],
                            '商品颜色': color,
                            '商品尺寸': size,
                            '商品得分': comment_info['commentScore']
                        }
                        comments.append(comment)
                        processed_comment_ids.add(comment_id)
    except Exception as e:
        print(f"解析评论数据时出错: {e}")
    
    return comments

def save_comments_to_csv(comments, filename):
    """将评论数据保存到CSV文件"""
    if not comments:
        return
    
    try:
        df = pd.DataFrame(comments)
        
        # 如果文件不存在，创建新文件
        if not os.path.exists(filename):
            df.to_csv(filename, index=False, encoding='utf-8-sig')
            print(f"创建新文件并保存了 {len(comments)} 条新评论")
        else:
            # 如果文件存在，追加数据
            df.to_csv(filename, mode='a', header=False, index=False, encoding='utf-8-sig')
            print(f"追加保存了 {len(comments)} 条新评论")
    except Exception as e:
        print(f"保存数据时出错: {e}")

print("开始持续监听评论数据...")
print("按 Ctrl+C 停止程序")

try:
    while True:
        try:
            # 等待新的网络响应，设置超时时间
            res = page.listen.wait(timeout=30)
            
            if res and hasattr(res, 'response') and hasattr(res.response, 'body'):
                data = res.response.body
                
                # 提取新评论
                new_comments = extract_comments_from_response(data)
                
                if new_comments:
                    # 保存新评论到CSV
                    save_comments_to_csv(new_comments, csv_filename)
                    print(f"当前已处理评论总数: {len(processed_comment_ids)}")
                else:
                    print("本次响应中没有发现新评论")
            else:
                print("等待新的网络请求...")
                
        except Exception as e:
            print(f"处理响应时出错: {e}")
            time.sleep(5)  # 出错后等待5秒再继续
            
        # 短暂休息避免过度占用资源
        time.sleep(1)
        
except KeyboardInterrupt:
    print(f"\n程序已停止，总共处理了 {len(processed_comment_ids)} 条评论")
    print(f"数据已保存到 {csv_filename}")
except Exception as e:
    print(f"程序运行出错: {e}")
finally:
    try:
        page.quit()
    except:
        pass