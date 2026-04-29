# -*- coding: utf-8 -*-
"""
测试抓取摄像头数据并进行拥堵度判断

功能：
1. 自动从2026年420台新购纯电动公交车辆信息表.csv中选择有成功爬取记录的车辆
2. 一次性爬取该车辆的所有通道图片
3. 对爬取的图片进行拥堵度判断
4. 输出详细的测试结果
"""

import csv
import os
import re
import time
import random
from datetime import datetime
from urllib.parse import unquote

import requests

# =========================
# 配置区：运行前按需修改
# =========================
URL = "http://119.146.222.192:8050/t1_device/RemoteSnapshot"
TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhZG1pbiI6dHJ1ZSwiYXBwIjoyMSwiY29tcGFkbWluIjpmYWxzZSwiZXBkIjo5MjE4ODgwMCwiaWF0IjoxNzc0ODMzNjY5LCJvcmciOiIxNjIwNjU3MTIzMDAwMDEwMDIiLCJwaG9uZSI6IiIsInNuIjoxLCJ0aWQiOiIxNzc0NzY3MzQ1MDAxMDAwMDMifQ.CEZXbkn2Rkil3HmOo_R04t9jb9xQCRExVwe0tX-whU0"

# 珠海公交车辆清单（用于获取线路信息）
CSV_FILE = "珠海公交车辆清单.csv"
OUTPUT_ROOT = "collected"

# 要抓取的通道号列表
# 根据 chNO说明.txt，重点关注: 3, 4, 8, 12, 13, 19, 20
CH_LIST = [3, 4, 8, 12, 13, 19, 20]

# 两次抓图请求之间的等待时间（秒）
DELAY_SECONDS = 0.2

# 单次请求超时（秒）
TIMEOUT_SECONDS = 2

# 失败重试次数（不含首次请求）
RETRY_TIMES = 0

# 接口参数
PAYLOAD_TEMPLATE = {
    "devSN": "",
    "plate": "",
    "chNO": 9,
    "cmd": 1,
    "interval": 1,
    "save": 1,
    "resolution": 255,
    "quality": 5,
    "brightness": 50,
    "contrast": 50,
    "saturation": 50,
    "chroma": 1,
}


def ensure_plate(value: str) -> str:
    """把 CSV 里的车辆编号补成完整车牌号。"""
    value = (value or "").strip()
    if not value:
        return ""
    if value.startswith("粤C"):
        return value
    return f"粤C{value}"


def sanitize_path_name(value: str) -> str:
    """清理 Windows 不允许的路径字符。"""
    value = str(value).strip()
    return re.sub(r'[<>:"/\\|?*]', "_", value)


def fix_filename_encoding(filename):
    """修复文件名编码问题，处理乱码"""
    if not filename:
        return filename
    
    # 尝试多种编码组合来修复乱码
    encodings = ['utf-8', 'gbk', 'gb18030']
    
    for enc in encodings:
        try:
            # 尝试将可能的乱码解码后重新编码
            if isinstance(filename, bytes):
                filename = filename.decode(enc)
            else:
                # 尝试处理已经是字符串但包含乱码的情况
                filename = filename.encode('latin1').decode(enc)
            break
        except Exception:
            continue
    
    return filename


def read_csv_rows(csv_path: str):
    """兼容 utf-8-sig / utf-8 / gb18030 / gbk。"""
    encodings = ["utf-8-sig", "utf-8", "gb18030", "gbk"]
    last_error = None

    for enc in encodings:
        try:
            with open(csv_path, "r", encoding=enc, newline="") as f:
                reader = csv.DictReader(f)
                rows = list(reader)
                return rows, enc
        except Exception as e:
            last_error = e

    raise RuntimeError(f"读取 CSV 失败：{last_error}")


def build_output_path(root: str, ch_no: int, line_name: str, header_filename: str, plate: str):
    """按 CHxx/线路/文件名 保存。"""
    ch_folder = f"CH{ch_no:02d}"
    line_folder = sanitize_path_name(line_name)

    save_dir = os.path.join(root, ch_folder, line_folder)
    os.makedirs(save_dir, exist_ok=True)

    filename = None
    if header_filename:
        filename = unquote(header_filename.strip().strip('"'))
        # 修复文件名编码问题
        filename = fix_filename_encoding(filename)
        filename = sanitize_path_name(filename)

    if not filename or filename == "snapshot.jpeg":
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        filename = f"{plate}_{ch_no}_{timestamp}.jpeg"

    # 确保文件名以 .jpeg 结尾
    if not filename.lower().endswith('.jpeg'):
        filename = f"{os.path.splitext(filename)[0]}.jpeg"

    return os.path.join(save_dir, filename)


def extract_header_filename(response: requests.Response) -> str:
    content_disposition = response.headers.get("content-disposition", "")
    match = re.search(r"filename=([^;]+)", content_disposition, flags=re.IGNORECASE)
    if match:
        return match.group(1)
    return ""


