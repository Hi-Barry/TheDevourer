"""大嘴怪 — 桌面精灵悬浮窗

透明无边框置顶窗口，显示精灵形象，支持拖拽移动、文件投喂和右键菜单。
"""
from pathlib import Path

from PySide6.QtWidgets import QWidget, QLabel, QMenu, QApplication
from PySide6.QtCore import Qt, QPoint, QTimer, Signal
from PySide6.QtGui import (
    QPixmap, QAction, QMouseEvent,
    QDragEnterEvent, QDropEvent,
)

from core.config import get_config
from core.feed_handler import (
    FeedItem, FeedSourceType, FeedQueueWorker,
    parse_mime_data, fetch_url_title,
)
from ui.feed_bubble import FeedBubble
from ui.sprite_animator import SpriteAnimator

# 精灵图片路径
PET_IMAGE = Path(__file__).resolve().parent.parent / "resources" / "pet_idle.png"
PET_SIZE = 200


class PetWindow(QWidget):
    """透明无边框悬浮精灵窗口 — 含投喂入口"""

    # 信号
    settings_requested = Signal()
    about_requested = Signal()
    question_requested = Signal()      # 打开提问对话框
    browser_requested = Signal()       # 打开内容浏览器
    closed = Signal()
    # 投喂信号
    feed_received = Signal(object)      # FeedItem
    feed_started = Signal(object)       # FeedItem — 开始处理
    feed_done = Signal(object, bool, str)  # FeedItem, success, message

    def __init__(self, feed_queue: FeedQueueWorker = None, parent=None):
        super().__init__(parent)

        self.config = get_config()
        self._drag_pos: QPoint | None = None
        self._feed_queue = feed_queue or FeedQueueWorker(self)

        self._setup_window()
        self._setup_ui()
        self._setup_menu()
        self._setup_drag_drop()
        self._setup_clipboard()
        self._connect_feed_queue()
        self._bubble = FeedBubble(self)
        self._animator = SpriteAnimator(self)
        self._animator.frame_changed.connect(self._on_frame)
        self._animator.play("idle")
        self._restore_position()

    # ── 窗口属性 ──────────────────────────────────
    def _setup_window(self) -> None:
        flags = (
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.NoDropShadowWindowHint
        )
        self.setWindowFlags(flags)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)
        self.setFixedSize(PET_SIZE, PET_SIZE)
        self.setWindowTitle("大嘴怪")

    # ── 精灵图片 ──────────────────────────────────
    def _setup_ui(self) -> None:
        self.pet_label = QLabel(self)
        self.pet_label.setFixedSize(PET_SIZE, PET_SIZE)
        self.pet_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if PET_IMAGE.exists():
            pixmap = QPixmap(str(PET_IMAGE))
            scaled = pixmap.scaled(
                PET_SIZE, PET_SIZE,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self.pet_label.setPixmap(scaled)
        else:
            self.pet_label.setText("🦖")
            self.pet_label.setStyleSheet("font-size: 80px;")

    # ── 右键菜单 ──────────────────────────────────
    def _setup_menu(self) -> None:
        self._menu = QMenu(self)

        action_feed_clipboard = QAction("投喂剪贴板", self)
        action_feed_clipboard.triggered.connect(self._feed_clipboard)
        self._menu.addAction(action_feed_clipboard)

        action_ask = QAction("提问...", self)
        action_ask.triggered.connect(self.question_requested.emit)
        self._menu.addAction(action_ask)

        self._menu.addSeparator()

        action_settings = QAction("设置...", self)
        action_settings.triggered.connect(self.settings_requested.emit)
        self._menu.addAction(action_settings)

        action_about = QAction("关于", self)
        action_about.triggered.connect(self.about_requested.emit)
        self._menu.addAction(action_about)

        self._menu.addSeparator()

        action_exit = QAction("退出", self)
        action_exit.triggered.connect(self._on_exit)
        self._menu.addAction(action_exit)

        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_menu)

    def _show_menu(self, pos: QPoint) -> None:
        self._menu.exec(self.mapToGlobal(pos))

    # ── 拖放投喂 ──────────────────────────────────
    def _setup_drag_drop(self) -> None:
        """启用拖放接受"""
        self.setAcceptDrops(True)
        self.pet_label.setAcceptDrops(True)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        """拖入时高亮，接受所有类型"""
        mime = event.mimeData()
        if mime.hasUrls() or mime.hasText() or mime.hasHtml():
            event.acceptProposedAction()
            self._highlight_feed(True)
        else:
            event.ignore()

    def dragLeaveEvent(self, event) -> None:
        self._highlight_feed(False)

    def dropEvent(self, event: QDropEvent) -> None:
        """接收拖放内容"""
        self._highlight_feed(False)
        items = parse_mime_data(event.mimeData())
        if items:
            self._feed_queue.enqueue_items(items)
            for item in items:
                self.feed_received.emit(item)
            event.acceptProposedAction()
        else:
            event.ignore()

    def _highlight_feed(self, on: bool) -> None:
        """投喂悬停高亮（临时缩放）"""
        if on:
            self.setStyleSheet("border: 3px solid #4CAF50; border-radius: 10px;")
        else:
            self.setStyleSheet("")

    # ── 剪贴板投喂 ────────────────────────────────
    def _setup_clipboard(self) -> None:
        """初始化剪贴板对象"""
        self._clipboard = QApplication.clipboard()
        self._last_clipboard_text: str = ""

    def _feed_clipboard(self) -> None:
        """主动投喂剪贴板内容"""
        mime = self._clipboard.mimeData()
        items = parse_mime_data(mime)
        if items:
            self._feed_queue.enqueue_items(items)
            for item in items:
                self.feed_received.emit(item)
        else:
            # 剪贴板为空或无法识别
            pass

    def check_clipboard(self) -> None:
        """检查剪贴板变化（供定时器调用）"""
        if not self.config.clipboard_monitor:
            return
        mime = self._clipboard.mimeData()
        if mime.hasText():
            text = mime.text()
            if text and text != self._last_clipboard_text:
                self._last_clipboard_text = text
                # 不自动投喂（太激进），记录即可
                # 用户可通过右键"投喂剪贴板"手动触发

    # ── 投喂队列连接 ──────────────────────────────
    def _connect_feed_queue(self) -> None:
        """连接投喂队列信号 + 气泡反馈 + 动画"""
        self._feed_queue.item_started.connect(self._on_feed_started)
        self._feed_queue.item_finished.connect(self._on_feed_done)
        # 气泡
        self.feed_received.connect(
            lambda item: self._bubble.show_received(item.display_name)
        )
        self.feed_done.connect(self._on_feed_bubble)
        # 动画：投喂中
        self.feed_received.connect(lambda _: self._animator.play("hungry"))
        self.feed_done.connect(
            lambda item, ok, msg: self._animator.play("happy" if ok else "error")
        )
        # 提问→思考
        self.question_requested.connect(lambda: self._animator.play("thinking"))

    def _on_frame(self, pixmap: QPixmap) -> None:
        """动画帧更新"""
        if pixmap and not pixmap.isNull():
            # 窗口尺寸随帧自适应
            w, h = pixmap.width(), pixmap.height()
            if self.width() != w or self.height() != h:
                self.setFixedSize(w, h)
            self.pet_label.setPixmap(
                pixmap.scaled(w, h, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            )

    def _on_feed_started(self, item: FeedItem) -> None:
        self.feed_started.emit(item)

    def _on_feed_done(self, item: FeedItem, success: bool, message: str) -> None:
        self.feed_done.emit(item, success, message)

    def _on_feed_bubble(self, item: FeedItem, success: bool, message: str) -> None:
        """将投喂结果转换为气泡样式"""
        if success:
            # 暂时使用通用成功提示，后续集成 ContentClassifier 后显示分类
            self._bubble.show_classified("已归档", tags=None)
        else:
            self._bubble.show_error(message)

    # ── 拖拽移动（鼠标左键） ───────────────────────
    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        """双击打开内容浏览器"""
        if event.button() == Qt.MouseButton.LeftButton:
            self.browser_requested.emit()
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if event.buttons() & Qt.MouseButton.LeftButton and self._drag_pos is not None:
            new_pos = event.globalPosition().toPoint() - self._drag_pos
            self.move(new_pos)
            event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = None
            self._save_position()
            event.accept()

    def _save_position(self) -> None:
        pos = self.pos()
        self.config.window_x = pos.x()
        self.config.window_y = pos.y()

    def _restore_position(self) -> None:
        x = self.config.window_x
        y = self.config.window_y
        if x < 0 or y < 0:
            screen = QApplication.primaryScreen()
            if screen:
                geo = screen.availableGeometry()
                x = geo.right() - PET_SIZE - 20
                y = geo.bottom() - PET_SIZE - 40
            else:
                x, y = 100, 100
        self.move(max(0, x), max(0, y))

    # ── 焦点 ──────────────────────────────────────
    def focusInEvent(self, event):
        pass

    # ── 退出 ──────────────────────────────────────
    def _on_exit(self) -> None:
        self._save_position()
        self._feed_queue.stop()
        self.closed.emit()
        self.hide()
        QApplication.quit()

    def closeEvent(self, event) -> None:
        self._save_position()
        self._feed_queue.stop()
        self.closed.emit()
        event.accept()
