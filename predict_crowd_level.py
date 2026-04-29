import os
import sys
from ultralytics import YOLO
import numpy as np

# 配置路径
VIEW_CLASSIFY_MODEL = 'view_weights/view_classify.pt'
CROWD_MODEL_FRONT = 'view_weights/front/front_best.pt'
CROWD_MODEL_REAR = 'view_weights/rear/rear_best.pt'
CROWD_MODEL_STANDING = 'view_weights/standing/standing_best.pt'

# 拥挤度级别映射
CROWD_LEVELS = {
    0: '1_empty',
    1: '2_seated',
    2: '3_standing',
    3: '4_crowd',
    4: '5_extremecrowd'
}

# 视角映射（基于view_datasets目录的字母顺序: front, other, rear, standing）
VIEW_LABELS = {
    0: 'front',
    1: 'other',
    2: 'rear',
    3: 'standing'
}

def load_models():
    """加载模型"""
    print("加载模型中...")

    view_model = None
    crowd_models = {}

    if os.path.exists(VIEW_CLASSIFY_MODEL):
        print(f"加载视角分类模型: {VIEW_CLASSIFY_MODEL}")
        view_model = YOLO(VIEW_CLASSIFY_MODEL)
    else:
        print(f"警告: 视角分类模型不存在: {VIEW_CLASSIFY_MODEL}")

    if os.path.exists(CROWD_MODEL_FRONT):
        print(f"加载front拥挤度模型: {CROWD_MODEL_FRONT}")
        crowd_models['front'] = YOLO(CROWD_MODEL_FRONT)
    else:
        print(f"警告: front拥挤度模型不存在: {CROWD_MODEL_FRONT}")

    if os.path.exists(CROWD_MODEL_REAR):
        print(f"加载rear拥挤度模型: {CROWD_MODEL_REAR}")
        crowd_models['rear'] = YOLO(CROWD_MODEL_REAR)
    else:
        print(f"警告: rear拥挤度模型不存在: {CROWD_MODEL_REAR}")

    if os.path.exists(CROWD_MODEL_STANDING):
        print(f"加载standing拥挤度模型: {CROWD_MODEL_STANDING}")
        crowd_models['standing'] = YOLO(CROWD_MODEL_STANDING)
    else:
        print(f"警告: standing拥挤度模型不存在: {CROWD_MODEL_STANDING}")

    return view_model, crowd_models


def classify_views(view_model, image_paths):
    """对输入图片进行视角分类"""
    print("进行视角分类...")
    view_results = {}

    for img_path in image_paths:
        if not os.path.exists(img_path):
            print(f"警告: 文件不存在: {img_path}")
            continue

        try:
            # 使用predict方法，设置verbose=False减少输出
            results = view_model.predict(source=str(img_path), verbose=False)
            for result in results:
                # 检查result.probs是否存在
                if hasattr(result, 'probs') and result.probs is not None:
                    try:
                        # 安全获取概率信息
                        print(f"\n图片: {os.path.basename(img_path)}")
                        print("视角分类结果:")

                        # 尝试不同的方式获取概率
                        try:
                            # 方法1：直接使用top1和top1conf
                            class_id = int(result.probs.top1)
                            if hasattr(result.probs, 'top1conf'):
                                if hasattr(result.probs.top1conf, 'item'):
                                    confidence = float(result.probs.top1conf.item())
                                else:
                                    confidence = float(result.probs.top1conf)
                            else:
                                # 方法2：尝试获取概率数组
                                if hasattr(result.probs, 'data'):
                                    # 先检查data属性
                                    if hasattr(result.probs.data, 'cpu'):
                                        probs_data = result.probs.data.cpu().numpy()
                                    else:
                                        probs_data = result.probs.data.numpy()
                                    confidence = float(probs_data[class_id])
                                else:
                                    # 方法3：尝试直接转换
                                    if hasattr(result.probs, 'cpu'):
                                        probs_data = result.probs.cpu().numpy()
                                    else:
                                        probs_data = result.probs.numpy()
                                    confidence = float(probs_data[class_id])

                            # 输出每个视角的置信度
                            if hasattr(result.probs, 'data'):
                                if hasattr(result.probs.data, 'cpu'):
                                    probs_data = result.probs.data.cpu().numpy()
                                else:
                                    probs_data = result.probs.data.numpy()
                                for i, prob in enumerate(probs_data):
                                    if i in VIEW_LABELS:
                                        view_label = VIEW_LABELS[i]
                                        print(f"  {view_label}: {prob:.4f}")
                            else:
                                # 如果无法获取所有概率，只输出最高置信度的视角
                                view_label = VIEW_LABELS.get(class_id, 'unknown')
                                print(f"  {view_label}: {confidence:.4f}")

                            # 确定最终的视角标签
                            view_label = VIEW_LABELS.get(class_id, 'unknown')
                        except Exception as e:
                            print(f"获取概率信息失败: {e}")
                            # 尝试使用默认值
                            class_id = 0
                            confidence = 0.0
                            view_label = 'unknown'

                        if view_label != 'unknown':
                            if view_label not in view_results or confidence > view_results[view_label]['confidence']:
                                view_results[view_label] = {
                                    'path': img_path,
                                    'confidence': confidence
                                }
                    except Exception as e:
                        print(f"处理分类结果失败: {e}")
                        # 打印详细的错误信息
                        import traceback
                        traceback.print_exc()
                else:
                    print(f"警告: 模型输出缺少probs属性")
        except Exception as e:
            print(f"分类失败: {e}")
            # 打印详细的错误信息
            import traceback
            traceback.print_exc()

    return view_results


