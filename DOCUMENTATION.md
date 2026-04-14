# Floor Navigator — QGIS Plugin

## Overview

Floor Navigator is a QGIS plugin that lets you work with multi-floor building plans directly in QGIS, replacing the traditional workflow of managing separate PDF or CAD files for each floor level.

When you switch floors in the dock panel, the plugin automatically updates what you see on the map — filtering vector layers to show only features on the active floor, and showing or hiding raster layers for that floor. Both can happen simultaneously in the same project.

---

## Installation

1. In QGIS, open **Plugins → Manage and Install Plugins → Install from ZIP**
2. Select the `floor_navigator.zip` file
3. Click **Install Plugin**
4. The Floor Navigator panel will appear below the Layers panel on the left side of the screen

---

## Concepts

### Floor ID

A Floor ID is a short alphanumeric code that uniquely identifies a physical floor or space. Floor IDs must contain only letters, numbers, and underscores — no spaces.

Examples: `B1`, `GF`, `L1`, `L2`, `L2N`, `L2S`, `MEZZANINE`

Floor IDs are the bridge between the plugin and your data. They appear in two places:

- As values in the `floor_level` column of your vector layers (Attribute Filter)
- As suffixes in your layer names (Layer Group Filter): `WallsAndDoors_GF`, `WallsAndDoors_L1`

### Level

A Level is what you navigate between in the dock panel. Most of the time a Level contains a single Floor ID — "Ground Floor" contains `GF`. However, sometimes a building has separate spaces on the same physical level that are stored as separate floor IDs. You can group these into a combined Level so they always display together.

**Example:** A building where Level 2 is split into North and South wings, stored as `L2N` and `L2S`, can be configured as a single Level called "Level 2" containing both IDs. When you select Level 2, both sets of features and layers become visible simultaneously.

### Attribute Filter

The Attribute Filter approach works with vector layers (points, lines, polygons) that have a `floor_level` column. This column stores the Floor ID for each feature.

When you switch floors, the plugin automatically applies a query filter to all registered layers:

```sql
"floor_level" IN ('L2')
"floor_level" IN ('L2N','L2S')   -- combined level
```

Features on other floors are hidden — they are not deleted, just filtered. The filter is removed or updated whenever you switch floors or unpause the plugin.

**Requirements:**
- Column name must be exactly `floor_level` (standardised)
- Values must match the Floor IDs defined in the plugin configuration

### Layer Group Filter

The Layer Group Filter approach works with any layer type — including rasters such as georeferenced PDFs or image exports from CAD. It uses layer visibility rather than attribute filtering.

Layers within a registered group must follow the naming convention:

```
LayerName_[FLOOR_ID]
```

The plugin reads the suffix after the last underscore to determine which floor each layer belongs to. When you switch floors, it shows layers whose suffix matches the active floor and hides all others within the group.

**Examples:**
```
ArchitecturalPlan_GF     → shown when active floor is GF
ArchitecturalPlan_L1     → shown when active floor is L1
ArchitecturalPlan_L2N    → shown when active floor is L2N or L2S (combined level)
SitePlan                 → no suffix — left visible on all floors
```

Layers with no recognisable floor suffix are treated as non-floor-specific and are always left visible.

**Requirements:**
- Layers must be inside a QGIS layer tree group
- The group must be registered in the plugin configuration
- Layer names must end with `_[FLOOR_ID]` where the Floor ID matches one defined in the plugin

---

## Quick Start

1. **Define your floors** — open Configure and set up your Floor IDs and Levels in the Floors & Levels tab
2. **Register your vector layers** — in the Attribute Filter tab, tick any layers that have a `floor_level` column
3. **Register your layer groups** — in the Layer Group Filter tab, tick any groups containing per-floor raster or vector layers
4. **Click Apply or OK**
5. **Use the dock panel** to switch floors — the map updates immediately

---

## The Dock Panel

The Floor Navigator panel sits below the Layers panel on the left side of the QGIS window.

```
┌──────────────────────────────┐
│  Active Level                │
│  [Ground Floor          ▼]   │
│  [▼ Previous] [▲ Next]       │
│  [⏸ Pause]   [⚙ Configure]  │
└──────────────────────────────┘
```

**Level dropdown** — jump directly to any defined level without stepping through floors one at a time.

**▼ Previous / ▲ Next** — move one level down or up. The buttons disable automatically at the bottom and top of the floor list. Keyboard shortcuts: `Page Down` and `Page Up`.

**⏸ Pause** — freezes all plugin activity. Filters and visibility are left exactly as they are, and you can make manual changes. When you click **▶ Resume**, all filters are cleared and reapplied from the active level.

**⚙ Configure** — opens the configuration window.

---

## Configuring Floors — Manually

Open the configuration window via the **⚙ Configure** button or **Plugins → Floor Navigator → Configure Floor Navigator**.

In the **Floors & Levels** tab:

1. Click **+ Add Level** to add a row
2. Enter a display label in the first column (e.g. `Ground Floor`)
3. Enter one or more Floor IDs in the second column, comma-separated (e.g. `GF` or `L2N, L2S` for a combined level)
4. Use **↑ Move Up** and **↓ Move Down** to set the bottom-up order — the lowest floor should be at the top of the list (row 0)
5. Set the **Default Level on Project Open** — this level will be activated automatically whenever the project is opened
6. Click **Apply** or **OK**

