"""
strategies/group_visibility.py

Layer Group Filter: manages layer visibility within registered layer tree groups.

Naming convention (enforced):  LayerName_[FLOOR_ID]
e.g.  ArchPlan_GF, ArchPlan_L1, ArchPlan_L2N, ArchPlan_L2S

For each registered group, layers whose suffix matches any floor_id in the
active Level are shown. All other floor-matched layers are hidden.
Layers with no recognised floor suffix are left visible (non-floor content).
"""

from __future__ import annotations
import logging
from typing import TYPE_CHECKING, List, Optional, Set

from qgis.core import (
    QgsProject,
    QgsLayerTreeGroup,
    QgsLayerTreeLayer,
)

if TYPE_CHECKING:
    from ..floor_model import FloorModel, Level
    from ..layer_registry import LayerRegistry

log = logging.getLogger(__name__)


class GroupVisibilityStrategy:

    def __init__(self, registry: LayerRegistry, model: FloorModel):
        self._registry = registry
        self._model = model

    def apply(self, active_level: Level):
        if not self._registry.group_filter_enabled:
            return
        if self._registry.paused:
            return

        all_floor_ids = self._model.all_floor_ids()
        target_ids: Set[str] = set(active_level.floor_ids)
        root = QgsProject.instance().layerTreeRoot()

        for cfg in self._registry.groups:
            group = self._find_group(root, cfg.group_name)
            if group is None:
                log.warning("Layer Group Filter: group not found — '%s'", cfg.group_name)
                continue
            self._apply_to_group(group, target_ids, all_floor_ids)

    def deactivate(self):
        """Make all layers in registered groups visible on unload."""
        root = QgsProject.instance().layerTreeRoot()
        for cfg in self._registry.groups:
            group = self._find_group(root, cfg.group_name)
            if group:
                for tree_layer in group.findLayers():
                    tree_layer.setItemVisibilityChecked(True)

    def validate_group(self, group_name: str) -> List[str]:
        """
        Check layers inside a group against the known floor ID list.
        Returns warning strings for layers that don't match any floor ID.
        """
        warnings = []
        all_ids = set(self._model.all_floor_ids())
        root = QgsProject.instance().layerTreeRoot()
        group = self._find_group(root, group_name)

        if group is None:
            return [f"Group '{group_name}' not found in layer tree."]

        for tree_layer in group.findLayers():
            layer = tree_layer.layer()
            if layer is None:
                continue
            floor_id = self._extract_floor_id(layer.name())
            if floor_id is None:
                warnings.append(
                    f"'{layer.name()}' — no _[FLOOR_ID] suffix. Will always remain visible."
                )
            elif floor_id not in all_ids:
                warnings.append(
                    f"'{layer.name()}' — suffix '_{floor_id}' doesn't match any defined floor ID. "
                    f"Will always remain visible."
                )
        return warnings

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _apply_to_group(
        self,
        group: QgsLayerTreeGroup,
        target_floor_ids: Set[str],
        all_floor_ids: List[str],
    ):
        all_ids_set = set(all_floor_ids)
        for tree_layer in group.findLayers():
            layer = tree_layer.layer()
            if layer is None:
                continue
            floor_id = self._extract_floor_id(layer.name())
            if floor_id is None or floor_id not in all_ids_set:
                # Not floor-managed — leave visible
                tree_layer.setItemVisibilityChecked(True)
            elif floor_id in target_floor_ids:
                tree_layer.setItemVisibilityChecked(True)
            else:
                tree_layer.setItemVisibilityChecked(False)

    @staticmethod
    def _extract_floor_id(layer_name: str) -> Optional[str]:
        """
        Extract floor ID from layer name using the _[FLOOR_ID] convention.
        Uses the rightmost underscore.
        'ArchPlan_GF'  → 'GF'
        'A_B_L1'       → 'L1'
        'NoSuffix'     → None
        """
        if '_' not in layer_name:
            return None
        return layer_name.rsplit('_', 1)[-1]

    @staticmethod
    def _find_group(root: QgsLayerTreeGroup, name: str) -> Optional[QgsLayerTreeGroup]:
        for child in root.children():
            if isinstance(child, QgsLayerTreeGroup):
                if child.name() == name:
                    return child
                result = GroupVisibilityStrategy._find_group(child, name)
                if result:
                    return result
        return None
