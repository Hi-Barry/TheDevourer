"""大嘴怪 — 知识库提问对话框

用户对知识库提问的输入界面。
支持快捷键呼出、流式显示回答。
"""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTextEdit, QPushButton,
    QLabel, QProgressBar, QWidget, QSizePolicy,
)
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QFont, QKeySequence, QShortcut


class QuestionDialog(QDialog):
    """知识库提问对话框"""

    # 信号
    question_submitted = Signal(str)           # 用户提交问题
    dialog_closed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("🔍 向大嘴怪提问")
        self.setMinimumSize(450, 350)
        self.setWindowFlags(
            Qt.WindowType.Dialog
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self._session_id: str = ""
        self._is_loading = False

        self._setup_ui()
        self._setup_shortcuts()

    # ── UI ────────────────────────────────────────

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(16, 16, 16, 16)

        # 提示标签
        hint = QLabel("💡 基于你的知识库提问，大嘴怪会从已投喂的内容中找答案")
        hint.setStyleSheet("color: #888; font-size: 12px;")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        # 问题输入框
        self.question_input = QTextEdit()
        self.question_input.setPlaceholderText("例如：我上周收藏的微服务文章讲了什么？")
        self.question_input.setMaximumHeight(80)
        self.question_input.setStyleSheet("""
            QTextEdit {
                border: 2px solid #ddd;
                border-radius: 8px;
                padding: 8px;
                font-size: 14px;
            }
            QTextEdit:focus {
                border-color: #4CAF50;
            }
        """)
        layout.addWidget(self.question_input)

        # 按钮行
        btn_layout = QHBoxLayout()

        self.ask_btn = QPushButton("🔍 提问")
        self.ask_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 20px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:disabled {
                background-color: #ccc;
            }
        """)
        self.ask_btn.clicked.connect(self._on_ask)
        btn_layout.addWidget(self.ask_btn)

        btn_layout.addStretch()

        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(self.close)
        btn_layout.addWidget(close_btn)

        layout.addLayout(btn_layout)

        # 加载指示器
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)  # 不确定进度
        self.progress.setMaximumHeight(4)
        self.progress.setTextVisible(False)
        self.progress.hide()
        layout.addWidget(self.progress)

        # 回答显示区
        self.answer_display = QTextEdit()
        self.answer_display.setReadOnly(True)
        self.answer_display.setStyleSheet("""
            QTextEdit {
                border: 1px solid #e0e0e0;
                border-radius: 8px;
                padding: 10px;
                font-size: 13px;
                background-color: #fafafa;
            }
        """)
        layout.addWidget(self.answer_display)

    def _setup_shortcuts(self) -> None:
        """快捷键"""
        # Enter 提交问题
        self._submit_shortcut = QShortcut(QKeySequence("Return"), self)
        self._submit_shortcut.activated.connect(self._on_ask)
        # Escape 关闭
        self._close_shortcut = QShortcut(QKeySequence("Escape"), self)
        self._close_shortcut.activated.connect(self.close)

    # ── 交互 ──────────────────────────────────────

    def _on_ask(self) -> None:
        """提交问题"""
        question = self.question_input.toPlainText().strip()
        if not question or self._is_loading:
            return

        self.question_submitted.emit(question)
        self.set_loading(True)

    def set_loading(self, loading: bool) -> None:
        self._is_loading = loading
        self.progress.setVisible(loading)
        self.ask_btn.setEnabled(not loading)
        self.question_input.setReadOnly(loading)

    # ── 流式显示回答 ──────────────────────────────

    def append_token(self, token: str) -> None:
        """流式追加 token"""
        cursor = self.answer_display.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        cursor.insertText(token)
        # 自动滚动到底部
        self.answer_display.ensureCursorVisible()

    def show_answer(self, text: str) -> None:
        """直接显示完整回答"""
        self.answer_display.setMarkdown(text)

    def clear_answer(self) -> None:
        """清除之前的回答"""
        self.answer_display.clear()

    # ── 窗口生命周期 ──────────────────────────────

    def showEvent(self, event) -> None:
        self.question_input.setFocus()
        self.clear_answer()
        super().showEvent(event)

    def closeEvent(self, event) -> None:
        self.dialog_closed.emit()
        super().closeEvent(event)
