"""
layer_registry.py

Configuration store for both filter approaches.
Pure data — no QGIS API calls.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class AttrLayerConfig:
    """A vector layer registered for attribute filtering."""
    layer_id: str    # QGIS internal layer ID
    layer_name: str  # Display name


@dataclass
class GroupConfig:
    """
    A layer tree group registered for floor-based visibility management.
    Layers within the group follow the LayerName_[FLOOR_ID] convention.
    """
    group_name: str  # Exact QGIS layer tree group name

    def to_dict(self) -> dict:
        return {'group_name': self.group_name}

    @classmethod
    def from_dict(cls, d: dict) -> GroupConfig:
        return cls(group_name=d['group_name'])


class LayerRegistry:
    """
    Central config store. Serialises to/from dict for QGIS project persistence.
    Pause state is runtime-only (not persisted).
    """

    FLOOR_LEVEL_COLUMN = 'floor_level'  # Standardised column name — never changes

    def __init__(self):
        self.attr_filter_enabled: bool = True
        self.group_filter_enabled: bool = True
        self.paused: bool = False  # runtime only, not persisted

        # Optional: layer ID of a table defining floors/levels
        # Expected columns: floor_id, label, level_label, sort_order
        self.floor_table_layer_id: Optional[str] = None

        self.attr_layers: List[AttrLayerConfig] = []
        self.groups: List[GroupConfig] = []

    # ------------------------------------------------------------------
    # Attribute filter layers
    # ------------------------------------------------------------------

    def add_attr_layer(self, layer_id: str, layer_name: str):
        if not self.get_attr_layer(layer_id):
            self.attr_layers.append(AttrLayerConfig(layer_id=layer_id, layer_name=layer_name))

    def remove_attr_layer(self, layer_id: str):
        self.attr_layers = [l for l in self.attr_layers if l.layer_id != layer_id]

    def get_attr_layer(self, layer_id: str) -> Optional[AttrLayerConfig]:
        return next((l for l in self.attr_layers if l.layer_id == layer_id), None)

    # ------------------------------------------------------------------
    # Layer group filter
    # ------------------------------------------------------------------

    def add_group(self, group_name: str):
        if not self.get_group(group_name):
            self.groups.append(GroupConfig(group_name=group_name))

    def remove_group(self, group_name: str):
        self.groups = [g for g in self.groups if g.group_name != group_name]

    def get_group(self, group_name: str) -> Optional[GroupConfig]:
        return next((g for g in self.groups if g.group_name == group_name), None)

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_dict(self) -> dict:
        return {
            'attr_filter_enabled': self.attr_filter_enabled,
            'group_filter_enabled': self.group_filter_enabled,
            'floor_table_layer_id': self.floor_table_layer_id,
            'attr_layers': [{'layer_id': l.layer_id, 'layer_name': l.layer_name}
                            for l in self.attr_layers],
            'groups': [g.to_dict() for g in self.groups],
        }

    @classmethod
    def from_dict(cls, data: dict) -> LayerRegistry:
        reg = cls()
        reg.attr_filter_enabled  = data.get('attr_filter_enabled', True)
        reg.group_filter_enabled = data.get('group_filter_enabled', True)
        reg.floor_table_layer_id = data.get('floor_table_layer_id')
        reg.attr_layers = [
            AttrLayerConfig(layer_id=d['layer_id'], layer_name=d.get('layer_name', d['layer_id']))
            for d in data.get('attr_layers', [])
        ]
        reg.groups = [GroupConfig.from_dict(d) for d in data.get('groups', [])]
        return reg
