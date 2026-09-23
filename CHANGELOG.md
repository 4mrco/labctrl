# LabCTRL — Novidades

## Versão 1.2.2 — 22/09/2026

### Correções de Estabilidade 🔧

- **Servidores com identidade própria:** Corrigido um problema em que múltiplos servidores registrados pelo mesmo fluxo de entrada (sem matrícula) collidiam em uma única sessão. Cada servidor agora recebe uma matrícula interna única e não interfere com outros.
- **Órfãos corrigidos silenciosamente:** Registros de dias anteriores sem saída são encerrados automaticamente ao iniciar o sistema, sem exibir um popup de confirmação. Uma notificação discreta aparece e a reversão está disponível via Ctrl+Z.
- **Ordem cronológica dos meses:** Corrigida a ordenação do seletor de meses para que anos diferentes sejam ordenados corretamente.
- **Inicialização sem conflitos:** As verificações de inicialização (exportação pendente, registros órfãos, novidades) agora são executadas em sequência para evitar sobreposição de janelas.
- **Foco de teclado restaurado:** Resolvido o roubo intermitente de foco no Linux entre transições de janelas modais. Digitar a máquina agora funciona sempre de primeira após usar o registro manual.

### Melhorias Gerais ⚙️

- **Feedback visual de saída:** Ao registrar a saída de um usuário que já estava dentro do laboratório, uma notificação (toast) cinza-azulada agora aparece na tela para confirmar a ação visualmente.
- **Reset do seletor de máquina:** O seletor de máquinas agora retorna automaticamente para o estado vazio ("-") logo após o registro bem-sucedido de qualquer entrada, agilizando o atendimento ao próximo usuário.
