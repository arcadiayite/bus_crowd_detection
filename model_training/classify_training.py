#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
YOLO分类模型训练和预测脚本

功能：
1. 训练YOLO分类模型
2. 自动管理训练输出目录，避免覆盖已有结果
3. 在测试集上进行预测并可视化结果
4. 保存预测结果到CSV文件
"""

import logging
from pathlib import Path
from ultralytics import YOLO
import os

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


def train_model(
    model_path: str,
    data_dir: str,
    output_base_dir: str = r"output",
    epochs: int = 100,
    imgsz: int = 640,
    batch: int = 16,
    device: int = 0
) -> bool:
    """
    训练YOLO分类模型，自动管理输出文件夹
    
    :param model_path: 预训练模型路径
    :param data_dir: 数据集目录路径
    :param output_base_dir: 训练结果基础目录
    :param epochs: 训练轮数
    :param imgsz: 图片大小
    :param batch: 批次大小
    :param device: GPU设备ID
    :return: 是否训练成功
    """
    try:
        # 获取下一个运行编号
        run_num = get_next_run_number(output_base_dir)
        run_name = f"run_{run_num}"
        output_dir = Path(output_base_dir) / run_name
        
        logging.info(f"开始训练模型...")
        logging.info(f"模型: {model_path}")
        logging.info(f"数据集: {data_dir}")
        logging.info(f"输出目录: {output_dir}")
        logging.info(f"运行编号: {run_name}")
        
        # 加载模型
        model = YOLO(model_path)
        
        # 训练模型
        results = model.train(
            data=data_dir,
            epochs=epochs,
            imgsz=imgsz,
            batch=batch,
            device=device,
            project=output_base_dir,
            name=run_name,
            exist_ok=False  # 确保不会覆盖已有的文件夹
        )
        
        logging.info(f"✓ 训练完成！结果已保存到: {output_dir}")
        return True
        
    except Exception as e:
        logging.error(f"训练过程中出现错误: {e}")
        return False

def predict_on_test_set(
    model_path: str,
    test_data_dir: str,
    output_dir: Path = None,
    device: int = 0,
    save: bool = True,
    show_labels: bool = True
):
    """
    在测试集上进行预测并可视化结果
    
    :param model_path: 训练好的模型路径
    :param test_data_dir: 测试数据集目录
    :param output_dir: 输出目录
    :param device: GPU设备ID
    :param save: 是否保存预测结果
    :param show_labels: 是否显示标签
    """

    try:
        # 创建保存目录
        if output_dir:
            save_dir = os.path.join(output_dir, "predictions")
        else:
            save_dir = Path("predictions")
        
        os.makedirs(save_dir, exist_ok=True)
        
        logging.info(f"开始在测试集上进行预测...")
        logging.info(f"模型: {model_path}")
        logging.info(f"测试数据集: {test_data_dir}")
        logging.info(f"预测结果保存到: {save_dir}")
        
        # 加载模型
        model = YOLO(model_path)
        
        # 获取测试集所有图片
        test_dir = Path(test_data_dir)
        image_extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff'}
        test_images = []
        
        # 递归查找所有测试图片
        for ext in image_extensions:
            test_images.extend(test_dir.rglob(f"*{ext}"))
            test_images.extend(test_dir.rglob(f"*{ext.upper()}"))
        
        if not test_images:
            logging.warning(f"在 {test_data_dir} 中没有找到测试图片！")
            return
        
        logging.info(f"找到 {len(test_images)} 张测试图片")
        
        # 对每张图片进行预测
        predictions = []
        for i, img_path in enumerate(test_images, 1):
            logging.info(f"预测进度: {i}/{len(test_images)} - {img_path.name}")
            
            # 进行预测
            results = model.predict(
                source=str(img_path),
                device=device,
                save=save,
                save_dir=save_dir,
                show_labels=show_labels,
                exist_ok=True
            )
            
            # 保存预测结果
            for result in results:
                if hasattr(result, 'probs'):
                    pred_class = result.probs.top1
                    pred_conf = result.probs.top1conf.item()
                    predictions.append({
                        'image': img_path.name,
                        'predicted_class': pred_class,
                        'confidence': pred_conf,
                        'top5_classes': result.probs.top5,
                        'top5_confs': result.probs.top5conf.tolist()
                    })
        
        # 保存预测结果到CSV文件
        if predictions:
            import pandas as pd
            csv_path = os.path.join(save_dir, "predictions.csv")
            df = pd.DataFrame(predictions)
            df.to_csv(csv_path, index=False, encoding='utf-8')
            logging.info(f"预测结果已保存到: {csv_path}")
        
        logging.info(f"✓ 预测完成！")
        
    except Exception as e:
        logging.error(f"预测过程中出现错误: {e}")
        raise e

# %%
# 使用示例
if __name__ == "__main__":
    # model_path = r"D:\wyb_code\yolo26\YoloPt\yolo11m-cls.pt"
    # data_dir = r"X:\04_bus_passengers"
    # output_dir = r"D:\wyb_code\yolo26\output"
    model_path = "YoloPt\yolo11m-cls.pt"
    data_dir = "04_bus_passengers"
    output_dir = "output"
    
    '''
    # 执行训练
    '''
    train_model(
        model_path=model_path,
        data_dir=data_dir,
        output_base_dir=output_dir,
        epochs=100,
        imgsz=640,
        batch=16,
        device=0
    )

    
    # Load a model
    # best_model_path = "D:/wyb_code/yolo26/output/run_3/weights/best.pt"
    # test_dir = "X:/04_bus_passengers/test"
    # trained_run_dir = 'D:/wyb_code/yolo26/output/run_3/test'
    best_model_path = "output/run_3/weights/best.pt"
    test_dir = "04_bus_passengers/test"
    trained_run_dir = 'run_3/test'

    # Validate the model
    predict_on_test_set(
        model_path=str(best_model_path),
        test_data_dir=str(test_dir),
        output_dir=Path(trained_run_dir),
        device=0,
        save=True,
        show_labels=True
    ) # no arguments needed, dataset and settings remembered
    

# %%
