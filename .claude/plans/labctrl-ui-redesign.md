# LabCTRL UI Redesign Plan

## Context
The current Tkinter interface packs everything into a single horizontal line with no visual hierarchy. The goal is to transform it into a modern Linux desktop productivity app (GNOME/Ubuntu style) resembling Cockpit, Portainer, or Proxmox dashboards while preserving all functionality.

## Critical Files to Modify
- `/home/aluno/labctrl/app.py` - Main UI code (all changes here)

## Implementation Approach

### 1. Define Modern Theme Constants (lines 52-57)
Update `TEMAS` to include font sizes, border radius hints, and modern color palette:
```python
TEMAS = {
    "dark": {
        "bg": "#242424", "fg": "#e0e0e0",
        "card_bg": "#2d2d2d", "card_fg": "#ffffff",
        "accent": "#4a90d9", "ativo_bg": "#1a4d8c",
        "header_bg": "#2a2a2a", "border": "#404040"
    },
    "light": {...}
}
```

### 2. Redesign `_build_ui()` - Top Bar & Dashboard (lines 462-531)

**Top Bar Structure:**
- Row 1: App title (left) + Clock (right) + Menu button (right)
- Row 2: Dashboard cards in a horizontal flow (with gap)
- Row 3: Entry section with proper grid alignment

**Dashboard Cards:**
- Use `tk.Frame` with styled `tk.Label` for metrics
- CSS-style card appearance: padded, subtle border, accent color
- Larger font (14-16pt bold)

**Entry Section:**
- Use `tk.Grid` for proper alignment
- Labels left, entries right, consistent padding
- Primary action button styled as accent color

### 3. Redesign `_build_ui()` - Filters (lines 510-523)

Replace filter buttons with modern segmented control:
- Use `ttk.Frame` container with internal padding
- Equal-width buttons using grid
- Active state shows accent background
- Add "Todos" instead of "Mês" (per spec)

### 4. Redesign `_rebuild_abas()` - Modern Tabs (lines 632-686)

- Keep `ttk.Notebook` but heavily style it
- Increase tab padding (16x8)
- Use segmented/tab styling with no bottom border
- Add subtle hover effects via style.map

### 5. Redesign `_atualizar_lista()` - Modern Table (lines 972-1014)

Add to table styling:
- Row height: `tree.rowconfigure(height=28)`
- Alternating row colors via tags
- Hover effect: bind `<Motion>` for temporary tag change
- Active records: keep accent background
- Larger font via ttk.Style

### 6. Modern Status Bar (lines 528-531)

- Add static hint text on the right
- Style with theme-integrated background
- Font size 10 for subtlety

### 7. Add Helper Methods

- `_create_card(parent, title, value)` - reusable dashboard card
- `_apply_modern_styles()` - centralized style configuration
- Font constants: `FONT_TITLE`, `FONT_CARD`, `FONT_DEFAULT`

## Verification
- Run the application: `python3 /home/aluno/labctrl/app.py`
- Verify:
  1. All tabs display correctly
  2. Entry flow works (matrícula, máquina, bolsista)
  3. Filter buttons change view
  4. Double-click opens edit dialog
  5. Backspace/Delete for saida works
  6. Menu actions work
  7. Theme toggle works
  8. Dashboard updates in real-time