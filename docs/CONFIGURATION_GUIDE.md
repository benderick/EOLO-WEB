# 实验系统配置参数说明

## 概述

为了便于统一管理和调优，所有实验系统的关键参数都集中在 Django 的 `settings.py` 文件中。你可以根据硬件环境和使用需求调整这些参数。

## 配置项详解

### 1. GPU 配置 (`GPU_CONFIG`)

```python
GPU_CONFIG = {
    # GPU显存使用率阈值（百分比）
    'MEMORY_THRESHOLD': 20.0,
    # nvidia-smi命令超时时间（秒）
    'NVIDIA_SMI_TIMEOUT': 10,
}
```

**参数说明：**
- `MEMORY_THRESHOLD`: GPU显存使用率超过此阈值时认为GPU繁忙，默认20%
- `NVIDIA_SMI_TIMEOUT`: 执行nvidia-smi命令的超时时间，防止命令卡死

**调优建议：**
- **显存要求高的模型**：可以降低阈值到10-15%，确保有足够显存
- **轻量模型**：可以提高阈值到30-40%，允许多个实验共享GPU
- **服务器环境稳定**：可以延长nvidia-smi超时到15-20秒

### 2. 队列调度器配置 (`QUEUE_SCHEDULER_CONFIG`)

```python
QUEUE_SCHEDULER_CONFIG = {
    # 队列检查间隔（秒）
    'CHECK_INTERVAL': 30,
    # 是否在应用启动时自动启动调度器
    'AUTO_START': True,
    # 调度器线程名称
    'THREAD_NAME': 'GPUQueueScheduler',
}
```

**参数说明：**
- `CHECK_INTERVAL`: 调度器检查队列的频率，默认30秒
- `AUTO_START`: 是否自动启动调度器，生产环境建议True
- `THREAD_NAME`: 调度器线程名称，便于调试和监控

**调优建议：**
- **实验较多时**：缩短检查间隔到10-15秒，提高响应速度
- **资源紧张时**：延长间隔到60秒，减少系统开销
- **调试阶段**：设置AUTO_START为False，手动控制启动

### 3. 进程监控配置 (`PROCESS_MONITOR_CONFIG`)

```python
PROCESS_MONITOR_CONFIG = {
    # 进程状态检查间隔（秒）
    'STATUS_CHECK_INTERVAL': 1.0,
    # 进程监控超时时间（秒）
    'MONITOR_TIMEOUT': 10,
    # 日志监控缓冲大小
    'LOG_BUFFER_SIZE': 4096,
    # 进程终止等待时间（秒）
    'TERMINATION_TIMEOUT': 10,
    # 子进程清理等待时间（秒）
    'CLEANUP_TIMEOUT': 5,
}
```

**参数说明：**
- `STATUS_CHECK_INTERVAL`: 检查进程状态的频率，影响进程终止检测速度
- `MONITOR_TIMEOUT`: 进程监控操作的超时时间
- `LOG_BUFFER_SIZE`: 日志读取缓冲区大小，影响实时性
- `TERMINATION_TIMEOUT`: 等待进程优雅退出的时间
- `CLEANUP_TIMEOUT`: 等待子进程清理的时间

**调优建议：**
- **需要快速检测进程状态**：缩短STATUS_CHECK_INTERVAL到0.5秒
- **系统资源有限**：延长间隔到2-3秒，减少CPU使用
- **处理大量日志**：增加LOG_BUFFER_SIZE到8192或更大
- **进程难以终止**：延长TERMINATION_TIMEOUT到20-30秒

### 4. 实验日志配置 (`EXPERIMENT_LOG_CONFIG`)

```python
EXPERIMENT_LOG_CONFIG = {
    # 实验详情页面显示的最新日志条数
    'RECENT_LOGS_COUNT': 10,
    # 日志级别颜色映射
    'LOG_LEVEL_COLORS': {
        'DEBUG': 'text-muted',
        'INFO': 'text-info', 
        'WARNING': 'text-warning',
        'ERROR': 'text-danger',
    },
    # ANSI转义序列清理正则表达式
    'ANSI_ESCAPE_PATTERN': r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])',
}
```

**参数说明：**
- `RECENT_LOGS_COUNT`: API返回的最近日志条数，影响页面加载速度
- `LOG_LEVEL_COLORS`: 不同日志级别的CSS类名，用于页面显示
- `ANSI_ESCAPE_PATTERN`: 清理终端彩色字符的正则表达式

