import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib
import seaborn as sns
import jieba
import jieba.analyse
from wordcloud import WordCloud
import os
from datetime import datetime
import re
from collections import Counter
import warnings
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.decomposition import LatentDirichletAllocation
import platform

# 设置中文字体
def set_chinese_font():
    """根据操作系统设置合适的中文字体"""
    system = platform.system()
    
    if system == 'Windows':
        font_path = 'C:/Windows/Fonts/simhei.ttf'  # 黑体
        font_properties = {'family': 'SimHei'}
    elif system == 'Darwin':  # macOS
        # macOS 常见中文字体
        font_candidates = [
            '/System/Library/Fonts/PingFang.ttc',
            '/System/Library/Fonts/STHeiti Light.ttc',
            '/System/Library/Fonts/STHeiti Medium.ttc',
            '/System/Library/Fonts/Hiragino Sans GB.ttc',
            '/Library/Fonts/Microsoft/SimHei.ttf',
            '/Library/Fonts/Songti.ttc'
        ]
        
        font_path = None
        for path in font_candidates:
            if os.path.exists(path):
                font_path = path
                break
        
        if font_path:
            if 'PingFang' in font_path:
                font_properties = {'family': 'PingFang HK'}
            elif 'Hiragino' in font_path:
                font_properties = {'family': 'Hiragino Sans GB'}
            elif 'STHeiti' in font_path:
                font_properties = {'family': 'STHeiti'}
            elif 'SimHei' in font_path:
                font_properties = {'family': 'SimHei'}
            elif 'Songti' in font_path:
                font_properties = {'family': 'Songti SC'}
            else:
                font_properties = {'family': 'sans-serif'}
    else:  # Linux
        font_candidates = [
            '/usr/share/fonts/truetype/wqy/wqy-microhei.ttc',
            '/usr/share/fonts/truetype/arphic/uming.ttc'
        ]
        
        font_path = None
        for path in font_candidates:
            if os.path.exists(path):
                font_path = path
                break
        
        if font_path:
            if 'wqy-microhei' in font_path:
                font_properties = {'family': 'WenQuanYi Micro Hei'}
            else:
                font_properties = {'family': 'AR PL UMing CN'}
        else:
            font_properties = {'family': 'sans-serif'}
    
    # 如果找不到中文字体，使用默认字体
    if not font_path:
        print("警告：找不到合适的中文字体，将使用系统默认字体")
        matplotlib.rcParams['font.sans-serif'] = ['DejaVu Sans', 'Arial', 'Helvetica']
    else:
        print(f"使用中文字体: {font_properties['family']} ({font_path})")
        # 设置matplotlib字体
        matplotlib.rcParams['font.family'] = font_properties['family']
        matplotlib.rcParams['font.sans-serif'] = [font_properties['family']] + matplotlib.rcParams['font.sans-serif']
    
    # 确保负号正确显示
    matplotlib.rcParams['axes.unicode_minus'] = False
    
    return font_path

# 调用字体设置函数
chinese_font_path = set_chinese_font()
warnings.filterwarnings('ignore')  # 忽略警告

# 确保输出目录存在
def ensure_output_dir():
    """确保输出目录存在"""
    if not os.path.exists('output'):
        os.makedirs('output')
    if not os.path.exists('output/images'):
        os.makedirs('output/images')
    print("输出目录已就绪")

# 加载数据
def load_data(file_path='output/comments_cleaned.csv'):
    """加载数据"""
    try:
        df = pd.read_csv(file_path, encoding='utf-8-sig')
        print(f"成功加载 {len(df)} 条评论数据")
        return df
    except Exception as e:
        print(f"加载数据时出错: {e}")
        return None

# 数据预处理
def preprocess_data(df):
    """数据预处理"""
    if df is None or len(df) == 0:
        print("没有数据可处理")
        return None
    
    # 复制数据框以避免修改原始数据
    df_processed = df.copy()
    
    # 转换评论时间为日期时间格式
    if '评论时间' in df_processed.columns:
        try:
            df_processed['评论时间'] = pd.to_datetime(df_processed['评论时间'])
            df_processed['年份'] = df_processed['评论时间'].dt.year
            df_processed['月份'] = df_processed['评论时间'].dt.month
            df_processed['日期'] = df_processed['评论时间'].dt.day
            df_processed['星期'] = df_processed['评论时间'].dt.dayofweek
            df_processed['小时'] = df_processed['评论时间'].dt.hour
            print("时间特征提取完成")
        except Exception as e:
            print(f"时间特征提取出错: {e}")
    
    # 提取评论长度
    if '评论内容' in df_processed.columns:
        df_processed['评论长度'] = df_processed['评论内容'].apply(lambda x: len(str(x)) if pd.notna(x) else 0)
        print("评论长度特征提取完成")
    
    # 查找并统一颜色字段的名称
    color_columns = [col for col in df_processed.columns if '颜色' in col]
    if color_columns:
        main_color_column = color_columns[0]
        if main_color_column != '商品颜色' and '商品颜色' not in df_processed.columns:
            df_processed['商品颜色'] = df_processed[main_color_column]
        print(f"使用 {main_color_column} 作为颜色特征")
    
    return df_processed

