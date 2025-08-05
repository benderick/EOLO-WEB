"""
模块文件管理工具
"""
import os
import hashlib
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from django.conf import settings
from django.contrib.auth import get_user_model
from .models import ModuleFile

User = get_user_model()


class ModuleFileManager:
    """
    模块文件管理器
    处理文件扫描、上传、删除等操作
    """
    
    def __init__(self):
        self.workpieces_dir = settings.EOLO_ULTRALYTICS_WORKPIECES_DIR
        
    def scan_python_files(self) -> List[Dict[str, Any]]:
        """
        扫描工作目录下的所有Python文件
        
        Returns:
            List[Dict]: 文件信息列表
        """
        files = []
        
        if not self.workpieces_dir.exists():
            return files
        
        # 递归遍历所有.py文件，忽略__pycache__目录
        for py_file in self.workpieces_dir.rglob("*.py"):
            try:
                # 计算相对路径
                relative_path = py_file.relative_to(self.workpieces_dir)
                
                # 忽略__pycache__目录及其子目录中的文件
                if '__pycache__' in relative_path.parts:
                    continue
                
                # 忽略__init__.py文件
                if py_file.name == '__init__.py':
                    continue
                
                # 获取文件信息
                stat = py_file.stat()
                
                files.append({
                    'name': py_file.name,
                    'relative_path': str(relative_path),
                    'absolute_path': str(py_file),
                    'size': stat.st_size,
                    'modified_time': stat.st_mtime,
                    'directory': str(relative_path.parent),
                    'depth': len(relative_path.parts) - 1,
                })
            except Exception as e:
                print(f"扫描文件时出错 {py_file}: {e}")
                continue
        
        # 按路径排序
        files.sort(key=lambda x: x['relative_path'])
        return files
    
    def build_file_tree(self) -> Dict[str, Any]:
        """
        构建文件树结构
        
        Returns:
            Dict: 树形结构的文件信息
        """
        files = self.scan_python_files()
        tree = {'files': []}  # 根目录可以有文件
        
        # 获取所有文件的状态信息
        module_files = {mf.relative_path: mf for mf in ModuleFile.objects.all()}
        
        for file_info in files:
            relative_path = file_info['relative_path']
            
            # 添加状态信息
            module_file = module_files.get(relative_path)
            if module_file:
                file_info['status'] = module_file.status
                file_info['status_icon'] = module_file.status_icon
                file_info['status_display'] = module_file.status_display
            else:
                # 默认状态：未审查
                file_info['status'] = 'unreviewed'
                file_info['status_icon'] = '⭕'
                file_info['status_display'] = '未审查'
            
            path_parts = Path(file_info['relative_path']).parts
            
            if len(path_parts) == 1:
                # 根目录下的文件
                tree['files'].append({
                    **file_info,
                    'type': 'file'
                })
            else:
                # 子目录中的文件，创建目录结构
                current = tree
                
                # 为每个目录部分创建节点
                for i, part in enumerate(path_parts[:-1]):
                    if part not in current:
                        current[part] = {
                            'type': 'directory',
                            'name': part,
                            'children': {},
                            'files': []
                        }
                    current = current[part]['children']
                
                # 添加文件到最后一个目录
                if 'files' not in current:
                    current['files'] = []
                
                current['files'].append({
                    **file_info,
                    'type': 'file'
                })
        
        return tree
    
    def get_file_content(self, relative_path: str) -> Tuple[bool, str]:
        """
        获取文件内容
        
        Args:
            relative_path: 相对路径
            
        Returns:
            Tuple[bool, str]: (成功标志, 内容或错误信息)
        """
        try:
            file_path = self.workpieces_dir / relative_path
            if not file_path.exists():
                return False, "文件不存在"
            
            if not file_path.suffix == '.py':
                return False, "只能编辑Python文件"
                
            content = file_path.read_text(encoding='utf-8')
            return True, content
        except Exception as e:
            return False, f"读取文件失败: {str(e)}"
    
    def save_file_content(self, relative_path: str, content: str, user: User) -> Tuple[bool, str]:
        """
        保存文件内容
        
        Args:
            relative_path: 相对路径
            content: 文件内容
            user: 操作用户
            
        Returns:
            Tuple[bool, str]: (成功标志, 消息)
        """
        try:
            file_path = self.workpieces_dir / relative_path
            
            # 确保目录存在
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            # 写入内容
            file_path.write_text(content, encoding='utf-8')
            
            # 更新或创建数据库记录
            self._update_file_record(relative_path, user)
            
            return True, "文件保存成功"
        except Exception as e:
            return False, f"保存失败: {str(e)}"
    
    def upload_file(self, file_data: bytes, relative_path: str, user: User) -> Tuple[bool, str]:
        """
        上传文件
        
        Args:
            file_data: 文件数据
            relative_path: 目标相对路径
            user: 上传用户
            
        Returns:
            Tuple[bool, str]: (成功标志, 消息)
        """
        try:
            # 检查文件扩展名
            if not relative_path.endswith('.py'):
                return False, "只能上传Python文件(.py)"
            
            file_path = self.workpieces_dir / relative_path
            
            # 检查文件是否已存在
            if file_path.exists():
                return False, f"文件已存在: {relative_path}"
            
            # 确保目录存在
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            # 写入文件
            file_path.write_bytes(file_data)
            
            # 创建数据库记录
            self._create_file_record(relative_path, user)
            
            return True, f"文件上传成功: {relative_path}"
        except Exception as e:
            return False, f"上传失败: {str(e)}"
    
    def delete_file(self, relative_path: str, user: User) -> Tuple[bool, str]:
        """
        删除文件
        
        Args:
            relative_path: 相对路径
            user: 操作用户
            
        Returns:
            Tuple[bool, str]: (成功标志, 消息)
        """
        try:
            file_path = self.workpieces_dir / relative_path
            
            if not file_path.exists():
                return False, "文件不存在"
            
            # 删除物理文件
            file_path.unlink()
            
            # 删除数据库记录
            ModuleFile.objects.filter(relative_path=relative_path).delete()
            
            return True, f"文件删除成功: {relative_path}"
        except Exception as e:
            return False, f"删除失败: {str(e)}"
    
    def _calculate_file_hash(self, file_path: Path) -> str:
        """计算文件SHA256哈希值"""
        try:
            with open(file_path, 'rb') as f:
                return hashlib.sha256(f.read()).hexdigest()
        except:
            return ""
    
    def _update_file_record(self, relative_path: str, user: User):
        """更新或创建文件数据库记录"""
        file_path = self.workpieces_dir / relative_path
        
        if not file_path.exists():
            return
        
        stat = file_path.stat()
        content_hash = self._calculate_file_hash(file_path)
        
        # 更新或创建记录
        obj, created = ModuleFile.objects.update_or_create(
            relative_path=relative_path,
            defaults={
                'name': file_path.name,
                'size': stat.st_size,
                'content_hash': content_hash,
                'uploaded_by': user,
            }
        )
        
        return obj
    
    def _create_file_record(self, relative_path: str, user: User):
        """创建文件数据库记录"""
        return self._update_file_record(relative_path, user)
    
    def get_directory_structure(self) -> List[Dict[str, Any]]:
        """
        获取目录结构（用于上传文件时选择目录）
        
        Returns:
            List[Dict]: 目录信息列表
        """
        directories = set()
        
        # 添加根目录
        directories.add(".")
        
        # 扫描所有子目录
        if self.workpieces_dir.exists():
            for item in self.workpieces_dir.rglob("*"):
                if item.is_dir():
                    rel_path = item.relative_to(self.workpieces_dir)
                    
                    # 忽略__pycache__目录
                    if '__pycache__' in rel_path.parts:
                        continue
                    
                    directories.add(str(rel_path))
        
        # 转换为列表并排序
        dir_list = []
        for dir_path in sorted(directories):
            depth = len(Path(dir_path).parts) if dir_path != "." else 0
            display_name = "根目录" if dir_path == "." else dir_path
            
            dir_list.append({
                'path': dir_path,
                'display_name': display_name,
                'depth': depth
            })
        
        return dir_list
    
    def update_file_status(self, relative_path: str, new_status: str, user) -> Tuple[bool, str]:
        """
        更新文件状态
        
        Args:
            relative_path: 文件相对路径
            new_status: 新状态 (unreviewed, available, unavailable)
            user: 操作用户
            
        Returns:
            Tuple[bool, str]: (成功标志, 消息)
        """
        try:
            # 验证状态值
            from .models import FileStatus
            if new_status not in [choice[0] for choice in FileStatus.choices]:
                return False, "无效的状态值"
                
            # 获取或创建模块文件记录
            module_file, created = ModuleFile.objects.get_or_create(
                relative_path=relative_path,
                defaults={
                    'name': Path(relative_path).name,
                    'size': 0,
                    'uploaded_by': user,
                    'status': new_status
                }
            )
            
            if not created:
                # 更新现有记录的状态
                module_file.update_status(new_status, user)
            
            status_display = module_file.get_status_display()
            return True, f"文件状态已更新为: {status_display}"
            
        except Exception as e:
            return False, f"更新状态失败: {str(e)}"


# 全局文件管理器实例
module_file_manager = ModuleFileManager()
