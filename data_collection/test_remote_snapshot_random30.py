# -*- coding: utf-8 -*-
"""
test 版远程抓图脚本

用途：
1. 从 CSV 中随机抽取车辆 + chNO 组合
2. 默认只跑 30 个任务，先验证接口、目录结构、命名和稳定性
3. 输出目录仍然按 CHxx/线路/图片文件 分层保存
4. 记录测试日志

使用前：
- 把 TOKEN 改成你的真实 Authorization
- 确认 CSV_FILE 文件名正确
"""

import csv
import os
import random
import re
import time
from datetime import datetime
from urllib.parse import unquote

import requests


# =========================
# 配置区
# =========================
URL = "http://119.146.222.192:8050/t1_device/RemoteSnapshot"
TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhZG1pbiI6dHJ1ZSwiYXBwIjoyMSwiY29tcGFkbWluIjpmYWxzZSwiZXBkIjo5MjE4ODgwMCwiaWF0IjoxNzc0ODMzNjY5LCJvcmciOiIxNjIwNjU3MTIzMDAwMDEwMDIiLCJwaG9uZSI6IiIsInNuIjoxLCJ0aWQiOiIxNzc0NzY3MzQ1MDAxMDAwMDMifQ.CEZXbkn2Rkil3HmOo_R04t9jb9xQCRExVwe0tX-whU0"


CSV_FILE = "前山站车辆清单.csv"
OUTPUT_ROOT = "collected_test"

CH_START = 1
CH_END = 20

# 本次随机测试任务数
SAMPLE_COUNT = 30

# 固定随机种子，便于复现；不需要复现可改成 None
RANDOM_SEED = 20260422

# 两次抓图之间的等待时间（秒）
DELAY_SECONDS = 10

# 单次请求超时（秒）
TIMEOUT_SECONDS = 30

# 失败重试次数（不含首次请求）
RETRY_TIMES = 1

