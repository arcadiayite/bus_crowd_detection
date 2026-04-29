#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
统计分类结果中各分类的图片数量
"""

import os
import glob

def count_images(directory):
    """统计目录中图片数量"""
    image_extensions = ['.jpg', '.jpeg', '.png', '.gif']
    count = 0
    for ext in image_extensions:
        count += len(glob.glob(os.path.join(directory, f'*{ext}'), recursive=False))
    return count

def main():
    sorted_dir = 'sorted'
    
    print("开始统计分类结果...")
    print("=" * 60)
    
    total = 0
    
    # 定义所有可能的分类目录
    categories = [
        ('front', 'crowd'),
        ('front', 'empty'),
        ('rear', 'crowd'),
        ('rear', 'empty'),
        ('standing', 'crowd'),
        ('standing', 'seated'),
        ('standing', 'standing'),
        ('other', 'empty')
    ]
    
    for first_cat, second_cat in categories:
        cat_dir = os.path.join(sorted_dir, first_cat, second_cat)
        if os.path.exists(cat_dir):
            cat_count = count_images(cat_dir)
            total += cat_count
            print(f"{first_cat}/{second_cat}: {cat_count}")
    
    print("=" * 60)
    print(f"总计: {total}")

if __name__ == "__main__":
    main()
