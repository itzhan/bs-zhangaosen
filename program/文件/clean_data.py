import pandas as pd
import os

def clean_data(input_file='comments_full_data.csv', output_file='comments_cleaned.csv'):
    """
    从完整数据中提取所需的字段并保存到新的CSV文件
    
    参数:
    input_file: 输入的完整数据文件路径
    output_file: 输出的清理后数据文件路径
    """
    try:
        # 检查输入文件是否存在
        if not os.path.exists(input_file):
            print(f"错误：输入文件 {input_file} 不存在")
            return False
        
        # 读取完整数据
        print(f"正在读取文件: {input_file}")
        df = pd.read_csv(input_file, encoding='utf-8-sig')
        print(f"成功读取 {len(df)} 条记录")
        
        # 创建输出目录（如果不存在）
        output_dir = os.path.dirname(output_file)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir)
            print(f"创建输出目录: {output_dir}")
        
        # 选择需要保留的字段
        # 必选字段
        essential_columns = ['评论ID', '评论时间', '评论内容']
        
        # 可选字段 - 根据是否存在来添加
        optional_columns = ['商品_颜色', '商品_型号', '评论得分', '用户昵称']
        
        # 构建最终要保留的列列表
        columns_to_keep = []
        
        # 添加必选字段（如果存在）
        for col in essential_columns:
            if col in df.columns:
                columns_to_keep.append(col)
            else:
                print(f"警告：必选字段 {col} 在数据中不存在")
        
        # 添加可选字段（如果存在）
        for col in optional_columns:
            if col in df.columns:
                columns_to_keep.append(col)
        
        # 检查是否存在商品颜色字段，不同名称可能会用到
        color_columns = [col for col in df.columns if '颜色' in col]
        for col in color_columns:
            if col not in columns_to_keep:
                columns_to_keep.append(col)
        
        # 如果没有找到任何列，则退出
        if not columns_to_keep:
            print("错误：找不到任何有效的列")
            return False
        
        # 提取所需的列
        df_clean = df[columns_to_keep]
        
        # 保存清理后的数据
        df_clean.to_csv(output_file, index=False, encoding='utf-8-sig')
        print(f"成功将清理后的数据保存到: {output_file}")
        print(f"保留的字段: {', '.join(columns_to_keep)}")
        
        return True
    
    except Exception as e:
        print(f"处理数据时出错: {e}")
        return False

if __name__ == "__main__":
    # 确保output目录存在
    if not os.path.exists('output'):
        os.makedirs('output')
        print("创建output目录")
    
    # 清理数据
    input_file = 'comments_full_data.csv'
    output_file = 'output/comments_cleaned.csv'
    
    if clean_data(input_file, output_file):
        print("数据清理完成")
    else:
        print("数据清理失败") 