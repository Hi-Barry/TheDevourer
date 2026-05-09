"""大嘴怪 — 投喂反馈气泡

功能气泡组件：QLabel 圆角白底，3 秒自动消失。
不依赖任何动画框架。
"""
from PySide6.QtWidgets import QLabel, QGraphicsOpacityEffect
from PySide6.QtCore import Qt, QTimer, QPoint, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QFont


BUBBLE_STYLE = """
    QLabel {
        background-color: rgba(255, 255, 255, 230);
        color: #333333;
        border: 1px solid #d0d0d0;
        border-radius: 12px;
        padding: 10px 16px;
        font-size: 14px;
    }
"""

BUBBLE_STYLE_ERROR = """
    QLabel {
        background-color: rgba(255, 240, 240, 240);
        color: #c0392b;
        border: 1px solid #e74c3c;
        border-radius: 12px;
        padding: 10px 16px;
        font-size: 14px;
    }
"""

BUBBLE_STYLE_SUCCESS = """
    QLabel {
        background-color: rgba(240, 255, 240, 240);
        color: #27ae60;
        border: 1px solid #2ecc71;
        border-radius: 12px;
        padding: 10px 16px;
        font-size: 14px;
    }
"""


class FeedBubble(QLabel):
    """投喂反馈气泡，显示在精灵窗口旁边，3 秒后自动消失"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setWordWrap(True)
        self.setMaximumWidth(300)
        self.hide()

        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self.fade_out)

        self._opacity_effect: QGraphicsOpacityEffect | None = None
        self._fade_anim: QPropertyAnimation | None = None

    # ── 显示气泡 ──────────────────────────────────

    def show_received(self, display_name: str) -> None:
        """投喂接收提示"""
        self.setText(f"📥 已收到：{display_name}")
        self.setStyleSheet(BUBBLE_STYLE)
        self._pop_near_pet()
        self._auto_hide(2500)

    def show_classified(self, category: str, tags: list[str] = None) -> None:
        """分类完成提示"""
        tag_str = f" #{' #'.join(tags)}" if tags else ""
        icon = self._category_icon(category)
        self.setText(f"{icon} 已归档 → {category}{tag_str}")
        self.setStyleSheet(BUBBLE_STYLE_SUCCESS)
        self._pop_near_pet()
        self._auto_hide(3000)

    def show_error(self, reason: str) -> None:
        """处理失败提示"""
        self.setText(f"❌ {reason}")
        self.setStyleSheet(BUBBLE_STYLE_ERROR)
        self._pop_near_pet()
        self._auto_hide(4000)

    def show_question_response(self, snippet: str) -> None:
        """LLM 回答（流式更新用）"""
        self.setText(snippet)
        self.setStyleSheet(BUBBLE_STYLE)
        self.setMinimumWidth(250)
        self.setMaximumWidth(400)
        self._pop_near_pet()
        self._cancel_hide()

    # ── 定位 ──────────────────────────────────────

    def _pop_near_pet(self) -> None:
        """定位在父窗口（精灵）右侧"""
        if self.parent():
            parent_pos = self.parent().pos()
            parent_size = self.parent().size()
            x = parent_pos.x() + parent_size.width() + 10
            y = parent_pos.y() + (parent_size.height() - self.sizeHint().height()) // 2
            self.move(QPoint(x, max(y, 0)))
        self.show()
        self.raise_()

    def _auto_hide(self, ms: int) -> None:
        """设置延迟隐藏"""
        self._cancel_hide()
        self._hide_timer.start(ms)

    def _cancel_hide(self) -> None:
        self._hide_timer.stop()

    # ── 淡出 ──────────────────────────────────────

    def fade_out(self) -> None:
        """淡出动画后隐藏"""
        if self._opacity_effect is None:
            self._opacity_effect = QGraphicsOpacityEffect(self)
            self.setGraphicsEffect(self._opacity_effect)

        self._opacity_effect.setOpacity(1.0)
        if self._fade_anim is None:
            self._fade_anim = QPropertyAnimation(self._opacity_effect, b"opacity")
            self._fade_anim.setDuration(300)
            self._fade_anim.setEasingCurve(QEasingCurve.Type.OutQuad)
            self._fade_anim.finished.connect(self._on_fade_done)

        self._fade_anim.setStartValue(1.0)
        self._fade_anim.setEndValue(0.0)
        self._fade_anim.start()

    def _on_fade_done(self) -> None:
        self.hide()

    # ── 工具 ──────────────────────────────────────

    @staticmethod
    def _category_icon(category: str) -> str:
        icons = {
            "网址": "🔗", "文档": "📄", "图片": "🖼️",
            "截图": "📷", "音视频": "🎬", "音频": "🎵",
            "视频": "🎬", "其他": "📦", "压缩包": "📦",
        }
        # 取第一级分类
        top_cat = category.split("/")[0] if "/" in category else category
        return icons.get(top_cat, "📌")
