from django.core.management.base import BaseCommand
from django.conf import settings
import json

class Command(BaseCommand):
    help = '显示实验系统的配置参数'

    def add_arguments(self, parser):
        parser.add_argument(
            '--section',
            choices=['gpu', 'queue', 'process', 'log', 'api', 'all'],
            default='all',
            help='显示特定配置段'
        )
        parser.add_argument(
            '--json',
            action='store_true',
            help='以JSON格式输出'
        )

    def handle(self, *args, **options):
        section = options['section']
        json_output = options['json']
        
        configs = {}
        
        if section in ['gpu', 'all']:
            configs['GPU_CONFIG'] = getattr(settings, 'GPU_CONFIG', {})
            
        if section in ['queue', 'all']:
            configs['QUEUE_SCHEDULER_CONFIG'] = getattr(settings, 'QUEUE_SCHEDULER_CONFIG', {})
            
        if section in ['process', 'all']:
            configs['PROCESS_MONITOR_CONFIG'] = getattr(settings, 'PROCESS_MONITOR_CONFIG', {})
            
        if section in ['log', 'all']:
            configs['EXPERIMENT_LOG_CONFIG'] = getattr(settings, 'EXPERIMENT_LOG_CONFIG', {})
            
        if section in ['api', 'all']:
            configs['EXPERIMENT_API_CONFIG'] = getattr(settings, 'EXPERIMENT_API_CONFIG', {})
        
        if json_output:
            self.stdout.write(json.dumps(configs, indent=2, ensure_ascii=False))
        else:
            self.display_configs(configs)
    
    def display_configs(self, configs):
        """以友好格式显示配置"""
        self.stdout.write(self.style.SUCCESS('🔧 实验系统配置参数'))
        self.stdout.write('=' * 60)
        
        for config_name, config_data in configs.items():
            section_name = {
                'GPU_CONFIG': 'GPU 配置',
                'QUEUE_SCHEDULER_CONFIG': '队列调度器配置',
                'PROCESS_MONITOR_CONFIG': '进程监控配置',
                'EXPERIMENT_LOG_CONFIG': '实验日志配置',
                'EXPERIMENT_API_CONFIG': '实验API配置'
            }.get(config_name, config_name)
            
            self.stdout.write(f'\n📋 {section_name}:')
            self.stdout.write('-' * 40)
            
            if not config_data:
                self.stdout.write('  (未配置)')
                continue
                
            for key, value in config_data.items():
                if isinstance(value, dict):
                    self.stdout.write(f'  {key}:')
                    for sub_key, sub_value in value.items():
                        self.stdout.write(f'    {sub_key}: {sub_value}')
                else:
                    self.stdout.write(f'  {key}: {value}')
        
        self.stdout.write('\n' + '=' * 60)
        self.stdout.write('💡 使用 --section=<section> 查看特定配置段')
        self.stdout.write('💡 使用 --json 输出JSON格式')
