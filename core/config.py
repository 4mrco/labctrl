import os

# Resolves to the parent directory (root of the project)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

CONFIG_FILE    = os.path.join(BASE_DIR, "config.json")
DB_FILE        = os.path.join(BASE_DIR, "lab.db")
SCHEMA_VERSION = 3
EXPORT_DIR     = os.path.join(BASE_DIR, "exports")

BOLSISTAS_INICIAIS = [
    "Francisco Jônathan Lima Paula", "Raimundo Nonato Odilson",
    "Antônio Francisco Gomes de Oliveira", "Pedro Carolino Neto",
    "Gustavo Emanoel Dutra", "Antonio Martins Neto",
    "Francisco Breno Gomes Melo", "Samara Nascimento de Lima",
    "Sabrina Nascimento de Lima", "Anna Alícya Magalhães Cruz",
    "João Pedro Batista Barbosa", "Pedro Rian Martins Fialho",
    "Vinícius Cavalcante Marques", "Luiz Miguel Rodrigues de Souza",
    "Caio Bendó de Lima", "Andrey Barbosa",
    "Edmilson Felipe Pereira Almeida", "Mateus Fernandes Sousa",
    "João Pedro Sousa Marques", "Daniel de Araujo", "Marco Aurelio",
]

TEMAS = {
    "dark":  {"bg": "#1E1F22", "fg": "#FFFFFF", "field": "#313338", "select": "#404249",
              "ativo_bg": "#2A3B5A", "row_a": "#2B2D31", "row_b": "#25272B"},
    "light": {"bg": "#F5F5F5", "fg": "#000000", "field": "#FFFFFF", "select": "#E0E0E0",
              "ativo_bg": "#D0E0F0", "row_a": "#FFFFFF", "row_b": "#F8F8F8"},
}

COL_NAMES = ("Nome", "Matrícula", "Entrada", "Saída", "Tempo", "Máquina")
