"""
ui/config_dialog.py

Configuration window for Floor Navigator.
Three tabs:
  1. Floors & Levels    — define levels, set order, nominate table source, set default
  2. Attribute Filter   — register vector layers for floor_level filtering
  3. Layer Group Filter — register layer tree groups for visibility management

Changes are applied to the live plugin only on Apply or OK.
Cancel discards all changes.
"""

from __future__ import annotations
import copy
import csv
import json
import logging
from collections import defaultdict
from typing import List, Optional, TYPE_CHECKING

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import (
    QDialog, QDialogButtonBox, QTabWidget, QWidget,
    QVBoxLayout, QHBoxLayout, QFormLayout,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QPushButton, QLabel, QCheckBox,
    QGroupBox, QListWidget, QListWidgetItem,
    QMessageBox, QAbstractItemView,
    QTextEdit, QSizePolicy, QComboBox,
    QFileDialog,
)
from qgis.core import QgsProject, QgsVectorLayer, QgsLayerTreeGroup

if TYPE_CHECKING:
    from ..floor_navigator import FloorNavigator
from ..floor_model import FloorModel, Level

log = logging.getLogger(__name__)


class ConfigDialog(QDialog):

    def __init__(self, parent, plugin: FloorNavigator):
        super().__init__(parent)
        self.plugin = plugin
        self.setWindowTitle("Floor Navigator — Configuration")
        self.setMinimumSize(660, 540)
        self.resize(740, 600)

        # Work on deep copies so Cancel truly cancels
        self._model_copy    = FloorModel.from_dict(json.loads(json.dumps(plugin.model.to_dict())))
        self._registry_copy = copy.deepcopy(plugin.registry)

        self._init_ui()
        self._populate_all()

    # ==================================================================
    # UI construction
    # ==================================================================

    def _init_ui(self):
        layout = QVBoxLayout(self)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_floors_tab(),  "Floors && Levels")
        self.tabs.addTab(self._build_attr_tab(),    "Attribute Filter")
        self.tabs.addTab(self._build_group_tab(),   "Layer Group Filter")
        layout.addWidget(self.tabs)

        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel | QDialogButtonBox.Apply
        )
        buttons.accepted.connect(self._on_ok)
        buttons.rejected.connect(self.reject)
        buttons.button(QDialogButtonBox.Apply).clicked.connect(self._on_apply)
        layout.addWidget(buttons)

    # ── Tab 1: Floors & Levels ─────────────────────────────────────────

    def _build_floors_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)

        # Floor table source
        src_box = QGroupBox("Floor Table Source  (optional)")
        src_layout = QFormLayout(src_box)
        src_layout.addRow(QLabel(
            "Nominate a loaded table layer as the source of floor/level definitions.<br>"
            "Required columns: <code>floor_id</code>, <code>label</code>, "
            "<code>level_label</code>, <code>sort_order</code>"
        ))
        self.combo_floor_table = QComboBox()
        self.combo_floor_table.addItem("(manual entry — no table source)", None)
        for layer in QgsProject.instance().mapLayers().values():
            if isinstance(layer, QgsVectorLayer):
                self.combo_floor_table.addItem(layer.name(), layer.id())
        src_layout.addRow("Table layer:", self.combo_floor_table)

        btn_load = QPushButton("Load Floors from Table")
        btn_load.setToolTip(
            "Reads the nominated table and populates the level list below.\n"
            "Rows with the same level_label are combined into one level."
        )
        btn_load.clicked.connect(self._load_floors_from_table)
        src_layout.addRow(btn_load)
        layout.addWidget(src_box)

        # Level table
        layout.addWidget(QLabel(
            "<b>Levels — bottom-up order</b> (row 0 = lowest floor).<br>"
            "Label = display name &nbsp;|&nbsp; "
            "Floor ID(s) = comma-separated e.g. <code>L2N, L2S</code>"
        ))

        self.level_table = QTableWidget(0, 2)
        self.level_table.setHorizontalHeaderLabels(["Display Label", "Floor ID(s)  [comma-separated]"])
        self.level_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.level_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.level_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.level_table.setAlternatingRowColors(True)
        self.level_table.itemChanged.connect(self._sync_default_combo)
        self.level_table.itemChanged.connect(self._sync_model_copy)
        layout.addWidget(self.level_table)

        btn_row = QHBoxLayout()
        btn_add    = QPushButton("+ Add Level")
        btn_remove = QPushButton("− Remove")
        btn_up     = QPushButton("↑ Move Up")
        btn_down   = QPushButton("↓ Move Down")
        btn_add.clicked.connect(self._add_level_row)
        btn_remove.clicked.connect(self._remove_level_row)
        btn_up.clicked.connect(lambda: self._move_level_row(-1))
        btn_down.clicked.connect(lambda: self._move_level_row(1))
        for b in (btn_add, btn_remove, btn_up, btn_down):
            btn_row.addWidget(b)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        # Default level
        default_box = QGroupBox("Default Level on Project Open")
        default_layout = QFormLayout(default_box)
        self.combo_default_level = QComboBox()
        default_layout.addRow("Open project at:", self.combo_default_level)
        default_layout.addRow(QLabel(
            "<i>This level is activated automatically when the project is opened.</i>"
        ))
        layout.addWidget(default_box)

        # CSV import / export
        csv_box = QGroupBox("Configuration Backup")
        csv_layout = QHBoxLayout(csv_box)
        btn_export_csv = QPushButton("⬆ Export Config to CSV")
        btn_import_csv = QPushButton("⬇ Import Config from CSV")
        btn_export_csv.setToolTip(
            "Save the current floor definitions, registered layers, and "
            "registered groups to a CSV file."
        )
        btn_import_csv.setToolTip(
            "Restore floor definitions, layers, and groups from a previously "
            "exported CSV file. Layers and groups are matched by name."
        )
        btn_export_csv.clicked.connect(self._export_csv)
        btn_import_csv.clicked.connect(self._import_csv)
        csv_layout.addWidget(btn_export_csv)
        csv_layout.addWidget(btn_import_csv)
        layout.addWidget(csv_box)

        return w

    # ── Tab 2: Attribute Filter ────────────────────────────────────────

    def _build_attr_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)

        self.chk_attr = QCheckBox("Enable Attribute Filter")
        layout.addWidget(self.chk_attr)

        layout.addWidget(QLabel(
            "Tick the vector layers that contain a <code>floor_level</code> column.<br>"
            "Checked layers are actively managed by the plugin. "
            "Unchecked layers are ignored."
        ))

        self.attr_list = QListWidget()
        self.attr_list.setSelectionMode(QAbstractItemView.NoSelection)
        layout.addWidget(self.attr_list)

        layout.addWidget(QLabel(
            "<i>Only vector layers loaded in the current project are shown.</i>"
        ))

        btn_validate = QPushButton("Validate Selected Layers")
        btn_validate.clicked.connect(self._validate_attr_layers)
        layout.addWidget(btn_validate)

        self.attr_validation_label = QLabel("")
        self.attr_validation_label.setWordWrap(True)
        layout.addWidget(self.attr_validation_label)

        return w

    # ── Tab 3: Layer Group Filter ──────────────────────────────────────

    def _build_group_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)

        self.chk_group = QCheckBox("Enable Layer Group Filter")
        layout.addWidget(self.chk_group)

        layout.addWidget(QLabel(
            "Tick the layer tree groups whose layers follow the "
            "<code>LayerName_[FLOOR_ID]</code> naming convention.<br>"
            "Checked groups are actively managed by the plugin. "
            "Unchecked groups are ignored."
        ))

        self.group_list = QListWidget()
        self.group_list.setSelectionMode(QAbstractItemView.NoSelection)
        layout.addWidget(self.group_list)

        btn_validate = QPushButton("Validate Selected Groups")
        btn_validate.clicked.connect(self._validate_groups)
        layout.addWidget(btn_validate)

        self.group_validation = QTextEdit()
        self.group_validation.setReadOnly(True)
        self.group_validation.setMaximumHeight(120)
        self.group_validation.setPlaceholderText("Validation results will appear here…")
        layout.addWidget(self.group_validation)

        return w

    # ==================================================================
    # Population
    # ==================================================================

    def _populate_all(self):
        self._populate_levels()
        self._populate_attr_list()
        self._populate_group_list()
        self.chk_attr.setChecked(self._registry_copy.attr_filter_enabled)
        self.chk_group.setChecked(self._registry_copy.group_filter_enabled)

    def _populate_levels(self):
        self.level_table.blockSignals(True)
        self.level_table.setRowCount(0)
        for level in self._model_copy.levels:
            self._append_level_row(level.label, ', '.join(level.floor_ids))
        self.level_table.blockSignals(False)
        self._sync_default_combo()

        # Restore default selection
        default_idx = self._model_copy.default_index
        if self.combo_default_level.count() > default_idx:
            self.combo_default_level.setCurrentIndex(default_idx)

        # Restore floor table selection
        table_id = self._registry_copy.floor_table_layer_id
        if table_id:
            for i in range(self.combo_floor_table.count()):
                if self.combo_floor_table.itemData(i) == table_id:
                    self.combo_floor_table.setCurrentIndex(i)
                    break

    def _populate_attr_list(self):
        self.attr_list.clear()
        registered_ids = {l.layer_id for l in self._registry_copy.attr_layers}
        for layer in QgsProject.instance().mapLayers().values():
            if not isinstance(layer, QgsVectorLayer):
                continue
            item = QListWidgetItem(layer.name())
            item.setData(Qt.UserRole, layer.id())
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(
                Qt.Checked if layer.id() in registered_ids else Qt.Unchecked
            )
            self.attr_list.addItem(item)

    def _populate_group_list(self):
        self.group_list.clear()
        registered_names = {g.group_name for g in self._registry_copy.groups}
        root = QgsProject.instance().layerTreeRoot()
        self._collect_groups(root, registered_names)

    def _collect_groups(self, node, registered: set, depth: int = 0):
        for child in node.children():
            if isinstance(child, QgsLayerTreeGroup):
                indent = '  ' * depth
                item = QListWidgetItem(f"{indent}{child.name()}")
                item.setData(Qt.UserRole, child.name())
                item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
                item.setCheckState(
                    Qt.Checked if child.name() in registered else Qt.Unchecked
                )
                self.group_list.addItem(item)
                self._collect_groups(child, registered, depth + 1)

    # ==================================================================
    # Level table operations
    # ==================================================================

    def _append_level_row(self, label: str = '', floor_ids: str = ''):
        row = self.level_table.rowCount()
        self.level_table.insertRow(row)
        self.level_table.setItem(row, 0, QTableWidgetItem(label))
        self.level_table.setItem(row, 1, QTableWidgetItem(floor_ids))

    def _add_level_row(self):
        self._append_level_row('New Level', 'ID1')
        self.level_table.scrollToBottom()
        self.level_table.editItem(self.level_table.item(self.level_table.rowCount() - 1, 0))
        self._sync_default_combo()

    def _remove_level_row(self):
        rows = sorted({i.row() for i in self.level_table.selectedItems()}, reverse=True)
        for row in rows:
            self.level_table.removeRow(row)
        self._sync_default_combo()

    def _move_level_row(self, direction: int):
        rows = sorted({i.row() for i in self.level_table.selectedItems()})
        if not rows:
            return
        row = rows[0]
        target = row + direction
        if target < 0 or target >= self.level_table.rowCount():
            return
        self.level_table.blockSignals(True)
        for col in range(self.level_table.columnCount()):
            a = self.level_table.takeItem(row, col)
            b = self.level_table.takeItem(target, col)
            self.level_table.setItem(row, col, b)
            self.level_table.setItem(target, col, a)
        self.level_table.blockSignals(False)
        self.level_table.selectRow(target)
        self._sync_default_combo()

    def _sync_default_combo(self):
        """Keep the default level combo in sync with the level table."""
        current = self.combo_default_level.currentText()
        self.combo_default_level.blockSignals(True)
        self.combo_default_level.clear()
        for row in range(self.level_table.rowCount()):
            item = self.level_table.item(row, 0)
            label = item.text().strip() if item else ''
            if label:
                self.combo_default_level.addItem(label)
        idx = self.combo_default_level.findText(current)
        self.combo_default_level.setCurrentIndex(max(0, idx))
        self.combo_default_level.blockSignals(False)

    def _sync_model_copy(self):
        """
        Keep _model_copy floor IDs in sync with the level table as the user types.
        This ensures the Group Layer Filter tab can validate immediately
        without requiring an Apply/OK cycle first.
        """
        levels = self._read_levels_from_table(silent=True)
        if levels is not None:
            self._model_copy.set_levels(levels)

    # ==================================================================
    # Load floors from table
    # ==================================================================

    def _load_floors_from_table(self):
        layer_id = self.combo_floor_table.currentData()
        if not layer_id:
            QMessageBox.information(
                self, "No Table Selected",
                "Please select a table layer from the dropdown before loading."
            )
            return

        layer = QgsProject.instance().mapLayer(layer_id)
        if not isinstance(layer, QgsVectorLayer):
            QMessageBox.warning(self, "Invalid Layer", "Selected layer is not a vector layer.")
            return

        field_names = [f.name() for f in layer.fields()]
        required = {'floor_id', 'label', 'level_label', 'sort_order'}
        missing = required - set(field_names)
        if missing:
            QMessageBox.warning(
                self, "Missing Columns",
                f"The table is missing required columns: {', '.join(sorted(missing))}\n\n"
                f"Required: floor_id, label, level_label, sort_order"
            )
            return

        level_groups: dict = defaultdict(lambda: {'floor_ids': [], 'sort_order': 9999})
        for feature in layer.getFeatures():
            floor_id    = str(feature['floor_id']).strip()
            level_label = str(feature['level_label']).strip()
            sort_order  = int(feature['sort_order']) if feature['sort_order'] is not None else 9999
            if not floor_id or not level_label:
                continue
            entry = level_groups[level_label]
            entry['floor_ids'].append(floor_id)
            entry['sort_order'] = min(entry['sort_order'], sort_order)

        if not level_groups:
            QMessageBox.warning(self, "No Data", "No valid rows found in the selected table.")
            return

        sorted_levels = sorted(level_groups.items(), key=lambda x: x[1]['sort_order'])

        if self.level_table.rowCount() > 0:
            reply = QMessageBox.question(
                self, "Replace Level List",
                f"This will replace the current {self.level_table.rowCount()} level(s) "
                f"with {len(sorted_levels)} level(s) from the table.\n\nContinue?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            if reply != QMessageBox.Yes:
                return

        self.level_table.blockSignals(True)
        self.level_table.setRowCount(0)
        for level_label, data in sorted_levels:
            self._append_level_row(level_label, ', '.join(data['floor_ids']))
        self.level_table.blockSignals(False)
        self._sync_default_combo()

        # Update _model_copy immediately so the Group Layer Filter tab
        # can validate against the new floor IDs without needing an Apply first
        levels = self._read_levels_from_table(silent=True)
        if levels is not None:
            self._model_copy.set_levels(levels)

        QMessageBox.information(
            self, "Floors Loaded",
            f"Loaded {len(sorted_levels)} level(s) from '{layer.name()}'."
        )

    # ==================================================================
    # Validation
    # ==================================================================

    def _validate_attr_layers(self):
        issues = []
        for i in range(self.attr_list.count()):
            item = self.attr_list.item(i)
            if item.checkState() != Qt.Checked:
                continue
            layer_id = item.data(Qt.UserRole)
            layer = QgsProject.instance().mapLayer(layer_id)
            if not isinstance(layer, QgsVectorLayer):
                continue
            fields = [f.name() for f in layer.fields()]
            if 'floor_level' not in fields:
                issues.append(f"⚠ '{layer.name()}' — no 'floor_level' column found.")
        if issues:
            self.attr_validation_label.setText('\n'.join(issues))
            self.attr_validation_label.setStyleSheet('color: orange;')
        else:
            self.attr_validation_label.setText('✓ All checked layers have a floor_level column.')
            self.attr_validation_label.setStyleSheet('color: green;')

    def _validate_groups(self):
        # Read the current level table state into _model_copy first
        # so floor IDs are up to date even before the user clicks Apply
        levels = self._read_levels_from_table(silent=True)
        if levels is not None:
            self._model_copy.set_levels(levels)

        all_ids = set(self._model_copy.all_floor_ids())
        if not all_ids:
            self.group_validation.setText(
                "⚠ No floor IDs defined yet. Configure Floors & Levels first."
            )
            return

        from ..strategies.group_visibility import GroupVisibilityStrategy
        strategy = GroupVisibilityStrategy(self._registry_copy, self._model_copy)

        messages = []
        for i in range(self.group_list.count()):
            item = self.group_list.item(i)
            if item.checkState() != Qt.Checked:
                continue
            group_name = item.data(Qt.UserRole)
            warnings = strategy.validate_group(group_name)
            if warnings:
                messages.append(f"Group: {group_name}")
                messages.extend(f"  {w}" for w in warnings)
            else:
                messages.append(f"✓ {group_name} — all layers matched to floor IDs.")

        self.group_validation.setText('\n'.join(messages) if messages else 'No groups checked.')

    # ==================================================================
    # Apply config to plugin
    # ==================================================================

    def _read_levels_from_table(self, silent: bool = False) -> Optional[List[Level]]:
        levels = []
        for row in range(self.level_table.rowCount()):
            label_item = self.level_table.item(row, 0)
            ids_item   = self.level_table.item(row, 1)
            label   = label_item.text().strip() if label_item else ''
            ids_raw = ids_item.text().strip()   if ids_item   else ''

            if not label:
                if not silent:
                    QMessageBox.warning(self, "Validation", f"Row {row + 1}: Level label cannot be empty.")
                return None

            floor_ids = [x.strip() for x in ids_raw.split(',') if x.strip()]
            if not floor_ids:
                if not silent:
                    QMessageBox.warning(self, "Validation", f"Row {row + 1}: Must have at least one floor ID.")
                return None

            for fid in floor_ids:
                if not fid.replace('_', '').isalnum():
                    if not silent:
                        QMessageBox.warning(
                            self, "Validation",
                            f"Row {row + 1}: Floor ID '{fid}' is invalid. "
                            f"Alphanumeric characters only (underscores allowed)."
                        )
                    return None

            try:
                levels.append(Level(label=label, floor_ids=floor_ids))
            except ValueError as e:
                QMessageBox.warning(self, "Validation", str(e))
                return None

        return levels

    def _apply_to_plugin(self) -> bool:
        levels = self._read_levels_from_table()
        if levels is None:
            return False

        # Model — preserve active level label if possible
        active_label = self.plugin.model.active_level.label \
            if self.plugin.model.active_level else None
        self._model_copy.set_levels(levels)
        if active_label:
            self._model_copy.set_active_by_label(active_label)

        # Default level
        default_label = self.combo_default_level.currentText()
        self._model_copy.set_default_by_label(default_label)

        # Registry — floor table source
        self._registry_copy.floor_table_layer_id = self.combo_floor_table.currentData()

        # Registry — Attribute Filter
        self._registry_copy.attr_filter_enabled = self.chk_attr.isChecked()
        self._registry_copy.attr_layers.clear()
        for i in range(self.attr_list.count()):
            item = self.attr_list.item(i)
            if item.checkState() != Qt.Checked:
                continue
            layer_id = item.data(Qt.UserRole)
            layer    = QgsProject.instance().mapLayer(layer_id)
            name     = layer.name() if layer else layer_id
            self._registry_copy.add_attr_layer(layer_id, name)

        # Registry — Layer Group Filter
        self._registry_copy.group_filter_enabled = self.chk_group.isChecked()
        self._registry_copy.groups.clear()
        for i in range(self.group_list.count()):
            item = self.group_list.item(i)
            if item.checkState() == Qt.Checked:
                self._registry_copy.add_group(item.data(Qt.UserRole))

        # Push to live plugin
        self.plugin.model    = self._model_copy
        self.plugin.registry = self._registry_copy
        self.plugin._rewire()

        self.plugin.apply_current_level()
        return True

    # ==================================================================
    # CSV export / import
    # ==================================================================

    def _export_csv(self):
        """
        Export the current UI state to a CSV file.
        Sections: floor, attr_layer, group
        Captures whatever is currently entered/checked in the dialog,
        not just what has been applied to the plugin.
        """
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Floor Navigator Config", "", "CSV files (*.csv)"
        )
        if not path:
            return
        if not path.lower().endswith('.csv'):
            path += '.csv'

        rows = []

        # ── Floor/level definitions ────────────────────────────────────
        default_label = self.combo_default_level.currentText()
        floor_table_name = ''
        table_id = self.combo_floor_table.currentData()
        if table_id:
            layer = QgsProject.instance().mapLayer(table_id)
            if layer:
                floor_table_name = layer.name()

        rows.append(['section', 'key1', 'key2', 'key3', 'key4'])  # header

        if floor_table_name:
            rows.append(['floor_table', floor_table_name, '', '', ''])

        for row in range(self.level_table.rowCount()):
            label_item = self.level_table.item(row, 0)
            ids_item   = self.level_table.item(row, 1)
            label    = label_item.text().strip() if label_item else ''
            floor_ids = ids_item.text().strip()   if ids_item   else ''
            is_default = 'default' if label == default_label else ''
            rows.append(['floor', label, floor_ids, str(row), is_default])

        # ── Checked attribute filter layers ────────────────────────────
        for i in range(self.attr_list.count()):
            item = self.attr_list.item(i)
            if item.checkState() == Qt.Checked:
                rows.append(['attr_layer', item.text(), '', '', ''])

        # ── Checked layer groups ───────────────────────────────────────
        for i in range(self.group_list.count()):
            item = self.group_list.item(i)
            if item.checkState() == Qt.Checked:
                rows.append(['group', item.data(Qt.UserRole), '', '', ''])

        try:
            with open(path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerows(rows)
            QMessageBox.information(
                self, "Export Complete",
                f"Configuration exported to:\n{path}"
            )
        except Exception as e:
            QMessageBox.critical(self, "Export Failed", str(e))

    def _import_csv(self):
        """
        Import configuration from a previously exported CSV file.
        Floors replace the current level table.
        Attr layers and groups are matched by name and auto-checked.
        No manual clicking required after import — just Apply or OK.
        """
        path, _ = QFileDialog.getOpenFileName(
            self, "Import Floor Navigator Config", "", "CSV files (*.csv)"
        )
        if not path:
            return

        try:
            with open(path, 'r', newline='', encoding='utf-8') as f:
                reader = csv.reader(f)
                rows = [r for r in reader if r and r[0] != 'section']  # skip header
        except Exception as e:
            QMessageBox.critical(self, "Import Failed", f"Could not read file:\n{e}")
            return

        if not rows:
            QMessageBox.warning(self, "Empty File", "No configuration rows found in the CSV.")
            return

        # Confirm before overwriting
        reply = QMessageBox.question(
            self, "Replace Configuration",
            "This will replace the current configuration with the contents of the CSV.\n\n"
            "Continue?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return

        # Parse rows by section
        floor_rows   = [r for r in rows if r[0] == 'floor']
        attr_rows    = [r for r in rows if r[0] == 'attr_layer']
        group_rows   = [r for r in rows if r[0] == 'group']
        table_rows   = [r for r in rows if r[0] == 'floor_table']

        # ── Floor table source ─────────────────────────────────────────
        if table_rows:
            table_name = table_rows[0][1].strip()
            for i in range(self.combo_floor_table.count()):
                if self.combo_floor_table.itemText(i) == table_name:
                    self.combo_floor_table.setCurrentIndex(i)
                    break

        # ── Floor/level definitions ────────────────────────────────────
        # Sort by sort_order (key3) so order is preserved correctly
        try:
            floor_rows.sort(key=lambda r: int(r[3]) if len(r) > 3 and r[3].isdigit() else 0)
        except Exception:
            pass

        default_label = ''
        self.level_table.blockSignals(True)
        self.level_table.setRowCount(0)
        for r in floor_rows:
            label     = r[1].strip() if len(r) > 1 else ''
            floor_ids = r[2].strip() if len(r) > 2 else ''
            is_default = r[4].strip() if len(r) > 4 else ''
            if label:
                self._append_level_row(label, floor_ids)
            if is_default == 'default':
                default_label = label
        self.level_table.blockSignals(False)
        self._sync_default_combo()

        if default_label:
            idx = self.combo_default_level.findText(default_label)
            if idx >= 0:
                self.combo_default_level.setCurrentIndex(idx)

        # ── Attribute filter layers — match by name, auto-check ────────
        attr_names = {r[1].strip() for r in attr_rows if len(r) > 1}
        for i in range(self.attr_list.count()):
            item = self.attr_list.item(i)
            item.setCheckState(
                Qt.Checked if item.text().strip() in attr_names else Qt.Unchecked
            )

        # ── Layer groups — match by name, auto-check ───────────────────
        group_names = {r[1].strip() for r in group_rows if len(r) > 1}
        for i in range(self.group_list.count()):
            item = self.group_list.item(i)
            item.setCheckState(
                Qt.Checked if item.data(Qt.UserRole).strip() in group_names else Qt.Unchecked
            )

        QMessageBox.information(
            self, "Import Complete",
            f"Loaded {len(floor_rows)} level(s), "
            f"{len(attr_names)} attribute layer(s), "
            f"{len(group_names)} group(s).\n\n"
            f"Click Apply or OK to activate the imported configuration."
        )

    # ==================================================================
    # Dialog actions
    # ==================================================================

    def _on_apply(self):
        self._apply_to_plugin()

    def _on_ok(self):
        if self._apply_to_plugin():
            self.accept()
