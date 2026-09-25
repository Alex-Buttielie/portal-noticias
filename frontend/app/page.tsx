import type { Metadata } from "next";
import Link from "next/link";
import { SITE_DESCRIPTION, SITE_NAME } from "@/lib/site";
import {
  obterDestaquesDia,
  obterFeed,
  obterMaisLidas,
  obterUrgentes,
  ApiError,
  type EntradaRanqueda,
  type FeedEntrada,
  type MetadadosResposta,
} from "@/lib/api";
import { carregarHome } from "@/lib/recomendacao";
import { carregarColunistas, type Colunista } from "@/lib/colunistas";
import {
  formatarIdade,
  lerConteudoReal,
  registrarConteudoReal,
  JANELA_STALE_MS,
} from "@/lib/ultimo-conteudo-real";
import { HomeClient } from "@/components/HomeClient";
import { DestaquesDia } from "@/components/DestaquesDia";

export const metadata: Metadata = {
  title: SITE_NAME,
  description: SITE_DESCRIPTION,
};

export const revalidate = 60;

/**
 * `true` durante o `next build` (geração estática) e `false` em runtime.
 *
 * POR QUE ISSO EXISTE — e por que não é um contorno: sem esta guarda, a falha
 * "sem último conteúdo real" repropaga durante a geração estática e o
 * `next build` INTEIRO falha ("Export encountered errors on following paths:
 * /page: /"). O job `frontend-build` do CI roda `npm run build` sem nenhum
 * serviço de backend (`.github/workflows/ci.yml`), então a Home lá não teria
 * como ter conteúdo real — e um build vermelho por isso seria um falso
 * alarme que treina a equipe a ignorar o gate. O build de PRODUÇÃO roda na
 * própria VPS com o Django no ar (`.github/workflows/deploy.yml:302-312`), e
 * é lá que a degradação évidenciada.
 *
 * Em runtime a falha NÃO é engole: ela repropaga e o `error.tsx` mostra a tela
 * de recuperação com código de suporte. O valor é defensivo: se o Next mudar a
 * fase, o default (não é build) mantém o comportamento correto em produção.
 */
function emFaseDeBuild(): boolean {
  return process.env.NEXT_PHASE === "phase-production-build";
}

// Densidade editorial da Home: busca página cheia do backend (page_size 60)
// para alimentar Manchetes + Últimas + Em Alta + Bombando + Portfólio sem
// limite arbitrário pequeno no cliente.
const PAGE_SIZE_HOME = 60;

const CHAVE_ULTIMO_BOM = "home";

/**
 * Conteúdo que a Home exibe, e de onde ele veio.
 *
 * `origem` é o que o usuário vê sinalizado:
 * - "real"      — resposta real do backend nesta renderização;
 * - "stale"     — último conteúdo REAL gravado, dentro da janela de 5 min;
 * - "indisponivel" — não há nada real; a Home diz isso em vez de inventar.
 *
 * NÃO existe array de exemplo nesta página (critérios 11 e 12). Antes havia
 * `MOCK`, consultado quando o `catch` de `lib/recomendacao.ts` devolvia lista
 * vazia — e o fictício ainda "assar" no output estático, porque
 * `obterFeed`/`carregarHome` são fetch com `revalidate` e a falha de
 * revalidação servia a página anterior em HTML.
 */
interface DadosHome {
  feed: FeedEntrada[];
  urg: FeedEntrada[];
  maisLidas: FeedEntrada[];
  destaques: EntradaRanqueda[];
  colunistas: Colunista[];
  origem: "real" | "stale" | "indisponivel" | "sem-dado-real";
  idadeMs: number | null;
  /** Estado operacional declarado pelo backend no header da resposta. */
  degradadoBackend: boolean;
  requestId: string | null;
}

function agora(): number {
  return Date.now();
}

