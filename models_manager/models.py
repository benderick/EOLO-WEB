"""
模型管理器 - 管理EOLO配置文件
"""
import os
import json
from pathlib import Path
from typing import Dict, List, Optional
from django.conf import settings
from django.contrib.auth import get_user_model

User = get_user_model()


class SettingFileManager:
    """
    参数配置文件管理器
    管理EOLO/configs/setting下的文件和文件夹
    """
    
    def __init__(self):
        # EOLO配置参数路径 - 使用配置化路径
        self.base_path = settings.EOLO_SETTING_CONFIGS_DIR
        self.default_path = self.base_path / "default"
        
    def get_user_setting_path(self, username: str) -> Path:
        """
        获取用户专用的参数配置路径
        
        Args:
            username: 用户名
            
        Returns:
            Path: 用户参数配置路径
        """
        return self.base_path / username
    
    def ensure_user_folder(self, username: str) -> Path:
        """
        确保用户文件夹存在，不存在则创建
        
        Args:
            username: 用户名
            
        Returns:
            Path: 用户文件夹路径
        """
        user_path = self.get_user_setting_path(username)
        user_path.mkdir(exist_ok=True)
        
        # 创建用户README文件
        readme_path = user_path / "README.md"
        if not readme_path.exists():
            readme_content = f"""# {username} 的参数配置

这个文件夹包含用户 {username} 的个人参数配置文件。

## 使用说明

1. 您可以在这里存储个人的参数配置文件
2. 支持的文件格式：.yaml, .yml, .json, .txt, .md
3. 可以创建子文件夹来组织不同类型的配置

## 配置文件类型

- **训练参数**: 学习率、批次大小、训练轮数等
- **模型参数**: 网络结构、损失函数等参数
- **数据参数**: 数据增强、预处理参数
- **其他配置**: 自定义的其他参数配置

创建时间: {Path().cwd().stat().st_mtime}
"""
            readme_path.write_text(readme_content, encoding='utf-8')
        
        return user_path
    
    def get_directory_tree(self, path: Path) -> Dict:
        """
        获取目录树结构
        
        Args:
            path: 目录路径
            
        Returns:
            Dict: 目录树结构
        """
        if not path.exists():
            return {"name": path.name, "path": str(path), "is_file": False, "children": []}
        
        result = {
            "name": path.name,
            "path": str(path.relative_to(self.base_path)),
            "is_file": path.is_file(),
            "children": []
        }
        
        if path.is_file():
            result["size"] = path.stat().st_size
            return result
        
        # 获取文件夹内容
        try:
            items = sorted(path.iterdir(), key=lambda x: (x.is_file(), x.name.lower()))
            for item in items:
                if item.name.startswith('.'):
                    continue
                result["children"].append(self.get_directory_tree(item))
        except PermissionError:
            pass
        
        return result
    
    def get_file_content(self, relative_path: str) -> str:
        """
        获取文件内容
        
        Args:
            relative_path: 相对路径
            
        Returns:
            str: 文件内容
        """
        file_path = self.base_path / relative_path
        
        if not file_path.exists():
            raise FileNotFoundError(f"文件不存在: {relative_path}")
        
        if not file_path.is_file():
            raise ValueError(f"路径不是文件: {relative_path}")
        
        # 安全检查：确保文件在允许的目录内
        try:
            file_path.resolve().relative_to(self.base_path.resolve())
        except ValueError:
            raise PermissionError("不允许访问此路径")
        
        try:
            return file_path.read_text(encoding='utf-8')
        except UnicodeDecodeError:
            # 尝试其他编码
            try:
                return file_path.read_text(encoding='gbk')
            except UnicodeDecodeError:
                return file_path.read_text(encoding='latin-1')
    
    def save_file_content(self, relative_path: str, content: str, username: str) -> bool:
        """
        保存文件内容
        
        Args:
            relative_path: 相对路径
            content: 文件内容
            username: 用户名
            
        Returns:
            bool: 保存是否成功
        """
        file_path = self.base_path / relative_path
        
        # 安全检查：确保文件在允许的目录内
        try:
            file_path.resolve().relative_to(self.base_path.resolve())
        except ValueError:
            raise PermissionError("不允许访问此路径")
        
        # 权限检查：只有default文件夹允许写入，或用户自己的文件夹
        if not (relative_path.startswith(username + '/') or relative_path.startswith('default/')):
            raise PermissionError("没有权限修改此文件")
        
        # 确保目录存在
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            file_path.write_text(content, encoding='utf-8')
            return True
        except Exception:
            return False
    
    def create_file(self, parent_path: str, file_name: str, content: str, username: str) -> str:
        """
        创建新文件
        
        Args:
            parent_path: 父目录路径
            file_name: 文件名
            content: 文件内容
            username: 用户名
            
        Returns:
            str: 新文件的相对路径
        """
        if parent_path:
            file_path = self.base_path / parent_path / file_name
            relative_path = f"{parent_path}/{file_name}"
        else:
            # 默认创建在用户文件夹中
            user_folder = self.ensure_user_folder(username)
            file_path = user_folder / file_name
            relative_path = f"{username}/{file_name}"
        
        # 权限检查
        if not (relative_path.startswith(username + '/') or relative_path.startswith('default/')):
            raise PermissionError("没有权限在此位置创建文件")
        
        if file_path.exists():
            raise FileExistsError("文件已存在")
        
        # 确保目录存在
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            file_path.write_text(content, encoding='utf-8')
            return relative_path
        except Exception as e:
            raise RuntimeError(f"创建文件失败: {str(e)}")
    
    def delete_file_or_folder(self, relative_path: str, username: str) -> bool:
        """
        删除文件或文件夹
        
        Args:
            relative_path: 相对路径
            username: 用户名
            
        Returns:
            bool: 删除是否成功
        """
        file_path = self.base_path / relative_path
        
        # 安全检查
        try:
            file_path.resolve().relative_to(self.base_path.resolve())
        except ValueError:
            raise PermissionError("不允许访问此路径")
        
        # 权限检查：只能删除用户自己的文件
        if not relative_path.startswith(username + '/'):
            raise PermissionError("没有权限删除此文件")
        
        if not file_path.exists():
            raise FileNotFoundError("文件或文件夹不存在")
        
        try:
            if file_path.is_file():
                file_path.unlink()
            else:
                import shutil
                shutil.rmtree(file_path)
            return True
        except Exception:
            return False
    
    def create_folder(self, parent_path: str, folder_name: str, username: str) -> str:
        """
        创建新文件夹
        
        Args:
            parent_path: 父目录路径
            folder_name: 文件夹名
            username: 用户名
            
        Returns:
            str: 新文件夹的相对路径
        """
        if parent_path:
            folder_path = self.base_path / parent_path / folder_name
            relative_path = f"{parent_path}/{folder_name}"
        else:
            user_folder = self.ensure_user_folder(username)
            folder_path = user_folder / folder_name
            relative_path = f"{username}/{folder_name}"
        
        # 权限检查
        if not (relative_path.startswith(username + '/') or relative_path.startswith('default/')):
            raise PermissionError("没有权限在此位置创建文件夹")
        
        if folder_path.exists():
            raise FileExistsError("文件夹已存在")
        
        try:
            folder_path.mkdir(parents=True, exist_ok=True)
            return relative_path
        except Exception as e:
            raise RuntimeError(f"创建文件夹失败: {str(e)}")


