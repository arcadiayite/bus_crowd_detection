# -*- coding: utf-8 -*-
"""
批量远程抓图脚本（只爬取可采集车辆）

功能：
1. 从 available_vehicles_channels.csv 中读取可采集的车辆
2. 对每个车辆尝试 1-20 频道的抓图
3. 输出目录先按 chNO 分文件夹，再按线路分文件夹
4. 记录成功/失败日志，便于后续排查

目录结构示例：
collected/
    CH01/
        14/
            粤C00151D_1_20260422093001.jpeg
        86/
            ...
    CH02/
        K10/
            ...
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

# 可采集车辆列表文件
AVAILABLE_VEHICLES_FILE = "available_vehicles_channels.csv"
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
RETRY_TIMES = 1

# 时间窗口设置（24小时制）
# 今天晚上时间窗口
EVENING_START_HOUR = 0    # 开始时间（0表示从当前时间开始）
EVENING_END_HOUR = 21      # 结束时间

# 明天早上时间窗口
MORNING_START_HOUR = 6     # 开始时间
MORNING_START_MINUTE = 30   # 开始分钟
MORNING_END_HOUR = 9        # 结束时间
MORNING_END_MINUTE = 20     # 结束分钟

# 抓取计划
# 0: 尚未开始
# 1: 正在执行晚上时间窗口
# 2: 正在执行早上时间窗口
# 3: 所有时间窗口完成
GRAB_PLAN = 0

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
            print(payload)
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

def get_available_vehicles():
    """从 available_vehicles_channels.csv 中读取可采集的车辆"""
    # 尝试多种编码读取文件
    encodings = ["utf-8-sig", "utf-8", "gb18030", "gbk"]
    available_plates = set()
    
    for enc in encodings:
        try:
            with open(AVAILABLE_VEHICLES_FILE, "r", encoding=enc, newline="") as f:
                reader = csv.reader(f)
                next(reader)  # 跳过表头
                for row in reader:
                    if row:
                        # 处理可能的乱码
                        plate = fix_filename_encoding(row[0])
                        plate = ensure_plate(plate)
                        if plate:
                            available_plates.add(plate)
            break
        except Exception:
            continue
    
    return list(available_plates)

def main():
    if "请替换成你的 Authorization Token" in TOKEN:
        raise RuntimeError("请先在脚本顶部把 TOKEN 替换成真实值。")

    # 获取可采集的车辆列表
    available_plates = get_available_vehicles()
    print(f"发现 {len(available_plates)} 辆可采集的车辆")
    
    if not available_plates:
        print("没有找到可采集的车辆")
        return
    
    # 获取车牌号到线路的映射
    plate_line_map = get_plate_line_map()
    
    # 构建要处理的行
    filtered_rows = []
    for plate in available_plates:
        line = plate_line_map.get(plate, "未知")
        filtered_rows.append({"plate": plate, "line": line})
    
    print(f"筛选后数据条数: {len(filtered_rows)}")

    if not filtered_rows:
        print("没有找到数据")
        return

    session = requests.Session()
    os.makedirs(OUTPUT_ROOT, exist_ok=True)
    
    # 主循环：持续抓取直到时间窗口结束
    cycle = 1
    grab_plan = 0  # 0: 尚未开始, 1: 晚上时间窗口, 2: 早上时间窗口, 3: 完成
    
    while True:
        current_time = datetime.now()
        
        # 检查是否在允许的时间窗口内
        is_valid_time = False
        current_window = ""
        
        # 检查当前时间窗口
        if grab_plan < 2 and current_time.hour >= EVENING_START_HOUR and current_time.hour < EVENING_END_HOUR:
            is_valid_time = True
            current_window = "晚上"
            if grab_plan == 0:
                grab_plan = 1
                print(f"\n========== 开始晚上时间窗口（{EVENING_START_HOUR}:00-{EVENING_END_HOUR}:00） ==========")
        elif grab_plan < 3 and (
            (current_time.hour == MORNING_START_HOUR and current_time.minute >= MORNING_START_MINUTE) or
            (current_time.hour > MORNING_START_HOUR and current_time.hour < MORNING_END_HOUR) or
            (current_time.hour == MORNING_END_HOUR and current_time.minute <= MORNING_END_MINUTE)
        ):
            is_valid_time = True
            current_window = "早上"
            if grab_plan == 1:
                grab_plan = 2
                print(f"\n========== 开始早上时间窗口（{MORNING_START_HOUR}:{MORNING_START_MINUTE}-{MORNING_END_HOUR}:{MORNING_END_MINUTE}） ==========")
        
        if not is_valid_time:
            # 检查是否所有时间窗口都已完成
            if grab_plan == 2 and current_time.hour > MORNING_END_HOUR:
                print("\n========== 所有时间窗口已完成，停止抓取 ==========")
                break
            
            # 如果不在时间窗口内，等待到下一个有效时间
            print(f"\n当前时间 {current_time.strftime('%H:%M:%S')} 不在允许的时间窗口内")
            print("等待到下一个有效时间...")
            
            # 计算下一个有效时间
            if grab_plan == 0 or grab_plan == 1:
                # 还没开始或正在晚上时间窗口
                if current_time.hour < EVENING_START_HOUR:
                    # 早于晚上时间窗口，等待到晚上开始时间
                    wait_until = current_time.replace(
                        hour=EVENING_START_HOUR, 
                        minute=0, 
                        second=0, 
                        microsecond=0
                    )
                elif current_time.hour < EVENING_END_HOUR:
                    # 白天时间，等待到晚上开始时间
                    wait_until = current_time.replace(
                        hour=EVENING_START_HOUR, 
                        minute=0, 
                        second=0, 
                        microsecond=0
                    )
                else:
                    # 晚上时间窗口结束后，等待到明天早上开始时间
                    from datetime import timedelta
                    tomorrow = current_time + timedelta(days=1)
                    wait_until = tomorrow.replace(
                        hour=MORNING_START_HOUR, 
                        minute=MORNING_START_MINUTE, 
                        second=0, 
                        microsecond=0
                    )
                    grab_plan = 2  # 进入早上时间窗口准备
            else:
                # 早上时间窗口已完成
                print("\n========== 所有时间窗口已完成，停止抓取 ==========")
                break
            
            # 等待到指定时间
            wait_seconds = (wait_until - current_time).total_seconds()
            if wait_seconds > 0:
                for i in range(int(wait_seconds), 0, -1):
                    print(f"等待中，剩余 {i} 秒", end="\r")
                    time.sleep(1)
            continue
        
        print(f"\n========== 第 {cycle} 轮抓取开始（{current_window}时间窗口） ==========")
        print(f"当前时间: {current_time.strftime('%Y-%m-%d %H:%M:%S')}")
        
        # 每轮创建新的日志文件
        log_path = os.path.join(OUTPUT_ROOT, f"batch_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")
        
        total_tasks = len(filtered_rows) * len(CH_LIST)
        done = 0
        success = 0
        failed = 0
        
        with open(log_path, "w", encoding="utf-8-sig", newline="") as log_file:
            writer = csv.writer(log_file)
            writer.writerow([
                "time", "plate", "line", "chNO", "status", "saved_path", "error"
            ])

            for ch_no in CH_LIST:
                print(f"\n---------- 开始抓取 CH{ch_no:02d} ----------")

                for row in filtered_rows:
                    plate = row.get("plate", "")
                    line_name = row.get("line", "未知")
                    done += 1

                    if not plate:
                        failed += 1
                        err = "空车牌"
                        print(f"[失败] CH{ch_no:02d} | line={line_name} | {err}")
                        writer.writerow([
                            datetime.now().isoformat(timespec="seconds"),
                            "", line_name, ch_no, "FAIL", "", err
                        ])
                        time.sleep(DELAY_SECONDS)
                        continue

                    try:
                        response = request_snapshot(session, plate, ch_no)
                        header_filename = extract_header_filename(response)
                        save_path = build_output_path(OUTPUT_ROOT, ch_no, line_name, header_filename, plate)

                        with open(save_path, "wb") as f:
                            f.write(response.content)

                        success += 1
                        print(f"[成功] {done}/{total_tasks} | CH{ch_no:02d} | line={line_name} | plate={plate} -> {save_path}")
                        writer.writerow([
                            datetime.now().isoformat(timespec="seconds"),
                            plate, line_name, ch_no, "OK", save_path, ""
                        ])

                    except Exception as e:
                        failed += 1
                        print(f"[失败] {done}/{total_tasks} | CH{ch_no:02d} | line={line_name} | plate={plate} | error={e}")
                        writer.writerow([
                            datetime.now().isoformat(timespec="seconds"),
                            plate, line_name, ch_no, "FAIL", "", str(e)
                        ])

                    # 每次抓图之间留间隔
                    if done < total_tasks:
                        time.sleep(DELAY_SECONDS)
        
        print(f"\n---------- 第 {cycle} 轮抓取完成 ----------")
        print(f"总任务数: {total_tasks}")
        print(f"成功: {success}")
        print(f"失败: {failed}")
        print(f"日志文件: {log_path}")
        
        # 检查是否需要继续
        current_time = datetime.now()
        if grab_plan == 1 and current_time.hour >= EVENING_END_HOUR:
            print(f"\n========== 晚上时间窗口结束，等待早上时间窗口 ==========")
        elif grab_plan == 2 and current_time.hour > MORNING_END_HOUR:
            print("\n========== 早上时间窗口结束，所有抓取任务完成 ==========")
            break
        
        # 每轮之间无间隔，直接开始下一轮
        print("\n开始下一轮抓取...")
        cycle += 1
    
    print("\n========== 所有抓取任务完成 ==========")


if __name__ == "__main__":
    main()