from DrissionPage import ChromiumPage, ChromiumOptions
import os
import sys
import time
import pandas as pd

# 创建浏览器设置
options = ChromiumOptions()
user_data_path = os.path.join(os.getcwd(), 'chrome_user_data')
options.set_paths(user_data_path=user_data_path)
# 反自动化检测设置
options.set_argument('--disable-infobars')
# 使用set_pref方法设置首选项
options.set_pref('excludeSwitches', ['enable-automation'])
options.set_pref('useAutomationExtension', False)
# 性能设置
options.set_argument('--disable-gpu')
options.set_argument('--disable-dev-shm-usage')

# 读取用户输入的商品链接和输出文件名
product_url = input("请输入商品链接：").strip()
if not product_url:
    print("未输入商品链接，程序退出。")
    sys.exit(1)

excel_filename = input("请输入输出文件名（xlsx）：").strip()
if not excel_filename:
    print("未输入文件名，程序退出。")
    sys.exit(1)
if not excel_filename.lower().endswith('.xlsx'):
    excel_filename += '.xlsx'

# 开始操作
page = ChromiumPage(options)

page.get(product_url)
time.sleep(5)
page.listen.start('api.m.jd.com/client.action')
page.ele("全部评价").click()

# 用于存储已处理的评论ID，避免重复
processed_comment_ids = set()

# 如果Excel文件已存在，加载已有的评论ID
if os.path.exists(excel_filename):
    try:
        existing_df = pd.read_excel(excel_filename)
        if '评论ID' in existing_df.columns:
            processed_comment_ids = set(existing_df['评论ID'].dropna().tolist())
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
                        
                        # 创建一个包含所有字段的字典
                        comment = {
                            '评论ID': comment_id,
                            '评论时间': comment_info.get('commentDate'),
                            '评论内容': comment_info.get('commentData'),
                            '评论得分': comment_info.get('commentScore'),
                            '用户ID': comment_info.get('userId'),
                            '用户昵称': comment_info.get('userNickName'),
                            '用户等级': comment_info.get('userLevel'),
                            '点赞数': comment_info.get('praiseCount'),
                            '回复数': comment_info.get('replyCount'),
                            '是否置顶': comment_info.get('isTop', 0),
                            '是否精华': comment_info.get('isEssence', 0),
                            '商品ID': comment_info.get('wareId'),
                            '购买时间': comment_info.get('days', 0),
                        }
                        
                        # 添加商品属性
                        if 'wareAttribute' in comment_info:
                            for attr in comment_info['wareAttribute']:
                                for key, value in attr.items():
                                    comment[f'商品_{key}'] = value
                        
                        # 添加标签信息
                        if 'commentTagList' in comment_info:
                            tags = []
                            for tag in comment_info['commentTagList']:
                                if 'name' in tag:
                                    tags.append(tag['name'])
                            comment['评论标签'] = '|'.join(tags)
                        
                        # 添加图片信息
                        if 'pictureInfoList' in comment_info:
                            pics = []
                            for pic in comment_info['pictureInfoList']:
                                if 'picURL' in pic:
                                    pics.append(pic['picURL'])
                            comment['评论图片'] = '|'.join(pics)
                        
                        # 添加视频信息
                        if 'videoInfoList' in comment_info:
                            videos = []
                            for video in comment_info['videoInfoList']:
                                if 'videoUrl' in video:
                                    videos.append(video['videoUrl'])
                            comment['评论视频'] = '|'.join(videos)
                        
                        comments.append(comment)
                        processed_comment_ids.add(comment_id)
    except Exception as e:
        print(f"解析评论数据时出错: {e}")
    
    return comments

def save_comments_to_excel(comments, filename):
    """将评论数据保存到Excel文件"""
    if not comments:
        return

    try:
        df = pd.DataFrame(comments)

        if not os.path.exists(filename):
            df.to_excel(filename, index=False)
            print(f"创建新文件并保存了 {len(comments)} 条新评论")
            return

        existing_df = pd.read_excel(filename)

        # 获取新列并补齐现有数据
        new_columns = [col for col in df.columns if col not in existing_df.columns]
        for col in new_columns:
            existing_df[col] = None

        # 将现有数据与新数据对齐后写回
        combined_df = pd.concat([existing_df, df], ignore_index=True)
        combined_df.to_excel(filename, index=False)
        if new_columns:
            print(f"添加了新列并保存了 {len(comments)} 条新评论")
        else:
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
                    # 保存新评论到Excel
                    save_comments_to_excel(new_comments, excel_filename)
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
    print(f"数据已保存到 {excel_filename}")
except Exception as e:
    print(f"程序运行出错: {e}")
