# LabCTRL — Novidades

## Versão 1.1 — 16/09/2026

### Mapa Interativo de Seleção de Máquina 🗺️
- Na entrada, o bolsista agora pode ver um mapa visual do laboratório e escolher exatamente qual computador ou Mesa Livre o aluno vai ocupar.
- O sistema memoriza a posição exata da cadeira e reconstrói o estado do laboratório ao ser reiniciado, sem precisar de redes ou configurações extras.
- A funcionalidade pode ser ativada ou desativada pelo menu **Configurações → Escolher Máquina na Entrada**.

### Backups Automáticos Diários 💾
- O sistema agora realiza backup automático do banco de dados todo dia. **(Futuramente para um local seguro, para evitar incidentes de pastas home sendo apagadas do nada...)**
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

## Versão 1.2 — 20/09/2026

### Exportação e Relatórios Otimizados
- **Nova Janela de Exportação:** Os submenus de exportação foram substituídos por uma janela unificada. Agora é possível escolher o período (Hoje, Ontem, Semana, Mês) e visualizar as opções de exportar para CSV ou copiar para a área de transferência no mesmo lugar.
- **CSV Compacto:** O arquivo exportado foi reestruturado para ser mais denso e legível. O ranking de usuários agora é agrupado em blocos dispostos lado a lado.
- **Ajustes de Estatísticas:** Máquinas do tipo "Mesa Livre" (ML) foram removidas do Top 3 de uso, e o relatório passou a exibir o "Dia mais movimentado".

### Visualização de Dados e Navegação
- **Média de Visitas/Dia:** No painel Visualizar DB, o indicador acumulado de "Tempo Total" foi substituído pela "Média de Visitas/Dia", entregando uma métrica mais precisa sobre a taxa de ocupação diária do laboratório.
- **Seletor de Meses Hierárquico:** O menu de histórico na tela principal agora agrupa os meses dentro de seus respectivos anos (ex: 2026 → Setembro). O Visualizar DB também recebeu seletores independentes para Ano e Mês.
- **Correção de Foco no Linux:** Resolução de um problema crônico onde menus suspensos (meses e opções) e notificações flutuantes ficavam presos na tela sobrepondo outros aplicativos no sistema operacional.

### Configurações e Operação
- **Saída Expressa:** Adicionada uma nova preferência no menu de Configurações para desativar o aviso "Tem certeza que deseja registrar a saída?". Quando desativado, o registro de saída via teclado ou clique se torna imediato.
- **Instruções no Mapa:** Adicionado um texto auxiliar discreto no mapa interativo orientando sobre o uso das teclas numéricas e das letras "M" e "L" para seleção rápida de máquinas.
