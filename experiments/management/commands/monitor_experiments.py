"""
实验进程监控管理命令
用于测试和管理实验进程
"""
from django.core.management.base import BaseCommand
from experiments.process_manager import process_manager
from experiments.models import Experiment


class Command(BaseCommand):
    help = '实验进程管理命令'

    def add_arguments(self, parser):
        parser.add_argument(
            'action',
            choices=['list', 'start', 'stop', 'status', 'health_check', 'queue', 'scheduler'],
            help='执行的操作'
        )
        parser.add_argument(
            '--experiment-id',
            type=int,
            help='实验ID'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='强制启动（忽略GPU检查）'
        )
        parser.add_argument(
            '--scheduler-action',
            choices=['start', 'stop', 'status'],
            help='调度器操作'
        )

    def handle(self, *args, **options):
        action = options['action']
        experiment_id = options.get('experiment_id')

        if action == 'list':
            self.list_running_experiments()
        elif action == 'start':
            if not experiment_id:
                self.stdout.write(self.style.ERROR('启动实验需要指定 --experiment-id'))
                return
            self.start_experiment(experiment_id, options.get('force', False))
        elif action == 'stop':
            if not experiment_id:
                self.stdout.write(self.style.ERROR('停止实验需要指定 --experiment-id'))
                return
            self.stop_experiment(experiment_id)
        elif action == 'status':
            if not experiment_id:
                self.stdout.write(self.style.ERROR('查看状态需要指定 --experiment-id'))
                return
            self.show_experiment_status(experiment_id)
        elif action == 'health_check':
            self.health_check()
        elif action == 'queue':
            self.queue_operations(experiment_id)
        elif action == 'scheduler':
            self.scheduler_operations(options.get('scheduler_action'))

    def list_running_experiments(self):
        """列出所有正在运行的实验"""
        running = process_manager.list_running_experiments()
        
        if not running:
            self.stdout.write(self.style.WARNING('没有正在运行的实验'))
            return
        
        self.stdout.write(self.style.SUCCESS(f'共有 {len(running)} 个正在运行的实验：'))
        self.stdout.write('-' * 80)
        
        for item in running:
            exp = item['experiment']
            status = item['status']
            self.stdout.write(f'实验ID: {exp.id}')
            self.stdout.write(f'实验名称: {exp.name}')
            self.stdout.write(f'用户: {exp.user.username}')
            self.stdout.write(f'状态: {status.get("status", "未知")}')
            if 'pid' in status:
                self.stdout.write(f'进程ID: {status["pid"]}')
            if 'running_time' in status:
                self.stdout.write(f'运行时间: {status["running_time"]:.1f}秒')
            self.stdout.write('-' * 40)

    def start_experiment(self, experiment_id, force=False):
        """启动实验"""
        try:
            experiment = Experiment.objects.get(id=experiment_id)
            self.stdout.write(f'正在启动实验: {experiment.name} (ID: {experiment_id})')
            
            success, message = process_manager.start_experiment(experiment_id, force_start=force)
            
            if success:
                self.stdout.write(self.style.SUCCESS(f'实验启动成功: {message}'))
            else:
                self.stdout.write(self.style.ERROR(f'实验启动失败: {message}'))
                
        except Experiment.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'实验不存在 (ID: {experiment_id})'))

    def stop_experiment(self, experiment_id):
        """停止实验"""
        try:
            experiment = Experiment.objects.get(id=experiment_id)
            self.stdout.write(f'正在停止实验: {experiment.name} (ID: {experiment_id})')
            
            success, message = process_manager.stop_experiment(experiment_id, user_initiated=True)
            
            if success:
                self.stdout.write(self.style.SUCCESS(f'实验停止成功: {message}'))
            else:
                self.stdout.write(self.style.ERROR(f'实验停止失败: {message}'))
                
        except Experiment.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'实验不存在 (ID: {experiment_id})'))

    def show_experiment_status(self, experiment_id):
        """显示实验状态"""
        try:
            experiment = Experiment.objects.get(id=experiment_id)
            self.stdout.write(f'实验: {experiment.name} (ID: {experiment_id})')
            self.stdout.write(f'数据库状态: {experiment.status}')
            
            status = process_manager.get_experiment_status(experiment_id)
            self.stdout.write(f'进程状态: {status}')
            
        except Experiment.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'实验不存在 (ID: {experiment_id})'))

    def health_check(self):
        """执行进程健康检查"""
        self.stdout.write('正在执行进程健康检查...')
        
        result = process_manager.health_check()
        
        self.stdout.write(
            self.style.SUCCESS(
                f'健康检查完成，清理了 {result["cleaned_processes"]} 个死进程'
            )
        )
        
        if result['details']:
            self.stdout.write('清理详情:')
            for exp_id, exit_code, reason in result['details']:
                self.stdout.write(f'  实验 {exp_id}: {reason} (退出码: {exit_code})')
        else:
            self.stdout.write('未发现需要清理的进程')

    def queue_operations(self, experiment_id):
        """队列操作"""
        from experiments.queue_scheduler import gpu_scheduler
        
        if experiment_id:
            # 将特定实验加入队列
            success, message = gpu_scheduler.add_to_queue(experiment_id)
            if success:
                self.stdout.write(self.style.SUCCESS(f'实验 {experiment_id} 已加入队列: {message}'))
            else:
                self.stdout.write(self.style.ERROR(f'加入队列失败: {message}'))
        else:
            # 显示队列状态
            status = gpu_scheduler.get_queue_status()
            
            self.stdout.write(f'队列调度器状态: {"运行中" if status["scheduler_running"] else "已停止"}')
            self.stdout.write(f'检查间隔: {status["check_interval"]}秒')
            self.stdout.write(f'排队实验总数: {status["total_queued"]}')
            
            if status['device_groups']:
                self.stdout.write('\n按设备分组的队列:')
                for device, info in status['device_groups'].items():
                    self.stdout.write(f'  设备 {device}: {info["count"]} 个实验')
                    for exp in info['experiments']:
                        queued_time = int(exp['queued_time'])
                        self.stdout.write(f'    - 实验 {exp["id"]}: {exp["name"]} (用户: {exp["user"]}, 排队时间: {queued_time}秒)')
            else:
                self.stdout.write('当前没有排队的实验')

    def scheduler_operations(self, scheduler_action):
        """调度器操作"""
        from experiments.queue_scheduler import gpu_scheduler
        
        if scheduler_action == 'start':
            gpu_scheduler.start_scheduler()
            self.stdout.write(self.style.SUCCESS('GPU队列调度器已启动'))
        elif scheduler_action == 'stop':
            gpu_scheduler.stop_scheduler()
            self.stdout.write(self.style.SUCCESS('GPU队列调度器已停止'))
        elif scheduler_action == 'status':
            status = gpu_scheduler.get_queue_status()
            self.stdout.write(f'调度器状态: {"运行中" if status["scheduler_running"] else "已停止"}')
            self.stdout.write(f'检查间隔: {status["check_interval"]}秒')
            self.stdout.write(f'排队实验总数: {status["total_queued"]}')
        else:
            self.stdout.write(self.style.ERROR('请指定调度器操作: --scheduler-action start|stop|status'))
