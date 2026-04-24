"""
ui/dock_widget.py

Dockable panel — runtime control surface for Floor Navigator.

Layout:
  ┌─────────────────────────────────┐
  │  Active Level: [Ground Floor ▼] │
  │  [▼ Previous]    [▲ Next]       │
  │  [⏸ Pause]   [⚙ Configure]     │
  └─────────────────────────────────┘
"""

from __future__ import annotations
import logging
from typing import TYPE_CHECKING

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import (
    QDockWidget, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QComboBox, QPushButton, QGroupBox,
    QSizePolicy,
)

if TYPE_CHECKING:
    from ..floor_navigator import FloorNavigator

log = logging.getLogger(__name__)


class FloorNavigatorDock(QDockWidget):

    def __init__(self, parent, plugin: FloorNavigator):
        super().__init__("Floor Navigator", parent)
        self.plugin = plugin
        self.setObjectName("FloorNavigatorDock")
        self.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        self._updating = False
        self._init_ui()

    # ==================================================================
    # UI construction
    # ==================================================================

    def _init_ui(self):
        root = QWidget()
        root.setMinimumWidth(200)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)

        # ── Level selector ─────────────────────────────────────────────
        level_box = QGroupBox("Active Level")
        level_layout = QVBoxLayout(level_box)

        self.combo_level = QComboBox()
        self.combo_level.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.combo_level.currentIndexChanged.connect(self._on_combo_changed)
        level_layout.addWidget(self.combo_level)

        # Previous / Next buttons
        nav_row = QHBoxLayout()
        self.btn_down = QPushButton("▼ Previous")
        self.btn_up   = QPushButton("▲ Next")
        self.btn_down.setToolTip("Go to lower level  [Page Down]")
        self.btn_up.setToolTip("Go to upper level  [Page Up]")
        self.btn_down.clicked.connect(self._on_go_down)
        self.btn_up.clicked.connect(self._on_go_up)
        nav_row.addWidget(self.btn_down)
        nav_row.addWidget(self.btn_up)
        level_layout.addLayout(nav_row)

        # Pause / Configure buttons
        ctrl_row = QHBoxLayout()
        self.btn_pause = QPushButton("⏸ Pause")
        self.btn_pause.setCheckable(True)
        self.btn_pause.setToolTip(
            "Pause: plugin stops touching filters and visibility.\n"
            "Resume: clears and reapplies all filters from the active level."
        )
        self.btn_pause.toggled.connect(self._on_pause_toggled)

        self.btn_config = QPushButton("⚙ Configure")
        self.btn_config.clicked.connect(self._on_configure)

        ctrl_row.addWidget(self.btn_pause)
        ctrl_row.addWidget(self.btn_config)
        level_layout.addLayout(ctrl_row)

        layout.addWidget(level_box)
        layout.addStretch()
        self.setWidget(root)

    # ==================================================================
    # Public — called by FloorNavigator to keep dock in sync
    # ==================================================================

    def refresh(self):
        """Rebuild dock UI from current plugin state."""
        self._updating = True
        try:
            self._rebuild_combo()
            self._sync_pause_button()
        finally:
            self._updating = False

    def revert_combo(self):
        """Snap combo back to actual active index without triggering a floor change."""
        self.combo_level.blockSignals(True)
        self.combo_level.setCurrentIndex(self.plugin.model.active_index)
        self.combo_level.blockSignals(False)

    # ==================================================================
    # Internal rebuild
    # ==================================================================

    def _rebuild_combo(self):
        self.combo_level.blockSignals(True)
        self.combo_level.clear()
        model  = self.plugin.model
        paused = self.plugin.registry.paused

        if model.count == 0:
            self.combo_level.addItem("(no levels configured)")
            self.combo_level.setEnabled(False)
            self.btn_up.setEnabled(False)
            self.btn_down.setEnabled(False)
        else:
            self.combo_level.setEnabled(not paused)
            for label in model.labels:
                self.combo_level.addItem(label)
            self.combo_level.setCurrentIndex(model.active_index)

            at_top    = model.active_index >= model.count - 1
            at_bottom = model.active_index <= 0
            self.btn_up.setEnabled(not paused and not at_top)
            self.btn_down.setEnabled(not paused and not at_bottom)

        self.combo_level.blockSignals(False)

    def _sync_pause_button(self):
        paused = self.plugin.registry.paused
        self.btn_pause.blockSignals(True)
        self.btn_pause.setChecked(paused)
        self.btn_pause.setText("▶ Resume" if paused else "⏸ Pause")
        self.btn_pause.blockSignals(False)

    # ==================================================================
    # Signal handlers
    # ==================================================================

    def _on_combo_changed(self, index: int):
        if self._updating:
            return
        self.plugin.set_level_by_index(index)

    def _on_go_up(self):
        self.plugin.go_up()

    def _on_go_down(self):
        self.plugin.go_down()

    def _on_pause_toggled(self, paused: bool):
        if self._updating:
            return
        self.plugin.set_paused(paused)

    def _on_configure(self):
        from .config_dialog import ConfigDialog
        dlg = ConfigDialog(self, self.plugin)
        dlg.exec_()
        self.refresh()
