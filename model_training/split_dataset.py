#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据集划分脚本

功能：
1. 将sorted目录中的图片按照7:2:1的比例分配到train、val、test目录中
2. 处理视角分类数据集（front、rear、standing、other）
3. 处理拥挤度分类数据集（empty、seated、standing、crowd、extremecrowd）
4. 确保拥挤度级别按照指定顺序排列
"""

import os
import shutil
import random
import glob

# 定义路径
SOURCE_DIR = 'sorted'
VIEW_DATASET_DIR = 'dataset_view'
CROWD_DATASET_DIR = 'view_datasets'

# 定义划分比例
TRAIN_RATIO = 0.7
VAL_RATIO = 0.2
TEST_RATIO = 0.1

# 定义视角类别
views = ['front', 'rear', 'standing', 'other']

# 定义拥挤度级别（按照指定顺序）
crowd_levels = [
    ('1_empty', 'empty'),
    ('2_seated', 'seated'),
    ('3_standing', 'standing'),
    ('4_crowd', 'crowd'),
    ('5_extremecrowd', 'extremecrowd')
]

# 确保目标目录存在
def ensure_dirs():
    # 视角分类数据集目录
    os.makedirs(VIEW_DATASET_DIR, exist_ok=True)
    os.makedirs(os.path.join(VIEW_DATASET_DIR, 'train'), exist_ok=True)
    os.makedirs(os.path.join(VIEW_DATASET_DIR, 'val'), exist_ok=True)
    os.makedirs(os.path.join(VIEW_DATASET_DIR, 'test'), exist_ok=True)
    
    # 为每个视角创建子目录
    for view in views:
        os.makedirs(os.path.join(VIEW_DATASET_DIR, 'train', view), exist_ok=True)
        os.makedirs(os.path.join(VIEW_DATASET_DIR, 'val', view), exist_ok=True)
        os.makedirs(os.path.join(VIEW_DATASET_DIR, 'test', view), exist_ok=True)
    
    # 拥挤度分类数据集目录
    if os.path.exists(CROWD_DATASET_DIR):
        shutil.rmtree(CROWD_DATASET_DIR)
    
    for view in views:
        if view == 'other':
            continue
        view_dir = os.path.join(CROWD_DATASET_DIR, view)
        os.makedirs(os.path.join(view_dir, 'train'), exist_ok=True)
        os.makedirs(os.path.join(view_dir, 'val'), exist_ok=True)
        os.makedirs(os.path.join(view_dir, 'test'), exist_ok=True)
        
        # 为每个拥挤度级别创建子目录（按照指定顺序）
        for level_folder, _ in crowd_levels:
            os.makedirs(os.path.join(view_dir, 'train', level_folder), exist_ok=True)
            os.makedirs(os.path.join(view_dir, 'val', level_folder), exist_ok=True)
            os.makedirs(os.path.join(view_dir, 'test', level_folder), exist_ok=True)

# 复制文件到对应目录
def copy_files(files, dest):
    for file in files:
        dest_path = os.path.join(dest, os.path.basename(file))
        shutil.copy2(file, dest_path)

# 处理视角分类数据集
def process_view_dataset():
    print("\n===== 处理视角分类数据集 =====")
    
    # 处理每个视角
    for view in views:
        view_path = os.path.join(SOURCE_DIR, view)
        
        # 获取该视角下的所有图片文件
        image_files = []
        for root, dirs, files in os.walk(view_path):
            for file in files:
                if file.lower().endswith(('.jpg', '.jpeg', '.png')):
                    image_files.append(os.path.join(root, file))
        
        # 随机打乱图片顺序
        random.shuffle(image_files)
        
        # 计算划分数量
        total = len(image_files)
        train_count = int(total * TRAIN_RATIO)
        val_count = int(total * VAL_RATIO)
        test_count = total - train_count - val_count
        
        # 划分数据集
        train_files = image_files[:train_count]
        val_files = image_files[train_count:train_count+val_count]
        test_files = image_files[train_count+val_count:]
        
        # 复制文件到对应目录
        copy_files(train_files, os.path.join(VIEW_DATASET_DIR, 'train', view))
        copy_files(val_files, os.path.join(VIEW_DATASET_DIR, 'val', view))
        copy_files(test_files, os.path.join(VIEW_DATASET_DIR, 'test', view))
        
        print(f"视角 '{view}' 处理完成:")
        print(f"  总图片数: {total}")
        print(f"  训练集: {len(train_files)}")
        print(f"  验证集: {len(val_files)}")
        print(f"  测试集: {len(test_files)}")

# 处理拥挤度分类数据集
def process_crowd_dataset():
    print("\n===== 处理拥挤度分类数据集 =====")
    
    # 处理每个视角（除了other）
    for view in views:
        if view == 'other':
            continue
        
        view_path = os.path.join(SOURCE_DIR, view)
        print(f"\n处理视角: {view}")
        
        # 统计每个级别的图片
        level_counts = {}
        for root, dirs, files in os.walk(view_path):
            for file in files:
                if file.lower().endswith(('.jpg', '.jpeg', '.png')):
                    # 从文件名中提取级别
                    # 文件名格式: {view}_{level}_{plate}_{line}_{time}.jpeg
                    parts = file.split('_')
                    if len(parts) >= 2:
                        level = parts[1]
                        if level not in level_counts:
                            level_counts[level] = []
                        level_counts[level].append(os.path.join(root, file))
        
        # 打印每个级别的图片数量（按照指定顺序）
        print("级别分布:")
        total = 0
        for level_folder, level_name in crowd_levels:
            if level_name in level_counts:
                count = len(level_counts[level_name])
                total += count
                print(f"  {level_name}: {count} 张")
            else:
                print(f"  {level_name}: 0 张")
        print(f"  总计: {total} 张")
        
        # 为每个级别分配数据集（按照指定顺序）
        for level_folder, level_name in crowd_levels:
            if level_name not in level_counts or not level_counts[level_name]:
                continue
            
            files = level_counts[level_name]
            # 随机打乱图片顺序
            random.shuffle(files)
            
            # 计算划分数量
            count = len(files)
            train_count = int(count * TRAIN_RATIO)
            val_count = int(count * VAL_RATIO)
            test_count = count - train_count - val_count
            
            # 划分数据集
            train_files = files[:train_count]
            val_files = files[train_count:train_count+val_count]
            test_files = files[train_count+val_count:]
            
            # 复制文件到对应目录（使用带数字前缀的文件夹名）
            copy_files(train_files, os.path.join(CROWD_DATASET_DIR, view, 'train', level_folder))
            copy_files(val_files, os.path.join(CROWD_DATASET_DIR, view, 'val', level_folder))
            copy_files(test_files, os.path.join(CROWD_DATASET_DIR, view, 'test', level_folder))
            
            print(f"  级别 {level_name} 分配:")
            print(f"    训练集: {len(train_files)} 张")
            print(f"    验证集: {len(val_files)} 张")
            print(f"    测试集: {len(test_files)} 张")

if __name__ == "__main__":
    # 确保目录结构
    ensure_dirs()
    
    # 处理视角分类数据集
    process_view_dataset()
    
    # 处理拥挤度分类数据集
    process_crowd_dataset()
    
    print("\n数据集处理完成！")
    print("1. 视角分类数据集已保存到: dataset_view")
    print("2. 拥挤度分类数据集已保存到: view_datasets")
    print("3. 拥挤度级别已按照 empty → seated → standing → crowd → extremecrowd 排列")