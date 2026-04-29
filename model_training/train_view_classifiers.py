#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
视角拥挤度分类器训练脚本

功能：
1. 训练指定视角（front、rear、standing）的拥挤度分类器
2. 自动管理训练输出目录，避免覆盖已有结果
3. 保存最佳权重到指定目录
4. 支持自定义训练参数（ epochs、batch size、image size 等）
"""

import logging
from pathlib import Path
from ultralytics import YOLO
import os
import argparse
import shutil

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')


def get_next_run_number(output_base_dir: str) -> int:
    """
    获取下一个训练文件夹的编号
    :param output_base_dir: 训练结果基础目录
    :return: 下一个编号
    """
    base_path = Path(output_base_dir)
    base_path.mkdir(parents=True, exist_ok=True)
    
    # 查找所有 runs 文件夹
    existing_runs = [d for d in base_path.iterdir() if d.is_dir() and d.name.startswith('run_')]
    
    if not existing_runs:
        return 1
    
    # 提取编号并返回最大编号 + 1
    run_numbers = []
    for run_dir in existing_runs:
        try:
            num = int(run_dir.name.split('_')[1])
            run_numbers.append(num)
        except (IndexError, ValueError):
            continue
    
    return max(run_numbers) + 1 if run_numbers else 1


def train_view_classifier(
    view: str,
    model_path: str = "YoloPt\yolo11m-cls.pt",
    data_dir: str = "view_datasets",
    output_base_dir: str = r"output_crowd",
    weights_dir: str = r"view_weights",
    epochs: int = 100,
    imgsz: int = 640,
    batch: int = 16,
    device: int = 0
) -> bool:
    """
    训练指定视角的拥挤度分类器
    
    :param view: 视角名称 (front, rear, standing)
    :param model_path: 预训练模型路径
    :param data_dir: 数据集基础目录
    :param output_base_dir: 训练结果基础目录
    :param weights_dir: 权重保存目录
    :param epochs: 训练轮数
    :param imgsz: 图片大小
    :param batch: 批次大小
    :param device: GPU设备ID
    :return: 是否训练成功
    """
    try:
        # 构建数据集路径
        view_data_dir = os.path.join(data_dir, view)
        if not os.path.exists(view_data_dir):
            logging.error(f"数据集目录不存在: {view_data_dir}")
            return False
        
        # 获取下一个运行编号
        run_num = get_next_run_number(output_base_dir)
        run_name = f"{view}_run_{run_num}"
        output_dir = Path(output_base_dir) / run_name
        
        logging.info(f"开始训练 {view} 视角的拥挤度分类器...")
        logging.info(f"模型: {model_path}")
        logging.info(f"数据集: {view_data_dir}")
        logging.info(f"输出目录: {output_dir}")
        logging.info(f"运行编号: {run_name}")
        
        # 加载模型
        model = YOLO(model_path)
        
        # 训练模型
        results = model.train(
            data=view_data_dir,
            epochs=epochs,
            imgsz=imgsz,
            batch=batch,
            device=device,
            project=output_base_dir,
            name=run_name,
            exist_ok=False  # 确保不会覆盖已有的文件夹
        )
        
        logging.info(f"✓ 训练完成！结果已保存到: {output_dir}")
        
        # 保存最佳权重到指定目录
        best_weight_path = output_dir / "weights" / "best.pt"
        if best_weight_path.exists():
            # 构建目标权重路径
            target_weight_dir = os.path.join(weights_dir, view)
            os.makedirs(target_weight_dir, exist_ok=True)
            
            # 构建目标文件名
            target_weight_path = os.path.join(target_weight_dir, f"{view}_best.pt")
            
            # 复制最佳权重
            shutil.copy2(best_weight_path, target_weight_path)
            logging.info(f"✓ 最佳权重已保存到: {target_weight_path}")
        else:
            logging.error(f"未找到最佳权重文件: {best_weight_path}")
            return False
        
        return True
        
    except Exception as e:
        logging.error(f"训练过程中出现错误: {e}")
        return False

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="训练视角拥挤度分类器")
    parser.add_argument("view", nargs="+", choices=["front", "rear", "standing"], help="要训练的视角（可多个）")
    parser.add_argument("--model", default="YoloPt\yolo11m-cls.pt", help="预训练模型路径")
    parser.add_argument("--data", default="view_datasets", help="数据集基础目录")
    parser.add_argument("--output", default="output_crowd", help="训练结果基础目录")
    parser.add_argument("--weights", default="view_weights", help="权重保存目录")
    parser.add_argument("--epochs", type=int, default=100, help="训练轮数")
    parser.add_argument("--imgsz", type=int, default=640, help="图片大小")
    parser.add_argument("--batch", type=int, default=16, help="批次大小")
    parser.add_argument("--device", type=int, default=0, help="GPU设备ID")
    
    args = parser.parse_args()
    
    # 执行训练
    all_success = True
    for view in args.view:
        logging.info(f"\n====================================")
        logging.info(f"开始训练 {view} 视角分类器")
        logging.info(f"====================================")
        
        success = train_view_classifier(
            view=view,
            model_path=args.model,
            data_dir=args.data,
            output_base_dir=args.output,
            weights_dir=args.weights,
            epochs=args.epochs,
            imgsz=args.imgsz,
            batch=args.batch,
            device=args.device
        )
        
        if success:
            logging.info(f"{view} 视角分类器训练成功！")
        else:
            logging.error(f"{view} 视角分类器训练失败！")
            all_success = False
    
    logging.info(f"\n====================================")
    if all_success:
        logging.info("所有视角分类器训练成功！")
    else:
        logging.error("部分视角分类器训练失败！")