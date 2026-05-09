"""大嘴怪 — 精灵动画引擎

状态机驱动的帧动画：idle/hungry/eating/happy/thinking/error。
QTimer 驱动帧切换，窗口尺寸自适应每帧。
"""
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QTimer, QObject, Signal
from PySide6.QtGui import QPixmap


ANIM_DIR = Path(__file__).resolve().parent.parent / "resources" / "anim"

STATE_CONFIG = {
    "idle":     {"fps": 6,  "loop": True,  "next": "idle"},
    "hungry":   {"fps": 10, "loop": False, "next": "eating"},
    "eating":   {"fps": 8,  "loop": False, "next": "happy"},
    "happy":    {"fps": 8,  "loop": False, "next": "idle"},
    "thinking": {"fps": 6,  "loop": True,  "next": "thinking"},
    "error":    {"fps": 8,  "loop": False, "next": "idle"},
}


class SpriteAnimator(QObject):
    """精灵帧动画控制器"""

    frame_changed = Signal(QPixmap)     # 帧更新时发射，携带当前帧图片
    animation_done = Signal(str)        # 非循环动画完成时发射，携带状态名

    def __init__(self, parent=None):
        super().__init__(parent)
        self._state = "idle"
        self._frames: dict[str, list[QPixmap]] = {}
        self._frame_idx = 0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._next_frame)
        self._load_frames()

    # ── 帧加载 ──────────────────────────────────

    def _load_frames(self) -> None:
        """从 resources/anim/ 加载所有帧"""
        for state in STATE_CONFIG:
            state_dir = ANIM_DIR / state
            pixmaps = []
            if state_dir.exists():
                for f in sorted(state_dir.iterdir()):
                    if f.suffix == ".png":
                        pixmaps.append(QPixmap(str(f)))
            if not pixmaps:
                # 回退：使用 idle 的第一帧
                if state != "idle" and "idle" in self._frames and self._frames["idle"]:
                    pixmaps = self._frames["idle"]
            self._frames[state] = pixmaps

    # ── 状态切换 ──────────────────────────────────

    def play(self, state: str) -> None:
        """切换到指定状态并开始播放"""
        if state not in STATE_CONFIG:
            state = "idle"

        if state == self._state and self._timer.isActive():
            return  # 已在播放同状态

        self._state = state
        self._frame_idx = 0
        cfg = STATE_CONFIG[state]
        interval = int(1000 / cfg["fps"])
        self._timer.start(interval)
        self._emit_current()

    def stop(self) -> None:
        """停止动画，保持当前帧"""
        self._timer.stop()

    # ── 帧推进 ────────────────────────────────────

    def _next_frame(self) -> None:
        """推进到下一帧"""
        frames = self._frames.get(self._state, [])
        if not frames:
            return

        cfg = STATE_CONFIG.get(self._state, {})
        self._frame_idx += 1

        if self._frame_idx >= len(frames):
            if cfg.get("loop", False):
                self._frame_idx = 0
            else:
                self._frame_idx = len(frames) - 1
                self._timer.stop()
                self.animation_done.emit(self._state)
                # 自动过渡到下一状态
                next_state = cfg.get("next", "idle")
                if next_state and next_state != self._state:
                    self.play(next_state)
                return

        self._emit_current()

    def _emit_current(self) -> None:
        """发射当前帧"""
        frames = self._frames.get(self._state, [])
        if frames and self._frame_idx < len(frames):
            self.frame_changed.emit(frames[self._frame_idx])

    # ── 属性 ──────────────────────────────────────

    @property
    def current_frame(self) -> Optional[QPixmap]:
        frames = self._frames.get(self._state, [])
        if frames and self._frame_idx < len(frames):
            return frames[self._frame_idx]
        return None

    @property
    def state(self) -> str:
        return self._state
