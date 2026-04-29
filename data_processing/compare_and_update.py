#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
比对车辆清单并更新珠海公交车辆清单

功能：
1. 自动发现所有符合格式的车辆清单文件
2. 比对珠海公交车辆清单中的数据
3. 将缺失的车辆信息添加到珠海公交车辆清单中
4. 保存更新后的文件
"""

import csv
import os
import glob

# 文件路径
ZHUHAI_BUS_LIST = "e:/公交拥挤度识别/珠海公交车辆清单.csv"
BASE_DIR = "e:/公交拥挤度识别"

# 匹配模式：查找所有包含"车辆清单"的CSV文件
PATTERN = os.path.join(BASE_DIR, "*车辆清单*.csv")

def read_csv_with_encoding(file_path):
    """尝试多种编码读取CSV文件"""
    encodings = ['utf-8-sig', 'utf-8', 'gb18030', 'gbk']
    for enc in encodings:
        try:
            with open(file_path, 'r', encoding=enc, newline='') as f:
                reader = csv.DictReader(f)
                return list(reader), enc
        except Exception:
            continue
    raise Exception(f"无法读取文件: {file_path}")

def write_csv_with_encoding(file_path, rows, headers):
    """以UTF-8-SIG编码写入CSV文件"""
    with open(file_path, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)

def main():
    print("开始比对车辆清单...")
    
    # 读取珠海公交车辆清单
    try:
        zhuhai_rows, zhuhai_encoding = read_csv_with_encoding(ZHUHAI_BUS_LIST)
        print(f"读取珠海公交车辆清单成功，使用编码: {zhuhai_encoding}")
    except Exception as e:
        print(f"读取珠海公交车辆清单失败: {e}")
        return
    
    # 提取现有车辆信息（用于快速查找）
    existing_vehicles = set()
    for row in zhuhai_rows:
        # 处理不同的列名
        plate = row.get('车辆编号') or row.get('�������')
        route = row.get('线路') or row.get('��·')
        if plate and route:
            existing_vehicles.add((plate.strip(), route.strip()))
    
    print(f"珠海公交车辆清单现有 {len(existing_vehicles)} 条记录")
    
    # 自动发现所有车辆清单文件
    route_files = glob.glob(PATTERN)
    # 排除珠海公交车辆清单本身
    route_files = [f for f in route_files if os.path.basename(f) != os.path.basename(ZHUHAI_BUS_LIST)]
    
    if not route_files:
        print("未找到车辆清单文件")
        return
    
    print(f"发现 {len(route_files)} 个车辆清单文件:")
    for f in route_files:
        print(f"  - {os.path.basename(f)}")
    
    # 读取各线路清单并比对
    new_vehicles = []
    
    for route_file in route_files:
        try:
            route_rows, route_encoding = read_csv_with_encoding(route_file)
            print(f"读取 {os.path.basename(route_file)} 成功，使用编码: {route_encoding}")
            
            for row in route_rows:
                plate = row.get('车辆编号')
                route = row.get('线路')
                company = row.get('分公司')
                station = row.get('站点')
                
                if plate and route:
                    plate = plate.strip()
                    route = route.strip()
                    
                    if (plate, route) not in existing_vehicles:
                        new_vehicles.append({
                            '车辆编号': plate,
                            '线路': route,
                            '分公司': company or '',
                            '站点': station or ''
                        })
                        existing_vehicles.add((plate, route))
                        print(f"发现新车辆: {plate} (线路: {route})")
        except Exception as e:
            print(f"读取 {os.path.basename(route_file)} 失败: {e}")
    
    if new_vehicles:
        print(f"\n共发现 {len(new_vehicles)} 辆新车辆")
        
        # 合并数据
        # 首先转换现有数据为字典格式
        zhuhai_dict_rows = []
        for row in zhuhai_rows:
            # 标准化列名
            normalized_row = {
                '车辆编号': row.get('车辆编号') or row.get('�������', ''),
                '线路': row.get('线路') or row.get('��·', ''),
                '分公司': row.get('分公司') or row.get('�ֹ�˾', ''),
                '站点': row.get('站点') or row.get('վ��', '')
            }
            zhuhai_dict_rows.append(normalized_row)
        
        # 添加新车辆
        zhuhai_dict_rows.extend(new_vehicles)
        
        # 保存更新后的文件
        headers = ['车辆编号', '线路', '分公司', '站点']
        write_csv_with_encoding(ZHUHAI_BUS_LIST, zhuhai_dict_rows, headers)
        print(f"\n已更新珠海公交车辆清单，新增 {len(new_vehicles)} 条记录")
    else:
        print("\n没有发现新车辆，珠海公交车辆清单已是最新")
    
    print("\n任务完成！")

if __name__ == "__main__":
    main()
