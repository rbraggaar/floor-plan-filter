"""
floor_model.py

Core data model for Floor Navigator.

Hierarchy:
    FloorID    — atomic identifier matching 'floor_level' column values and _[FLOOR_ID] suffixes
    Level      — one or more FloorIDs that activate together (e.g. L2N + L2S = "Level 2")
    FloorModel — ordered list of Levels (bottom-up), tracks active and default level
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class FloorID:
    id: str  # e.g. 'GF', 'L1', 'B1', 'L2N'

    def __post_init__(self):
        if not self.id or not self.id.replace('_', '').isalnum():
            raise ValueError(f"Invalid FloorID: '{self.id}'. Must be alphanumeric (underscores allowed).")

    def __hash__(self):
        return hash(self.id)

    def __eq__(self, other):
        if isinstance(other, FloorID):
            return self.id == other.id
        return self.id == other

    def __repr__(self):
        return f"FloorID({self.id!r})"


@dataclass
class Level:
    """
    A navigable level — one or more FloorIDs that always display together.

    Single floor:   Level(label='Ground Floor', floor_ids=['GF'])
    Combined level: Level(label='Level 2',      floor_ids=['L2N', 'L2S'])
    """
    label: str
    floor_ids: List[str]

    def __post_init__(self):
        if not self.label:
            raise ValueError("Level label cannot be empty.")
        if not self.floor_ids:
            raise ValueError(f"Level '{self.label}' must have at least one floor ID.")
        self.floor_ids = [f.id if isinstance(f, FloorID) else str(f) for f in self.floor_ids]

    @property
    def is_combined(self) -> bool:
        return len(self.floor_ids) > 1

    def contains(self, floor_id: str) -> bool:
        return floor_id in self.floor_ids

    def sql_filter(self, column: str = 'floor_level') -> str:
        """
        Build a SQL subset string for this level.
        Always uses IN (...) for consistency.
        e.g.  "floor_level" IN ('GF')
              "floor_level" IN ('L2N','L2S')
        """
        safe_col = column.replace('"', '""')
        values = ','.join(f"'{fid.replace(chr(39), chr(39)*2)}'" for fid in self.floor_ids)
        return f'"{safe_col}" IN ({values})'

    def to_dict(self) -> dict:
        return {'label': self.label, 'floor_ids': list(self.floor_ids)}

    @classmethod
    def from_dict(cls, d: dict) -> Level:
        return cls(label=d['label'], floor_ids=d['floor_ids'])

    def __repr__(self):
        return f"Level({self.label!r}, {self.floor_ids})"


class FloorModel:
    """
    Ordered list of Levels (bottom-up, index 0 = lowest).
    Tracks the active level and the default level applied on project open.
    """

    def __init__(self):
        self._levels: List[Level] = []
        self._active_index: int = 0
        self._default_index: int = 0

    # ------------------------------------------------------------------
    # Population
    # ------------------------------------------------------------------

    def set_levels(self, levels: List[Level]):
        self._levels = list(levels)
        n = max(0, len(self._levels) - 1)
        self._active_index  = min(self._active_index,  n)
        self._default_index = min(self._default_index, n)

    def clear(self):
        self._levels.clear()
        self._active_index = 0
        self._default_index = 0

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    @property
    def active_level(self) -> Optional[Level]:
        if not self._levels:
            return None
        return self._levels[self._active_index]

    @property
    def active_index(self) -> int:
        return self._active_index

    def set_active_index(self, index: int) -> bool:
        if 0 <= index < len(self._levels):
            self._active_index = index
            return True
        return False

    def set_active_by_label(self, label: str) -> bool:
        for i, level in enumerate(self._levels):
            if level.label == label:
                self._active_index = i
                return True
        return False

    def go_up(self) -> bool:
        if self._active_index < len(self._levels) - 1:
            self._active_index += 1
            return True
        return False

    def go_down(self) -> bool:
        if self._active_index > 0:
            self._active_index -= 1
            return True
        return False

    # ------------------------------------------------------------------
    # Default level
    # ------------------------------------------------------------------

    @property
    def default_index(self) -> int:
        return self._default_index

    def set_default_index(self, index: int) -> bool:
        if 0 <= index < len(self._levels):
            self._default_index = index
            return True
        return False

    def set_default_by_label(self, label: str) -> bool:
        for i, level in enumerate(self._levels):
            if level.label == label:
                self._default_index = i
                return True
        return False

    def apply_default(self):
        """Snap active level to the configured default. Called on project open."""
        self._active_index = min(self._default_index, max(0, len(self._levels) - 1))

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    @property
    def levels(self) -> List[Level]:
        return list(self._levels)

    @property
    def labels(self) -> List[str]:
        return [lv.label for lv in self._levels]

    @property
    def count(self) -> int:
        return len(self._levels)

    def level_at(self, index: int) -> Optional[Level]:
        if 0 <= index < len(self._levels):
            return self._levels[index]
        return None

    def all_floor_ids(self) -> List[str]:
        ids = []
        for lv in self._levels:
            ids.extend(lv.floor_ids)
        return ids

    def level_for_floor_id(self, floor_id: str) -> Optional[Level]:
        for lv in self._levels:
            if lv.contains(floor_id):
                return lv
        return None

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_dict(self) -> dict:
        return {
            'levels': [lv.to_dict() for lv in self._levels],
            'active_index': self._active_index,
            'default_index': self._default_index,
        }

    @classmethod
    def from_dict(cls, data: dict) -> FloorModel:
        model = cls()
        levels = [Level.from_dict(d) for d in data.get('levels', [])]
        model.set_levels(levels)
        n = max(0, len(levels) - 1)
        model._default_index = min(data.get('default_index', 0), n)
        model._active_index  = min(data.get('active_index',  0), n)
        return model
