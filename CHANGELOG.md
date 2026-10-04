# LabCTRL — Novidades

## Versão 1.2.3 — 04/10/2026

### Robustez & Automação 🔧
- **Exportação automática do mês anterior:** O sistema agora exporta silenciosamente o CSV do mês anterior no primeiro boot em que o mês consta como não exportado. Sem popups ou cliques, o arquivo é salvo em `exports/YYYY-MM/`.
- **Duplo slot de backup (12h e 17h):** Implementação de dois backups automáticos diários rastreados de forma independente. Se o app estiver desligado em um horário, o backup é compensado no próximo boot do dia.
- **Detecção de anomalia de relógio:** Nas primeiras 15 minutos de execução, se o LabCTRL detectar que o relógio do sistema operacional está atrasado em relação ao último registro do banco, ele intercepta a entrada e exibe um alerta preventivo.
- **Proteção de Inputs (Debounce):** Implementada trava temporal de 1 segundo de alta precisão na ação de entrada para prevenir registros acidentais duplicados por cliques rápidos ou teclado.

### Interface & Experiência de Uso (UX) 🎨
- **Confirmação inteligente de Matrícula:** Matrículas não reconhecidas abrem um dialog expandido. Se o usuário corrigir a digitação para uma matrícula existente diretamente nessa tela, o sistema inteligentemente reaproveita o cadastro em vez de duplicar.
- **Timeout no Mapa Interativo:** O mapa de seleção agora conta com um temporizador de 60 segundos. Sem interação, a tela é liberada automaticamente (fallback), evitando que seleções abandonadas travem a fila.
- **Legibilidade do Mapa:** Ajuste fino nas cores das máquinas e slots de mesa livre, acompanhado de novos textos instrutivos para facilitar a leitura rápida pelos usuários.
- **Lembrete do Bolsista:** Nova sinalização visual integrada à interface para auxiliar o gerenciamento da rotina e troca de turnos.