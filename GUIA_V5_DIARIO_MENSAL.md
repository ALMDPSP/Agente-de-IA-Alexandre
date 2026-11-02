# Meu Controle de Peso V5 — Diário e mensal

- O diário é separado automaticamente por data civil em São Paulo. Cada dia novo começa com 0 kcal na dashboard, mas o banco preserva os registros anteriores.
- A API `GET /api/evolucao/resumo-mensal?mes=AAAA-MM` agrega calorias e refeições de cada dia, com base no horário America/Sao_Paulo.
- O mês pode ser selecionado na tela.
- A projeção de perda teórica só aparece se for preenchido um **gasto energético diário estimado** e somente usa dias com refeições registradas. Não é uma estimativa médica nem compara com peso real.
- Dados permanecem individuais, gravados no Neon.
- Verifique `DATABASE_URL` no Render antes de usar o app.
- Não foi realizado teste de integração com o Neon hospedado pelo usuário.
