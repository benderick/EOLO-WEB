from django.apps import AppConfig
import logging

logger = logging.getLogger(__name__)


class ExperimentsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'experiments'

    def ready(self):
        """
        应用准备就绪时的初始化操作
        """
        # 只在主进程中启动调度器，避免在开发模式下重复启动
        import os
        if os.environ.get('RUN_MAIN') != 'true':
            return
            
        try:
            from django.conf import settings
            from .queue_scheduler import gpu_scheduler
            
            # 检查是否启用自动启动
            scheduler_config = getattr(settings, 'QUEUE_SCHEDULER_CONFIG', {})
            auto_start = scheduler_config.get('AUTO_START', True)
            
            if auto_start:
                # 启动GPU队列调度器
                gpu_scheduler.start_scheduler()
                logger.info("GPU队列调度器已在应用启动时自动启动")
            else:
                logger.info("GPU队列调度器自动启动已禁用")
            
        except Exception as e:
            logger.error(f"启动GPU队列调度器失败: {str(e)}")
