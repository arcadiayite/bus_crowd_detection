#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
公交车辆图片分类工具

功能：
1. 显示collected文件夹中的图片
2. 第一步分类：前车厢、后车厢、站立禁区、都不是
3. 第二步分类：empty、seated、standing、crowd、extremecrowd
4. 分类完成后重命名文件并移动到sorted文件夹
5. 记录已分类图片，避免重复分类
6. 自动排除视角为front、standing、rear且拥挤度为empty、seated的图片
"""

import os
import shutil
import json
import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk
import glob
import sys

# 配置
COLLECTED_DIR = "collected"
SORTED_DIR = "sorted"
CLASSIFICATION_FILE = "classified_images.json"

# 分类定义
FIRST_CATEGORIES = {
    "front": "前车厢",
    "rear": "后车厢", 
    "standing": "站立禁区",
    "other": "都不是"
}

SECOND_CATEGORIES = {
    "empty": "empty",
    "seated": "seated",
    "standing": "standing",
    "crowd": "crowd",
    "extremecrowd": "extremecrowd"
}

def load_models():
    """加载视角分类模型和拥挤度分类模型"""
    try:
        # 导入预测模块
        sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from predict_crowd_level import load_models as load_prediction_models
        return load_prediction_models()
    except Exception as e:
        print(f"加载模型失败: {e}")
        return None, None

def auto_classify_images(image_paths, view_model, crowd_models):
    """自动分类图片，返回需要人工筛选的图片路径"""
    try:
        # 导入预测模块
        sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from predict_crowd_level import VIEW_LABELS, CROWD_LEVELS
        
        # 对每张图片进行独立的视角分类和拥挤度预测
        path_to_result = {}
        processed_count = 0
        
        print(f"开始对 {len(image_paths)} 张图片进行自动分类...")
        
        for img_path in image_paths:
            if not os.path.exists(img_path):
                print(f"警告: 文件不存在: {img_path}")
                continue
            
            try:
                # 1. 进行视角分类
                view_results = view_model.predict(source=str(img_path), verbose=False)
                
                for result in view_results:
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
                                confidence = 0.0
                        
                        view_label = VIEW_LABELS.get(class_id, 'unknown')
                        
                        # 2. 如果视角是front、rear或standing，进行拥挤度预测
                        crowd_level = 'unknown'
                        if view_label in ['front', 'rear', 'standing'] and view_label in crowd_models:
                            crowd_result = crowd_models[view_label].predict(source=str(img_path), verbose=False)
                            
                            for cr in crowd_result:
                                if hasattr(cr, 'probs') and cr.probs is not None:
                                    crowd_class_id = int(cr.probs.top1)
                                    crowd_confidence = float(cr.probs.top1conf.item() if hasattr(cr.probs.top1conf, 'item') else cr.probs.top1conf)
                                    crowd_level = CROWD_LEVELS.get(crowd_class_id, 'unknown')
                                elif hasattr(cr, 'boxes') and len(cr.boxes) > 0:
                                    crowd_class_id = int(cr.boxes[0].cls[0])
                                    crowd_confidence = float(cr.boxes[0].conf[0].item() if hasattr(cr.boxes[0].conf[0], 'item') else cr.boxes[0].conf[0])
                                    crowd_level = CROWD_LEVELS.get(crowd_class_id, 'unknown')
                                
                                break
                        
                        path_to_result[img_path] = (view_label, crowd_level)
                        break
                
                processed_count += 1
                if processed_count % 100 == 0:
                    print(f"已处理 {processed_count}/{len(image_paths)} 张图片...")
                
            except Exception as e:
                print(f"处理图片失败 {os.path.basename(img_path)}: {e}")
                path_to_result[img_path] = ('unknown', 'unknown')
        
        print(f"自动分类完成，共处理 {processed_count} 张图片")
        
        # 筛选需要人工处理的图片
        need_manual_check = []
        auto_classified_paths = []
        
        for img_path in image_paths:
            if img_path in path_to_result:
                view, crowd_level = path_to_result[img_path]
                # 排除视角为front、standing、rear且拥挤度为empty、seated的图片
                if view in ['front', 'rear', 'standing'] and crowd_level in ['1_empty', '2_seated']:
                    # 自动分类并移动到相应目录
                    first_category = view
                    second_category = crowd_level.split('_')[1]  # 从'1_empty'提取'empty'
                    
                    # 创建sorted目录结构
                    category_dir = os.path.join(SORTED_DIR, first_category, second_category)
                    os.makedirs(category_dir, exist_ok=True)
                    
                    # 生成新文件名
                    original_name = os.path.basename(img_path)
                    name_without_ext = os.path.splitext(original_name)[0]
                    ext = os.path.splitext(original_name)[1]
                    
                    # 新文件名格式: 区域_拥挤度_原始名称
                    new_filename = f"{first_category}_{second_category}_{name_without_ext}{ext}"
                    new_path = os.path.join(category_dir, new_filename)
                    
                    # 复制文件到新位置
                    shutil.copy2(img_path, new_path)
                    auto_classified_paths.append(img_path)
                else:
                    # 需要人工筛选
                    need_manual_check.append(img_path)
            else:
                # 无法分类，需要人工筛选
                need_manual_check.append(img_path)
        
        print(f"自动分类完成：自动分类 {len(auto_classified_paths)} 张，需要人工筛选 {len(need_manual_check)} 张")
        return need_manual_check, auto_classified_paths
        
    except Exception as e:
        print(f"自动分类失败: {e}")
        import traceback
        traceback.print_exc()
        return image_paths, []  # 出错时返回所有图片，确保人工筛选能正常进行

class ImageClassifier:
    def __init__(self, root):
        self.root = root
        self.root.title("公交车辆图片分类工具")
        self.root.geometry("1000x800")
        self.root.resizable(True, True)
        # 确保窗口显示在前台
        self.root.lift()
        self.root.attributes('-topmost', True)
        self.root.after(100, lambda: self.root.attributes('-topmost', False))
        
        # 初始化变量
        self.image_paths = []
        self.current_index = 0
        self.current_image_path = None
        self.first_category = None
        self.second_category = None
        self.classified_images = set()
        self.view_model = None
        self.crowd_models = None
        
        # 加载模型
        self.load_prediction_models()
        
        # 加载已分类记录
        self.load_classified()
        
        # 创建界面
        self.create_ui()
        
        # 收集所有图片路径
        self.collect_images()
        
        # 显示第一张图片
        self.show_next_image()
    
    def load_prediction_models(self):
        """加载预测模型"""
        print("正在加载预测模型...")
        self.view_model, self.crowd_models = load_models()
        if self.view_model and self.crowd_models:
            print("模型加载成功")
        else:
            print("模型加载失败，将跳过自动分类")
    
    def collect_images(self):
        """收集所有未分类的图片"""
        self.image_paths = []
        total_images = 0
        
        # 遍历collected文件夹及其子文件夹
        for root, dirs, files in os.walk(COLLECTED_DIR):
            for file in files:
                if file.lower().endswith(('.jpg', '.jpeg', '.png')):
                    total_images += 1
                    full_path = os.path.join(root, file)
                    # 只添加未分类的图片
                    if full_path not in self.classified_images:
                        self.image_paths.append(full_path)
        
        print(f"找到 {len(self.image_paths)} 张未分类图片，共 {total_images} 张图片")
        
        # 自动分类图片
        if self.view_model and self.crowd_models and self.image_paths:
            print("开始自动分类...")
            self.image_paths, auto_classified_paths = auto_classify_images(self.image_paths, self.view_model, self.crowd_models)
            print(f"自动分类后剩余 {len(self.image_paths)} 张图片需要人工筛选")
            
            # 将自动分类的图片记录到已分类集合中，避免重复检测
            for img_path in auto_classified_paths:
                self.classified_images.add(img_path)
            
            # 保存已分类记录
            self.save_classified()
            print(f"已将 {len(auto_classified_paths)} 张自动分类的图片记录到已分类集合")
        
        self.update_stats(total_images)
    
    def update_stats(self, total_images=None):
        """更新分类统计信息"""
        if total_images is None:
            # 重新计算总图片数
            total_images = 0
            for root, dirs, files in os.walk(COLLECTED_DIR):
                for file in files:
                    if file.lower().endswith(('.jpg', '.jpeg', '.png')):
                        total_images += 1
        
        classified_count = len(self.classified_images)
        unclassified_count = total_images - classified_count
        
        # 计算比例
        if total_images > 0:
            classified_percent = (classified_count / total_images) * 100
            unclassified_percent = (unclassified_count / total_images) * 100
        else:
            classified_percent = 0
            unclassified_percent = 0
        
        # 更新统计信息显示
        stats_text = f"总图片数: {total_images} | 已分类: {classified_count} ({classified_percent:.1f}%) | 未分类: {unclassified_count} ({unclassified_percent:.1f}%)"
        self.stats_label.config(text=stats_text)
        
        print(stats_text)
    
    def load_classified(self):
        """加载已分类的图片记录"""
        if os.path.exists(CLASSIFICATION_FILE):
            try:
                with open(CLASSIFICATION_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.classified_images = set(data.get('classified', []))
                print(f"加载了 {len(self.classified_images)} 张已分类图片记录")
            except Exception as e:
                print(f"加载分类记录失败: {e}")
                self.classified_images = set()
        else:
            self.classified_images = set()
    
    def save_classified(self):
        """保存已分类的图片记录"""
        data = {
            'classified': list(self.classified_images)
        }
        try:
            with open(CLASSIFICATION_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存分类记录失败: {e}")
    
    def create_ui(self):
        """创建UI界面"""
        # 主框架
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # 分类状态显示
        self.status_frame = ttk.LabelFrame(main_frame, text="分类状态", padding="10")
        self.status_frame.pack(fill=tk.X, pady=5)
        
        self.status_label = ttk.Label(self.status_frame, text="请开始分类", font=("SimHei", 12))
        self.status_label.pack(anchor=tk.W)
        
        # 分类统计信息
        self.stats_frame = ttk.LabelFrame(main_frame, text="分类统计", padding="10")
        self.stats_frame.pack(fill=tk.X, pady=5)
        
        self.stats_label = ttk.Label(self.stats_frame, text="统计信息加载中...", font=("SimHei", 10))
        self.stats_label.pack(anchor=tk.W)
        
        # 第一步分类按钮
        self.first_frame = ttk.LabelFrame(main_frame, text="第一步分类：区域", padding="10")
        self.first_frame.pack(fill=tk.X, pady=5)
        
        first_buttons = ttk.Frame(self.first_frame)
        first_buttons.pack(fill=tk.X, expand=True)
        
        for i, (key, value) in enumerate(FIRST_CATEGORIES.items()):
            btn = ttk.Button(first_buttons, text=value, width=15, 
                           command=lambda k=key: self.select_first_category(k))
            btn.pack(side=tk.LEFT, padx=10, pady=5, expand=True, fill=tk.X)
        
        # 第二步分类按钮
        self.second_frame = ttk.LabelFrame(main_frame, text="第二步分类：拥挤度", padding="10")
        self.second_frame.pack(fill=tk.X, pady=5)
        
        second_buttons = ttk.Frame(self.second_frame)
        second_buttons.pack(fill=tk.X, expand=True)
        
        for i, (key, value) in enumerate(SECOND_CATEGORIES.items()):
            btn = ttk.Button(second_buttons, text=value, width=12, 
                           command=lambda k=key: self.select_second_category(k))
            btn.pack(side=tk.LEFT, padx=5, pady=5, expand=True, fill=tk.X)
        
        # 控制按钮
        self.control_frame = ttk.Frame(main_frame, padding="10")
        self.control_frame.pack(fill=tk.X, pady=5)
        
        self.next_btn = ttk.Button(self.control_frame, text="下一张", width=10, 
                                  command=self.show_next_image, state=tk.DISABLED)
        self.next_btn.pack(side=tk.RIGHT, padx=10)
        
        self.skip_btn = ttk.Button(self.control_frame, text="跳过", width=10, 
                                  command=self.skip_image)
        self.skip_btn.pack(side=tk.RIGHT, padx=10)
        
        # 图片显示区域
        self.image_frame = ttk.LabelFrame(main_frame, text="图片", padding="10")
        self.image_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        self.image_label = ttk.Label(self.image_frame, text="等待加载图片...")
        self.image_label.pack(fill=tk.BOTH, expand=True)
    
    def show_image(self, image_path):
        """显示图片"""
        try:
            # 打开并调整图片大小
            image = Image.open(image_path)
            # 调整图片大小以适应窗口
            max_width = self.image_frame.winfo_width() - 20
            max_height = self.image_frame.winfo_height() - 20
            
            if max_width > 0 and max_height > 0:
                image.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)
            
            # 转换为Tkinter可用的格式
            photo = ImageTk.PhotoImage(image)
            
            # 更新标签
            self.image_label.config(image=photo)
            self.image_label.image = photo  # 保持引用
            
            # 更新状态
            self.status_label.config(text=f"当前图片: {os.path.basename(image_path)}")
            
            # 重置分类状态
            self.first_category = None
            self.second_category = None
            self.next_btn.config(state=tk.DISABLED)
            
        except Exception as e:
            print(f"显示图片失败: {e}")
            self.image_label.config(text=f"无法显示图片: {e}")
    
    def show_next_image(self):
        """显示下一张图片"""
        if self.current_index < len(self.image_paths):
            self.current_image_path = self.image_paths[self.current_index]
            self.show_image(self.current_image_path)
            self.current_index += 1
        else:
            self.status_label.config(text="所有图片已分类完成！")
            self.image_label.config(text="没有更多未分类的图片")
            self.next_btn.config(state=tk.DISABLED)
    
    def select_first_category(self, category):
        """选择第一步分类"""
        self.first_category = category
        
        # 如果选择"都不是"，默认选择empty并直接处理
        if category == "other":
            self.second_category = "empty"
            self.status_label.config(text=f"第一步分类: {FIRST_CATEGORIES[category]} | 第二步分类: empty")
            self.check_classification()
        else:
            self.status_label.config(text=f"第一步分类: {FIRST_CATEGORIES[category]} | 第二步分类: 未选择")
            self.check_classification()
    
    def select_second_category(self, category):
        """选择第二步分类"""
        self.second_category = category
        self.status_label.config(text=f"第一步分类: {FIRST_CATEGORIES.get(self.first_category, '未选择')} | 第二步分类: {SECOND_CATEGORIES[category]}")
        self.check_classification()
    
    def check_classification(self):
        """检查分类是否完成"""
        if self.first_category and self.second_category:
            self.next_btn.config(state=tk.NORMAL)
            self.process_classification()
    
    def process_classification(self):
        """处理分类结果"""
        if not self.current_image_path:
            return
        
        try:
            # 创建sorted目录结构
            category_dir = os.path.join(SORTED_DIR, self.first_category, self.second_category)
            os.makedirs(category_dir, exist_ok=True)
            
            # 生成新文件名
            original_name = os.path.basename(self.current_image_path)
            name_without_ext = os.path.splitext(original_name)[0]
            ext = os.path.splitext(original_name)[1]
            
            # 新文件名格式: 区域_拥挤度_原始名称
            new_filename = f"{self.first_category}_{self.second_category}_{name_without_ext}{ext}"
            new_path = os.path.join(category_dir, new_filename)
            
            # 复制文件到新位置
            shutil.copy2(self.current_image_path, new_path)
            
            # 记录已分类
            self.classified_images.add(self.current_image_path)
            self.save_classified()
            
            print(f"分类完成: {self.current_image_path} -> {new_path}")
            
            # 更新统计信息
            self.update_stats()
            
            # 自动切换到下一张图片
            self.show_next_image()
            
        except Exception as e:
            print(f"处理分类失败: {e}")
    
    def skip_image(self):
        """跳过当前图片"""
        self.show_next_image()

if __name__ == "__main__":
    # 确保sorted目录存在
    os.makedirs(SORTED_DIR, exist_ok=True)
    
    # 创建主窗口
    root = tk.Tk()
    
    # 创建分类器实例
    app = ImageClassifier(root)
    
    # 启动主循环
    root.mainloop()