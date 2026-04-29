#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
分析所有batch_log文件，提取可采集的车辆和频道
并同步更新珠海公交车辆清单.csv和2026年420台新购纯电动公交车辆信息表.csv
"""

import os
import csv
from collections import defaultdict

# 日志文件目录
LOG_DIR = "collected"
# 输出文件
OUTPUT_CSV = "available_vehicles_channels.csv"
# 珠海公交车辆清单文件
ZHUHAI_BUS_LIST = "珠海公交车辆清单.csv"
# 新购车辆信息表文件
NEW_VEHICLES_LIST = "2026年420台新购纯电动公交车辆信息表.csv"

def analyze_logs():
    """分析所有日志文件，提取成功的车辆和频道"""
    # 存储成功的车辆-频道组合
    available = defaultdict(set)
    
    # 遍历所有日志文件
    for filename in os.listdir(LOG_DIR):
        if not filename.startswith("batch_log_") or not filename.endswith(".csv"):
            continue
        
        log_path = os.path.join(LOG_DIR, filename)
        print(f"分析: {filename}")
        
        try:
            with open(log_path, 'r', encoding='utf-8-sig', newline='') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row.get('status') == 'OK':
                        plate = row.get('plate', '').strip()
                        ch_no = row.get('chNO', '').strip()
                        line = row.get('line', '').strip()
                        if plate and ch_no:
                            available[plate].add((line, int(ch_no)))
        except Exception as e:
            print(f"读取 {filename} 失败: {e}")
    
    # 生成输出CSV
    with open(OUTPUT_CSV, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['车牌号', '线路', '频道'])
        
        for plate, channels in sorted(available.items()):
            for line, ch_no in sorted(channels, key=lambda x: x[1]):
                writer.writerow([plate, line, ch_no])
    
    print(f"\n分析完成！")
    print(f"找到 {len(available)} 辆可采集的车辆")
    print(f"输出文件: {OUTPUT_CSV}")
    
    # 打印简要结果
    print("\n可采集的车辆和频道:")
    for plate, channels in sorted(available.items()):
        lines = sorted(set([line for line, _ in channels]))
        ch_nos = sorted([ch_no for _, ch_no in channels])
        print(f"{plate} (线路: {', '.join(lines)}) - 频道: {ch_nos}")
    
    # 同步更新珠海公交车辆清单
    update_zhuhai_bus_list(available)
    
    # 同步更新新购车辆信息表
    update_new_vehicles_list(available)

def update_zhuhai_bus_list(available_vehicles):
    """同步更新珠海公交车辆清单，添加'是否有成功爬取记录'列"""
    print(f"\n开始同步更新珠海公交车辆清单...")
    
    # 读取珠海公交车辆清单
    encodings = ["utf-8-sig", "utf-8", "gb18030", "gbk"]
    rows = []
    used_encoding = None
    
    for enc in encodings:
        try:
            with open(ZHUHAI_BUS_LIST, 'r', encoding=enc, newline='') as f:
                reader = csv.DictReader(f)
                rows = list(reader)
                used_encoding = enc
                break
        except Exception as e:
            last_error = e
            continue
    
    if not rows:
        print(f"读取珠海公交车辆清单失败: {last_error}")
        return
    
    print(f"成功读取珠海公交车辆清单，编码={used_encoding}，记录数={len(rows)}")
    
    # 检查是否有'是否有成功爬取记录'列
    if rows and '是否有成功爬取记录' not in rows[0]:
        print("添加'是否有成功爬取记录'列...")
        # 为每行添加新列
        for row in rows:
            row['是否有成功爬取记录'] = '无'
    
    # 更新'是否有成功爬取记录'列
    updated_count = 0
    for row in rows:
        plate = row.get('车辆编号', '').strip()
        # 检查是否在可采集车辆列表中（匹配时去掉'粤C'前缀）
        matched = False
        # 直接匹配
        if plate in available_vehicles:
            matched = True
        else:
            # 尝试带'粤C'前缀匹配
            full_plate = f"粤C{plate}"
            if full_plate in available_vehicles:
                matched = True
        
        if matched:
            # 只有当前状态为'无'时才更新为'有'，避免覆盖已有的'有'状态
            if row.get('是否有成功爬取记录') != '有':
                row['是否有成功爬取记录'] = '有'
                updated_count += 1
    
    # 写回文件
    with open(ZHUHAI_BUS_LIST, 'w', encoding='utf-8-sig', newline='') as f:
        fieldnames = list(rows[0].keys()) if rows else []
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    
    print(f"珠海公交车辆清单更新完成！")
    print(f"更新了 {updated_count} 条记录")
    print(f"总记录数: {len(rows)}")

def update_new_vehicles_list(available_vehicles):
    """同步更新新购车辆信息表，更新'是否有成功爬取记录'列"""
    print(f"\n开始同步更新新购车辆信息表...")
    
    # 读取新购车辆信息表
    encodings = ["utf-8-sig", "utf-8", "gb18030", "gbk"]
    rows = []
    used_encoding = None
    
    for enc in encodings:
        try:
            with open(NEW_VEHICLES_LIST, 'r', encoding=enc, newline='') as f:
                reader = csv.DictReader(f)
                rows = list(reader)
                used_encoding = enc
                break
        except Exception as e:
            last_error = e
            continue
    
    if not rows:
        print(f"读取新购车辆信息表失败: {last_error}")
        return
    
    print(f"成功读取新购车辆信息表，编码={used_encoding}，记录数={len(rows)}")
    
    # 检查是否有'是否有成功爬取记录'列
    if rows and '是否有成功爬取记录' not in rows[0]:
        print("添加'是否有成功爬取记录'列...")
        # 为每行添加新列
        for row in rows:
            row['是否有成功爬取记录'] = '无'
    
    # 更新'是否有成功爬取记录'列
    updated_count = 0
    for row in rows:
        plate = row.get('车辆编号', '').strip()
        # 检查是否在可采集车辆列表中
        matched = False
        # 直接匹配
        if plate in available_vehicles:
            matched = True
        else:
            # 尝试不带'粤C'前缀匹配
            if plate.startswith('粤C'):
                short_plate = plate[2:]
                if short_plate in available_vehicles:
                    matched = True
        
        if matched:
            # 只有当前状态为'无'时才更新为'有'，避免覆盖已有的'有'状态
            if row.get('是否有成功爬取记录') != '有':
                row['是否有成功爬取记录'] = '有'
                updated_count += 1
    
    # 写回文件
    with open(NEW_VEHICLES_LIST, 'w', encoding='utf-8-sig', newline='') as f:
        fieldnames = list(rows[0].keys()) if rows else []
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    
    print(f"新购车辆信息表更新完成！")
    print(f"更新了 {updated_count} 条记录")
    print(f"总记录数: {len(rows)}")

if __name__ == "__main__":
    analyze_logs()
