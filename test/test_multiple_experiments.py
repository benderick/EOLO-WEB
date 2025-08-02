#!/usr/bin/env python3
"""
测试多个实验同时运行时的环境变量隔离
"""
import os
import subprocess
import time
import psutil

def simulate_experiment_process(experiment_id, duration=10):
    """模拟实验进程"""
    # 设置环境变量
    env = os.environ.copy()
    env['EOLO_EXPERIMENT_ID'] = str(experiment_id)
    env['PYTHONUNBUFFERED'] = '1'
    
    # 创建一个简单的训练脚本
    script_content = f"""
import os
import time
import sys

print(f"实验 {{os.environ.get('EOLO_EXPERIMENT_ID', 'UNKNOWN')}} 开始运行")
print(f"进程PID: {{os.getpid()}}")
print(f"环境变量EOLO_EXPERIMENT_ID: {{os.environ.get('EOLO_EXPERIMENT_ID')}}")

for i in range({duration}):
    print(f"实验 {{os.environ.get('EOLO_EXPERIMENT_ID')}}: 第 {{i+1}} 秒")
    time.sleep(1)

print(f"实验 {{os.environ.get('EOLO_EXPERIMENT_ID')}} 完成")
"""
    
    # 写入临时脚本文件
    script_file = f"/tmp/test_exp_{experiment_id}.py"
    with open(script_file, 'w') as f:
        f.write(script_content)
    
    # 启动进程
    command = f"python3 {script_file}"
    process = subprocess.Popen(
        command,
        shell=True,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    
    return process, script_file

def test_multiple_experiments():
    """测试多个实验同时运行"""
    print("开始测试多个实验同时运行...")
    
    # 启动3个实验
    experiments = []
    for exp_id in [100, 200, 300]:
        print(f"启动实验 {exp_id}")
        process, script_file = simulate_experiment_process(exp_id, duration=5)
        experiments.append((exp_id, process, script_file))
        time.sleep(0.5)  # 稍微错开启动时间
    
    print(f"已启动 {len(experiments)} 个实验")
    
    # 等待一段时间，然后检查进程
    time.sleep(2)
    
    print("\n检查进程环境变量...")
    # 检查每个进程的环境变量
    for exp_id, process, script_file in experiments:
        try:
            if process.poll() is None:  # 进程仍在运行
                psutil_proc = psutil.Process(process.pid)
                environ = psutil_proc.environ()
                eolo_id = environ.get('EOLO_EXPERIMENT_ID', 'NOT_FOUND')
                print(f"实验 {exp_id} (PID: {process.pid}): EOLO_EXPERIMENT_ID = {eolo_id}")
            else:
                print(f"实验 {exp_id} 已结束")
        except Exception as e:
            print(f"检查实验 {exp_id} 时出错: {e}")
    
    # 等待所有进程完成
    print("\n等待所有实验完成...")
    for exp_id, process, script_file in experiments:
        stdout, stderr = process.communicate()
        print(f"\n实验 {exp_id} 输出:")
        print(stdout)
        if stderr:
            print(f"实验 {exp_id} 错误:")
            print(stderr)
        
        # 清理临时文件
        try:
            os.unlink(script_file)
        except:
            pass
    
    print("测试完成！")

if __name__ == "__main__":
    test_multiple_experiments()
