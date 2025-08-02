#!/usr/bin/env python3
"""
测试日志输出脚本
模拟训练过程的各种日志输出，包括颜色、进度等
"""
import time
import sys
import random

# ANSI颜色代码
RED = '\033[91m'
GREEN = '\033[92m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
PURPLE = '\033[95m'
CYAN = '\033[96m'
WHITE = '\033[97m'
BOLD = '\033[1m'
RESET = '\033[0m'

def main():
    print(f"{GREEN}[INFO]{RESET} 开始模拟训练过程...")
    print(f"{CYAN}[INFO]{RESET} 加载数据集: UAVDT")
    print(f"{CYAN}[INFO]{RESET} 模型: YOLOv8n")
    print(f"{YELLOW}[WARNING]{RESET} GPU显存使用率较高")
    
    # 模拟训练过程
    for epoch in range(1, 6):
        print(f"{BOLD}{BLUE}[INFO]{RESET} {BOLD}Epoch {epoch}/5{RESET}")
        
        # 模拟训练步骤
        for step in range(1, 11):
            loss = random.uniform(0.1, 2.0)
            accuracy = random.uniform(0.7, 0.95)
            
            # 带颜色的训练日志
            print(f"  {GREEN}Step {step}/10{RESET}: Loss={loss:.4f}, Acc={accuracy:.3f}")
            time.sleep(0.5)
        
        # 验证阶段
        val_loss = random.uniform(0.1, 1.0)
        val_acc = random.uniform(0.8, 0.95)
        print(f"{PURPLE}[VALIDATION]{RESET} Val Loss: {val_loss:.4f}, Val Acc: {val_acc:.3f}")
        
        if epoch == 3:
            print(f"{YELLOW}[WARNING]{RESET} 学习率调整: 0.001 -> 0.0001")
        
        time.sleep(1)
    
    print(f"{GREEN}[INFO]{RESET} 训练完成！")
    print(f"{GREEN}[INFO]{RESET} 模型已保存到: /path/to/model.pt")
    print(f"{CYAN}[INFO]{RESET} 训练总时长: 42.3秒")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n{RED}[ERROR]{RESET} 训练被用户中断")
        sys.exit(1)
    except Exception as e:
        print(f"{RED}[ERROR]{RESET} 训练过程中出现错误: {str(e)}")
        sys.exit(1)