def is_image_response(response: requests.Response) -> tuple[bool, str]:
    """检查响应是否为图片，并返回详细信息
    
    Returns:
        tuple[bool, str]: (是否为图片, 详细信息)
    """
    # 首先检查响应内容是否为空
    if len(response.content) == 0:
        return False, "空响应内容"
    
    content_type = (response.headers.get("content-type") or "").lower()
    if "image" in content_type:
        return True, f"图片类型: {content_type}"

    # 某些服务端没正确回 content-type，但确实返回 jpeg 二进制
    magic = response.content[:4]
    if magic.startswith(b"\xff\xd8\xff"):
        return True, "JPEG 二进制数据"
    
    return False, f"非图片内容，content-type={content_type}, 前4字节={magic!r}"


def request_snapshot(session: requests.Session, plate: str, ch_no: int):
    payload = PAYLOAD_TEMPLATE.copy()
    payload["plate"] = plate
    payload["chNO"] = ch_no

    last_error = None

    for attempt in range(RETRY_TIMES + 1):
        try:
            response = session.request(
                method="GET",
                url=URL,
                headers={"Authorization": TOKEN},
                json=payload,
                timeout=TIMEOUT_SECONDS,
            )
            response.raise_for_status()

            is_image, info = is_image_response(response)
            if not is_image:
                if "空响应内容" in info:
                    raise RuntimeError(f"返回内容为空，服务器没有返回图片数据")
                else:
                    preview = response.text[:300] if response.text else "<empty body>"
                    raise RuntimeError(f"返回内容不是图片，{info}，body前300字符={preview}")

            return response

        except Exception as e:
            last_error = e
            if attempt < RETRY_TIMES:
                print(f"[重试] plate={plate}, chNO={ch_no}, attempt={attempt + 1}, error={e}")
                time.sleep(2)

    raise last_error

def get_vehicles_with_success_record():
    """从2026年420台新购纯电动公交车辆信息表.csv中获取有成功爬取记录的车辆"""
    csv_path = "2026年420台新购纯电动公交车辆信息表.csv"
    if not os.path.exists(csv_path):
        print(f"文件不存在: {csv_path}")
        return []
    
    rows, _ = read_csv_rows(csv_path)
    vehicles = []
    
    for row in rows:
        plate = row.get("车辆编号", "").strip()
        line = row.get("线路", "").strip()
        status = row.get("是否有成功爬取记录", "").strip()
        
        if plate and line and status == "有":
            vehicles.append((plate, line))
    
    return vehicles

def crawl_vehicle_images(plate, line_name):
    """抓取指定车辆的所有通道图片"""
    session = requests.Session()
    os.makedirs(OUTPUT_ROOT, exist_ok=True)
    
    image_paths = []
    success_count = 0
    failed_count = 0
    
    print(f"\n开始抓取车辆 {plate} 的所有通道图片...")
    
    for ch_no in CH_LIST:
        try:
            response = request_snapshot(session, plate, ch_no)
            header_filename = extract_header_filename(response)
            save_path = build_output_path(OUTPUT_ROOT, ch_no, line_name, header_filename, plate)

            with open(save_path, "wb") as f:
                f.write(response.content)

            image_paths.append(save_path)
            success_count += 1
            print(f"[成功] CH{ch_no:02d} -> {save_path}")

        except Exception as e:
            failed_count += 1
            print(f"[失败] CH{ch_no:02d} | error={e}")

        # 每次抓图之间留间隔
        time.sleep(DELAY_SECONDS)
    
    print(f"\n抓取完成：成功 {success_count} 个，失败 {failed_count} 个")
    return image_paths

def predict_crowd_level(image_paths):
    """预测拥挤度级别"""
    if not image_paths:
        print("没有图片可以预测")
        return {}, {}, []
    
    # 导入预测模块
    try:
        import sys
        sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from predict_crowd_level import classify_views, predict_crowd_level as do_predict, load_models
        
        # 加载模型
        view_model, crowd_models = load_models()
        
        if view_model is None:
            print("错误: 无法加载视角分类模型")
            return {}, {}, []
        
        # 进行视角分类
        view_results = classify_views(view_model, image_paths)
        
        if not view_results:
            print("错误: 没有有效的视角分类结果")
            return {}, {}, []
        
        # 进行拥挤度预测
        results = do_predict(view_model, crowd_models, view_results)
        
        # 建立图片路径到视角的映射
        path_to_view = {}
        for item in view_results:
            path_to_view[item['path']] = item['view']
        
        return results, path_to_view, view_results
        
    except Exception as e:
        print(f"预测失败: {e}")
        import traceback
        traceback.print_exc()
        return {}, {}, []