def predict_crowd_level(view_model, crowd_models, view_results):
    """预测拥挤度级别"""
    print("预测拥挤度级别...")

    results = {}

    for view, info in view_results.items():
        if view not in crowd_models:
            print(f"警告: 缺少{view}视角的拥挤度模型")
            continue

        img_path = info['path']
        model = crowd_models[view]

        try:
            # 使用predict方法，设置verbose=False减少输出
            crowd_results = model.predict(source=str(img_path), verbose=False)

            for crowd_result in crowd_results:
                # 获取预测结果
                if hasattr(crowd_result, 'probs') and crowd_result.probs is not None:
                    class_id = int(crowd_result.probs.top1)
                    confidence = float(crowd_result.probs.top1conf.item() if hasattr(crowd_result.probs.top1conf, 'item') else crowd_result.probs.top1conf)
                elif hasattr(crowd_result, 'boxes') and len(crowd_result.boxes) > 0:
                    # 如果是检测模型，获取第一个检测结果的类别
                    class_id = int(crowd_result.boxes[0].cls[0])
                    confidence = float(crowd_result.boxes[0].conf[0].item() if hasattr(crowd_result.boxes[0].conf[0], 'item') else crowd_result.boxes[0].conf[0])
                else:
                    print(f"警告: 无法从模型输出获取预测结果")
                    continue

                crowd_level = CROWD_LEVELS.get(class_id, '未知')

                results[view] = {
                    'level': crowd_level,
                    'confidence': confidence,
                    'image': img_path
                }

                print(f"视角: {view}")
                print(f"  图片: {img_path}")
                print(f"  拥挤度级别: {crowd_level}")
                print(f"  置信度: {confidence:.4f}")
                print()

        except Exception as e:
            print(f"预测{view}视角拥挤度失败: {e}")
            import traceback
            traceback.print_exc()

    # 检查未预测的视角
    predicted_views = set(results.keys())
    all_views = {'front', 'rear', 'standing'}
    missing_views = all_views - predicted_views

    for view in missing_views:
        if view in view_results:
            print(f"警告: {view}视角有有效图片但未进行拥挤度预测")

    return results


def main(image_paths):
    """主函数"""
    view_model, crowd_models = load_models()

    if view_model is None:
        print("错误: 无法加载视角分类模型")
        return

    view_results = classify_views(view_model, image_paths)

    if not view_results:
        print("错误: 没有有效的视角分类结果")
        return

    results = predict_crowd_level(view_model, crowd_models, view_results)

    print("\n=== 预测结果 ===")
    for view, result in results.items():
        print(f"视角: {view}")
        print(f"  图片: {result.get('image', 'N/A')}")
        print(f"  拥挤度级别: {result.get('level', '未知')}")
        confidence = result.get('confidence', '未知')
        if isinstance(confidence, (int, float)):
            print(f"  置信度: {confidence:.4f}")
        else:
            print(f"  置信度: {confidence}")
        print()

    # 返回结果字典供调用者使用
    return results


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python predict_crowd_level.py <图片路径1> [图片路径2] ...")
        sys.exit(1)

    image_paths = sys.argv[1:]
    main(image_paths)