import os

# Resolves to the parent directory (root of the project)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

CONFIG_FILE    = os.path.join(BASE_DIR, "config.json")
DB_FILE        = os.path.join(BASE_DIR, "lab.db")
SCHEMA_VERSION = 3
EXPORT_DIR     = os.path.join(BASE_DIR, "exports")


TEMAS = {
    "default": {"bg": "#1E1F22", "fg": "#FFFFFF", "field": "#282A2E", "select": "#404249",
                "ativo_bg": "#2A3B5A", "row_a": "#2B2D31", "row_b": "#25272B"},
}

COL_NAMES = ("Nome", "Matrícula", "Entrada", "Saída", "Tempo", "Máquina")