**调优建议：**
- **网络较慢**：减少RECENT_LOGS_COUNT到5条，提高响应速度
- **需要更多上下文**：增加到20-50条，但注意性能影响
- **自定义日志显示**：修改LOG_LEVEL_COLORS的CSS类名

### 5. 实验API配置 (`EXPERIMENT_API_CONFIG`)

```python
EXPERIMENT_API_CONFIG = {
    # 状态API更新间隔（毫秒）
    'STATUS_UPDATE_INTERVAL': 1000,
    # 健康检查间隔（秒）
    'HEALTH_CHECK_INTERVAL': 60,
    # API响应超时时间（秒）
    'API_TIMEOUT': 30,
}
```

**参数说明：**
- `STATUS_UPDATE_INTERVAL`: 前端状态更新频率，影响实时性和网络开销
- `HEALTH_CHECK_INTERVAL`: 自动健康检查的间隔
- `API_TIMEOUT`: API请求的超时时间

**调优建议：**
- **需要高实时性**：缩短更新间隔到500毫秒，但增加服务器负载
- **网络带宽有限**：延长间隔到2000-5000毫秒
- **系统稳定**：延长健康检查间隔到300秒（5分钟）
- **网络不稳定**：延长API_TIMEOUT到60秒

## 配置管理

### 查看当前配置

```bash
# 查看所有配置
uv run python manage.py show_config

# 查看特定配置段
uv run python manage.py show_config --section=gpu

# 输出JSON格式
uv run python manage.py show_config --json
```

### 修改配置

1. 编辑 `eolo_web/settings.py` 文件
2. 修改对应的配置项
3. 重启Django应用使配置生效

### 配置验证

修改配置后建议进行验证：

```bash
# 检查Django配置
uv run python manage.py check

# 测试队列调度器
uv run python manage.py monitor_experiments scheduler --scheduler-action status

# 测试GPU检测
uv run python manage.py shell
>>> from experiments.gpu_utils import check_gpu_memory_usage
>>> check_gpu_memory_usage()
```

## 性能调优建议

### 高并发环境
```python
# 减少检查频率，降低系统负载
QUEUE_SCHEDULER_CONFIG = {
    'CHECK_INTERVAL': 60,  # 增加到1分钟
}

PROCESS_MONITOR_CONFIG = {
    'STATUS_CHECK_INTERVAL': 2.0,  # 降低检查频率
}

EXPERIMENT_API_CONFIG = {
    'STATUS_UPDATE_INTERVAL': 3000,  # 降低前端更新频率
}
```

### 实时性要求高
```python
# 提高响应速度
QUEUE_SCHEDULER_CONFIG = {
    'CHECK_INTERVAL': 10,  # 缩短到10秒
}

PROCESS_MONITOR_CONFIG = {
    'STATUS_CHECK_INTERVAL': 0.5,  # 提高检查频率
}

EXPERIMENT_API_CONFIG = {
    'STATUS_UPDATE_INTERVAL': 500,  # 提高前端更新频率
}
```

### 资源受限环境
```python
# 优化资源使用
GPU_CONFIG = {
    'MEMORY_THRESHOLD': 30.0,  # 提高阈值，允许更多共享
}

EXPERIMENT_LOG_CONFIG = {
    'RECENT_LOGS_COUNT': 5,  # 减少日志条数
}

PROCESS_MONITOR_CONFIG = {
    'LOG_BUFFER_SIZE': 2048,  # 减少缓冲区
}
```

## 常见问题

**Q: 修改配置后没有生效？**
A: 需要重启Django应用，配置才会重新加载。

**Q: 如何确认配置被正确加载？**
A: 使用 `uv run python manage.py show_config` 命令查看。

**Q: 某个配置项设置为None会怎样？**
A: 系统会使用代码中的默认值，建议显式设置所有配置。

**Q: 可以在运行时动态修改配置吗？**
A: 目前不支持，需要重启应用。未来可以考虑添加动态配置功能。

## 总结

通过集中化的配置管理，你可以：

✅ **统一调优**: 所有参数在一个文件中，便于整体优化
✅ **环境适配**: 根据不同环境（开发/测试/生产）调整参数  
✅ **性能调节**: 在实时性和资源消耗之间找到平衡
✅ **问题排查**: 配置透明，便于问题定位和解决
✅ **版本控制**: 配置变更可以通过Git跟踪和回滚

建议在修改配置前备份原始设置，并在测试环境验证后再应用到生产环境。
