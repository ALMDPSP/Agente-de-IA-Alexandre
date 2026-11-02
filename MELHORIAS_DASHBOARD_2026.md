# Dashboard e IA por usuário

- Dashboard de evolução: diferença do peso inicial, distância da meta, refeições da semana, total de pesagens, histórico de conversas e calorias médias estimadas por foto.
- Histórico dos últimos 60 chats por conta (mostrar 20) e botão de excluir. As conversas passam a ser armazenadas no banco; atenção à privacidade.
- Teste de conexão de IA no painel Minha IA, consome uma pequena requisição real do provedor.
- A configuração de IA é vinculada ao ID da conta, associado ao e-mail cadastrado. Google Login não concede chaves de API automaticamente.
- Corrigido acesso de usuários comuns à rota /configurar-ia e /api/minha-ia.
- O fallback automático não está ativado: usar outro provedor sem autorização explícita poderia gerar cobrança ou exposição de dados.
- O dashboard mostra apenas estimativas de energia, não valida o consumo real de calorias.
- Configurar DATABASE_URL e AI_CREDENTIALS_KEY estável no Render; não publicar segredos em Git.
