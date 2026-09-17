# LabCTRL — Novidades

## Versão 1.1 — 16/09/2026

### Mapa Interativo de Seleção de Máquina 🗺️
- Na entrada, o bolsista agora pode ver um mapa visual do laboratório e escolher exatamente qual computador ou Mesa Livre o aluno vai ocupar.
- O sistema memoriza a posição exata da cadeira e reconstrói o estado do laboratório ao ser reiniciado, sem precisar de redes ou configurações extras.
- A funcionalidade pode ser ativada ou desativada pelo menu **Configurações → Escolher Máquina na Entrada**.

### Backups Automáticos Diários 💾
- O sistema agora realiza backup automático do banco de dados todo dia. **(Para evitar incidentes de pastas home sendo apagadas do nada...)**
- São mantidas as últimas **5 cópias** automaticamente. Cópias mais antigas são removidas sem intervenção manual.
- Se o sistema ficar um dia ou mais sem abrir, o backup atrasado é realizado automaticamente na próxima inicialização.
- O backup pode ser forçado manualmente pelo painel de **Configurações → Gerar Agora**. 

### Painel de Configurações ⚙️
- Um menu de configurações foi criado com um layout mais limpo.
- Agora é possível **abrir a pasta de exportações e a pasta de backups** diretamente pelo gerenciador de arquivos, sem precisar navegar manualmente.
- A data do último backup é exibida na própria tela, e é possivel fazer backup manualmente.

### Correções e Melhorias 🔧
- Corrigido erro em que a edição de visitantes sem matrícula não era salva corretamente.
- Corrigido o formato das pastas de exportação (agora seguem o padrão `Ano-Mês`, ex.: `2026-09`).
- Corrigido o posicionamento dos ícones das máquinas no mapa (alinhados corretamente dentro das mesas).
- Melhorias de estabilidade geral: o sistema não fecha mais inesperadamente em situações específicas de registro.