---

## Configuring Floors — From a Database Table

If your floor definitions are maintained in a database (PostgreSQL, GeoPackage, or any other source accessible as a QGIS layer), you can load them directly instead of entering them manually.

### Required Table Structure

Your table must have these four columns:

| Column | Type | Description |
|---|---|---|
| `floor_id` | text | The Floor ID code, e.g. `GF`, `L2N` |
| `label` | text | Human-readable floor name, e.g. `Ground Floor` |
| `level_label` | text | The Level this floor belongs to, e.g. `Level 2`. Rows sharing the same `level_label` are combined into one Level |
| `sort_order` | integer | Bottom-up ordering — lower numbers are lower floors |

**Example table:**

| floor_id | label | level_label | sort_order |
|---|---|---|---|
| B1 | Basement 1 | Basement | 10 |
| GF | Ground Floor | Ground Floor | 20 |
| L1 | Level 1 | Level 1 | 30 |
| L2N | Level 2 North | Level 2 | 40 |
| L2S | Level 2 South | Level 2 | 40 |
| L3 | Level 3 | Level 3 | 50 |

### Loading from the Table

1. Load the table as a layer in your QGIS project
2. Open **⚙ Configure**
3. In the **Floors & Levels** tab, expand **Floor Table Source**
4. Select the table layer from the dropdown
5. Click **Load Floors from Table**
6. The level list is populated automatically — rows with the same `level_label` are combined into a single Level
7. Click **Apply** or **OK**

The table layer is saved as the nominated source in the project. You can reload it anytime if the floor definitions change.

---

## Attribute Filter Configuration

In the **Attribute Filter** tab:

- **Enable Attribute Filter** checkbox turns the feature on or off globally
- The list shows all vector layers currently loaded in the project
- Tick the layers that contain a `floor_level` column and should be filtered by floor
- Use **Validate Selected Layers** to confirm all ticked layers actually have a `floor_level` column — layers without it will be flagged with a warning

Previously registered layers will already be checked when you open the dialog.

---

## Layer Group Filter Configuration

In the **Layer Group Filter** tab:

- **Enable Layer Group Filter** checkbox turns the feature on or off globally
- The list shows all layer tree groups in the current project (indented to reflect nesting)
- Tick the groups whose layers follow the `LayerName_[FLOOR_ID]` naming convention
- Use **Validate Selected Groups** to check which layers inside each ticked group match a defined Floor ID and which don't

Previously registered groups will already be checked when you open the dialog.

---

## Configuration Backup — CSV Export and Import

The CSV backup feature lets you save and restore the complete plugin configuration without having to manually re-enter floors or re-tick layers and groups.

### Exporting

1. Set up your configuration in the dialog (floors, layers, groups)
2. Click **⬆ Export Config to CSV**
3. Choose a location and filename
4. The CSV captures the current state of the dialog — including all floor definitions, the default level, the floor table source, all ticked attribute filter layers, and all ticked layer groups

### Importing

1. Open **⚙ Configure**
2. Click **⬇ Import Config from CSV**
3. Select a previously exported CSV file
4. The plugin restores floors, matches layer names and group names against what is currently loaded in the project, and ticks them automatically
5. Click **Apply** or **OK** to activate — no manual clicking required

### CSV Format

The CSV uses a single-file format with a `section` column identifying each row type:

| section | key1 | key2 | key3 | key4 |
|---|---|---|---|---|
| floor_table | Floors Table | | | |
| floor | Ground Floor | GF | 1 | default |
| floor | Level 2 | L2N, L2S | 2 | |
| attr_layer | Spaces | | | |
| attr_layer | Assets | | | |
| group | Architecture Rasters | | | |

Row types:

- `floor_table` — key1 is the layer name of the nominated floor table source
- `floor` — key1 = level label, key2 = floor IDs (comma-separated), key3 = sort order, key4 = `default` if this is the default level
- `attr_layer` — key1 = layer name as it appears in the QGIS project
- `group` — key1 = group name as it appears in the QGIS Layers panel

The CSV can be edited manually in a spreadsheet application if needed.

---

## Tips and Troubleshooting

**The floor switch is blocked with a warning**
A registered vector layer is currently in edit mode. Save your edits and exit edit mode, then switch floors.

**Layers are not filtering correctly**
Check that the `floor_level` column values exactly match the Floor IDs defined in the plugin. Values are case-sensitive.

**Group layers are not showing/hiding correctly**
Check that layer names end with `_[FLOOR_ID]` where the suffix exactly matches a defined Floor ID. The plugin uses the text after the last underscore — so `Arch_Plan_L1` matches `L1`, not `Plan_L1`.

**A layer in a group is always visible regardless of floor**
The layer name has no recognisable floor suffix, or the suffix doesn't match any defined Floor ID. The plugin intentionally leaves such layers visible as non-floor-specific content.

**The configuration is lost after closing QGIS**
Configuration is stored in the QGIS project file. Make sure you save your project after configuring the plugin.

**Importing a CSV doesn't tick any layers**
Layer and group matching is by name. Make sure the layer names and group names in the project match exactly what was in the project when the CSV was exported.
