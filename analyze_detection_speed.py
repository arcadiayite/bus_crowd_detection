# -*- coding: utf-8 -*-
"""
分析日志文件中的执行次数
"""

import re
from datetime import datetime

log_file = r'e:\公交拥挤度识别\logs\daily_20260427.log'

# 读取日志文件
with open(log_file, 'r', encoding='utf-8') as f:
    content = f.read()

# 提取执行块
execution_blocks = re.split(r'={60}', content)

# 统计执行次数
valid_executions = []

for block in execution_blocks:
    # 提取开始时间
    start_match = re.search(r'\[(2026-04-27 \d{2}:\d{2}:\d{2}\.\d{6})\] 开始执行', block)
    # 提取结束时间
    end_match = re.search(r'\[(2026-04-27 \d{2}:\d{2}:\d{2}\.\d{6})\] 执行完成', block)
    
    if start_match and end_match:
        start_time = datetime.strptime(start_match.group(1), '%Y-%m-%d %H:%M:%S.%f')
        end_time = datetime.strptime(end_match.group(1), '%Y-%m-%d %H:%M:%S.%f')
        
        valid_executions.append({
            'start_time': start_time,
            'end_time': end_time
        })

# 计算统计信息
if valid_executions:
    total_executions = len(valid_executions)
    
    # 获取时间范围
    start_times = [e['start_time'] for e in valid_executions]
    end_times = [e['end_time'] for e in valid_executions]
    
    earliest_time = min(start_times)
    latest_time = max(end_times)
    
    # 计算时间跨度
    time_span = (latest_time - earliest_time).total_seconds()
    time_span_hours = time_span / 3600
    
    # 输出结果
    print("=== 执行次数分析报告 ===")
    print(f"日志文件: {log_file}")
    print(f"分析时间范围: {earliest_time} 到 {latest_time}")
    print(f"总执行次数: {total_executions}")
    print(f"时间跨度: {time_span:.2f} 秒 ({time_span_hours:.2f} 小时)")
    print(f"平均每小时执行次数: {total_executions / time_span_hours:.2f}")
else:
    print("未找到有效执行记录")