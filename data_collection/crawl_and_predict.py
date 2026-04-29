# -*- coding: utf-8 -*-
"""
抓取摄像头数据并进行拥堵度判断

功能：
1. 可选择是否连接在线摄像头
2. 可设置线路和车牌号进行筛选
3. 一次性爬取一个车辆的所有chNO
4. 将爬取的图片组成list并进行拥堵度判断
5. 输出拥堵度判断结果
"""

import csv
import os
import re
import time
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
TIMEOUT_SECONDS = 15

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

def get_plate_line_map():
    """获取车牌号到线路的映射"""
    rows, _ = read_csv_rows(CSV_FILE)
    
    # 自动兼容列名
    possible_plate_cols = ["车辆编号", "车牌号", "车牌", "plate", "Plate"]
    possible_line_cols = ["线路", "line", "Line", "线路号"]

    plate_col = next((c for c in possible_plate_cols if rows and c in rows[0]), None)
    line_col = next((c for c in possible_line_cols if rows and c in rows[0]), None)

    if not plate_col or not line_col:
        raise RuntimeError(f"CSV 缺少必要字段。当前表头：{list(rows[0].keys()) if rows else '空文件'}")
    
    plate_line_map = {}
    for row in rows:
        plate = ensure_plate(row.get(plate_col, ""))
        line = row.get(line_col, "")
        if plate:
            plate_line_map[plate] = line
    
    return plate_line_map

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
        return {}
    
    # 导入预测模块
    try:
        import sys
        sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from predict_crowd_level import main as predict_main
        
        # 调用预测函数
        import io
        from contextlib import redirect_stdout
        
        # 捕获输出
        f = io.StringIO()
        with redirect_stdout(f):
            predict_main(image_paths)
        output = f.getvalue()
        print(output)
        
        # 解析结果
        results = {}
        lines = output.split('\n')
        current_view = None
        
        for line in lines:
            line = line.strip()
            if line.startswith('视角: '):
                current_view = line.split(': ')[1]
                results[current_view] = {}
            elif current_view and line.startswith('  拥挤度级别: '):
                results[current_view]['level'] = line.split(': ')[1]
            elif current_view and line.startswith('  置信度: '):
                results[current_view]['confidence'] = float(line.split(': ')[1])
        
        return results
        
    except Exception as e:
        print(f"预测失败: {e}")
        return {}

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

def main():
    if "请替换成你的 Authorization Token" in TOKEN:
        raise RuntimeError("请先在脚本顶部把 TOKEN 替换成真实值。")

    # 获取车牌号到线路的映射
    plate_line_map = get_plate_line_map()
    
    # 获取用户输入
    use_online_camera = input("是否连接在线摄像头？(y/n): ").strip().lower() == 'y'
    
    if not use_online_camera:
        print("不连接在线摄像头，程序结束。")
        return
    
    # 输入筛选条件
    line_filter = input("请输入要筛选的线路（留空表示所有线路）: ").strip()
    plate_filter = input("请输入要筛选的车牌号（留空表示所有车辆）: ").strip()
    
    # 筛选车辆
    filtered_vehicles = []
    for plate, line in plate_line_map.items():
        if line_filter and line != line_filter:
            continue
        if plate_filter and not plate.startswith(ensure_plate(plate_filter)):
            continue
        filtered_vehicles.append((plate, line))
    
    # 如果没有符合条件的车辆，尝试从2026年420台新购纯电动公交车辆信息表.csv中获取有成功爬取记录的车辆
    if not filtered_vehicles:
        print("没有找到符合条件的车辆，尝试从2026年420台新购纯电动公交车辆信息表.csv中获取有成功爬取记录的车辆...")
        filtered_vehicles = get_vehicles_with_success_record()
    
    if not filtered_vehicles:
        print("没有找到符合条件的车辆")
        return
    
    print(f"\n找到 {len(filtered_vehicles)} 辆符合条件的车辆：")
    for i, (plate, line) in enumerate(filtered_vehicles, 1):
        print(f"{i}. {plate} - {line}")
    
    # 选择车辆
    while True:
        try:
            choice = int(input("\n请选择要抓取的车辆编号: ")) - 1
            if 0 <= choice < len(filtered_vehicles):
                plate, line = filtered_vehicles[choice]
                break
            else:
                print("输入无效，请重新选择")
        except ValueError:
            print("输入无效，请输入数字")
    
    # 抓取该车辆的所有通道图片
    image_paths = crawl_vehicle_images(plate, line)
    
    # 进行拥堵度判断
    if image_paths:
        print("\n开始进行拥堵度判断...")
        results = predict_crowd_level(image_paths)
        
        # 输出判断结果
        print("\n=== 拥堵度判断结果 ===")
        for view, result in results.items():
            print(f"视角: {view}")
            print(f"  拥挤度级别: {result.get('level', '未知')}")
            confidence = result.get('confidence', '未知')
            if isinstance(confidence, (int, float)):
                print(f"  置信度: {confidence:.4f}")
            else:
                print(f"  置信度: {confidence}")
            print()

if __name__ == "__main__":
    main()