# 可视化1：评论时间分布
def plot_time_distribution(df, save_path='output/images/'):
    """可视化评论时间分布"""
    if df is None or '评论时间' not in df.columns:
        print("缺少必要的时间数据")
        return
    
    try:
        # 创建图形对象
        plt.figure(figsize=(20, 15))
        
        # 1. 按年月分布 - 折线图
        plt.subplot(2, 2, 1)
        df['年月'] = df['评论时间'].dt.strftime('%Y-%m')
        monthly_counts = df['年月'].value_counts().sort_index()
        monthly_counts.plot(kind='line', marker='o')
        plt.title('评论数量月度趋势')
        plt.xlabel('年月')
        plt.ylabel('评论数量')
        plt.xticks(rotation=45)
        plt.grid(True, linestyle='--', alpha=0.7)
        
        # 2. 按星期几分布 - 条形图
        plt.subplot(2, 2, 2)
        weekday_mapping = {0: '周一', 1: '周二', 2: '周三', 3: '周四', 4: '周五', 5: '周六', 6: '周日'}
        df['星期名'] = df['星期'].map(weekday_mapping)
        weekday_order = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']
        weekday_counts = df['星期名'].value_counts().reindex(weekday_order)
        sns.barplot(x=weekday_counts.index, y=weekday_counts.values, palette='viridis')
        plt.title('评论按星期分布')
        plt.xlabel('星期')
        plt.ylabel('评论数量')
        
        # 3. 按小时分布 - 条形图
        plt.subplot(2, 2, 3)
        hourly_counts = df['小时'].value_counts().sort_index()
        sns.barplot(x=hourly_counts.index, y=hourly_counts.values, palette='coolwarm')
        plt.title('评论按小时分布')
        plt.xlabel('小时')
        plt.ylabel('评论数量')
        plt.xticks(range(0, 24, 2))
        
        # 4. 按年月热力图
        plt.subplot(2, 2, 4)
        df['月'] = df['评论时间'].dt.month
        df['日'] = df['评论时间'].dt.day
        month_day_counts = df.groupby(['月', '日']).size().unstack()
        sns.heatmap(month_day_counts, cmap='YlGnBu', annot=False)
        plt.title('评论按月日分布热力图')
        plt.xlabel('日')
        plt.ylabel('月')
        
        # 保存图片
        plt.tight_layout()
        plt.savefig(f"{save_path}time_distribution.png", dpi=300)
        plt.close()
        print(f"时间分布图已保存至 {save_path}time_distribution.png")
    except Exception as e:
        print(f"生成时间分布图时出错: {e}")

# 可视化2：评论长度分析
def plot_comment_length(df, save_path='output/images/'):
    """可视化评论长度分析"""
    if df is None or '评论长度' not in df.columns:
        print("缺少评论长度数据")
        return
    
    try:
        plt.figure(figsize=(20, 10))
        
        # 1. 评论长度分布直方图
        plt.subplot(1, 2, 1)
        sns.histplot(df['评论长度'], bins=30, kde=True)
        plt.title('评论长度分布')
        plt.xlabel('评论长度（字符数）')
        plt.ylabel('频率')
        
        # 2. 评论长度箱线图
        plt.subplot(1, 2, 2)
        sns.boxplot(y=df['评论长度'])
        plt.title('评论长度箱线图')
        plt.ylabel('评论长度（字符数）')
        
        # 计算描述性统计信息
        length_stats = df['评论长度'].describe()
        stats_text = f"平均长度: {length_stats['mean']:.2f}\n" \
                     f"中位数: {length_stats['50%']:.0f}\n" \
                     f"最短评论: {length_stats['min']:.0f}\n" \
                     f"最长评论: {length_stats['max']:.0f}\n" \
                     f"标准差: {length_stats['std']:.2f}"
        
        plt.annotate(stats_text, xy=(0.05, 0.7), xycoords='axes fraction',
                     bbox=dict(boxstyle="round,pad=0.5", fc="yellow", alpha=0.7))
        
        # 保存图片
        plt.tight_layout()
        plt.savefig(f"{save_path}comment_length.png", dpi=300)
        plt.close()
        print(f"评论长度分析图已保存至 {save_path}comment_length.png")
        
        # 额外：长度与时间的关系散点图
        if '评论时间' in df.columns:
            plt.figure(figsize=(12, 6))
            plt.scatter(df['评论时间'], df['评论长度'], alpha=0.5, s=10)
            plt.title('评论长度随时间的变化')
            plt.xlabel('评论时间')
            plt.ylabel('评论长度')
            plt.grid(True, linestyle='--', alpha=0.7)
            
            # 添加趋势线
            try:
                from scipy import stats
                x = np.array(range(len(df)))
                y = df['评论长度'].values
                slope, intercept, r_value, p_value, std_err = stats.linregress(x, y)
                plt.plot(df['评论时间'], intercept + slope*x, 'r', 
                         label=f'趋势线 (r={r_value:.2f})')
                plt.legend()
            except:
                pass
            
            plt.tight_layout()
            plt.savefig(f"{save_path}comment_length_time.png", dpi=300)
            plt.close()
            print(f"评论长度时间趋势图已保存至 {save_path}comment_length_time.png")
    except Exception as e:
        print(f"生成评论长度分析图时出错: {e}")

