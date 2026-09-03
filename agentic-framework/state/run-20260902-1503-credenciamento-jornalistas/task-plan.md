# Task Plan — 20260902-1503-credenciamento-jornalistas

## Metadados
- **run_id:** 20260902-1503-credenciamento-jornalistas
- **Solicitado por:** usuário ("prossiga direto até terminar todo o MVP... finalizar a implementação de todos os requisitos do BRD")
- **Spec de origem:** `agentic-framework/specs/credenciamento-jornalistas.md`

## Nota sobre o formato deste e dos próximos runs
Dado o volume de trabalho restante (8 módulos do BRD ainda sem código), este e os próximos `task-plan.md` desta leva são mais concisos que os dos 5 módulos do MVP — o essencial (escopo, critérios de aceite, riscos) é mantido, mas sem repetir extensivamente o raciocínio já registrado nos runs anteriores (ex: a limitação de ferramentas de execução é a MESMA de todos os runs desde `20260902-0727-ingestao-noticias` — não repetida em detalhe a cada run novo).

## Objetivo
App Django `credenciamento` novo: fluxo completo de solicitação → fila administrativa → decisão (aprovar/reprovar/pedir informação) → selo de jornalista credenciado, consumível por `comunidade-blog.md` para checar quem pode publicar.

## Escopo
### Dentro
- `SolicitacaoCredenciamento` (dados profissionais + upload de documento) e `PerfilJornalista` (selo ativo, suspensão).
- Fila admin com decisão registrada (quem, quando, motivo).
- Endpoint de solicitação (usuário autenticado) e de consulta do próprio status.
- Notificação de decisão (reaproveita `EMAIL_BACKEND` já configurado).
- Suporte a suspensão/revogação (usado depois por `moderacao-reputacao-governanca.md`).

### Fora
- Publicação de conteúdo (fica em `comunidade-blog.md`).
- OCR/verificação automática de documento.
- Frontend (backend primeiro, mesma decisão já tomada para os módulos do MVP).

## Suposições assumidas
- **Upload de arquivo:** `MEDIA_ROOT`/`MEDIA_URL` ainda não configurados no projeto — vou adicionar (`backend/media/`, servido em dev via `static()` no `urls.py`, padrão Django). Documento nunca exposto publicamente — só via endpoint autenticado que checa se é o próprio usuário ou um admin.
- **`papel` do `User` não é alterado** por este módulo — credenciamento é um dado separado (`PerfilJornalista`), não um novo valor de `papel` (evita conflito com a semântica free/premium/admin já usada por `gating`).

## Critérios de aceite (técnicos, testáveis)
1. Usuário autenticado envia solicitação com documento; fica com status `pendente`.
2. Admin vê fila ordenada por data, aprova/reprova/pede informação — decisão registrada com autor e motivo.
3. Aprovação cria `PerfilJornalista(selo_ativo=True)`; reprovação não cria perfil.
4. Endpoint `GET /api/credenciamento/minha-solicitacao/` retorna o status atual ao próprio usuário.
5. Documento anexado só é acessível pelo próprio solicitante ou por admin (nunca por outro usuário comum).
6. Suspender um `PerfilJornalista` (`suspenso=True`) é possível via admin/serviço, com motivo registrado.
7. Usuário sem `PerfilJornalista` ativo (ou suspenso) não passa numa checagem `pode_publicar(user)` exposta para outros módulos usarem.

## Riscos
| Risco | Mitigação |
|---|---|
| Upload de arquivo é uma superfície nova (MEDIA config, storage) nunca testada nesta sessão | Usar `FileSystemStorage` padrão do Django, sem dependência externa nova |
| Mesma indisponibilidade de execução desde `20260902-0727-ingestao-noticias` | Mesma disciplina de leitura manual cuidadosa já aplicada nos módulos anteriores |