PAYLOAD_TEMPLATE = {
    "devSN": "",
    "plate": "",
    "chNO": 1,
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
    value = (value or "").strip()
    if not value:
        return ""
    if value.startswith("粤C"):
        return value
    return f"粤C{value}"


def sanitize_path_name(value: str) -> str:
    value = str(value).strip()
    return re.sub(r'[<>:"/\\\\|?*]', "_", value)


def read_csv_rows(csv_path: str):
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


def extract_header_filename(response: requests.Response) -> str:
    content_disposition = response.headers.get("content-disposition", "")
    match = re.search(r"filename=([^;]+)", content_disposition, flags=re.IGNORECASE)
    if match:
        return match.group(1)
    return ""


def is_image_response(response: requests.Response) -> bool:
    content_type = (response.headers.get("content-type") or "").lower()
    if "image" in content_type:
        return True
    magic = response.content[:4]
    return magic.startswith(b"\xff\xd8\xff")


def build_output_path(root: str, ch_no: int, line_name: str, header_filename: str, plate: str):
    ch_folder = f"CH{ch_no:02d}"
    line_folder = sanitize_path_name(line_name)

    save_dir = os.path.join(root, ch_folder, line_folder)
    os.makedirs(save_dir, exist_ok=True)

    filename = None
    if header_filename:
        filename = unquote(header_filename.strip().strip('"'))
        filename = sanitize_path_name(filename)

    if not filename:
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        filename = f"{plate}_{ch_no}_{timestamp}.jpeg"

    return os.path.join(save_dir, filename)


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

            if not is_image_response(response):
                preview = response.text[:300] if response.text else "<empty body>"
                raise RuntimeError(
                    f"返回内容不是图片，content-type={response.headers.get('content-type')}，body前300字符={preview}"
                )

            return response

        except Exception as e:
            last_error = e
            if attempt < RETRY_TIMES:
                print(f"[重试] plate={plate}, chNO={ch_no}, attempt={attempt + 1}, error={e}")
                time.sleep(2)

    raise last_error


def choose_sample_tasks(rows, sample_count):
    possible_plate_cols = ["车辆编号", "车牌号", "车牌", "plate", "Plate"]
    possible_line_cols = ["线路", "line", "Line", "线路号"]

    plate_col = next((c for c in possible_plate_cols if rows and c in rows[0]), None)
    line_col = next((c for c in possible_line_cols if rows and c in rows[0]), None)

    if not plate_col or not line_col:
        raise RuntimeError(f"CSV 缺少必要字段。当前表头：{list(rows[0].keys()) if rows else '空文件'}")

    valid_rows = []
    for row in rows:
        plate = ensure_plate(row.get(plate_col, ""))
        line_name = str(row.get(line_col, "")).strip()
        if plate and line_name:
            valid_rows.append({
                "plate": plate,
                "line": line_name,
            })

    if not valid_rows:
        raise RuntimeError("CSV 中没有可用的车辆记录。")

    all_tasks = []
    for item in valid_rows:
        for ch_no in range(CH_START, CH_END + 1):
            all_tasks.append({
                "plate": item["plate"],
                "line": item["line"],
                "chNO": ch_no,
            })

    if sample_count > len(all_tasks):
        raise RuntimeError(f"SAMPLE_COUNT={sample_count} 超过可选任务总数 {len(all_tasks)}")

    if RANDOM_SEED is not None:
        random.seed(RANDOM_SEED)

    return random.sample(all_tasks, sample_count)


def main():
    if "请替换成你的 Authorization Token" in TOKEN:
        raise RuntimeError("请先在脚本顶部把 TOKEN 替换成真实值。")

    rows, used_encoding = read_csv_rows(CSV_FILE)
    print(f"CSV 读取成功，编码={used_encoding}，原始记录数={len(rows)}")

    tasks = choose_sample_tasks(rows, SAMPLE_COUNT)
    print(f"本次随机抽样任务数：{len(tasks)}")
    print(f"随机种子：{RANDOM_SEED}")

    total_wait_seconds = max(0, (len(tasks) - 1) * DELAY_SECONDS)
    print(f"仅按等待时间估算，至少需要约 {total_wait_seconds / 60:.1f} 分钟。")

    session = requests.Session()
    os.makedirs(OUTPUT_ROOT, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = os.path.join(OUTPUT_ROOT, f"test_log_{timestamp}.csv")
    sample_path = os.path.join(OUTPUT_ROOT, f"test_sample_{timestamp}.csv")

    # 先把本次抽到的任务另存一份，便于复现
    with open(sample_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["plate", "line", "chNO"])
        for task in tasks:
            writer.writerow([task["plate"], task["line"], task["chNO"]])

    success = 0
    failed = 0

    with open(log_path, "w", encoding="utf-8-sig", newline="") as log_file:
        writer = csv.writer(log_file)
        writer.writerow(["time", "plate", "line", "chNO", "status", "saved_path", "error"])

        for idx, task in enumerate(tasks, start=1):
            plate = task["plate"]
            line_name = task["line"]
            ch_no = task["chNO"]

            try:
                response = request_snapshot(session, plate, ch_no)
                header_filename = extract_header_filename(response)
                save_path = build_output_path(OUTPUT_ROOT, ch_no, line_name, header_filename, plate)

                with open(save_path, "wb") as f:
                    f.write(response.content)

                success += 1
                print(f"[成功] {idx}/{len(tasks)} | CH{ch_no:02d} | line={line_name} | plate={plate} -> {save_path}")
                writer.writerow([
                    datetime.now().isoformat(timespec="seconds"),
                    plate, line_name, ch_no, "OK", save_path, ""
                ])

            except Exception as e:
                failed += 1
                print(f"[失败] {idx}/{len(tasks)} | CH{ch_no:02d} | line={line_name} | plate={plate} | error={e}")
                writer.writerow([
                    datetime.now().isoformat(timespec="seconds"),
                    plate, line_name, ch_no, "FAIL", "", str(e)
                ])

            if idx < len(tasks):
                time.sleep(DELAY_SECONDS)

    print("\n========== 测试完成 ==========")
    print(f"成功: {success}")
    print(f"失败: {failed}")
    print(f"抽样清单: {sample_path}")
    print(f"日志文件: {log_path}")


if __name__ == "__main__":
    main()
