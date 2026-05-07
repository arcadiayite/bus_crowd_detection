# 公交拥挤度识别系统

基于深度学习的公交车内部拥挤度检测系统，通过摄像头图像自动判断车内拥挤程度。

## 项目结构

```
公交拥挤度识别/
├── data_collection/      # 数据采集模块
├── data_processing/      # 数据处理模块
├── model_training/       # 模型训练模块
├── view_weights/         # 模型权重文件
├── collected/            # 采集的图片存储目录
├── logs/                 # 日志文件目录
└── predict_crowd_level.py # 核心预测模块
```

## 快速开始

### 🚀 运行公交车拥挤度检测

**方法1：测试单辆车（推荐用于测试）**
```bash
python data_collection/test_crawl_and_predict.py
```
功能：随机选择一辆有成功爬取记录的车辆，抓取图片并进行拥挤度判断

**方法2：爬取指定线路**
```bash
python data_collection/crawl_k10.py
```
功能：爬取指定线路（如B3、502）的所有车辆图片并进行拥挤度判断

**方法3：批量爬取新车**
```bash
python data_collection/crawl_new_vehicles.py
```
功能：批量爬取CSV文件中列出的车辆

---

## 📁 各模块功能说明

### 1. 数据采集模块 (data_collection/)

| 脚本名称 | 功能说明 | 使用场景 |
|---------|---------|---------|
| `test_crawl_and_predict.py` | **主测试脚本**：随机选车→抓图→拥挤度判断→输出结果 | 日常测试、实时检测 |
| `crawl_k10.py` | 爬取指定线路（如B3、502）的所有车辆 | 按线路批量检测 |
| `crawl_and_predict.py` | 爬取并预测拥挤度 | 通用爬取预测 |
| `crawl_new_vehicles.py` | 从CSV批量爬取新车数据 | 新车数据采集 |
| `crawl_available_vehicles.py` | 检测可用车辆列表 | 车辆可用性检查 |
| `batch_remote_snapshot.py` | 批量远程截图 | 大规模截图任务 |
| `GetCamera.py` | 获取摄像头信息 | 摄像头管理 |
| `test_remote_snapshot_random30.py` | 测试随机30辆车截图 | 测试截图功能 |
| `test_view_classify.py` | 测试视角分类模型 | 模型测试 |
| `check_dataset_duplicates.py` | 检查数据集重复图片 | 数据清洗 |

### 2. 数据处理模块 (data_processing/)

| 脚本名称 | 功能说明 | 使用场景 |
|---------|---------|---------|
| `image_classifier.py` | **人工标注工具**：手动分类图片视角和拥挤度 | 数据集标注 |
| `analyze_logs.py` | 分析日志文件，统计拥挤度数据 | 日志分析 |
| `check_vehicles.py` | 检查车辆信息 | 数据校验 |
| `compare_and_update.py` | 比较和更新车辆数据 | 数据同步 |
| `convert_excel_to_csv.py` | Excel转CSV格式 | 数据格式转换 |
| `count_classified_images.py` | 统计已分类图片数量 | 数据统计 |

### 3. 模型训练模块 (model_training/)

| 脚本名称 | 功能说明 | 使用场景 |
|---------|---------|---------|
| `train_view_classifiers.py` | 训练视角分类模型 | 模型训练 |
| `classify_training.py` | 训练拥挤度分类模型 | 模型训练 |
| `prepare_view_datasets.py` | 准备视角分类数据集 | 数据准备 |
| `split_dataset.py` | 分割训练/验证数据集 | 数据准备 |
| `view_classifier.py` | 视角分类器模块 | 模型调用 |

### 4. 核心预测模块 (根目录)

| 脚本名称 | 功能说明 | 使用场景 |
|---------|---------|---------|
| `predict_crowd_level.py` | **拥挤度预测主函数**：输入图片列表，返回拥挤度结果 | 被其他脚本调用 |
| `analyze_detection_speed.py` | 分析检测速度性能 | 性能测试 |

---

## 📊 拥挤度级别说明

系统将拥挤度分为5个级别：

| 级别 | 名称 | 描述 |
|------|------|------|
| 1 | empty | 空车，几乎没有乘客 |
| 2 | seated | 仅有坐着的乘客 |
| 3 | standing | 有少量站立乘客 |
| 4 | crowd | 拥挤，较多站立乘客 |
| 5 | extremecrowd | 极度拥挤 |

---

## 🛠️ 配置说明

### 主要配置项

1. **TOKEN配置**：在 `crawl_k10.py` 和 `test_crawl_and_predict.py` 中设置：
   ```python
   TOKEN = "your_authorization_token"
   ```

2. **线路配置**：在 `crawl_k10.py` 中设置：
   ```python
   LINE_NAME = "B3"  # 要检测的线路名称
   ```

3. **通道配置**：
   ```python
   CH_LIST = [3, 4, 8, 12, 13, 19, 20]  # 要抓取的摄像头通道
   ```

---

## 📝 输出说明

### 运行结果示例

```
===== 开始处理车辆: 粤C03180D - B2 =====
开始抓取车辆 粤C03180D 的所有通道图片...
[成功] CH03 -> collected\CH03\B2\粤C03180D_3_20260428112213.jpeg
[成功] CH08 -> collected\CH08\B2\粤C03180D_8_20260428112220.jpeg
[成功] CH12 -> collected\CH12\B2\粤C03180D_12_20260428112221.jpeg
[成功] CH13 -> collected\CH13\B2\粤C03180D_13_20260428112223.jpeg

开始进行拥挤度判断...
视角分类结果:
  front: 0.9989
  rear: 1.0000
  standing: 1.0000

拥挤度判断结果:
视角: front | 拥挤度级别: 1_empty | 置信度: 0.9844
视角: rear | 拥挤度级别: 1_empty | 置信度: 1.0000
视角: standing | 拥挤度级别: 2_seated | 置信度: 0.7523

整体拥挤度判断: empty
```

---

## 🔄 数据流程图

```
摄像头抓取 → 图片保存 → 视角分类 → 拥挤度预测 → 结果输出
    ↓              ↓           ↓            ↓
collected/    文件名格式   front/rear/   5个级别
              plate_chNO_timestamp.jpeg  standing/other
```

---

## 📁 文件目录说明

| 目录 | 用途 |
|------|------|
| `collected/` | 存储抓取的原始图片，按通道/线路组织 |
| `logs/` | 存储每日运行日志 |
| `view_weights/` | 存储预训练模型权重文件 |
| `output_view/` | 视角分类模型训练输出 |
| `output_crowd/` | 拥挤度分类模型训练输出 |

---

## 🚗 常用命令总结

| 任务 | 命令 |
|------|------|
| 测试单辆车拥挤度 | `python data_collection/test_crawl_and_predict.py` |
| 检测指定线路 | `python data_collection/crawl_k10.py` |
| 批量爬取新车 | `python data_collection/crawl_new_vehicles.py` |
| 人工标注图片 | `python data_processing/image_classifier.py` |
| 分析日志 | `python data_processing/analyze_logs.py` |