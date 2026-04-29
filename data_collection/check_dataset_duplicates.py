# -*- coding: utf-8 -*-
"""
检查 dataset_view 中 train、val、test 目录是否有重复文件
"""

import os

def get_all_files(directory):
    """获取目录下所有文件"""
    files = set()
    for root, dirs, filenames in os.walk(directory):
        for filename in filenames:
            if filename.endswith('.jpeg'):
                files.add(filename)
    return files

def main():
    base_dir = "e:\\公交拥挤度识别\\dataset_view"

    train_files = get_all_files(os.path.join(base_dir, "train"))
    val_files = get_all_files(os.path.join(base_dir, "val"))
    test_files = get_all_files(os.path.join(base_dir, "test"))

    print(f"train 文件数: {len(train_files)}")
    print(f"val 文件数: {len(val_files)}")
    print(f"test 文件数: {len(test_files)}")

    # 检查 train 和 val 是否有重复
    train_val_overlap = train_files & val_files
    if train_val_overlap:
        print(f"\ntrain 和 val 重复文件数: {len(train_val_overlap)}")
        for f in list(train_val_overlap)[:10]:
            print(f"  {f}")
    else:
        print("\ntrain 和 val 无重复")

    # 检查 train 和 test 是否有重复
    train_test_overlap = train_files & test_files
    if train_test_overlap:
        print(f"\ntrain 和 test 重复文件数: {len(train_test_overlap)}")
        for f in list(train_test_overlap)[:10]:
            print(f"  {f}")
    else:
        print("\ntrain 和 test 无重复")

    # 检查 val 和 test 是否有重复
    val_test_overlap = val_files & test_files
    if val_test_overlap:
        print(f"\nval 和 test 重复文件数: {len(val_test_overlap)}")
        for f in list(val_test_overlap)[:10]:
            print(f"  {f}")
    else:
        print("\nval 和 test 无重复")

    # 检查三个目录总共有多少唯一文件
    all_files = train_files | val_files | test_files
    print(f"\n唯一文件总数: {len(all_files)}")

if __name__ == "__main__":
    main()
