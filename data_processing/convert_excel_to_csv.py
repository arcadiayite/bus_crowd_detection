#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Excel转CSV工具
功能：将2026年420台新购纯电动公交车辆信息表.xlsx转换为CSV格式
"""

import pandas as pd
import os

# 输入输出文件路径
EXCEL_FILE = "2026年420台新购纯电动公交车辆信息表.xlsx"
OUTPUT_CSV = "2026年420台新购纯电动公交车辆信息表.csv"
REFERENCE_CSV = "珠海公交车辆清单.csv"

# 目标表头
TARGET_HEADERS = ["车辆编号", "线路", "分公司", "站点", "是否有成功爬取记录"]

def main():
    print("开始转换Excel到CSV...")
    
    # 检查文件是否存在
    if not os.path.exists(EXCEL_FILE):
        print(f"错误：文件 {EXCEL_FILE} 不存在")
        return
    
    try:
        # 读取Excel文件，跳过前2行，使用第3行作为表头
        print(f"读取Excel文件: {EXCEL_FILE}")
        df = pd.read_excel(EXCEL_FILE, header=2)
        
        print(f"Excel文件包含 {len(df)} 行数据")
        print(f"Excel表头: {list(df.columns)}")
        
        # 创建新的DataFrame，按照目标表头结构
        new_df = pd.DataFrame(columns=TARGET_HEADERS)
        
        # 映射Excel列到目标列，根据列位置
        # 假设列顺序为：序号(0), 车牌号(1), 接车单位(2), 所属站(3), 线路(4), 代码(5)
        if len(df.columns) >= 5:
            # 车牌号 -> 车辆编号
            new_df["车辆编号"] = df.iloc[:, 1]  # 第2列
            # 线路 -> 线路
            new_df["线路"] = df.iloc[:, 4]  # 第5列
            # 接车单位 -> 分公司
            new_df["分公司"] = df.iloc[:, 2]  # 第3列
            # 所属站 -> 站点
            new_df["站点"] = df.iloc[:, 3]  # 第4列
        
        # 设置默认值
        new_df["是否有成功爬取记录"] = "无"
        
        # 保存为CSV
        print(f"保存为CSV文件: {OUTPUT_CSV}")
        new_df.to_csv(OUTPUT_CSV, index=False, encoding="utf-8-sig")
        
        print("转换完成！")
        print(f"输出文件: {OUTPUT_CSV}")
        print(f"文件包含 {len(new_df)} 行数据")
        print(f"CSV表头: {list(new_df.columns)}")
        
    except Exception as e:
        print(f"转换失败: {e}")

if __name__ == "__main__":
    main()