# 可视化3：词云分析
def plot_word_cloud(df, save_path='output/images/'):
    """生成评论内容词云"""
    if df is None or '评论内容' not in df.columns:
        print("缺少评论内容数据")
        return
    
    try:
        # 合并所有评论文本
        all_comments = ' '.join([str(text) for text in df['评论内容'] if pd.notna(text)])
        
        # 使用jieba进行分词
        jieba.setLogLevel(20)  # 设置jieba的日志级别，避免输出过多信息
        words = jieba.cut(all_comments)
        
        # 过滤停用词（常见的无意义词汇）
        stopwords = {'的', '了', '和', '是', '就', '都', '而', '及', '与', '这', '那', '但', '然', '如果', '因为', '所以', '只是', '只有', '还有', '不过', '不是', '可以', '没有', '也是', '这个', '那个', '有点', '感觉', '我们', '你们', '他们', '很多', '一些', '特别', '非常'}
        filtered_words = ' '.join([word for word in words if len(word) > 1 and word not in stopwords])
        
        # 创建词云
        font_path = chinese_font_path if chinese_font_path else None
        
        if font_path:
            wordcloud = WordCloud(width=1200, height=800,
                                background_color='white',
                                font_path=font_path,  # 使用找到的中文字体
                                max_words=200,
                                contour_width=3,
                                contour_color='steelblue')
        else:
            # 尝试使用默认字体
            wordcloud = WordCloud(width=1200, height=800,
                                background_color='white',
                                max_words=200,
                                contour_width=3,
                                contour_color='steelblue')
        
        # 生成词云图像
        wordcloud.generate(filtered_words)
        
        # 显示词云图
        plt.figure(figsize=(15, 10))
        plt.imshow(wordcloud, interpolation='bilinear')
        plt.axis("off")
        plt.tight_layout()
        plt.savefig(f"{save_path}word_cloud.png", dpi=300)
        plt.close()
        print(f"词云图已保存至 {save_path}word_cloud.png")
        
        # 提取关键词及其权重，生成水平条形图
        keywords = jieba.analyse.extract_tags(all_comments, topK=20, withWeight=True)
        
        # 绘制关键词条形图
        plt.figure(figsize=(12, 10))
        keywords_df = pd.DataFrame(keywords, columns=['关键词', '权重'])
        keywords_df = keywords_df.sort_values('权重')
        plt.barh(keywords_df['关键词'], keywords_df['权重'], color='skyblue')
        plt.xlabel('权重')
        plt.ylabel('关键词')
        plt.title('评论关键词Top20')
        plt.grid(axis='x', linestyle='--', alpha=0.7)
        plt.tight_layout()
        plt.savefig(f"{save_path}keywords_bar.png", dpi=300)
        plt.close()
        print(f"关键词条形图已保存至 {save_path}keywords_bar.png")
    except Exception as e:
        print(f"生成词云图时出错: {e}")

