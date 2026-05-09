"""大嘴怪 — 设置对话框"""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLineEdit, QComboBox, QCheckBox, QPushButton,
    QGroupBox, QFileDialog, QLabel, QTabWidget, QWidget,
)
from PySide6.QtCore import Qt, Signal

from core.config import get_config


class SettingsDialog(QDialog):
    """应用设置对话框"""

    settings_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.config = get_config()
        self.setWindowTitle("⚙️ 大嘴怪设置")
        self.setMinimumWidth(500)

        self._setup_ui()
        self._load_values()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        tabs = QTabWidget()

        # 标签页 1：常规
        tab_general = QWidget()
        form_general = QFormLayout(tab_general)

        # 仓库路径
        path_layout = QHBoxLayout()
        self.repo_path_edit = QLineEdit()
        self.repo_path_edit.setReadOnly(True)
        path_layout.addWidget(self.repo_path_edit)
        browse_btn = QPushButton("浏览...")
        browse_btn.clicked.connect(self._browse_repo)
        path_layout.addWidget(browse_btn)
        form_general.addRow("仓库路径：", path_layout)

        # 开机启动
        self.autostart_check = QCheckBox("开机自动启动")
        form_general.addRow("", self.autostart_check)

        # 关闭到托盘
        self.tray_check = QCheckBox("关闭时最小化到系统托盘")
        form_general.addRow("", self.tray_check)

        # 剪贴板监听
        self.clipboard_check = QCheckBox("启用剪贴板监听")
        form_general.addRow("", self.clipboard_check)

        # 投喂后自动索引
        self.auto_index_check = QCheckBox("投喂后自动索引到知识库")
        form_general.addRow("", self.auto_index_check)

        # 文件监听
        self.watchdog_check = QCheckBox("启用仓库文件实时监听")
        form_general.addRow("", self.watchdog_check)

        tabs.addTab(tab_general, "📋 常规")

        # 标签页 2：LLM
        tab_llm = QWidget()
        form_llm = QFormLayout(tab_llm)

        self.llm_backend_combo = QComboBox()
        self.llm_backend_combo.addItems(["ollama", "openai_compatible"])
        self.llm_backend_combo.currentTextChanged.connect(self._on_llm_backend_changed)
        form_llm.addRow("LLM 后端：", self.llm_backend_combo)

        # Ollama 设置
        self.ollama_group = QGroupBox("Ollama 本地设置")
        ollama_form = QFormLayout(self.ollama_group)
        self.ollama_endpoint_edit = QLineEdit()
        ollama_form.addRow("端点地址：", self.ollama_endpoint_edit)
        self.ollama_model_edit = QLineEdit()
        ollama_form.addRow("模型名：", self.ollama_model_edit)
        form_llm.addRow(self.ollama_group)

        # API 设置
        self.api_group = QGroupBox("API 远程设置")
        api_form = QFormLayout(self.api_group)
        self.api_endpoint_edit = QLineEdit()
        api_form.addRow("API 地址：", self.api_endpoint_edit)
        self.api_key_edit = QLineEdit()
        self.api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        api_form.addRow("API Key：", self.api_key_edit)
        self.api_model_edit = QLineEdit()
        api_form.addRow("模型名：", self.api_model_edit)
        form_llm.addRow(self.api_group)

        # 嵌入设置
        embed_group = QGroupBox("嵌入模型")
        embed_form = QFormLayout(embed_group)
        self.embed_model_edit = QLineEdit()
        embed_form.addRow("模型名：", self.embed_model_edit)
        self.embed_device_combo = QComboBox()
        self.embed_device_combo.addItems(["cpu", "cuda"])
        embed_form.addRow("设备：", self.embed_device_combo)
        form_llm.addRow(embed_group)

        tabs.addTab(tab_llm, "🤖 LLM")

        # 标签页 3：关于
        tab_about = QWidget()
        about_layout = QVBoxLayout(tab_about)
        about_text = QLabel(
            "🦖 大嘴怪 v1.0.0\n\n"
            "桌面知识管家 — 投喂即知识\n\n"
            "🚀 技术栈：Python + PySide6\n"
            "📚 知识库：ChromaDB + FTS5\n"
            "🧠 LLM：Ollama / OpenAI 兼容 API\n\n"
            "拖拽投喂文件/网址/截图 → 自动分类 → 知识库问答"
        )
        about_text.setWordWrap(True)
        about_text.setStyleSheet("padding: 20px; line-height: 1.6;")
        about_layout.addWidget(about_text)
        about_layout.addStretch()
        tabs.addTab(tab_about, "ℹ️ 关于")

        layout.addWidget(tabs)

        # 按钮
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        save_btn = QPushButton("💾 保存")
        save_btn.setStyleSheet("font-weight: bold; padding: 8px 20px;")
        save_btn.clicked.connect(self._save)
        btn_layout.addWidget(save_btn)

        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.close)
        btn_layout.addWidget(cancel_btn)

        layout.addLayout(btn_layout)

    # ── 加载/保存 ─────────────────────────────────

    def _load_values(self) -> None:
        """从配置加载当前值"""
        c = self.config
        self.repo_path_edit.setText(c.repo_path)
        self.autostart_check.setChecked(c.autostart)
        self.tray_check.setChecked(c.get("minimize_to_tray", True))
        self.clipboard_check.setChecked(c.clipboard_monitor)
        self.auto_index_check.setChecked(c.auto_index)
        self.watchdog_check.setChecked(c.watchdog_enabled)

        self.llm_backend_combo.setCurrentText(c.llm_backend)
        self.ollama_endpoint_edit.setText(c.ollama_endpoint)
        self.ollama_model_edit.setText(c.ollama_model)
        self.api_endpoint_edit.setText(c.api_endpoint)
        self.api_key_edit.setText(c.api_key)
        self.api_model_edit.setText(c.api_model)
        self.embed_model_edit.setText(c.embedding_model)
        self.embed_device_combo.setCurrentText(c.embedding_device)

        self._on_llm_backend_changed(c.llm_backend)

    def _save(self) -> None:
        """保存到配置"""
        c = self.config
        c.repo_path = self.repo_path_edit.text()

        c.autostart = self.autostart_check.isChecked()
        c.set("minimize_to_tray", self.tray_check.isChecked())
        c.set("clipboard_monitor", self.clipboard_check.isChecked())
        c.set("auto_index", self.auto_index_check.isChecked())
        c.set("watchdog_enabled", self.watchdog_check.isChecked())

        c.llm_backend = self.llm_backend_combo.currentText()
        c.set("ollama_endpoint", self.ollama_endpoint_edit.text())
        c.set("ollama_model", self.ollama_model_edit.text())
        c.set("api_endpoint", self.api_endpoint_edit.text())
        c.api_key = self.api_key_edit.text()
        c.set("api_model", self.api_model_edit.text())
        c.set("embedding_model", self.embed_model_edit.text())
        c.set("embedding_device", self.embed_device_combo.currentText())

        # 开机启动
        self._set_autostart(self.autostart_check.isChecked())

        c.ensure_paths()
        self.settings_changed.emit()
        self.accept()

    # ── 交互 ──────────────────────────────────────

    def _browse_repo(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "选择仓库目录", self.repo_path_edit.text())
        if path:
            self.repo_path_edit.setText(path)

    def _on_llm_backend_changed(self, backend: str) -> None:
        is_ollama = backend == "ollama"
        self.ollama_group.setVisible(is_ollama)
        self.api_group.setVisible(not is_ollama)

    # ── 开机启动 ─────────────────────────────────

    def _set_autostart(self, enable: bool) -> None:
        """写入/删除 Windows 注册表 Run 键"""
        try:
            import sys
            if sys.platform != "win32":
                return  # 非 Windows 跳过

            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Run",
                0, winreg.KEY_SET_VALUE
            )

            if enable:
                exe_path = sys.executable
                if "python" in exe_path.lower():
                    main_path = str(__import__("pathlib").Path(__file__).resolve().parent.parent / "main.py")
                    cmd = f'"{exe_path}" "{main_path}"'
                else:
                    cmd = f'"{exe_path}"'
                winreg.SetValueEx(key, "大嘴怪", 0, winreg.REG_SZ, cmd)
            else:
                try:
                    winreg.DeleteValue(key, "大嘴怪")
                except FileNotFoundError:
                    pass

            winreg.CloseKey(key)
        except Exception:
            pass  # 非 Windows 环境忽略
