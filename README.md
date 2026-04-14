# Floor Navigator — QGIS Plugin

A QGIS plugin for navigating multi-floor building plans, replacing the traditional workflow of managing separate PDF or CAD files for each floor level.

This plugin is a significant evolution of [rbraggaar/floor-plan-filter](https://github.com/rbraggaar/floor-plan-filter), extending the original attribute filter concept with a second strategy for raster and per-floor layer management, combined level support, a full configuration UI, and project persistence.

> **Note:** This plugin was developed with AI assistance (Claude, Anthropic) for code generation and architecture design.

---

## Features

- **Attribute Filter** — dynamically applies a `floor_level` subset filter to registered vector layers when the active floor changes. No manual filter management required.
- **Layer Group Filter** — shows and hides layers within registered layer tree groups based on a `_[FLOOR_ID]` layer naming convention. Works with rasters, georeferenced PDFs, and any per-floor layer structure.
- **Combined Levels** — multiple floor IDs can be grouped into a single navigable level (e.g. `L2N` + `L2S` = "Level 2") and activate together.
- **Dock panel** — level dropdown, Previous/Next buttons, Pause/Resume, and Configure. Keyboard shortcuts: `Page Down` / `Page Up`.
- **Pause mode** — freezes all plugin activity so you can make manual filter adjustments, then resumes cleanly.
- **Edit state protection** — blocks floor switching if any registered layer is in edit mode, with a clear warning message.
- **Default level** — configurable level activated automatically when the project is opened.
- **Floor table source** — optionally load floor definitions from a database table layer instead of entering them manually.
- **CSV backup/restore** — export and import the complete plugin configuration (floors, layers, groups) as a CSV file. Import auto-matches layers and groups by name with no manual clicking required.
- **Project persistence** — all configuration is stored in the QGIS project file.

---

## Requirements

- QGIS 3.16 or later
- Python 3.9+

---

## Installation

### From ZIP
1. Download the latest release ZIP from the [Releases](https://github.com/skoodleedoo/floor-plan-filter/releases) page
2. In QGIS: **Plugins → Manage and Install Plugins → Install from ZIP**
3. Select the downloaded ZIP and click **Install Plugin**

### From source
1. Clone this repository into your QGIS plugins folder:
   ```bash
   cd ~/.local/share/QGIS/QGIS3/profiles/default/python/plugins
   git clone https://github.com/skoodleedoo/floor-plan-filter floor_navigator
   ```
2. Restart QGIS and enable the plugin via **Plugins → Manage and Install Plugins**

---

## Quick Start

1. Open **⚙ Configure** from the Floor Navigator dock panel
2. In the **Floors & Levels** tab, define your floors — label, floor IDs, and bottom-up order
3. In the **Attribute Filter** tab, tick any vector layers that have a `floor_level` column
4. In the **Layer Group Filter** tab, tick any layer tree groups whose layers follow the `LayerName_[FLOOR_ID]` naming convention
5. Click **Apply** or **OK**
6. Use the dock panel dropdown or Previous/Next buttons to switch floors

See [DOCUMENTATION.md](DOCUMENTATION.md) for full configuration instructions.

---

## Data Conventions

### Attribute Filter
Vector layers must have a column named exactly `floor_level`. Values must match the Floor IDs defined in the plugin (e.g. `GF`, `L1`, `B1`).

### Layer Group Filter
Layers inside registered groups must be named with a `_[FLOOR_ID]` suffix:
```
ArchitecturalPlan_GF
ArchitecturalPlan_L1
ArchitecturalPlan_L2N
```
The plugin uses the text after the last underscore as the floor ID. Layers with no recognisable suffix are left visible on all floors.

### Floor Table Source
If floor definitions are maintained in a database, the plugin can load them from a table layer with these columns:

| Column | Type | Description |
|---|---|---|
| `floor_id` | text | Floor ID code |
| `label` | text | Human-readable floor name |
| `level_label` | text | Level grouping label |
| `sort_order` | integer | Bottom-up ordering |

---

## Differences from floor-plan-filter

| Feature | floor-plan-filter | Floor Navigator |
|---|---|---|
| Attribute filter | ✓ | ✓ |
| Layer group visibility | — | ✓ |
| Combined levels | — | ✓ |
| Configuration UI | Basic | Full tabbed dialog |
| Floor table source | — | ✓ |
| CSV backup/restore | — | ✓ |
| Project persistence | — | ✓ |
| Default level on open | — | ✓ |
| Pause/resume | — | ✓ |
| Edit state protection | — | ✓ |
| Keyboard shortcuts | — | Page Up / Page Down |

---

## Contributing

Pull requests are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md) for architecture notes.

---

## Licence

GPL-3.0 — see [LICENSE](LICENSE) for details.
