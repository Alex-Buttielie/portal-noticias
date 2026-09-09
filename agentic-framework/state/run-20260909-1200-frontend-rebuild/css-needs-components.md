# CSS needs — agente components (run 20260909-1200-frontend-rebuild)

Classes novas referenciadas pelos componentes deste agente que **não existem**
em `frontend/app/globals.css`. Todas já têm fallback inline no JSX, então o
visual funciona mesmo antes do shell incluí-las — incluí-las só remove a
necessidade do inline e unifica o sistema.

## Pedidas (sugestão de regra)

```css
/* SearchBar em pílula — usada como `class="busca busca--pill"". */
.busca--pill .busca__campo { border-radius: var(--raio-completo); }

/* Faixa de compartilhar fixa no detalhe — usada como `class="share-sticky"`. */
.share-sticky {
  position: sticky;
  top: 72px;
  z-index: 20;
  background: color-mix(in srgb, var(--cor-fundo) 88%, transparent);
  backdrop-filter: blur(8px);
  padding: var(--espaco-2) 0;
  margin-top: var(--espaco-3);
}

/* Capitular editorial no 1º parágrafo do detalhe — sem fallback inline possível. */
.detalhe-dropcap::first-letter {
  font-family: var(--fonte-titulo, Georgia), serif;
  font-weight: 800;
  font-size: 3.2em;
  line-height: 0.9;
  float: left;
  padding-right: 0.12em;
}
```

## Ajustes de a11y em classes existentes (opcional, fallbacks inline aplicados)

- `.botao--pequeno`: `min-height` hoje 36px → sugerido 40px (contrato exige
  40px em interativos). Botões pequenos do Data/Drawer/ShareButtons já usam
  `style={{ minHeight: 40 }}`.
- `.botao-salvar`: `min-height` hoje 36px → sugerido 40px (BotaoSalvar já usa
  `style={{ minHeight: 40 }}`).
- `.cartao-noticia__titulo`: sugerido `font-size: clamp(1.05rem, 1rem + 0.6vw, 1.3rem)`
  (títulos serifados vêm do seletor de elemento `h1,h2,h3`; clamp aplicado inline).

## Verificadas como existentes (sem ação)

`botao`, `botao--primaria/secundaria/fantasma/perigo`, `botao--pequeno/medio/grande`,
`cartao-noticia`, `cartao-noticia--destaque/compacto/horizontal`, `cartao-noticia__imagem(--grande)`,
`cartao-noticia__corpo/meta/titulo(--grande)/resumo/posicao`, `etiqueta-urgente`,
`limitar-linhas-2/3`, `carregando`, `spinner`, `esqueleto`, `esqueleto--linha(--curta)`,
`estado-vazio/erro` + `__titulo/__descricao`, `busca`, `busca__campo`,
`busca__rotulo-visualmente-oculto`, `campo`, `campo__rotulo/controle(--invalido)/dica/erro`,
`cartao-indicador*`, `tabela-wrapper`, `tabela`, `paginacao`, `visualmente-oculto`,
`drawer-fundo`, `drawer`, `drawer__cabecalho/titulo/corpo`, `compartilhar`,
`progresso-leitura(__barra)`, `secao-bloco/cabecalho/titulo/eyebrow/ver-tudo/ver-todas`,
`grade-noticias`, `card-noticia(-imagem/-corpo/-categoria/-titulo/-resumo/-meta)`,
`mais-lidas(-titulo/-lista/-item/-numero/-link/-meta/-corpo)`, `faixa-publicidade`,
`cartao-noticia__meta`, `cartao-emoji`, `info-leitura`, `artigo-corpo` (68ch),
`fluxo-leitura`, `lista-compacta`, `botao-salvar(--ativo)`, `botao-tema`,
`palette*`, `dropdown`, `dropdown-menu(--direita)`, `dropdown-item`, `modal*`,
`tabs-*`, `tooltip*`, `chip`, `chip--selecionado`, `chip-remover`, `badge*`,
`accordion-*`, `explicacao-ia*`.
