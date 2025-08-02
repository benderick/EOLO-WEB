"""
训练进程管理命令
用于扫描、恢复和清理训练进程
"""
from django.core.management.base import BaseCommand
from experiments.process_manager import process_manager
from experiments.models import Experiment
import psutil


class Command(BaseCommand):
    help = '管理训练进程：扫描、恢复、清理'

    def add_arguments(self, parser):
        parser.add_argument(
            '--scan',
            action='store_true',
            help='扫描并恢复遗漏的训练进程',
        )
        parser.add_argument(
            '--list',
            action='store_true',
            help='列出所有正在运行的训练进程',
        )
        parser.add_argument(
            '--cleanup',
            action='store_true',
            help='清理孤儿训练进程',
        )
        parser.add_argument(
            '--force-cleanup',
            action='store_true',
            help='强制清理所有训练进程（危险操作）',
        )
        parser.add_argument(
            '--health-check',
            action='store_true',
            help='进行健康检查',
        )

    def handle(self, *args, **options):
        self.stdout.write("=== 训练进程管理工具 ===\n")

        if options['scan']:
            self.scan_processes()
        elif options['list']:
            self.list_processes()
        elif options['cleanup']:
            self.cleanup_processes()
        elif options['force_cleanup']:
            self.force_cleanup_processes()
        elif options['health_check']:
            self.health_check()
        else:
            self.show_help()

    def show_help(self):
        """显示使用帮助"""
        self.stdout.write("可用选项:")
        self.stdout.write("  --scan          扫描并恢复遗漏的训练进程")
        self.stdout.write("  --list          列出所有正在运行的训练进程")
        self.stdout.write("  --cleanup       清理孤儿训练进程")
        self.stdout.write("  --force-cleanup 强制清理所有训练进程（危险）")
        self.stdout.write("  --health-check  进行健康检查")
        self.stdout.write("\n示例:")
        self.stdout.write("  python manage.py manage_training_processes --scan")
        self.stdout.write("  python manage.py manage_training_processes --list")

    def scan_processes(self):
        """扫描并恢复进程"""
        self.stdout.write("正在扫描训练进程...")
        
        results = process_manager.scan_and_cleanup_orphaned_processes()
        
        self.stdout.write(f"\n=== 扫描结果 ===")
        self.stdout.write(f"发现训练进程: {len(results['found_processes'])}")
        self.stdout.write(f"恢复进程监控: {len(results['restored_processes'])}")
        self.stdout.write(f"清理孤儿进程: {len(results['cleaned_processes'])}")
        self.stdout.write(f"错误数量: {len(results['errors'])}")
        
        if results['found_processes']:
            self.stdout.write("\n发现的进程:")
            for proc in results['found_processes']:
                self.stdout.write(f"  PID {proc['pid']}: 实验 {proc['experiment_id']} ({proc['identification_method']})")
        
        if results['restored_processes']:
            self.stdout.write("\n恢复监控的进程:")
            for proc in results['restored_processes']:
                self.stdout.write(f"  PID {proc['pid']}: 实验 {proc['experiment_id']}")
        
        if results['cleaned_processes']:
            self.stdout.write("\n清理的孤儿进程:")
            for proc in results['cleaned_processes']:
                self.stdout.write(f"  PID {proc['pid']}: 实验 {proc['experiment_id']}")
        
        if results['errors']:
            self.stdout.write(self.style.ERROR("\n错误信息:"))
            for error in results['errors']:
                self.stdout.write(self.style.ERROR(f"  {error}"))

    def list_processes(self):
        """列出所有训练进程"""
        self.stdout.write("正在列出训练进程...\n")
        
        # Django监控中的进程
        running_experiments = process_manager.list_running_experiments()
        if running_experiments:
            self.stdout.write("=== Django监控中的进程 ===")
            for exp_info in running_experiments:
                exp = exp_info['experiment']
                proc_info = exp_info['process_info']
                status = exp_info['status']
                
                self.stdout.write(f"实验 {exp.id}: {exp.name}")
                self.stdout.write(f"  PID: {proc_info['process'].pid}")
                self.stdout.write(f"  状态: {status.get('status', 'unknown')}")
                self.stdout.write(f"  启动时间: {proc_info['start_time']}")
                if proc_info.get('restored'):
                    self.stdout.write(f"  类型: 恢复的进程")
                elif proc_info.get('independent'):
                    self.stdout.write(f"  类型: 独立进程")
                else:
                    self.stdout.write(f"  类型: 常规进程")
                self.stdout.write("")
        else:
            self.stdout.write("Django中没有正在监控的训练进程")
        
        # 系统中所有相关进程
        self.stdout.write("\n=== 系统中的训练进程 ===")
        found_any = False
        
        for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'environ', 'create_time']):
            try:
                environ = proc.info.get('environ', {})
                cmdline = ' '.join(proc.info.get('cmdline', []))
                
                # 检查是否是训练进程
                if environ.get('EOLO_EXPERIMENT_ID') or ('train.py' in cmdline and 'python' in cmdline):
                    found_any = True
                    exp_id = environ.get('EOLO_EXPERIMENT_ID', 'unknown')
                    
                    self.stdout.write(f"PID {proc.info['pid']}: 实验 {exp_id}")
                    self.stdout.write(f"  命令: {cmdline[:100]}...")
                    self.stdout.write(f"  创建时间: {proc.info.get('create_time', 'unknown')}")
                    
                    # 检查是否在Django监控中
                    if exp_id != 'unknown' and int(exp_id) in process_manager.running_processes:
                        self.stdout.write(f"  监控状态: ✓ 已监控")
                    else:
                        self.stdout.write(self.style.WARNING(f"  监控状态: ✗ 未监控"))
                    self.stdout.write("")
            
            except (psutil.AccessDenied, psutil.ZombieProcess, psutil.NoSuchProcess):
                continue
            except Exception as e:
                continue
        
        if not found_any:
            self.stdout.write("系统中没有发现训练进程")

    def cleanup_processes(self):
        """清理孤儿进程"""
        self.stdout.write("正在清理孤儿进程...")
        
        results = process_manager.scan_and_cleanup_orphaned_processes()
        
        if results['cleaned_processes']:
            self.stdout.write(f"成功清理 {len(results['cleaned_processes'])} 个孤儿进程")
            for proc in results['cleaned_processes']:
                self.stdout.write(f"  清理: PID {proc['pid']} (实验 {proc['experiment_id']})")
        else:
            self.stdout.write("没有发现需要清理的孤儿进程")

    def force_cleanup_processes(self):
        """强制清理所有训练进程"""
        self.stdout.write(self.style.WARNING("警告: 这将强制终止所有训练进程!"))
        
        confirm = input("确认要继续吗? (yes/no): ")
        if confirm.lower() != 'yes':
            self.stdout.write("操作已取消")
            return
        
        self.stdout.write("正在强制清理所有训练进程...")
        cleaned_count = process_manager.force_cleanup_all_training_processes()
        
        self.stdout.write(f"强制清理完成，共清理 {cleaned_count} 个进程")

    def health_check(self):
        """健康检查"""
        self.stdout.write("正在进行健康检查...")
        
        result = process_manager.health_check()
        
        self.stdout.write(f"健康检查完成:")
        self.stdout.write(f"  清理的死进程: {result['cleaned_processes']}")
        
        if result['details']:
            self.stdout.write("  详细信息:")
            for exp_id, exit_code, reason in result['details']:
                self.stdout.write(f"    实验 {exp_id}: {reason} (退出码: {exit_code})")
        
        # 检查数据库状态一致性
        running_in_db = Experiment.objects.filter(status='running').count()
        running_in_memory = len(process_manager.running_processes)
        
        self.stdout.write(f"\n状态一致性检查:")
        self.stdout.write(f"  数据库中运行状态的实验: {running_in_db}")
        self.stdout.write(f"  内存中监控的进程: {running_in_memory}")
        
        if running_in_db != running_in_memory:
            self.stdout.write(self.style.WARNING("  ⚠️ 状态不一致！建议运行 --scan 来修复"))
        else:
            self.stdout.write("  ✓ 状态一致")
