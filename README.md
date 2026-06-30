# LabCTRL

Sistema de controle de acesso para laboratório universitário, desenvolvido para substituir o processo manual de registro em papel seguido de transcrição para planilhas — um fluxo lento, repetitivo e sujeito a erros.

O LabCTRL centraliza o registro de entrada, saída e histórico de utilização em uma interface desktop simples, eliminando a etapa de transcrição manual e oferecendo visibilidade em tempo real de quem está presente no laboratório.



## Motivação

O laboratório utilizava um processo inteiramente manual: os alunos registravam entrada e saída em papel e, posteriormente, um bolsista transcrevia essas informações para uma planilha do Google Sheets.

Esse fluxo apresentava diversos problemas:

* Erros de transcrição (nomes, matrículas e horários);
* Atraso entre o registro real e os dados disponíveis na planilha;
* Impossibilidade de visualizar, em tempo real, quem estava utilizando o laboratório;
* Trabalho repetitivo e evitável para os bolsistas.

O LabCTRL resolve esse problema na origem. Os alunos registram a própria entrada utilizando um teclado dedicado, digitando apenas a matrícula, enquanto o sistema organiza automaticamente os registros e os mantém prontos para consulta, edição e exportação.

## Funcionalidades

* Registro de entrada e saída em poucos segundos, por matrícula ou por nome (para usuários sem matrícula cadastrada);
* Visualização em tempo real de quem está presente, com filtros por data e registros ativos;
* Histórico organizado por mês, com edição e remoção de registros;
* Sistema de desfazer (*Undo*) para entradas, saídas, edições e remoções durante a sessão;
* Autoformatação de horários (`1430` → `14:30`), nomes e número da máquina;
* Exportação para CSV e cópia direta dos dados para planilhas por dia, semana ou mês;
* Cadastro de alunos, servidores e bolsistas, mantendo o histórico vinculado à matrícula;
* Interface com tema claro e escuro, preservando as preferências entre execuções.

## Tecnologias

* **Python**
* **Tkinter** (interface gráfica)
* **SQLite** (armazenamento local)

## Estrutura


labctrl/
├── app.py              # Aplicação principal
├── lab.db              # Banco de dados SQLite
├── config.json         # Preferências do usuário
└── lab.log             # Registro de erros


## Status

O LabCTRL encontra-se em uso ativo no laboratório e continua recebendo melhorias incrementais baseadas na utilização diária e no feedback dos bolsistas.

## Autor

Desenvolvido por **Marco Aurélio** (@4mrco) durante a Bolsa de Iniciação Acadêmica da Universidade Federal do Ceará (UFC), com o objetivo de modernizar e simplificar o processo de controle de acesso do laboratório.