async function getData(): Promise<DadosHome> {
  // Holder em vez de `let`: a atribuição acontece dentro de um callback, e o
  // TypeScript não acompanha narrowed `let` escrito por função — com o holder a
  // leitura continua tipada e não degenera para `never`.
  const resposta: { metadados: MetadadosResposta | null } = { metadados: null };
  try {
    // FRENTE 3 — feed ranqueado pelo backend (curadoria/popularidade/
    // personalização/tendência/recência + overrides, sem repetição).
    const [home, urg, lidas, destaques, colunistas] = await Promise.all([
      carregarHome(10, { onResposta: (m) => { resposta.metadados = m; } }),
      obterUrgentes(8).catch(() => [] as FeedEntrada[]),
      obterMaisLidas(10).catch(() => [] as FeedEntrada[]),
      obterDestaquesDia({ limite: 5 }).catch(() => [] as EntradaRanqueda[]),
      carregarColunistas(4),
    ]);

    let lista = home.feed;
    if (!lista.length) {
      // O feed ranqueado voltou vazio. Um feed paginado "pleno" é a segunda
      // fonte real; se também vier vazio, a base está realmente sem conteúdo
      // (não é falha) e isso é um estado legítimo — não um erro.
      const feed = await obterFeed({ page_size: PAGE_SIZE_HOME }).catch(() => null);
      lista = feed?.results ?? [];
    }

    if (lista.length) {
      registrarConteudoReal(CHAVE_ULTIMO_BOM, lista);
      return {
        feed: lista,
        urg: urg.length ? urg : lista.filter((x) => x.urgente),
        maisLidas: lidas,
        destaques,
        colunistas,
        origem: "real",
        idadeMs: null,
        degradadoBackend: resposta.metadados?.operacional === "degraded",
        requestId: resposta.metadados?.requestId ?? null,
      };
    }

    // Resposta real e vazia: não há o que salvar como "último bom" (salvar
    // lista vazia faria a janela seguinte servir "nada" como se fosse conteúdo).
    return {
      feed: [],
      urg: [],
      maisLidas: lidas,
      destaques,
      colunistas,
      origem: "indisponivel",
      idadeMs: null,
      degradadoBackend: resposta.metadados?.operacional === "degraded",
      requestId: resposta.metadados?.requestId ?? null,
    };
  } catch (erro) {
    // Falha real do backend. Só agora se recorre ao último conteúdo real, e
    // somente dentro da janela de 5 min (critério 10).
    const velho = lerConteudoReal<FeedEntrada>(CHAVE_ULTIMO_BOM, JANELA_STALE_MS, agora());
    const requestId = erro instanceof ApiError ? erro.requestId : null;
    if (velho) {
      return {
        feed: velho.itens,
        urg: velho.itens.filter((x) => x.urgente),
        maisLidas: [],
        destaques: [],
        colunistas: [],
        origem: "stale",
        idadeMs: velho.idadeMs,
        degradadoBackend: true,
        requestId,
      };
    }
    // Critério 11: sem cache válido, não existe resposta honesta que não seja
    // dizer que o serviço está fora. Nenhum conteúdo inventado, em nenhuma
    // hipótese. Em RUNTIME a falha repropaga: a resposta sai 5xx, o `error.tsx`
    // mostra a recuperação com código de suporte e o operador/monitor vê o
    // evento. Durante o `next build` (ver `emFaseDeBuild`) o mesmo estado é
    // renderizado honestamente em vez de repropagar, para não derrubar o build
    // inteiro por indisponibilidade de um serviço que não existe lá.
    if (emFaseDeBuild()) {
      return {
        feed: [],
        urg: [],
        maisLidas: [],
        destaques: [],
        colunistas: [],
        origem: "sem-dado-real",
        idadeMs: null,
        degradadoBackend: true,
        requestId: erro instanceof ApiError ? erro.requestId : null,
      };
    }
    throw erro;
  }
}

function AvisoDeDegradacao({ dados }: { dados: DadosHome }) {
  if (dados.origem === "real" && !dados.degradadoBackend) return null;
  let titulo: string;
  let descricao: string;
  if (dados.origem === "stale") {
    titulo = "Conteúdo temporariamente desatualizado";
    descricao =
      "Não conseguimos atualizar as notícias agora. Mostramos a última atualização bem-sucedida" +
      (dados.idadeMs !== null ? ` ${formatarIdade(dados.idadeMs)}` : "") +
      ".";
  } else if (dados.origem === "indisponivel") {
    titulo = "Sem notícias no momento";
    descricao =
      "A base de notícias respondeu sem nenhum item publicado. Não exibimos conteúdo de exemplo — confira o arquivo.";
  } else if (dados.origem === "sem-dado-real") {
    titulo = "Sem notícias no momento";
    descricao =
      "Não conseguimos falar com a base de notícias. Não exibimos conteúdo de exemplo — volte em instantes ou confira o arquivo.";
  } else {
    titulo = "Serviço parcialmente indisponível";
    descricao =
      "As notícias carregaram, mas alguma parte do serviço está degradada. Algumas telas podem pedir para tentar de novo.";
  }
  return (
    <div
      role="status"
      aria-live="polite"
      className="mb-6 rounded-[var(--raio-lg)] border border-[var(--cor-alerta)] bg-[var(--cor-alerta-suave)] p-4"
    >
      <p className="text-sm font-semibold text-[var(--cor-texto)]">{titulo}</p>
      <p className="mt-1 text-sm text-[var(--cor-texto-suave)]">{descricao}</p>
      <p className="mt-2 flex flex-wrap items-center gap-2 text-xs text-[var(--cor-texto-suave)]">
        <Link href="/arquivo" className="underline underline-offset-2 hover:text-[var(--cor-texto)]">
          Ver o arquivo
        </Link>
        {dados.requestId ? <span>· código de suporte: {dados.requestId}</span> : null}
      </p>
    </div>
  );
}

export default async function Page() {
  const dados = await getData();
  if (dados.origem === "sem-dado-real" || dados.origem === "indisponivel") {
    return (
      <>
        <AvisoDeDegradacao dados={dados} />
        <div className="rounded-[var(--raio-lg)] border border-dashed border-[var(--cor-borda)] p-10 text-center">
          <p className="text-sm text-[var(--cor-texto-suave)]">
            Nenhuma notícia real disponível para exibir agora. Preferimos mostrar isto a mostrar
            conteúdo inventado.
          </p>
        </div>
      </>
    );
  }
  return (
    <>
      <AvisoDeDegradacao dados={dados} />
      <DestaquesDia destaques={dados.destaques} />
      <HomeClient
        feed={dados.feed}
        urg={dados.urg}
        maisLidas={dados.maisLidas}
        colunistas={dados.colunistas}
      />
    </>
  );
}
