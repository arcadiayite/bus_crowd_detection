# -*- coding: utf-8 -*-
"""
测试视角分类

功能：
1. 使用 dataset_view/test 数据进行视角分类测试
2. 计算分类准确率、精确率、召回率等指标
3. 生成混淆矩阵
"""

import os
import sys
from collections import defaultdict

# 测试数据目录
TEST_DIR = "e:\\公交拥挤度识别\\dataset_view\\test"

# 视角标签映射（按目录名字母顺序）
VIEW_LABELS = {
    0: 'front',
    1: 'other',
    2: 'rear',
    3: 'standing'
}


def get_ground_truth_from_filename(filename):
    """从文件名中提取真实的视角标签"""
    parts = filename.split('_')
    if len(parts) >= 2:
        view = parts[0]
        if view in ['front', 'other', 'rear', 'standing']:
            return view
    return None


def collect_test_images():
    """收集测试图片路径和真实标签"""
    test_data = []
    for view_dir in ['front', 'other', 'rear', 'standing']:
        dir_path = os.path.join(TEST_DIR, view_dir)
        if os.path.exists(dir_path):
            for filename in os.listdir(dir_path):
                if filename.endswith('.jpeg'):
                    img_path = os.path.join(dir_path, filename)
                    ground_truth = get_ground_truth_from_filename(filename)
                    if ground_truth:
                        test_data.append((img_path, ground_truth))
    return test_data


def classify_single_image(view_model, img_path):
    """对单张图片进行视角分类"""
    try:
        results = view_model.predict(source=str(img_path), verbose=False)
        for result in results:
            if hasattr(result, 'probs') and result.probs is not None:
                class_id = int(result.probs.top1)
                if hasattr(result.probs, 'top1conf'):
                    if hasattr(result.probs.top1conf, 'item'):
                        confidence = float(result.probs.top1conf.item())
                    else:
                        confidence = float(result.probs.top1conf)
                else:
                    if hasattr(result.probs, 'data'):
                        if hasattr(result.probs.data, 'cpu'):
                            probs_data = result.probs.data.cpu().numpy()
                        else:
                            probs_data = result.probs.data.numpy()
                        confidence = float(probs_data[class_id])
                    else:
                        if hasattr(result.probs, 'cpu'):
                            probs_data = result.probs.cpu().numpy()
                        else:
                            probs_data = result.probs.numpy()
                        confidence = float(probs_data[class_id])
                view_label = VIEW_LABELS.get(class_id, 'unknown')
                return view_label, confidence
            else:
                return 'unknown', 0.0
    except Exception as e:
        print(f"分类失败 {img_path}: {e}")
        return 'unknown', 0.0
    return 'unknown', 0.0


def calculate_metrics(true_labels, predicted_labels):
    """计算分类指标"""
    confusion_matrix = defaultdict(lambda: defaultdict(int))
    for true, pred in zip(true_labels, predicted_labels):
        confusion_matrix[true][pred] += 1
    
    correct = sum(1 for true, pred in zip(true_labels, predicted_labels) if true == pred)
    accuracy = correct / len(true_labels) if true_labels else 0
    
    precision = {}
    recall = {}
    for label in set(true_labels):
        pred_positive = sum(1 for pred in predicted_labels if pred == label)
        precision[label] = confusion_matrix[label][label] / pred_positive if pred_positive > 0 else 0
        true_positive = sum(1 for true in true_labels if true == label)
        recall[label] = confusion_matrix[label][label] / true_positive if true_positive > 0 else 0
    
    return accuracy, precision, recall, confusion_matrix


def main():
    print("开始测试视角分类...")
    
    # 动态导入，避免模块加载失败时影响其他功能
    try:
        from ultralytics import YOLO
    except ImportError:
        print("错误: 无法导入 ultralytics，请先安装: pip install ultralytics")
        return
    
    # 加载模型
    VIEW_CLASSIFY_MODEL = 'e:\\公交拥挤度识别\\view_weights\\view_classify.pt'
    if not os.path.exists(VIEW_CLASSIFY_MODEL):
        print(f"错误: 视角分类模型不存在: {VIEW_CLASSIFY_MODEL}")
        return
    
    print(f"加载模型: {VIEW_CLASSIFY_MODEL}")
    view_model = YOLO(VIEW_CLASSIFY_MODEL)
    
    # 收集测试数据
    test_data = collect_test_images()
    print(f"找到 {len(test_data)} 张测试图片")
    
    if not test_data:
        print("错误: 没有找到测试图片")
        return
    
    # 提取图片路径和真实标签
    image_paths = [img_path for img_path, _ in test_data]
    true_labels = [ground_truth for _, ground_truth in test_data]
    
    # 进行视角分类
    print("\n进行视角分类...")
    predicted_labels = []
    confidences = []
    
    for i, img_path in enumerate(image_paths):
        view, conf = classify_single_image(view_model, img_path)
        predicted_labels.append(view)
        confidences.append(conf)
        if (i + 1) % 50 == 0:
            print(f"已处理 {i + 1}/{len(image_paths)} 张图片")
    
    # 计算指标
    accuracy, precision, recall, confusion_matrix = calculate_metrics(true_labels, predicted_labels)
    
    # 输出结果
    print("\n=== 测试结果 ===")
    print(f"测试图片数量: {len(test_data)}")
    print(f"准确率: {accuracy:.4f}")
    print()
    
    print("精确率:")
    for label, value in precision.items():
        print(f"  {label}: {value:.4f}")
    print()
    
    print("召回率:")
    for label, value in recall.items():
        print(f"  {label}: {value:.4f}")
    print()
    
    print("混淆矩阵:")
    all_labels = sorted(set(true_labels + predicted_labels))
    print("\t" + "\t".join(all_labels))
    for true_label in all_labels:
        row = [str(confusion_matrix[true_label].get(pred_label, 0)) for pred_label in all_labels]
        print(f"{true_label}\t" + "\t".join(row))
    print()
    
    # 输出错误分类的样本
    print("错误分类的样本（前10个）:")
    error_count = 0
    for i, (img_path, true_label) in enumerate(test_data):
        pred_label = predicted_labels[i]
        if true_label != pred_label:
            error_count += 1
            if error_count <= 10:
                conf = confidences[i]
                print(f"  样本 {error_count}: {os.path.basename(img_path)}")
                print(f"    真实视角={true_label}, 预测视角={pred_label}, 置信度={conf:.4f}")
    
    print(f"\n错误分类数量: {error_count}")
    print(f"错误分类率: {error_count / len(true_labels):.4f}")


if __name__ == "__main__":
    main()
