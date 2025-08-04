"""
Python模块分析工具
用于解析Python文件中的__all__字段和提取模块信息
"""
import ast
import re
from pathlib import Path
from typing import List, Dict, Optional, Tuple


class ModuleAnalyzer:
    """Python模块分析器"""
    
    def __init__(self):
        pass
    
    def extract_all_items(self, file_path: Path) -> List[str]:
        """
        从Python文件中提取__all__字段的内容
        
        Args:
            file_path: Python文件路径
            
        Returns:
            __all__字段中的模块名列表
        """
        try:
            content = file_path.read_text(encoding='utf-8')
            return self._parse_all_from_content(content)
        except Exception as e:
            print(f"解析文件 {file_path} 失败: {str(e)}")
            return []
    
    def _parse_all_from_content(self, content: str) -> List[str]:
        """
        从文件内容中解析__all__字段
        
        Args:
            content: Python文件内容
            
        Returns:
            __all__字段中的模块名列表
        """
        try:
            # 方法1: 使用AST解析（更准确）
            tree = ast.parse(content)
            all_items = self._extract_all_from_ast(tree)
            if all_items:
                return all_items
        except (SyntaxError, ValueError) as e:
            print(f"AST解析失败，尝试正则表达式: {str(e)}")
        
        # 方法2: 使用正则表达式（备用方案）
        return self._extract_all_from_regex(content)
    
    def _extract_all_from_ast(self, tree: ast.AST) -> List[str]:
        """
        使用AST从语法树中提取__all__字段
        
        Args:
            tree: AST语法树
            
        Returns:
            __all__字段中的模块名列表
        """
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                # 检查是否是__all__赋值
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == '__all__':
                        # 解析赋值的值
                        return self._parse_list_value(node.value)
        return []
    
    def _parse_list_value(self, value_node: ast.AST) -> List[str]:
        """
        解析AST中的列表值
        
        Args:
            value_node: AST值节点
            
        Returns:
            字符串列表
        """
        if isinstance(value_node, ast.List):
            items = []
            for elt in value_node.elts:
                if isinstance(elt, ast.Str):  # Python < 3.8
                    items.append(elt.s)
                elif isinstance(elt, ast.Constant) and isinstance(elt.value, str):  # Python >= 3.8
                    items.append(elt.value)
            return items
        elif isinstance(value_node, ast.Tuple):
            items = []
            for elt in value_node.elts:
                if isinstance(elt, ast.Str):  # Python < 3.8
                    items.append(elt.s)
                elif isinstance(elt, ast.Constant) and isinstance(elt.value, str):  # Python >= 3.8
                    items.append(elt.value)
            return items
        return []
    
    def _extract_all_from_regex(self, content: str) -> List[str]:
        """
        使用正则表达式提取__all__字段（备用方案）
        
        Args:
            content: Python文件内容
            
        Returns:
            __all__字段中的模块名列表
        """
        # 匹配__all__ = [...]格式
        pattern = r'__all__\s*=\s*\[(.*?)\]'
        match = re.search(pattern, content, re.DOTALL)
        if match:
            all_content = match.group(1)
            # 提取引号中的字符串
            items = re.findall(r'["\']([^"\']+)["\']', all_content)
            return items
        
        # 匹配__all__ = (...)格式
        pattern = r'__all__\s*=\s*\((.*?)\)'
        match = re.search(pattern, content, re.DOTALL)
        if match:
            all_content = match.group(1)
            # 提取引号中的字符串
            items = re.findall(r'["\']([^"\']+)["\']', all_content)
            return items
        
        return []
    
    def analyze_module_file(self, file_path: Path) -> Dict:
        """
        分析Python模块文件，提取详细信息
        
        Args:
            file_path: Python文件路径
            
        Returns:
            模块分析结果字典
        """
        result = {
            'file_path': str(file_path),
            'file_name': file_path.name,
            'all_items': [],
            'has_all': False,
            'classes': [],
            'functions': [],
            'imports': [],
            'docstring': '',
            'encoding': 'utf-8'
        }
        
        try:
            content = file_path.read_text(encoding='utf-8')
            result['all_items'] = self._parse_all_from_content(content)
            result['has_all'] = len(result['all_items']) > 0
            
            # 解析其他信息
            try:
                tree = ast.parse(content)
                result.update(self._extract_additional_info(tree))
            except (SyntaxError, ValueError):
                pass
                
        except Exception as e:
            print(f"分析文件 {file_path} 失败: {str(e)}")
        
        return result
    
    def _extract_additional_info(self, tree: ast.AST) -> Dict:
        """
        从AST中提取额外的模块信息
        
        Args:
            tree: AST语法树
            
        Returns:
            包含类、函数、导入等信息的字典
        """
        info = {
            'classes': [],
            'functions': [],
            'imports': [],
            'docstring': ''
        }
        
        # 提取模块文档字符串
        if (isinstance(tree, ast.Module) and tree.body and 
            isinstance(tree.body[0], ast.Expr) and 
            isinstance(tree.body[0].value, (ast.Str, ast.Constant))):
            
            docstring_node = tree.body[0].value
            if isinstance(docstring_node, ast.Str):
                info['docstring'] = docstring_node.s
            elif isinstance(docstring_node, ast.Constant) and isinstance(docstring_node.value, str):
                info['docstring'] = docstring_node.value
        
        # 遍历所有节点
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                info['classes'].append(node.name)
            elif isinstance(node, ast.FunctionDef):
                info['functions'].append(node.name)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    info['imports'].append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ''
                for alias in node.names:
                    import_name = f"{module}.{alias.name}" if module else alias.name
                    info['imports'].append(import_name)
        
        return info
    
    def scan_modules_in_directory(self, directory: Path) -> List[Dict]:
        """
        扫描目录中的所有Python模块
        
        Args:
            directory: 要扫描的目录路径
            
        Returns:
            模块分析结果列表
        """
        modules = []
        
        if not directory.exists() or not directory.is_dir():
            return modules
        
        # 递归扫描所有.py文件
        for py_file in directory.rglob("*.py"):
            # 跳过__pycache__目录和__init__.py文件
            if '__pycache__' in str(py_file) or py_file.name == '__init__.py':
                continue
            
            module_info = self.analyze_module_file(py_file)
            if module_info['has_all']:  # 只包含有__all__字段的文件
                modules.append(module_info)
        
        return modules


# 创建全局分析器实例
module_analyzer = ModuleAnalyzer()
