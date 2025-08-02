#!/usr/bin/env python3
"""
测试退出码检测机制
验证系统能够正确检测训练进程的实际退出码，而不是shell的退出码
"""
import os
import time
import subprocess
import tempfile
from pathlib import Path

def test_exit_code_capture():
    """测试退出码捕获机制"""
    print("=== 测试退出码捕获机制 ===")
    
    # 创建临时日志文件
    with tempfile.NamedTemporaryFile(mode='w+', suffix='.log', delete=False) as f:
        log_file = f.name
    
    try:
        # 测试1: 成功的命令（退出码0）
        print("\n1. 测试成功命令（退出码应为0）:")
        command1 = "echo 'Hello World'"
        nohup_command1 = f"nohup bash -c '({command1}); echo \"EOLO_EXIT_CODE:$?\" >> {log_file}' > {log_file} 2>&1 &"
        
        result1 = subprocess.run(nohup_command1, shell=True, capture_output=True, text=True)
        print(f"shell返回码: {result1.returncode}")
        
        # 等待命令完成
        time.sleep(2)
        
        # 读取日志文件
        with open(log_file, 'r') as f:
            log_content = f.read()
        print(f"日志内容: {log_content}")
        
        # 检查是否找到EOLO_EXIT_CODE
        lines = log_content.strip().split('\n')
        actual_exit_code = None
        for line in lines:
            if line.startswith('EOLO_EXIT_CODE:'):
                try:
                    actual_exit_code = int(line.split(':')[1])
                    break
                except:
                    pass
        
        print(f"实际退出码: {actual_exit_code}")
        print(f"预期: shell返回码=0, 实际退出码=0")
        
        # 清空日志文件
        with open(log_file, 'w') as f:
            f.write("")
        
        # 测试2: 失败的命令（退出码非0）
        print("\n2. 测试失败命令（退出码应为1）:")
        command2 = "exit 1"
        nohup_command2 = f"nohup bash -c '({command2}); echo \"EOLO_EXIT_CODE:$?\" >> {log_file}' > {log_file} 2>&1 &"
        
        result2 = subprocess.run(nohup_command2, shell=True, capture_output=True, text=True)
        print(f"shell返回码: {result2.returncode}")
        
        # 等待命令完成
        time.sleep(2)
        
        # 读取日志文件
        with open(log_file, 'r') as f:
            log_content = f.read()
        print(f"日志内容: {log_content}")
        
        # 检查是否找到EOLO_EXIT_CODE
        lines = log_content.strip().split('\n')
        actual_exit_code = None
        for line in lines:
            if line.startswith('EOLO_EXIT_CODE:'):
                try:
                    actual_exit_code = int(line.split(':')[1])
                    break
                except:
                    pass
        
        print(f"实际退出码: {actual_exit_code}")
        print(f"预期: shell返回码=0, 实际退出码=1")
        
        # 清空日志文件
        with open(log_file, 'w') as f:
            f.write("")
        
        # 测试3: 模拟显存不足错误
        print("\n3. 测试模拟显存不足错误（退出码应为2）:")
        command3 = "echo 'RuntimeError: CUDA out of memory' && exit 2"
        nohup_command3 = f"nohup bash -c '({command3}); echo \"EOLO_EXIT_CODE:$?\" >> {log_file}' > {log_file} 2>&1 &"
        
        result3 = subprocess.run(nohup_command3, shell=True, capture_output=True, text=True)
        print(f"shell返回码: {result3.returncode}")
        
        # 等待命令完成
        time.sleep(2)
        
        # 读取日志文件
        with open(log_file, 'r') as f:
            log_content = f.read()
        print(f"日志内容: {log_content}")
        
        # 检查是否找到EOLO_EXIT_CODE
        lines = log_content.strip().split('\n')
        actual_exit_code = None
        for line in lines:
            if line.startswith('EOLO_EXIT_CODE:'):
                try:
                    actual_exit_code = int(line.split(':')[1])
                    break
                except:
                    pass
        
        print(f"实际退出码: {actual_exit_code}")
        print(f"预期: shell返回码=0, 实际退出码=2")
        
        # 测试4: 模拟Python训练脚本
        print("\n4. 测试模拟Python训练脚本:")
        python_script = f"""
import sys
import time
print("开始训练...")
time.sleep(1)
print("训练中...")
time.sleep(1)
print("发生错误: 显存不足")
sys.exit(42)  # 使用特殊退出码
"""
        
        # 创建临时Python脚本
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(python_script)
            python_file = f.name
        
        try:
            command4 = f"python {python_file}"
            nohup_command4 = f"nohup bash -c '({command4}); echo \"EOLO_EXIT_CODE:$?\" >> {log_file}' > {log_file} 2>&1 &"
            
            result4 = subprocess.run(nohup_command4, shell=True, capture_output=True, text=True)
            print(f"shell返回码: {result4.returncode}")
            
            # 等待命令完成
            time.sleep(3)
            
            # 读取日志文件
            with open(log_file, 'r') as f:
                log_content = f.read()
            print(f"日志内容:\n{log_content}")
            
            # 检查是否找到EOLO_EXIT_CODE
            lines = log_content.strip().split('\n')
            actual_exit_code = None
            for line in lines:
                if line.startswith('EOLO_EXIT_CODE:'):
                    try:
                        actual_exit_code = int(line.split(':')[1])
                        break
                    except:
                        pass
            
            print(f"实际退出码: {actual_exit_code}")
            print(f"预期: shell返回码=0, 实际退出码=42")
            
        finally:
            # 清理临时Python文件
            try:
                os.unlink(python_file)
            except:
                pass
        
    finally:
        # 清理临时日志文件
        try:
            os.unlink(log_file)
        except:
            pass
    
    print("\n=== 测试总结 ===")
    print("如果上述测试都显示：")
    print("- shell返回码始终为0（因为nohup命令本身成功启动）")
    print("- 实际退出码正确反映内部命令的真实退出码")
    print("那么退出码捕获机制工作正常！")

if __name__ == "__main__":
    test_exit_code_capture()
