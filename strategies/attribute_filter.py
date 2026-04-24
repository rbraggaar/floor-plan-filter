"""
strategies/attribute_filter.py

Attribute Filter: applies a subset string to registered vector layers
based on the active Level's floor IDs.

Filter format:  "floor_level" IN ('GF')
                "floor_level" IN ('L2N','L2S')
"""

from __future__ import annotations
import logging
from typing import TYPE_CHECKING, Optional

from qgis.core import QgsProject, QgsVectorLayer

if TYPE_CHECKING:
    from ..floor_model import FloorModel, Level
    from ..layer_registry import LayerRegistry

log = logging.getLogger(__name__)


class AttributeFilterStrategy:

    COLUMN = 'floor_level'

    def __init__(self, registry: LayerRegistry, model: FloorModel):
        self._registry = registry
        self._model = model

    def apply(self, level: Level):
        if not self._registry.attr_filter_enabled:
            return
        if self._registry.paused:
            return

        filter_expr = level.sql_filter(self.COLUMN)
        log.debug("Attribute filter applying: %s", filter_expr)

        for cfg in self._registry.attr_layers:
            layer = self._get_layer(cfg.layer_id)
            if layer is None:
                log.warning("Attribute filter: layer not found — %s (%s)", cfg.layer_name, cfg.layer_id)
                continue
            layer.setSubsetString(filter_expr)

    def clear_all(self):
        """Remove all managed filters. Called on unpause before reapply."""
        for cfg in self._registry.attr_layers:
            layer = self._get_layer(cfg.layer_id)
            if layer:
                layer.setSubsetString('')

    def deactivate(self):
        self.clear_all()

    @staticmethod
    def _get_layer(layer_id: str) -> Optional[QgsVectorLayer]:
        layer = QgsProject.instance().mapLayer(layer_id)
        if isinstance(layer, QgsVectorLayer):
            return layer
        return None
