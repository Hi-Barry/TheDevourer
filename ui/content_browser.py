"""大嘴怪 — 内容浏览器

QMainWindow 窗口：分类树 + 内容列表 + 搜索栏 + 右键菜单 + 状态栏。
"""
import os
import subprocess
import json
import webbrowser
from pathlib import Path

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QTreeView, QTreeWidget, QTreeWidgetItem, QTableView, QHeaderView,
    QLineEdit, QPushButton, QLabel, QStatusBar, QMenu, QCheckBox,
    QAbstractItemView, QMessageBox, QInputDialog, QSizePolicy,
    QApplication,
)
from PySide6.QtCore import Qt, Signal, QSortFilterProxyModel, QAbstractTableModel, QModelIndex
from PySide6.QtGui import QIcon, QAction, QKeySequence, QShortcut

from core.db import Database
from core.storage_manager import StorageManager
from core.config import get_config


# ── 表格模型 ──────────────────────────────────────

COLUMNS = ["图标", "标题", "类型", "分类", "标签", "大小", "日期", "索引"]
COL_ICON = 0
COL_TITLE = 1
COL_TYPE = 2
COL_CATEGORY = 3
COL_TAGS = 4
COL_SIZE = 5
COL_DATE = 6
COL_INDEX = 7

TYPE_ICONS = {
    "document": "📄",
    "image": "🖼️",
    "audio": "🎵",
    "video": "🎬",
    "archive": "📦",
    "url": "🔗",
    "other": "📌",
}


class ContentTableModel(QAbstractTableModel):
    """内容列表的表格模型"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._items: list[dict] = []

    def set_items(self, items: list[dict]) -> None:
        self.beginResetModel()
        self._items = items
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()) -> int:
        return len(self._items)

    def columnCount(self, parent=QModelIndex()) -> int:
        return len(COLUMNS)

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return COLUMNS[section]
        return None

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        item = self._items[index.row()]
        col = index.column()

        if role == Qt.ItemDataRole.DisplayRole:
            if col == COL_ICON:
                return TYPE_ICONS.get(item.get("type", ""), "📌")
            if col == COL_TITLE:
                return item.get("title", "")[:60]
            if col == COL_TYPE:
                return item.get("type", "")
            if col == COL_CATEGORY:
                return item.get("category", "")
            if col == COL_TAGS:
                try:
                    tags = json.loads(item.get("tags", "[]"))
                    return " ".join(f"#{t}" for t in tags)
                except (json.JSONDecodeError, TypeError):
                    return ""
            if col == COL_SIZE:
                return self._format_size(item.get("file_size", 0))
            if col == COL_DATE:
                created = item.get("created_at", "")
                return created[:16] if created else ""
            if col == COL_INDEX:
                status = item.get("embedding_status", "pending")
                return {"done": "✅", "indexing": "⏳", "pending": "⬜", "failed": "❌", "skipped": "➖"}.get(status, "⬜")

        if role == Qt.ItemDataRole.UserRole:
            # 存储 item_id 用于后续操作
            return item.get("id", "")

        return None

    @staticmethod
    def _format_size(size: int) -> str:
        if size < 1024:
            return f"{size}B"
        elif size < 1024 * 1024:
            return f"{size / 1024:.1f}KB"
        else:
            return f"{size / (1024 * 1024):.1f}MB"


# ── 代理模型（过滤）───────────────────────────────

class ContentFilterModel(QSortFilterProxyModel):
    """支持标题+分类+标签+搜索模式过滤"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._filter_text = ""
        self._filter_category = ""
        self._semantic_mode = False

    def set_filter_text(self, text: str) -> None:
        self._filter_text = text.strip().lower()
        self.invalidateFilter()

    def set_filter_category(self, category: str) -> None:
        self._filter_category = category
        self.invalidateFilter()

    def set_semantic_mode(self, enabled: bool) -> None:
        self._semantic_mode = enabled

    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:
        model = self.sourceModel()
        if not model:
            return True

        # 分类过滤
        if self._filter_category:
            cat_idx = model.index(source_row, COL_CATEGORY)
            cat = (model.data(cat_idx, Qt.ItemDataRole.DisplayRole) or "").lower()
            if self._filter_category.lower() not in cat:
                return False

        # 文本过滤：标题+标签
        if self._filter_text:
            title_idx = model.index(source_row, COL_TITLE)
            title = (model.data(title_idx, Qt.ItemDataRole.DisplayRole) or "").lower()
            tags_idx = model.index(source_row, COL_TAGS)
            tags = (model.data(tags_idx, Qt.ItemDataRole.DisplayRole) or "").lower()

            if self._filter_text not in title and self._filter_text not in tags:
                return False

        return True


