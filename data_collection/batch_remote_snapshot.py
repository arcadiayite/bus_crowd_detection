# -*- coding: utf-8 -*-
"""
批量远程抓图脚本

功能：
1. 按 CSV 中的车辆编号批量抓图，自动补前缀“粤C”
2. chNO 按指定列表批量抓取
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
from datetime import datetime, timedelta
from urllib.parse import unquote

import requests


# =========================
# 配置区：运行前按需修改
# =========================
URL = "http://119.146.222.192:8050/t1_device/RemoteSnapshot"
TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhZG1pbiI6dHJ1ZSwiYXBwIjoyMSwiY29tcGFkbWluIjpmYWxzZSwiZXBkIjo5MjE4ODgwMCwiaWF0IjoxNzc0ODMzNjY5LCJvcmciOiIxNjIwNjU3MTIzMDAwMDEwMDIiLCJwaG9uZSI6IiIsInNuIjoxLCJ0aWQiOiIxNzc0NzY3MzQ1MDAxMDAwMDMifQ.CEZXbkn2Rkil3HmOo_R04t9jb9xQCRExVwe0tX-whU0"

# 多个CSV文件路径
CSV_FILES = [
    "珠海公交车辆清单.csv",
    "2026年420台新购纯电动公交车辆信息表.csv"
]
OUTPUT_ROOT = "collected"

# 要抓取的通道号列表
# CH_LIST = [5, 6, 7, 8, 9, 10, 11, 12, 13,14,15,16]
CH_LIST = [3, 4, 8, 12, 13, 19, 20]
# 两次抓图请求之间的等待时间（秒）
DELAY_SECONDS = 0.02

# 单次请求超时（秒）
TIMEOUT_SECONDS = 30

# 失败重试次数（不含首次请求）
RETRY_TIMES = 0

# 统计相关配置
HISTORY_TIME_WINDOW = 3600  # 历史时间窗口（秒），用于计算成功率
SKIP_THRESHOLD = 0.0  # 成功率阈值，低于此值且有请求记录则跳过

# 定时运行配置
RUN_SCHEDULE = [
    # (开始时间, 结束时间)，格式为 (小时, 分钟)
    (6, 30),   # 早上6:30开始
    (9, 30),   # 早上9:30结束
    (12, 0),   # 中午12:00开始（可选）
    (14, 0),   # 中午14:00结束（可选）
    (17, 21),  # 下午5:30开始
    (22, 30)   # 晚上9:30结束
]

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

# 是否启用线路筛选（True: 只采集 TARGET_LINES 中的线路；False: 采集所有线路）
ENABLE_LINE_FILTER = False

# 要筛选的线路列表
TARGET_LINES = ["B10","K11","26"]


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


def load_history_logs():
    """加载历史日志数据，用于计算成功率"""
    history = {
        'channel': {},  # 通道成功率统计
        'vehicle': {},  # 车辆成功率统计
        'vehicle_channel': {}  # 车辆-通道组合成功率统计
    }
    
    # 查找历史日志文件
    if os.path.exists(OUTPUT_ROOT):
        log_files = [f for f in os.listdir(OUTPUT_ROOT) if f.startswith('batch_log_') and f.endswith('.csv')]
        current_time = time.time()
        
        for log_file in log_files:
            log_path = os.path.join(OUTPUT_ROOT, log_file)
            try:
                with open(log_path, 'r', encoding='utf-8-sig') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        # 解析时间
                        try:
                            log_time = datetime.fromisoformat(row['time']).timestamp()
                            # 只保留时间窗口内的记录
                            if current_time - log_time <= HISTORY_TIME_WINDOW:
                                plate = row['plate'].strip()
                                ch_no = int(row['chNO'])
                                status = row['status'].strip()
                                success = status == 'OK'
                                
                                # 通道统计
                                if ch_no not in history['channel']:
                                    history['channel'][ch_no] = {'total': 0, 'success': 0}
                                history['channel'][ch_no]['total'] += 1
                                if success:
                                    history['channel'][ch_no]['success'] += 1
                                
                                # 车辆统计
                                if plate not in history['vehicle']:
                                    history['vehicle'][plate] = {'total': 0, 'success': 0}
                                history['vehicle'][plate]['total'] += 1
                                if success:
                                    history['vehicle'][plate]['success'] += 1
                                
                                # 车辆-通道统计
                                key = (plate, ch_no)
                                if key not in history['vehicle_channel']:
                                    history['vehicle_channel'][key] = {'total': 0, 'success': 0}
                                history['vehicle_channel'][key]['total'] += 1
                                if success:
                                    history['vehicle_channel'][key]['success'] += 1
                        except Exception:
                            continue
            except Exception:
                continue
    
    return history

def calculate_success_rate(stats):
    """计算成功率"""
    if stats['total'] == 0:
        return None
    return stats['success'] / stats['total']

def is_in_run_window():
    """判断当前时间是否在运行时间窗口内"""
    now = datetime.now()
    current_hour = now.hour
    current_minute = now.minute
    current_time = current_hour * 60 + current_minute
    
    # 检查是否在运行时间窗口内
    for i in range(0, len(RUN_SCHEDULE), 2):
        if i + 1 < len(RUN_SCHEDULE):
            start_hour, start_minute = RUN_SCHEDULE[i]
            end_hour, end_minute = RUN_SCHEDULE[i + 1]
            start_time = start_hour * 60 + start_minute
            end_time = end_hour * 60 + end_minute
            
            if start_time <= current_time <= end_time:
                return True
    
    return False

def get_next_run_time():
    """获取下一次运行的时间"""
    now = datetime.now()
    current_hour = now.hour
    current_minute = now.minute
    current_time = current_hour * 60 + current_minute
    
    # 找到下一个开始时间
    next_start = None
    for i in range(0, len(RUN_SCHEDULE), 2):
        start_hour, start_minute = RUN_SCHEDULE[i]
        start_time = start_hour * 60 + start_minute
        
        if start_time > current_time:
            next_start = (start_hour, start_minute)
            break
    
    # 如果今天没有下一个开始时间，使用明天的第一个开始时间
    if next_start is None and RUN_SCHEDULE:
        next_start = RUN_SCHEDULE[0]
    
    if next_start:
        # 计算距离下一次运行的时间（秒）
        next_hour, next_minute = next_start
        next_datetime = now.replace(hour=next_hour, minute=next_minute, second=0, microsecond=0)
        
        # 如果下一次运行时间在今天，则直接使用
        # 否则，使用明天的这个时间
        if next_datetime <= now:
            # 加上一天
            from datetime import timedelta
            next_datetime += timedelta(days=1)
        
        return (next_datetime - now).total_seconds()
    
    return None

def main():
    if "请替换成你的 Authorization Token" in TOKEN:
        raise RuntimeError("请先在脚本顶部把 TOKEN 替换成真实值。")

    print("=== 批量远程抓图脚本启动 ===")
    print(f"运行时间窗口: {RUN_SCHEDULE}")
    print("脚本将在运行时间窗口内执行抓取任务，在非运行时间窗口内休眠")
    
    while True:
        # 检查当前是否在运行时间窗口内
        if is_in_run_window():
            print(f"\n=== 当前时间在运行窗口内，开始执行抓取任务 ===")
            
            # 加载历史日志数据
            history = load_history_logs()

            # 自动兼容列名
            possible_plate_cols = ["车辆编号", "车牌号", "车牌", "plate", "Plate"]
            possible_line_cols = ["线路", "line", "Line", "线路号"]

            # 收集所有符合条件的行
            all_filtered_rows = []
            
            for csv_file in CSV_FILES:
                try:
                    rows, used_encoding = read_csv_rows(csv_file)
                    print(f"CSV {csv_file} 读取成功，编码={used_encoding}，记录数={len(rows)}")

                    if not rows:
                        print(f"CSV {csv_file} 为空")
                        continue

                    plate_col = next((c for c in possible_plate_cols if c in rows[0]), None)
                    line_col = next((c for c in possible_line_cols if c in rows[0]), None)

                    if not plate_col or not line_col:
                        print(f"CSV {csv_file} 缺少必要字段。当前表头：{list(rows[0].keys())}")
                        continue

                    # 筛选指定线路的数据
                    filtered_rows = []
                    for row in rows:
                        line = str(row.get(line_col, ""))
                        
                        # 如果启用线路筛选，只保留 TARGET_LINES 中的线路
                        if ENABLE_LINE_FILTER and line not in TARGET_LINES:
                            continue
                        
                        filtered_rows.append(row)
                    
                    if ENABLE_LINE_FILTER:
                        print(f"CSV {csv_file} 筛选后 {TARGET_LINES} 路数据条数: {len(filtered_rows)}")
                    else:
                        print(f"CSV {csv_file} 未启用线路筛选，全部数据条数: {len(filtered_rows)}")

                    all_filtered_rows.extend(filtered_rows)
                except Exception as e:
                    print(f"处理 CSV {csv_file} 时出错: {e}")
                    continue

            if not all_filtered_rows:
                print(f"没有找到 {TARGET_LINES} 路的数据")
                # 休眠一段时间后再次检查
                time.sleep(3600)  # 休眠1小时
                continue

            print(f"\n总计收集到 {len(all_filtered_rows)} 条数据")

            # 重新确定列名（使用第一条数据）
            if all_filtered_rows:
                plate_col = next((c for c in possible_plate_cols if c in all_filtered_rows[0]), None)
                line_col = next((c for c in possible_line_cols if c in all_filtered_rows[0]), None)

                if not plate_col or not line_col:
                    print(f"CSV 缺少必要字段。当前表头：{list(all_filtered_rows[0].keys())}")
                    # 休眠一段时间后再次检查
                    time.sleep(3600)  # 休眠1小时
                    continue

            session = requests.Session()

            total_tasks = len(all_filtered_rows) * len(CH_LIST)
            done = 0
            success = 0
            failed = 0
            skipped = 0
            
            # 本次运行的统计数据
            current_stats = {
                'channel': {},
                'vehicle': {},
                'vehicle_channel': {}
            }

            os.makedirs(OUTPUT_ROOT, exist_ok=True)
            log_path = os.path.join(OUTPUT_ROOT, f"batch_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")

            with open(log_path, "w", encoding="utf-8-sig", newline="") as log_file:
                writer = csv.writer(log_file)
                writer.writerow([
                    "time", "plate", "line", "chNO", "status", "saved_path", "error"
                ])

                for ch_no in CH_LIST:
                    print(f"\n========== 开始抓取 CH{ch_no:02d} ==========")

                    for row in all_filtered_rows:
                        # 检查是否仍然在运行时间窗口内
                        if not is_in_run_window():
                            print("\n=== 运行时间窗口结束，停止当前抓取任务 ===")
                            break

                        raw_plate = row.get(plate_col, "")
                        line_name = row.get(line_col, "")

                        plate = ensure_plate(raw_plate)
                        done += 1

                        if not plate:
                            failed += 1
                            err = "空车牌"
                            print(f"[失败] CH{ch_no:02d} | line={line_name} | {err}")
                            writer.writerow([
                                datetime.now().isoformat(timespec="seconds"),
                                raw_plate, line_name, ch_no, "FAIL", "", err
                            ])
                            time.sleep(DELAY_SECONDS)
                            continue

                        # 检查成功率，决定是否跳过
                        vch_key = (plate, ch_no)
                        
                        # 检查车辆-通道成功率
                        if vch_key in history['vehicle_channel']:
                            vch_rate = calculate_success_rate(history['vehicle_channel'][vch_key])
                            if vch_rate is not None and vch_rate <= SKIP_THRESHOLD:
                                skipped += 1
                                print(f"[跳过] CH{ch_no:02d} | line={line_name} | plate={plate} | 过去1小时成功率为0%")
                                writer.writerow([
                                    datetime.now().isoformat(timespec="seconds"),
                                    plate, line_name, ch_no, "SKIP", "", f"过去1小时成功率为0%"
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
                            
                            # 更新本次统计数据
                            # 通道统计
                            if ch_no not in current_stats['channel']:
                                current_stats['channel'][ch_no] = {'total': 0, 'success': 0}
                            current_stats['channel'][ch_no]['total'] += 1
                            current_stats['channel'][ch_no]['success'] += 1
                            
                            # 车辆统计
                            if plate not in current_stats['vehicle']:
                                current_stats['vehicle'][plate] = {'total': 0, 'success': 0}
                            current_stats['vehicle'][plate]['total'] += 1
                            current_stats['vehicle'][plate]['success'] += 1
                            
                            # 车辆-通道统计
                            if vch_key not in current_stats['vehicle_channel']:
                                current_stats['vehicle_channel'][vch_key] = {'total': 0, 'success': 0}
                            current_stats['vehicle_channel'][vch_key]['total'] += 1
                            current_stats['vehicle_channel'][vch_key]['success'] += 1
                            
                            # 计算当前成功率
                            ch_rate = calculate_success_rate(current_stats['channel'][ch_no])
                            v_rate = calculate_success_rate(current_stats['vehicle'][plate])
                            vch_rate = calculate_success_rate(current_stats['vehicle_channel'][vch_key])
                            
                            # 输出成功率信息
                            print(f"[成功] {done}/{total_tasks} | CH{ch_no:02d} | line={line_name} | plate={plate} -> {save_path}")
                            print(f"  通道成功率: {ch_rate*100:.1f}% | 车辆成功率: {v_rate*100:.1f}% | 车辆-通道成功率: {vch_rate*100:.1f}%")
                            
                            writer.writerow([
                                datetime.now().isoformat(timespec="seconds"),
                                plate, line_name, ch_no, "OK", save_path, ""
                            ])

                        except Exception as e:
                            failed += 1
                            
                            # 更新本次统计数据（失败情况）
                            # 通道统计
                            if ch_no not in current_stats['channel']:
                                current_stats['channel'][ch_no] = {'total': 0, 'success': 0}
                            current_stats['channel'][ch_no]['total'] += 1
                            
                            # 车辆统计
                            if plate not in current_stats['vehicle']:
                                current_stats['vehicle'][plate] = {'total': 0, 'success': 0}
                            current_stats['vehicle'][plate]['total'] += 1
                            
                            # 车辆-通道统计
                            if vch_key not in current_stats['vehicle_channel']:
                                current_stats['vehicle_channel'][vch_key] = {'total': 0, 'success': 0}
                            current_stats['vehicle_channel'][vch_key]['total'] += 1
                            
                            # 计算当前成功率
                            ch_rate = calculate_success_rate(current_stats['channel'][ch_no])
                            v_rate = calculate_success_rate(current_stats['vehicle'][plate])
                            vch_rate = calculate_success_rate(current_stats['vehicle_channel'][vch_key])
                            
                            # 输出成功率信息
                            print(f"[失败] {done}/{total_tasks} | CH{ch_no:02d} | line={line_name} | plate={plate} | error={e}")
                            print(f"  通道成功率: {ch_rate*100:.1f}% | 车辆成功率: {v_rate*100:.1f}% | 车辆-通道成功率: {vch_rate*100:.1f}%")
                            
                            writer.writerow([
                                datetime.now().isoformat(timespec="seconds"),
                                plate, line_name, ch_no, "FAIL", "", str(e)
                            ])

                        # 每次抓图之间留间隔
                        if done < total_tasks:
                            time.sleep(DELAY_SECONDS)

            print("\n========== 本次抓取任务完成 ==========")
            print(f"总任务数: {total_tasks}")
            print(f"成功: {success}")
            print(f"失败: {failed}")
            print(f"跳过: {skipped}")
            print(f"日志文件: {log_path}")
            
            # 输出最终成功率统计
            print("\n========== 成功率统计 ==========")
            
            # 通道成功率
            print("\n通道成功率:")
            for ch_no in sorted(current_stats['channel'].keys()):
                stats = current_stats['channel'][ch_no]
                rate = calculate_success_rate(stats)
                if rate is not None:
                    print(f"  CH{ch_no:02d}: {rate*100:.1f}% ({stats['success']}/{stats['total']})")
            
            # 车辆成功率（只显示前10个）
            print("\n车辆成功率（前10）:")
            vehicle_rates = []
            for plate, stats in current_stats['vehicle'].items():
                rate = calculate_success_rate(stats)
                if rate is not None:
                    vehicle_rates.append((plate, rate, stats['success'], stats['total']))
            
            # 按成功率排序
            vehicle_rates.sort(key=lambda x: x[1], reverse=True)
            
            for plate, rate, succ, total in vehicle_rates[:10]:
                print(f"  {plate}: {rate*100:.1f}% ({succ}/{total})")
            
            if len(vehicle_rates) > 10:
                print(f"  ... 还有 {len(vehicle_rates) - 10} 个车辆")
            
            # 车辆-通道成功率（只显示成功率为0%的）
            print("\n车辆-通道成功率（成功率为0%的）:")
            zero_rates = []
            for (plate, ch_no), stats in current_stats['vehicle_channel'].items():
                rate = calculate_success_rate(stats)
                if rate == 0:
                    zero_rates.append((plate, ch_no, stats['total']))
            
            if zero_rates:
                for plate, ch_no, total in zero_rates:
                    print(f"  {plate} - CH{ch_no:02d}: 0% (0/{total})")
            else:
                print("  没有成功率为0%的车辆-通道组合")
        else:
            # 计算距离下一次运行的时间
            next_run_seconds = get_next_run_time()
            if next_run_seconds:
                print(f"\n=== 当前时间不在运行窗口内，将在 {next_run_seconds:.0f} 秒后开始下一次运行 ===")
                print(f"下次运行时间: {datetime.now() + timedelta(seconds=next_run_seconds)}")
                time.sleep(next_run_seconds)
            else:
                print("\n=== 未设置运行时间窗口，脚本将退出 ===")
                break


if __name__ == "__main__":
    main()
