#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
视角数据集准备脚本

功能：
1. 为front、rear、standing三个视角准备数据集
2. 将每个视角的图片按照7:2:1的比例分配到train、val、test目录中
3. 为每个视角创建对应的拥挤度级别子目录
4. 统计并显示每个级别的图片数量
5. 排除与现有数据集重复的文件
"""

import os
import shutil
import random
from pathlib import Path

# 获取项目根目录（model_training 的上一级）
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)

# 定义路径
SOURCE_DIR = os.path.join(PROJECT_ROOT, 'sorted')
TARGET_BASE_DIR = os.path.join(PROJECT_ROOT, 'view_datasets')

# 定义视角类别
views = ['front', 'other', 'rear', 'standing']

# 定义拥挤度级别（带数字前缀）
levels = ['1_empty', '2_seated', '3_standing', '4_crowd', '5_extremecrowd']

# 级别映射（用于合并现有数据）
level_mapping = {
    'empty': '1_empty',
    'seated': '2_seated',
    'standing': '3_standing',
    'crowd': '4_crowd',
    'extremecrowd': '5_extremecrowd'
}

# 定义划分比例
TRAIN_RATIO = 0.7
VAL_RATIO = 0.2
TEST_RATIO = 0.1


def get_existing_files():
    """获取目标目录中已存在的所有文件"""
    existing_files = set()
    for view in views:
        for split in ['train', 'val', 'test']:
            split_dir = os.path.join(TARGET_BASE_DIR, view, split)
            if os.path.exists(split_dir):
                for root, dirs, files in os.walk(split_dir):
                    for file in files:
                        if file.endswith('.jpeg'):
                            existing_files.add(file)
    return existing_files


def merge_existing_datasets():
    """合并现有的数据集，将不带数字前缀的级别目录中的文件移动到带数字前缀的目录中"""
    print("\n=== 开始合并现有数据集 ===")

    for view in views:
        view_dir = os.path.join(TARGET_BASE_DIR, view)
        if not os.path.exists(view_dir):
            continue

        print(f"处理视角: {view}")

        for split in ['train', 'val', 'test']:
            split_dir = os.path.join(view_dir, split)
            if not os.path.exists(split_dir):
                continue

            for item in os.listdir(split_dir):
                item_path = os.path.join(split_dir, item)
                if os.path.isdir(item_path):
                    if item in level_mapping:
                        target_level = level_mapping[item]
                        target_dir = os.path.join(split_dir, target_level)
                        os.makedirs(target_dir, exist_ok=True)

                        files = os.listdir(item_path)
                        for file in files:
                            src_file = os.path.join(item_path, file)
                            dest_file = os.path.join(target_dir, file)
                            if os.path.exists(src_file) and not os.path.exists(dest_file):
                                shutil.move(src_file, dest_file)
                                print(f"  移动: {src_file} -> {dest_file}")

                        if not os.listdir(item_path):
                            os.rmdir(item_path)
                            print(f"  删除空目录: {item_path}")


for view in views:
    view_dir = os.path.join(TARGET_BASE_DIR, view)
    os.makedirs(os.path.join(view_dir, 'train'), exist_ok=True)
    os.makedirs(os.path.join(view_dir, 'val'), exist_ok=True)
    os.makedirs(os.path.join(view_dir, 'test'), exist_ok=True)

    for level in levels:
        os.makedirs(os.path.join(view_dir, 'train', level), exist_ok=True)
        os.makedirs(os.path.join(view_dir, 'val', level), exist_ok=True)
        os.makedirs(os.path.join(view_dir, 'test', level), exist_ok=True)

merge_existing_datasets()

print("\n=== 检查现有数据集 ===")
existing_files = get_existing_files()
print(f"目标目录中已存在的文件数: {len(existing_files)}")

print("\n=== 开始划分新数据集 ===")
for view in views:
    view_path = os.path.join(SOURCE_DIR, view)
    if not os.path.exists(view_path):
        print(f"\n视角 {view} 源目录不存在，跳过")
        continue

    print(f"\n处理视角: {view}")

    level_counts = {}
    for root, dirs, files in os.walk(view_path):
        for file in files:
            if file.lower().endswith(('.jpg', '.jpeg', '.png')):
                if file in existing_files:
                    continue

                parts = file.split('_')
                if len(parts) >= 2:
                    level = parts[1]
                    if level in level_mapping:
                        mapped_level = level_mapping[level]
                        if mapped_level not in level_counts:
                            level_counts[mapped_level] = []
                        level_counts[mapped_level].append(os.path.join(root, file))

    print("级别分布:")
    total = 0
    new_count = 0
    for level, files in level_counts.items():
        count = len(files)
        total += count
        print(f"  {level}: {count} 张")
    print(f"  总计: {total} 张")

    for level, files in level_counts.items():
        if not files:
            continue

        random.shuffle(files)

        count = len(files)
        train_count = int(count * TRAIN_RATIO)
        val_count = int(count * VAL_RATIO)
        test_count = count - train_count - val_count

        train_files = files[:train_count]
        val_files = files[train_count:train_count+val_count]
        test_files = files[train_count+val_count:]

        def copy_files(src_files, dest):
            for src_file in src_files:
                dest_file = os.path.join(dest, os.path.basename(src_file))
                shutil.copy2(src_file, dest_file)

        copy_files(train_files, os.path.join(TARGET_BASE_DIR, view, 'train', level))
        copy_files(val_files, os.path.join(TARGET_BASE_DIR, view, 'val', level))
        copy_files(test_files, os.path.join(TARGET_BASE_DIR, view, 'test', level))

        print(f"  级别 {level} 分配:")
        print(f"    训练集: {len(train_files)} 张")
        print(f"    验证集: {len(val_files)} 张")
        print(f"    测试集: {len(test_files)} 张")

print("\n数据集准备完成！")