# ── 内容浏览器窗口 ────────────────────────────────

class ContentBrowser(QMainWindow):
    """内容浏览器主窗口"""

    def __init__(self, db: Database, storage_manager: StorageManager = None, parent=None):
        super().__init__(parent)
        self.db = db
        self.sm = storage_manager
        self.config = get_config()

        self.setWindowTitle("📚 大嘴怪仓库浏览器")
        self.setMinimumSize(900, 550)
        self.resize(1100, 650)

        self._setup_ui()
        self._setup_model()
        self._load_data()
        self._setup_shortcuts()

    # ── UI 搭建 ────────────────────────────────────

    def _setup_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(8, 8, 8, 8)

        # 搜索栏
        search_layout = QHBoxLayout()

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("搜索标题、标签... 支持 #标签 过滤")
        self.search_input.setStyleSheet("font-size: 14px; padding: 6px; border-radius: 6px; border: 1px solid #ccc;")
        self.search_input.textChanged.connect(self._on_search)
        search_layout.addWidget(self.search_input, 1)

        self.semantic_check = QCheckBox("语义搜索")
        self.semantic_check.setChecked(False)
        self.semantic_check.stateChanged.connect(self._on_semantic_toggle)
        search_layout.addWidget(self.semantic_check)

        layout.addLayout(search_layout)

        # 分割器：分类树 + 列表
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # 左侧分类树
        self.tree = QTreeWidget()
        self.tree.setHeaderLabel("分类")
        self.tree.setMinimumWidth(180)
        self.tree.setMaximumWidth(280)
        self.tree.itemClicked.connect(self._on_category_clicked)
        splitter.addWidget(self.tree)

        # 右侧表格
        self.table = QTableView()
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.setAlternatingRowColors(True)
        self.table.setSortingEnabled(True)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._on_context_menu)
        self.table.doubleClicked.connect(self._on_double_click)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(COL_TITLE, QHeaderView.ResizeMode.Stretch)
        splitter.addWidget(self.table)

        splitter.setStretchFactor(1, 3)
        layout.addWidget(splitter, 1)

        # 底部状态栏
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self._update_status_bar()

    def _setup_model(self) -> None:
        """初始化数据模型"""
        self._source_model = ContentTableModel()
        self._filter_model = ContentFilterModel()
        self._filter_model.setSourceModel(self._source_model)
        self.table.setModel(self._filter_model)

    # ── 数据加载 ───────────────────────────────────

    def _load_data(self) -> None:
        """加载内容列表"""
        items = self.db.list_items(limit=10000)
        self._source_model.set_items(items)

        # 构建分类树
        self._build_category_tree(items)

        # 更新状态栏
        self._update_status_bar()

    def _build_category_tree(self, items: list[dict]) -> None:
        """构建分类树"""
        self.tree.clear()

        # 全部
        all_item = QTreeWidgetItem(self.tree, ["📚 全部"])
        all_item.setData(0, Qt.ItemDataRole.UserRole, "")
        all_item.setExpanded(True)

        # 统计每类数量
        cat_counts: dict[str, int] = {}
        for item in items:
            cat = item.get("category", "其他")
            cat_counts[cat] = cat_counts.get(cat, 0) + 1

        # 构建树（按 "/" 分层）
        tree_nodes: dict[str, QTreeWidgetItem] = {}
        for cat_path, count in sorted(cat_counts.items()):
            parts = cat_path.split("/")
            parent = self.tree
            parent_key = ""

            for i, part in enumerate(parts):
                full_key = "/".join(parts[:i + 1])
                if full_key in tree_nodes:
                    parent_node = tree_nodes[full_key]
                else:
                    label = f"{part} ({count})" if i == len(parts) - 1 else part
                    if i == 0:
                        icon_map = {"文档": "📄", "网址": "🔗", "图片": "🖼️", "音视频": "🎬", "其他": "📦"}
                        label = f"{icon_map.get(part, '📌')} {label}"
                    parent_node = QTreeWidgetItem(parent, [label])
                    parent_node.setData(0, Qt.ItemDataRole.UserRole, full_key)
                    tree_nodes[full_key] = parent_node

                parent = parent_node
                parent_key = full_key

        self.tree.expandAll()

    def refresh(self) -> None:
        """刷新数据"""
        self._load_data()
        self._filter_model.invalidateFilter()

    # ── 搜索 ───────────────────────────────────────

    def _on_search(self, text: str) -> None:
        self._filter_model.set_filter_text(text)

    def _on_semantic_toggle(self, state: int) -> None:
        enabled = state == Qt.CheckState.Checked.value
        self._filter_model.set_semantic_mode(enabled)

    def _on_category_clicked(self, item: QTreeWidgetItem, column: int) -> None:
        category = item.data(0, Qt.ItemDataRole.UserRole) or ""
        self._filter_model.set_filter_category(category)

    # ── 交互 ───────────────────────────────────────

    def _on_double_click(self, index: QModelIndex) -> None:
        """双击打开文件"""
        source_idx = self._filter_model.mapToSource(index)
        item_id = self._source_model.data(source_idx, Qt.ItemDataRole.UserRole)
        if not item_id:
            return

        item = self.db.get_item(item_id)
        if not item:
            return

        if item["type"] == "url":
            url = item.get("source_url", "")
            if url:
                webbrowser.open(url)
            return

        repo_path = item.get("repo_path", "")
        full_path = Path(self.config.files_path) / repo_path if repo_path else ""

        if full_path and full_path.exists():
            # 用系统默认程序打开
            try:
                if os.name == "nt":
                    os.startfile(str(full_path))
                else:
                    subprocess.run(["xdg-open", str(full_path)])
            except Exception:
                QMessageBox.warning(self, "打开失败", f"无法打开文件:\n{full_path}")
        else:
            QMessageBox.information(self, "文件不存在", f"文件已被移动或删除:\n{full_path}")

    def _on_context_menu(self, pos) -> None:
        """右键菜单"""
        indexes = self.table.selectedIndexes()
        if not indexes:
            return

        # 收集选中的 item_id
        item_ids: set[str] = set()
        for idx in indexes:
            source_idx = self._filter_model.mapToSource(idx)
            iid = self._source_model.data(source_idx, Qt.ItemDataRole.UserRole)
            if iid:
                item_ids.add(iid)

        if not item_ids:
            return

        menu = QMenu(self)

        # 获取第一个选中项的信息
        first_id = next(iter(item_ids))
        first_item = self.db.get_item(first_id)

        # 打开文件位置
        action_open_location = QAction("📂 打开文件位置", self)
        action_open_location.triggered.connect(lambda: self._open_location(first_item))
        menu.addAction(action_open_location)

        # 复制路径
        action_copy_path = QAction("📋 复制路径", self)
        action_copy_path.triggered.connect(lambda: self._copy_path(first_item))
        menu.addAction(action_copy_path)

        menu.addSeparator()

        # 重新索引
        action_reindex = QAction("🔄 重新索引", self)
        action_reindex.triggered.connect(lambda: self._reindex_items(item_ids))
        menu.addAction(action_reindex)

        # 编辑标签
        action_edit_tags = QAction("🏷️ 编辑标签", self)
        action_edit_tags.triggered.connect(lambda: self._edit_tags(first_item))
        menu.addAction(action_edit_tags)

        menu.addSeparator()

        # 删除
        action_delete = QAction("🗑️ 删除", self)
        action_delete.triggered.connect(lambda: self._delete_items(item_ids))
        menu.addAction(action_delete)

        menu.exec(self.table.viewport().mapToGlobal(pos))

    # ── 操作实现 ────────────────────────────────────

    def _open_location(self, item: dict) -> None:
        repo_path = item.get("repo_path", "")
        full_dir = Path(self.config.files_path) / Path(repo_path).parent if repo_path else ""
        if full_dir and full_dir.exists():
            try:
                if os.name == "nt":
                    os.startfile(str(full_dir))
                else:
                    subprocess.run(["xdg-open", str(full_dir)])
            except Exception:
                pass

    def _copy_path(self, item: dict) -> None:
        repo_path = item.get("repo_path", "")
        full_path = str(Path(self.config.files_path) / repo_path if repo_path else "")
        clipboard = QApplication.clipboard()
        clipboard.setText(full_path)

    def _reindex_items(self, item_ids: set[str]) -> None:
        if not self.sm:
            return
        count = 0
        for iid in item_ids:
            if self.sm.index_item(iid):
                count += 1
        self.refresh()
        self._update_status_bar()

    def _edit_tags(self, item: dict) -> None:
        current_tags = json.loads(item.get("tags", "[]"))
        current_str = " ".join(current_tags)

        new_str, ok = QInputDialog.getText(
            self, "编辑标签",
            "标签（空格分隔）：",
            text=current_str,
        )
        if ok:
            new_tags = [t.strip() for t in new_str.split() if t.strip()]
            tags_json = json.dumps(new_tags, ensure_ascii=False)
            self.db.execute(
                "UPDATE content_items SET tags=?, updated_at=datetime('now','localtime') WHERE id=?",
                (tags_json, item["id"]),
            )
            self.db.commit()
            self.refresh()

    def _delete_items(self, item_ids: set[str]) -> None:
        count = len(item_ids)
        reply = QMessageBox.question(
            self, "确认删除",
            f"确认删除 {count} 项内容？\n此项操作将同时删除仓库中的文件。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        if self.sm:
            for iid in item_ids:
                self.sm.delete_item(iid)
        else:
            for iid in item_ids:
                self.db.execute("DELETE FROM content_items WHERE id=?", (iid,))
            self.db.commit()

        self.refresh()
        self._update_status_bar()

    # ── 状态栏 ──────────────────────────────────────

    def _update_status_bar(self) -> None:
        stats = self.db.get_stats()
        total = stats["total_items"]
        indexed = stats["indexed_items"]
        total_size = stats["total_size"]

        size_str = self._format_size_detail(total_size)
        coverage = f"{indexed}/{total} 已索引" if total > 0 else "空仓库"
        self.status_bar.showMessage(f"📦 {total} 项  |  💾 {size_str}  |  🔍 {coverage}")

    @staticmethod
    def _format_size_detail(size: int) -> str:
        if size < 1024:
            return f"{size} B"
        elif size < 1024 * 1024:
            return f"{size / 1024:.1f} KB"
        elif size < 1024 * 1024 * 1024:
            return f"{size / (1024*1024):.1f} MB"
        return f"{size / (1024*1024*1024):.2f} GB"

    # ── 快捷键 ──────────────────────────────────────

    def _setup_shortcuts(self) -> None:
        # Ctrl+F 聚焦搜索框
        shortcut = QShortcut(QKeySequence("Ctrl+F"), self)
        shortcut.activated.connect(self.search_input.setFocus)
        # F5 刷新
        shortcut_refresh = QShortcut(QKeySequence("F5"), self)
        shortcut_refresh.activated.connect(self.refresh)

    def closeEvent(self, event) -> None:
        # 隐藏而非关闭（可再次显示）
        self.hide()
        event.ignore()
