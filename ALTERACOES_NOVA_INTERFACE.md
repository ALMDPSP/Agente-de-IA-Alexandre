# Minha Evolução IA — nova interface e registro manual

- Dashboard renovado e responsivo para iPhone / PWA.
- Novo formulário manual por alimento com nome, gramas e kcal por 100 g, até 20 itens por refeição.
- Catálogo indicativo para facilitar preenchimento; valores são aproximados e variam conforme preparo.
- Novo endpoint POST /api/evolucao/refeicao/manual: dados persistidos na mesma tabela individual no Neon.
- Endpoint GET /api/evolucao/ia/status indica quais chaves estão definidas, sem testar se funcionam.
- IA com foto e chat continuam opcionais e precisam de GEMINI_API_KEY e/ou OPENAI_API_KEY válidas.
- Rodapé com créditos solicitado.
- DATABASE_URL deve estar configurada no Render para gravar informações.
- ATENÇÃO: o registro manual não define meta calórica segura ou plano alimentar individual automaticamente.
