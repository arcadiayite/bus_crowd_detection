

"""
获取摄像头快照的脚本
用于测试和获取公交车辆摄像头的实时快照
功能：
- 向指定URL发送请求获取摄像头快照
- 支持多通道测试（4-19通道）
- 处理响应内容，保存为JPEG文件
- 包含错误处理和重试机制
"""

import requests
import os
import re
from urllib.parse import unquote, quote
import sys
import time
from datetime import datetime

sys.stdout.reconfigure(encoding='utf-8')

url = "http://119.146.222.192:8050/t1_device/RemoteSnapshot"
token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhZG1pbiI6dHJ1ZSwiYXBwIjoyMSwiY29tcGFkbWluIjpmYWxzZSwiZXBkIjo5MjE4ODgwMCwiaWF0IjoxNzc0ODMzNjY5LCJvcmciOiIxNjIwNjU3MTIzMDAwMDEwMDIiLCJwaG9uZSI6IiIsInNuIjoxLCJ0aWQiOiIxNzc0NzY3MzQ1MDAxMDAwMDMifQ.CEZXbkn2Rkil3HmOo_R04t9jb9xQCRExVwe0tX-whU0"

headers = {
    "Authorization": token
}

RETRY_TIMES = 1
RETRY_DELAY = 5
TIMEOUT_SECONDS = 10
MIN_CONTENT_SIZE = 1024  # 最小响应大小，1KB

test_plates=["粤C05909D"]
payloads=[]

for test_plate in test_plates:
    for chNO in range(4, 20):
        payloads.append({
            "devSN": "",
            "plate": test_plate,
            "chNO": chNO,
            "cmd": 1,
            "interval": 1,
            "save": 1,
            "resolution": 255,
            "quality": 5,
            "brightness": 50,
            "contrast": 50,
            "saturation": 50,
            "chroma": 1
        })

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

for i, payload in enumerate(payloads):
    print(f"\n处理第 {i+1} 个车牌: {payload['plate']}")
    
    last_error = None
    content_length = 0
    
    for attempt in range(RETRY_TIMES + 1):
        try:
            resp = requests.request(
                method="GET",
                url=url,
                headers=headers,
                json=payload,
                timeout=TIMEOUT_SECONDS
            )

            resp.raise_for_status()

            content_length = len(resp.content)
            print(f"响应内容大小: {content_length} 字节")

            if content_length == 0:
                print("错误: 响应内容为空，服务器没有返回图片数据")
                print("跳过保存文件操作")
                break

            if content_length < MIN_CONTENT_SIZE:
                print(f"错误: 响应内容太小 ({content_length} 字节)，小于最小要求 ({MIN_CONTENT_SIZE} 字节)")
                # 打印响应内容，以便查看具体是什么
                try:
                    content_str = resp.content.decode('utf-8', errors='replace')
                    print(f"响应内容: {content_str!r}")
                except Exception as e:
                    print(f"无法解码响应内容: {e}")
                    print(f"响应内容 (原始): {resp.content!r}")
                print("跳过保存文件操作")
                break

            cd = resp.headers.get("content-disposition", "")
            print(f"Content-Disposition: {cd}")
            filename = None

            match = re.search(r'filename=([^;]+)', cd)
            if match:
                filename = match.group(1).strip().strip('"')
                filename = unquote(filename)
                # 修复文件名编码问题
                filename = fix_filename_encoding(filename)
                print(f"提取到的文件名: {filename}")

            if not filename or filename == "snapshot.jpeg":
                plate = payload['plate']
                chNO = payload['chNO']
                timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
                filename = f"{plate}_{chNO}_{timestamp}.jpeg"

            if not filename.lower().endswith('.jpeg'):
                filename = f"{os.path.splitext(filename)[0]}.jpeg"

            with open(filename, "wb") as f:
                f.write(resp.content)

            print(f"抓图成功，已保存为: {filename}")
            last_error = None
            break

        except requests.exceptions.Timeout as e:
            last_error = f"请求超时"
            print(f"[重试 {attempt + 1}/{RETRY_TIMES + 1}] 请求超时，等待 {RETRY_DELAY} 秒后重试...")
            if attempt < RETRY_TIMES:
                time.sleep(RETRY_DELAY)
        except requests.exceptions.ConnectionError as e:
            last_error = f"连接错误"
            print(f"[重试 {attempt + 1}/{RETRY_TIMES + 1}] 连接错误，等待 {RETRY_DELAY} 秒后重试...")
            if attempt < RETRY_TIMES:
                time.sleep(RETRY_DELAY)
        except requests.RequestException as e:
            last_error = f"请求失败: {e}"
            print(f"请求失败: {e}")
            break
        except Exception as e:
            last_error = f"其他错误: {type(e).__name__}: {e}"
            print(f"其他错误: {type(e).__name__}: {e}")
            break

    if last_error:
        print(f"最终错误: {last_error}，跳过保存")