class ModelFileManager:
    """
    模型文件管理器
    管理EOLO/configs/model下的文件和文件夹
    """
    
    def __init__(self):
        # EOLO配置模型路径 - 使用配置化路径
        self.base_path = settings.EOLO_MODEL_CONFIGS_DIR
        self.common_path = self.base_path / "common"
        
    def get_user_model_path(self, username: str) -> Path:
        """
        获取用户专用的模型配置路径
        
        Args:
            username: 用户名
            
        Returns:
            Path: 用户模型配置路径
        """
        return self.base_path / username
    
    def ensure_user_folder(self, username: str) -> Path:
        """
        确保用户文件夹存在，不存在则创建
        
        Args:
            username: 用户名
            
        Returns:
            Path: 用户文件夹路径
        """
        user_path = self.get_user_model_path(username)
        user_path.mkdir(exist_ok=True)
        
        # 创建用户README文件
        readme_path = user_path / "README.md"
        if not readme_path.exists():
            readme_content = f"""# {username} 的模型配置

这是 {username} 的个人模型配置文件夹。

## 使用说明

在这里您可以存放：
- 个人定制的模型配置文件
- 实验特定的配置
- 训练参数调优文件

## 注意事项

- 配置文件应使用YAML格式
- 建议使用有意义的文件名
- 可以创建子文件夹来组织配置
"""
            with open(readme_path, 'w', encoding='utf-8') as f:
                f.write(readme_content)
        
        return user_path
    
    def get_directory_tree(self, path: Path, max_depth: int = 5, current_depth: int = 0) -> Dict:
        """
        获取目录树结构
        
        Args:
            path: 目录路径
            max_depth: 最大深度
            current_depth: 当前深度
            
        Returns:
            Dict: 目录树结构
        """
        if not path.exists() or current_depth >= max_depth:
            return {}
        
        tree = {
            'name': path.name,
            'path': str(path.relative_to(self.base_path)),
            'is_file': path.is_file(),
            'size': path.stat().st_size if path.is_file() else 0,
            'modified': path.stat().st_mtime,
            'children': []
        }
        
        if path.is_dir():
            try:
                # 获取子项并排序（文件夹在前，文件在后）
                items = list(path.iterdir())
                items.sort(key=lambda x: (x.is_file(), x.name.lower()))
                
                for item in items:
                    # 跳过隐藏文件和临时文件
                    if item.name.startswith('.') or item.name.endswith('.tmp'):
                        continue
                    
                    child_tree = self.get_directory_tree(item, max_depth, current_depth + 1)
                    if child_tree:
                        tree['children'].append(child_tree)
                        
            except PermissionError:
                pass
        
        return tree
    
    def get_file_content(self, relative_path: str) -> Optional[str]:
        """
        获取文件内容
        
        Args:
            relative_path: 相对于model目录的路径
            
        Returns:
            str: 文件内容，如果失败返回None
        """
        try:
            file_path = self.base_path / relative_path
            
            # 安全检查：确保文件在允许的目录内
            if not str(file_path.resolve()).startswith(str(self.base_path.resolve())):
                return None
            
            if not file_path.exists() or not file_path.is_file():
                return None
            
            # 检查文件大小（限制为1MB）
            if file_path.stat().st_size > 1024 * 1024:
                return "文件过大，无法显示（超过1MB）"
            
            # 检查是否为文本文件
            if not self.is_text_file(file_path):
                return "这不是一个文本文件，无法显示内容"
            
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
                
        except UnicodeDecodeError:
            try:
                # 尝试其他编码
                with open(file_path, 'r', encoding='gbk') as f:
                    return f.read()
            except:
                return "文件编码不支持，无法显示"
        except Exception as e:
            return f"读取文件时出错: {str(e)}"
    
    def is_text_file(self, file_path: Path) -> bool:
        """
        判断是否为文本文件
        
        Args:
            file_path: 文件路径
            
        Returns:
            bool: 是否为文本文件
        """
        # 常见文本文件扩展名
        text_extensions = {
            '.yaml', '.yml', '.json', '.txt', '.md', '.py', 
            '.js', '.html', '.css', '.xml', '.cfg', '.conf',
            '.ini', '.log', '.sh', '.bat'
        }
        
        return file_path.suffix.lower() in text_extensions
    
    def save_file_content(self, relative_path: str, content: str, username: str) -> tuple[bool, str]:
        """
        保存文件内容
        
        Args:
            relative_path: 相对路径
            content: 文件内容
            username: 用户名（用于权限检查）
            
        Returns:
            tuple: (成功与否, 消息)
        """
        try:
            file_path = self.base_path / relative_path
            
            # 安全检查
            if not str(file_path.resolve()).startswith(str(self.base_path.resolve())):
                return False, "无效的文件路径"
            
            # 权限检查：只能编辑自己的文件夹或common文件夹
            relative_parts = Path(relative_path).parts
            if len(relative_parts) > 0:
                first_part = relative_parts[0]
                if first_part != 'common' and first_part != username:
                    return False, "没有权限编辑此文件"
            
            # 确保目录存在
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            # 保存文件
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            return True, "文件保存成功"
            
        except Exception as e:
            return False, f"保存文件时出错: {str(e)}"
    
    def delete_file(self, relative_path: str, username: str) -> tuple[bool, str]:
        """
        删除文件
        
        Args:
            relative_path: 相对路径
            username: 用户名（用于权限检查）
            
        Returns:
            tuple: (成功与否, 消息)
        """
        try:
            file_path = self.base_path / relative_path
            
            # 安全检查
            if not str(file_path.resolve()).startswith(str(self.base_path.resolve())):
                return False, "无效的文件路径"
            
            # 权限检查：只能删除自己的文件夹中的文件
            relative_parts = Path(relative_path).parts
            if len(relative_parts) > 0:
                first_part = relative_parts[0]
                if first_part != username:
                    return False, "只能删除自己文件夹中的文件"
            
            if not file_path.exists():
                return False, "文件不存在"
            
            if file_path.is_file():
                file_path.unlink()
                return True, "文件删除成功"
            elif file_path.is_dir():
                # 删除空文件夹
                try:
                    file_path.rmdir()
                    return True, "文件夹删除成功"
                except OSError:
                    return False, "文件夹不为空，无法删除"
            
        except Exception as e:
            return False, f"删除文件时出错: {str(e)}"
    
    def create_folder(self, relative_path: str, folder_name: str, username: str) -> tuple[bool, str]:
        """
        创建文件夹
        
        Args:
            relative_path: 父文件夹相对路径
            folder_name: 新文件夹名称
            username: 用户名（用于权限检查）
            
        Returns:
            tuple: (成功与否, 消息)
        """
        try:
            parent_path = self.base_path / relative_path
            new_folder_path = parent_path / folder_name
            
            # 安全检查
            if not str(new_folder_path.resolve()).startswith(str(self.base_path.resolve())):
                return False, "无效的文件夹路径"
            
            # 权限检查
            relative_parts = Path(relative_path).parts if relative_path else []
            if len(relative_parts) > 0:
                first_part = relative_parts[0]
                if first_part != username:
                    return False, "只能在自己的文件夹中创建子文件夹"
            elif relative_path == "" or relative_path == username:
                # 在用户根目录创建是允许的
                pass
            else:
                return False, "无权在此位置创建文件夹"
            
            if new_folder_path.exists():
                return False, "文件夹已存在"
            
            new_folder_path.mkdir(parents=True)
            return True, "文件夹创建成功"
            
        except Exception as e:
            return False, f"创建文件夹时出错: {str(e)}"


# 全局实例
model_file_manager = ModelFileManager()
setting_file_manager = SettingFileManager()