def save_log(plate, line, image_paths, results, path_to_view, overall_level):
    """保存日志到文件（追加到当天的汇总日志）"""
    log_dir = "logs"
    os.makedirs(log_dir, exist_ok=True)
    
    # 使用当天日期作为日志文件名
    today = datetime.now().strftime("%Y%m%d")
    daily_log_file = os.path.join(log_dir, f"daily_{today}.log")
    
    # 构建日志内容
    log_content = []
    log_content.append("")
    log_content.append("=" * 60)
    log_content.append(f"[{datetime.now()}] 开始执行")
    log_content.append(f"车辆: {plate} - {line}")
    log_content.append(f"抓取图片数量: {len(image_paths)}")
    log_content.append("")
    
    # 建立通道号到图片路径的映射
    ch_to_image = {}
    for img_path in image_paths:
        folder_name = os.path.basename(os.path.dirname(img_path))
        ch_to_image[folder_name] = img_path
    
    # 建立视角到通道号的映射
    view_to_ch = {}
    for img_path, view in path_to_view.items():
        if view not in view_to_ch:
            view_to_ch[view] = []
        folder_name = os.path.basename(os.path.dirname(img_path))
        view_to_ch[view].append(folder_name)
    
    # 按视角分组显示通道图片
    log_content.append("=== 各视角对应的通道和图片 ===")
    for view in ['front', 'rear', 'standing', 'other']:
        if view in view_to_ch:
            log_content.append(f"\n【{view.upper()}】视角:")
            for ch in sorted(view_to_ch[view]):
                img_path = ch_to_image.get(ch, '未知')
                log_content.append(f"  {ch} -> {img_path}")
        else:
            log_content.append(f"\n【{view.upper()}】视角: 无")
    log_content.append("")
    
    # 记录预测结果
    log_content.append("=== 预测结果 ===")
    for view, result in results.items():
        level = result.get('level', '未知')
        confidence = result.get('confidence', 0.0)
        log_content.append(f"  视角={view}, 级别={level}, 置信度={confidence:.4f}")
    log_content.append("")
    
    # 记录整体判断结果
    log_content.append("=== 整体拥堵度判断 ===")
    log_content.append(f"  {overall_level}")
    log_content.append("")
    log_content.append(f"[{datetime.now()}] 执行完成")
    
    # 保存日志文件（追加到当天的汇总日志）
    with open(daily_log_file, 'a', encoding='utf-8') as f:
        f.write('\n'.join(log_content))
        f.write('\n')
    
    print(f"\n日志已追加到: {daily_log_file}")
    return daily_log_file

def main():
    if "请替换成你的 Authorization Token" in TOKEN:
        raise RuntimeError("请先在脚本顶部把 TOKEN 替换成真实值。")

    # 从2026年420台新购纯电动公交车辆信息表.csv中获取有成功爬取记录的车辆
    vehicles = get_vehicles_with_success_record()
    
    if not vehicles:
        print("没有找到有成功爬取记录的车辆")
        return
    
    print(f"\n找到 {len(vehicles)} 辆有成功爬取记录的车辆")
    print("前10辆车辆:")
    for i, (plate, line) in enumerate(vehicles[:10], 1):
        print(f"{i}. {plate} - {line}")
    # 随机选择一辆车进行测试
    plate, line = random.choice(vehicles)
    print(f"\n选择测试车辆: {plate} - {line}")
    
    # 抓取该车辆的所有通道图片
    image_paths = crawl_vehicle_images(plate, line)
    
    # 进行拥堵度判断
    if image_paths:
        print("\n开始进行拥堵度判断...")
        results, path_to_view, view_results = predict_crowd_level(image_paths)
        
        # 输出判断结果
        print("\n=== 拥堵度判断结果 ===")
        print(f"results = {results}")
        print(f"path_to_view = {path_to_view}")
        print(f"view_results = {view_results}")
        
        # 拥挤度级别映射（与公交返回一致）
        crowd_level_mapping = {
            '1_empty': '空闲',
            '2_seated': '有位',
            '3_standing': '站立',
            '4_crowd': '拥挤',
            '5_extremecrowd': '严重拥挤'
        }
        
        # 整体判断：如果三个都是未知则为未知，否则取最高的level
        level_priority = {'严重拥挤': 4, '拥挤': 3, '站立': 2, '有位': 1, '空闲': 0, '未知': -1}
        
        all_unknown = True
        max_level = '未知'
        max_priority = -1
        
        # 检查是否有有效的预测结果
        if results:
            for view, result in results.items():
                level = result.get('level', '未知')
                if level != '未知':
                    all_unknown = False
                    # 转换为与公交返回一致的级别
                    mapped_level = crowd_level_mapping.get(level, '未知')
                    priority = level_priority.get(mapped_level, -1)
                    if priority > max_priority:
                        max_priority = priority
                        max_level = mapped_level
        else:
            # 如果没有预测结果，整体判断为 '未知'
            overall_level = '未知'
            
            # 输出整体拥堵度判断
            print(f"整体拥堵度判断: {overall_level}")
            
            # 保存日志
            save_log(plate, line, image_paths, results, path_to_view, overall_level)
            return
        
        overall_level = '未知' if all_unknown else max_level
        
        # 只输出整体拥堵度判断
        print(f"整体拥堵度判断: {overall_level}")
        
        # 保存日志
        save_log(plate, line, image_paths, results, path_to_view, overall_level)


if __name__ == "__main__":
    main()