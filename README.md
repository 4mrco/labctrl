# LabCTRL

![Python](https://img.shields.io/badge/Python-3.10+-blue.svg?logo=python&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-Database-lightgrey.svg?logo=sqlite)
![Tkinter](https://img.shields.io/badge/GUI-Tkinter-green.svg)
![License](https://img.shields.io/badge/License-MIT-yellow.svg)

Sistema de controle de acesso para laboratório universitário. Substitui o registro manual em papel e a transcrição de dados. O LabCTRL centraliza entradas, saídas e histórico em uma interface desktop, reduzindo drasticamente o trabalho manual dos bolsistas e oferecendo visibilidade em tempo real da ocupação do ambiente.

## Motivação

O controle de acesso era um procedimento manual e fragmentado: registrar no papel, transcrever para planilhas e consolidar depois. Esse fluxo gerava:

* **Inconsistência:** Erros de transcrição de nomes, matrículas e horários.
* **Atraso:** Falta de sincronia entre o registro físico e os dados na planilha.
* **Ponto Cego:** Impossibilidade de visualizar quem estava utilizando o laboratório em tempo real.
* **Retrabalho:** Desperdício de horas úteis dos bolsistas em tarefas repetitivas.

O LabCTRL resolve o problema na origem. O usuário digita apenas a matrícula no teclado numérico, e o sistema valida, formata e persiste os dados de forma autônoma em um banco local relacional.

## Engenharia e Arquitetura

O LabCTRL adota uma arquitetura modular que isola dados, lógica e interface — a base para as próximas fases de hardware e nuvem. A interface foi reescrita sob um design moderno em Dark Mode, otimizado para ambientes Linux, com rotinas básicas de auto-recuperação do banco e encerramento seguro da aplicação.

* **Desacoplamento (Core vs. UI):** Persistência de dados (SQLite) e lógica de negócio isoladas da interface gráfica (Tkinter). Alterações visuais ou de fluxo não comprometem a integridade das transações do banco.

## Funcionalidades

* **Gestão completa do ciclo de acesso:** entrada, saída, histórico e edição de registros.
* **Controle de usuários e perfis:** alunos, servidores e bolsistas, com histórico vinculado à matrícula.
* **Registro ágil:** entrada e saída em segundos via matrícula ou nome, com perfis temporários para usuários não cadastrados.
* **Dashboard em tempo real:** visão da ocupação do ambiente, com filtros por data e status de atividade.
* **Autoformatação inteligente:** correção autônoma de inputs (`1430` para `14:30`), padronização de nomes e validação de estações de trabalho.
* **Sistema de desfazer (Undo):** reversão segura de entradas, saídas, edições e remoções durante a sessão.
* **Relatórios e exportação:** geração de CSV e cópia direta formatada para planilhas, organizados por dia, semana ou mês.

## Instalação e Implantação

### Pré-requisitos

* Python 3.10 ou superior.
* Pacote `tkinter` (Debian/Ubuntu: `sudo apt install python3-tk` | Fedora-based distros: `sudo dnf install python3-tkinter`).

### Produção (Laboratório — Recomendado)

1. Acesse a aba [Releases](https://github.com/4mrco/labctrl/releases) do repositório.
2. Baixe e extraia o pacote `Source code (zip)` da versão estável mais recente.
3. Execute o inicializador:

```bash
python3 app.py
```

## Estrutura de Diretórios

```text
labctrl/
├── app.py              # Entrypoint e orquestrador principal
├── core/               # Lógica de Negócios e Dados
│   ├── config.py       # Configurações globais, constantes e tema
│   ├── database.py     # Transações SQLite e auto-recuperação
│   └── services.py     # Histórico, Undo Stack e formatação
├── ui/                 # Interface Gráfica (Tkinter)
│   ├── app_window.py   # Janela principal, event loop e binds
│   └── dialogs.py      # Popups, formulários e dashboard
└── hardware/           # Coming soon (integração com leitor RFID)
```

## Roadmap

* [x] **Atual:** Arquitetura modular, refatoração de interface e gestão de usuários.
* [ ] **Fase 2 (Cloud):** Integração com a API do Google Sheets para espelhamento e backup automatizado na nuvem.
* [ ] **Fase 3 (Hardware):** Integração serial com ESP32 para leitura de tags RFID/NFC, transformando o registro por teclado em autenticação física instantânea.


## Status

O LabCTRL está em uso ativo no laboratório e recebe melhorias incrementais baseadas na utilização diária e no feedback dos bolsistas.

## Autor e Licença

Desenvolvido por **Marco Aurélio** (@4mrco) durante a Bolsa de Iniciação Acadêmica da Universidade Federal do Ceará (UFC - Campus Sobral).

Distribuído sob a Licença MIT. Consulte o arquivo `LICENSE` para mais detalhes.
