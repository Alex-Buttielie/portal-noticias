# Spec: Credenciamento de Jornalistas

## Contexto de negócio
BRD seção 13 (Credenciamento de Jornalistas) e seção 14 (Poderes do Autor Credenciado). Pré-requisito para `comunidade-blog.md` — só autor credenciado pode publicar opinião/análise.

## Problema / oportunidade
Sem um fluxo de credenciamento, não há como diferenciar jornalistas de usuários comuns, nem controlar quem ganha poder de publicação editorial — risco de credibilidade e de moderação (BRD §13, §14).

## Histórias de usuário
- Como usuário, eu quero solicitar credenciamento como jornalista, anexando meu diploma/documento comprobatório, para poder publicar análises/opiniões.
- Como administrador, eu quero revisar solicitações em uma fila, aprovar/reprovar/pedir informação adicional, para controlar a qualidade de quem publica.
- Como jornalista aprovado, eu quero ter um selo visível no meu perfil, para que leitores saibam que sou credenciado.

## Requisitos funcionais
1. Solicitação de credenciamento: cadastro profissional básico (cidade/UF, foto opcional, mini bio, dados profissionais) + upload de documento comprobatório (PDF ou imagem, formato configurável pelo admin).
2. Fila administrativa de análise, ordenada por data/hora da solicitação.
3. Admin pode aprovar, reprovar ou solicitar informação adicional — decisão registra o administrador responsável.
4. Prazo operacional de referência: decisão em até 24h após documentação válida (SLA registrado, não uma trava automática de sistema).
5. Notificação ao candidato sobre a decisão (mesmo padrão de "log/e-mail simulado" já usado em `identidade/`).
6. Usuário aprovado ganha `papel` diferenciado (`jornalista`, novo valor em `User.papel` ou um flag `credenciado=True` — ver ARCHITECTURE.md a atualizar) e selo visível.
7. Suspensão/revogação do credenciamento em caso de descumprimento das regras (referenciando `moderacao-reputacao-governanca.md`).
8. Texto explícito em qualquer selo/perfil: aprovação não significa endosso das opiniões do autor.

## Requisitos não-funcionais
- Upload de documento tratado como dado sensível (não expor publicamente a URL do documento — só acessível ao próprio candidato e a administradores).
- Auditoria de toda decisão (quem, quando, decisão).

## Fora de escopo
- Publicação de conteúdo em si (fica em `comunidade-blog.md`).
- Verificação automática/OCR do diploma — decisão é sempre humana.

## Critérios de sucesso
- Um usuário sem credencial não consegue publicar opinião/análise.
- Um administrador consegue aprovar uma solicitação e, a partir daí, o usuário publica normalmente.

## Questões em aberto
- Formato(s) de arquivo aceitos por padrão (PDF apenas, ou também imagem) — parametrizável, valor inicial a definir com produto.
