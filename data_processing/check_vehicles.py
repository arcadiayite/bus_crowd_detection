#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
检查脚本：验证Excel中有成功记录的车辆是否都在新购车辆列表中
"""

import pandas as pd
import csv

# 文件路径
EXCEL_FILE = "珠海公交车辆爬取清单.xlsx"
CSV_FILE = "2026年420台新购纯电动公交车辆信息表.csv"

def ensure_plate(value: str) -> str:
    """把车辆编号补成完整车牌号"""
    value = (value or "").strip()
    if not value:
        return ""
    if value.startswith("粤C"):
        return value
    return f"粤C{value}"

def main():
    print("开始检查...")
    
    # 1. 读取Excel文件
    print(f"\n读取Excel文件: {EXCEL_FILE}")
    try:
        df_excel = pd.read_excel(EXCEL_FILE)
        print(f"Excel列名: {list(df_excel.columns)}")
        print(f"Excel总行数: {len(df_excel)}")
    except Exception as e:
        print(f"读取Excel失败: {e}")
        return
    
    # 2. 找出Excel中有成功记录的车辆
    success_col = "是否有成功爬取记录"
    plate_col = "车辆编号"
    
    print(f"使用列名: {success_col}")
    
    # 获取有成功记录的车辆
    success_mask = df_excel[success_col].astype(str).str.contains('有|成功', na=False)
    success_plates = set(df_excel.loc[success_mask, plate_col].astype(str).tolist())
    
    # 清理车牌号（去除空格等）并添加"粤C"前缀
    success_plates = {ensure_plate(p) for p in success_plates if p and str(p).strip()}
    
    print(f"\nExcel中有成功记录的车辆数: {len(success_plates)}")
    if success_plates:
        print(f"示例车牌: {list(success_plates)[:5]}")
    
    # 3. 读取CSV文件
    print(f"\n读取CSV文件: {CSV_FILE}")
    csv_plates = set()
    try:
        with open(CSV_FILE, 'r', encoding='utf-8-sig', newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                plate = row.get("车辆编号", "").strip()
                if plate:
                    csv_plates.add(ensure_plate(plate))
    except Exception as e:
        print(f"读取CSV失败: {e}")
        return
    
    print(f"CSV中新购车辆总数: {len(csv_plates)}")
    
    # 4. 检查哪些在Excel有成功记录但不在CSV中
    in_excel_not_in_csv = success_plates - csv_plates
    in_csv_not_in_excel = csv_plates - success_plates
    
    print("\n" + "="*60)
    print("检查结果")
    print("="*60)
    
    print(f"\n在Excel有成功记录但不在新购车辆列表中的车辆: {len(in_excel_not_in_csv)}")
    if in_excel_not_in_csv:
        print("车牌号列表:")
        for plate in sorted(in_excel_not_in_csv):
            print(f"  - {plate}")
    
    print(f"\n在新购车辆列表中但Excel无成功记录的车辆: {len(in_csv_not_in_excel)}")
    
    print("\n" + "="*60)
    print("总结")
    print("="*60)
    print(f"Excel中有成功记录的车辆总数: {len(success_plates)}")
    print(f"这些车辆中，在新购车辆列表中的数量: {len(success_plates) - len(in_excel_not_in_csv)}")
    print(f"这些车辆中，不在新购车辆列表中的数量: {len(in_excel_not_in_csv)}")
    
    if len(in_excel_not_in_csv) == 0:
        print("\n[OK] 所有在Excel中有成功记录的车辆都在新购车辆列表中！")
    else:
        print(f"\n[ERROR] 有 {len(in_excel_not_in_csv)} 辆在Excel中有成功记录的车辆不在新购车辆列表中")

if __name__ == "__main__":
    main()