# 可视化4：商品颜色分布
def plot_color_distribution(df, save_path='output/images/'):
    """可视化商品颜色分布"""
    color_columns = [col for col in df.columns if '颜色' in col]
    if not color_columns:
        print("数据中没有找到颜色相关字段")
        return
    
    # 使用找到的第一个颜色列
    color_column = color_columns[0]
    
    try:
        # 统计颜色分布
        color_counts = df[color_column].value_counts()
        
        # 饼图
        plt.figure(figsize=(12, 10))
        plt.pie(color_counts, labels=color_counts.index, autopct='%1.1f%%', 
                startangle=90, shadow=True, 
                wedgeprops={'edgecolor': 'w', 'linewidth': 1},
                textprops={'fontsize': 12})
        plt.axis('equal')  # 确保饼图是圆的
        plt.title(f'商品{color_column}分布')
        plt.tight_layout()
        plt.savefig(f"{save_path}color_pie.png", dpi=300)
        plt.close()
        print(f"颜色分布饼图已保存至 {save_path}color_pie.png")
        
        # 条形图
        plt.figure(figsize=(12, 8))
        ax = sns.countplot(y=df[color_column], order=color_counts.index, palette='viridis')
        
        # 在条形上显示具体数量
        for i, count in enumerate(color_counts):
            ax.text(count + 3, i, str(count), va='center')
        
        plt.title(f'商品{color_column}分布')
        plt.xlabel('数量')
        plt.ylabel(color_column)
        plt.tight_layout()
        plt.savefig(f"{save_path}color_bar.png", dpi=300)
        plt.close()
        print(f"颜色分布条形图已保存至 {save_path}color_bar.png")
        
        # 额外：如果有评论分数，按颜色分析评论分数
        if '评论得分' in df.columns:
            plt.figure(figsize=(14, 8))
            sns.boxplot(x=color_column, y='评论得分', data=df, palette='Set3')
            plt.title('不同颜色的评论得分分布')
            plt.xlabel(color_column)
            plt.ylabel('评论得分')
            plt.xticks(rotation=45)
            plt.tight_layout()
            plt.savefig(f"{save_path}color_score.png", dpi=300)
            plt.close()
            print(f"颜色评分关系图已保存至 {save_path}color_score.png")
    except Exception as e:
        print(f"生成颜色分布图时出错: {e}")

# 可视化5：主题模型分析 (LDA)
def plot_topic_model(df, save_path='output/images/', n_topics=5):
    """使用LDA进行主题模型分析"""
    if df is None or '评论内容' not in df.columns:
        print("缺少评论内容数据")
        return
    
    try:
        # 准备文本数据
        documents = df['评论内容'].fillna('').astype(str).tolist()
        
        # 分词处理
        processed_docs = []
        for doc in documents:
            words = jieba.cut(doc)
            # 过滤停用词和单字词
            stopwords = {'的', '了', '和', '是', '就', '都', '而', '及', '与', '这', '那', '但', '然', '如果', '因为', '所以', '只是', '只有', '还有', '不过', '不是', '可以', '没有', '也是', '这个', '那个', '有点', '感觉', '我们', '你们', '他们', '很多', '一些', '特别', '非常'}
            filtered_words = [word for word in words if len(word) > 1 and word not in stopwords]
            processed_docs.append(' '.join(filtered_words))
        
        # 创建词袋模型
        vectorizer = CountVectorizer(max_df=0.95, min_df=2, max_features=1000)
        X = vectorizer.fit_transform(processed_docs)
        
        # 应用LDA模型
        lda = LatentDirichletAllocation(n_components=n_topics, random_state=42)
        lda.fit(X)
        
        # 获取特征词
        feature_names = vectorizer.get_feature_names_out()
        
        # 绘制主题-词语分布
        fig, axes = plt.subplots(n_topics, 1, figsize=(10, n_topics*3), sharex=True)
        
        for i, (topic, ax) in enumerate(zip(lda.components_, axes)):
            top_features_ind = topic.argsort()[:-11:-1]  # 获取前10个特征词的索引
            top_features = [feature_names[j] for j in top_features_ind]
            weights = topic[top_features_ind]
            
            ax.barh(top_features, weights, height=0.7)
            ax.set_title(f'主题 {i+1}')
            ax.invert_yaxis()
            ax.tick_params(axis='both', which='major', labelsize=8)
            for j in 'top right left'.split():
                ax.spines[j].set_visible(False)
            fig.suptitle('主题-词语分布', fontsize=14)
        
        plt.subplots_adjust(top=0.95, bottom=0.05, wspace=0, hspace=0.3)
        plt.tight_layout()
        plt.savefig(f"{save_path}topic_model.png", dpi=300)
        plt.close()
        print(f"主题模型分析图已保存至 {save_path}topic_model.png")
    except Exception as e:
        print(f"生成主题模型分析图时出错: {e}")

# 主函数
def main():
    """主函数，运行所有可视化"""
    # 确保输出目录存在
    ensure_output_dir()
    
    # 加载并预处理数据
    df = load_data()
    if df is None:
        print("数据加载失败，程序终止")
        return
    
    df_processed = preprocess_data(df)
    if df_processed is None:
        print("数据预处理失败，程序终止")
        return
    
    # 运行所有可视化
    plot_time_distribution(df_processed)
    plot_comment_length(df_processed)
    plot_word_cloud(df_processed)
    plot_color_distribution(df_processed)
    plot_topic_model(df_processed)
    
    print("所有可视化任务已完成！")

if __name__ == "__main__":
    main() 