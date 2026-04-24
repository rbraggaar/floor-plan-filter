"""
floor_navigator.py

Main plugin class. Owns the FloorModel, LayerRegistry, both strategies,
dock widget, and menu actions. Persists config in QGIS project custom variables.
"""

from __future__ import annotations
import json
import logging
from typing import Optional

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QKeySequence
from qgis.PyQt.QtWidgets import QAction, QShortcut
from qgis.core import QgsProject, QgsVectorLayer

from .floor_model import FloorModel
from .layer_registry import LayerRegistry
from .strategies import AttributeFilterStrategy, GroupVisibilityStrategy

log = logging.getLogger(__name__)

_VAR_MODEL    = 'floor_navigator_model'
_VAR_REGISTRY = 'floor_navigator_registry'


class FloorNavigator:

    def __init__(self, iface):
        self.iface    = iface
        self.model    = FloorModel()
        self.registry = LayerRegistry()
        self.attr_strategy  = AttributeFilterStrategy(self.registry, self.model)
        self.group_strategy = GroupVisibilityStrategy(self.registry, self.model)
        self._dock    = None
        self._actions = []
        self._shortcut_up   = None
        self._shortcut_down = None

    # ==================================================================
    # QGIS plugin lifecycle
    # ==================================================================

    def initGui(self):
        self._add_action("⚙ Configure Floor Navigator…", self._open_config)
        self._add_action("⏸ Pause / Resume",             self._toggle_pause, checkable=True)
        self._add_separator()
        self._add_action("Show Floor Navigator Panel",    self._show_dock, checkable=True)

        from .ui.dock_widget import FloorNavigatorDock
        self._dock = FloorNavigatorDock(self.iface.mainWindow(), self)
        self.iface.addDockWidget(Qt.RightDockWidgetArea, self._dock)
        self._dock.setVisible(True)

        # Page Up / Page Down hotkeys
        self._shortcut_up = QShortcut(QKeySequence(Qt.Key_PageUp), self.iface.mainWindow())
        self._shortcut_up.setContext(Qt.ApplicationShortcut)
        self._shortcut_up.activated.connect(self.go_up)

        self._shortcut_down = QShortcut(QKeySequence(Qt.Key_PageDown), self.iface.mainWindow())
        self._shortcut_down.setContext(Qt.ApplicationShortcut)
        self._shortcut_down.activated.connect(self.go_down)

        QgsProject.instance().readProject.connect(self._on_project_read)
        QgsProject.instance().writeProject.connect(self._on_project_write)
        QgsProject.instance().cleared.connect(self._on_project_cleared)

    def unload(self):
        self.attr_strategy.deactivate()
        self.group_strategy.deactivate()

        for sc in (self._shortcut_up, self._shortcut_down):
            if sc:
                sc.setEnabled(False)
                sc.deleteLater()
        self._shortcut_up = self._shortcut_down = None

        if self._dock:
            self.iface.removeDockWidget(self._dock)
            self._dock.deleteLater()
            self._dock = None

        for action in self._actions:
            self.iface.removePluginMenu("&Floor Navigator", action)
            self.iface.removeToolBarIcon(action)
        self._actions.clear()

        QgsProject.instance().readProject.disconnect(self._on_project_read)
        QgsProject.instance().writeProject.disconnect(self._on_project_write)
        QgsProject.instance().cleared.disconnect(self._on_project_cleared)

    # ==================================================================
    # Floor navigation
    # ==================================================================

    def _check_edit_state(self) -> bool:
        """
        Returns True if any registered attribute filter layer is in edit mode.
        Shows a message bar warning and blocks the floor switch.
        """
        for cfg in self.registry.attr_layers:
            layer = QgsProject.instance().mapLayer(cfg.layer_id)
            if isinstance(layer, QgsVectorLayer) and layer.isEditable():
                self.iface.messageBar().pushWarning(
                    "Floor Navigator",
                    "Warning — cannot switch floors while editing a layer. "
                    "Please save all changes and stop edit mode for the floor switch to operate."
                )
                return True
        return False

    def set_level_by_index(self, index: int):
        if self.registry.paused:
            return
        if self._check_edit_state():
            if self._dock:
                self._dock.revert_combo()
            return
        if self.model.set_active_index(index):
            self.apply_current_level()

    def go_up(self):
        """Move one level up. Triggered by ▲ button and Page Up hotkey."""
        if self.registry.paused:
            return
        if self._check_edit_state():
            return
        if self.model.go_up():
            self.apply_current_level()

    def go_down(self):
        """Move one level down. Triggered by ▼ button and Page Down hotkey."""
        if self.registry.paused:
            return
        if self._check_edit_state():
            return
        if self.model.go_down():
            self.apply_current_level()

    def apply_current_level(self):
        """Push current level to both strategies and refresh canvas."""
        level = self.model.active_level
        if level is None:
            return
        log.debug("Applying level: %s  floor_ids=%s", level.label, level.floor_ids)
        self.attr_strategy.apply(level)
        self.group_strategy.apply(level)
        self.iface.mapCanvas().refresh()
        if self._dock:
            self._dock.refresh()

    # ==================================================================
    # Pause / resume
    # ==================================================================

    def set_paused(self, paused: bool):
        self.registry.paused = paused
        if not paused:
            self.attr_strategy.clear_all()
            self.apply_current_level()
        if self._dock:
            self._dock.refresh()

    def _toggle_pause(self):
        self.set_paused(not self.registry.paused)

    # ==================================================================
    # Config
    # ==================================================================

    def _open_config(self):
        from .ui.config_dialog import ConfigDialog
        dlg = ConfigDialog(self.iface.mainWindow(), self)
        dlg.exec_()
        if self._dock:
            self._dock.refresh()

    def _show_dock(self):
        if self._dock:
            self._dock.setVisible(not self._dock.isVisible())

    # ==================================================================
    # Project persistence
    # ==================================================================

    def _on_project_read(self):
        try:
            variables = QgsProject.instance().customVariables()
            model_json    = variables.get(_VAR_MODEL, '')
            registry_json = variables.get(_VAR_REGISTRY, '')

            if model_json:
                self.model = FloorModel.from_dict(json.loads(model_json))
            if registry_json:
                self.registry = LayerRegistry.from_dict(json.loads(registry_json))

            self._rewire()

            if self._dock:
                self._dock.refresh()

            self.model.apply_default()
            self.apply_current_level()

        except Exception as e:
            log.error("FloorNavigator: failed to load project config: %s", e)

    def _on_project_write(self):
        try:
            variables = QgsProject.instance().customVariables()
            variables[_VAR_MODEL]    = json.dumps(self.model.to_dict())
            variables[_VAR_REGISTRY] = json.dumps(self.registry.to_dict())
            QgsProject.instance().setCustomVariables(variables)
        except Exception as e:
            log.error("FloorNavigator: failed to save project config: %s", e)

    def _on_project_cleared(self):
        self.model    = FloorModel()
        self.registry = LayerRegistry()
        self._rewire()
        if self._dock:
            self._dock.refresh()

    def _rewire(self):
        """Re-point strategies at the current model and registry instances."""
        self.attr_strategy._model     = self.model
        self.attr_strategy._registry  = self.registry
        self.group_strategy._model    = self.model
        self.group_strategy._registry = self.registry

    # ==================================================================
    # Menu helpers
    # ==================================================================

    def _add_action(self, text: str, slot, checkable: bool = False) -> QAction:
        action = QAction(text, self.iface.mainWindow())
        action.setCheckable(checkable)
        action.triggered.connect(slot)
        self.iface.addPluginToMenu("&Floor Navigator", action)
        self._actions.append(action)
        return action

    def _add_separator(self):
        sep = QAction(self.iface.mainWindow())
        sep.setSeparator(True)
        self.iface.addPluginToMenu("&Floor Navigator", sep)
        self._actions.append(sep)
