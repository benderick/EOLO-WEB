from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.conf import settings
from pathlib import Path
import json


User = get_user_model()


class TemplateApiPermissionTests(TestCase):
	"""
	模板配置API权限测试：
	- 禁止写入 common 目录
	- 允许写入用户目录
	"""

	def setUp(self):
		self.user = User.objects.create_user(username="alice", password="pass123")
		self.client.force_login(self.user)
		# 确保基础目录存在
		settings.EOLO_MODEL_TEMPLATE_DIR.mkdir(parents=True, exist_ok=True)
		(settings.EOLO_MODEL_TEMPLATE_DIR / "common").mkdir(exist_ok=True)

	def test_cannot_write_common(self):
		url = reverse("models_manager:api_templates_file")
		resp = self.client.post(
			url,
			data=json.dumps({
				"path": "common/test.yaml",
				"content": "foo: 1\n"
			}),
			content_type="application/json",
		)
		self.assertEqual(resp.status_code, 200)
		data = resp.json()
		self.assertFalse(data["success"])  # 应失败

	def test_can_write_user_folder(self):
		url = reverse("models_manager:api_templates_file")
		path = f"{self.user.username}/my.yaml"
		resp = self.client.post(
			url,
			data=json.dumps({
				"path": path,
				"content": "bar: 2\n"
			}),
			content_type="application/json",
		)
		self.assertEqual(resp.status_code, 200)
		data = resp.json()
		self.assertTrue(data["success"])  # 应成功
		# 文件应实际写入
		abs_file = settings.EOLO_MODEL_TEMPLATE_DIR / path
		self.assertTrue(abs_file.exists())
		self.assertIn("bar: 2", abs_file.read_text(encoding="utf-8"))


class AbsolutePathSupportTests(TestCase):
	"""验证文件内容API支持位于允许根目录内的绝对路径参数"""

	def setUp(self):
		self.user = User.objects.create_user(username="bob", password="pass123")
		self.client.force_login(self.user)
		# 准备模型与模板根目录
		settings.EOLO_MODEL_CONFIGS_DIR.mkdir(parents=True, exist_ok=True)
		settings.EOLO_MODEL_TEMPLATE_DIR.mkdir(parents=True, exist_ok=True)
		# 写入各自用户目录文件
		(settings.EOLO_MODEL_CONFIGS_DIR / self.user.username).mkdir(exist_ok=True)
		(settings.EOLO_MODEL_TEMPLATE_DIR / self.user.username).mkdir(exist_ok=True)
		self.abs_model_file = settings.EOLO_MODEL_CONFIGS_DIR / self.user.username / "m.yaml"
		self.abs_model_file.write_text("m: 1\n", encoding="utf-8")
		self.abs_tpl_file = settings.EOLO_MODEL_TEMPLATE_DIR / self.user.username / "t.yaml"
		self.abs_tpl_file.write_text("t: 2\n", encoding="utf-8")

	def test_model_file_get_by_absolute_path(self):
		url = reverse("models_manager:api_file")
		resp = self.client.get(url, {"path": str(self.abs_model_file)})
		self.assertEqual(resp.status_code, 200)
		data = resp.json()
		self.assertTrue(data["success"])  # 能读取
		self.assertIn("m: 1", data["data"]["content"])  # 内容正确

	def test_template_file_get_by_absolute_path(self):
		url = reverse("models_manager:api_templates_file")
		resp = self.client.get(url, {"path": str(self.abs_tpl_file)})
		self.assertEqual(resp.status_code, 200)
		data = resp.json()
		self.assertTrue(data["success"])  # 能读取
		self.assertIn("t: 2", data["data"]["content"])  # 内容正确
