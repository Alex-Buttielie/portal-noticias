"use client";

/**
 * Formulário de assinatura da newsletter + descadastro.
 *
 * Antes: `frontend/app/newsletter/page.tsx:17` tinha `<form>` sem `onSubmit`,
 * um único `<Input>` sem `name`, `<Button type="submit">` inerte e editorias
 * desenhadas como `<Badge cursor-pointer>` sem `onClick` (nada era selecionável).
 * Clicar recarregava a página e o e-mail digitado era perdido.
 *
 * Endpoints usados (ambos reais, conferidos nos `urls.py` de cada app):
 *
 * 1. Visitário AUTENTICADO → `POST /api/newsletter/inscrever/`
 *    - rota:     backend/newsletter/urls.py:8
 *    - mounted:  backend/config/urls.py:23 (`path("api/newsletter/", ...)`)
 *    - view:     backend/newsletter/views.py:9-21 — `IsAuthenticated`;
 *                corpo `{tipo, categorias, periodo}`; 201
 *                `{tipo, periodo, ativa}`; 403 com `{"detail": ...}` quando
 *                `tipo="personalizada"` sem o recurso Premium
 *                (newsletter/services.py:22-25). Só oferecemos `padrao` e
 *                `categoria`, que não são gated.
 *
 * 2. Visitante ANÔNIMO → `POST /api/landing/lista-espera/`
 *    - rota:     backend/landing/urls.py:8
 *    - mounted:  backend/config/urls.py:21
 *    - view:     backend/landing/views.py:10-34 — `AllowAny`; este é o ÚNICO
 *                registro público de e-mail que o backend expõe, já que
 *                `newsletter/inscrever/` exige token. Contrato em
 *                backend/landing/serializers.py:4-17: `nome` e `email`
 *                obrigatórios, `interesses` lista de str, `aceite_comunicacao`
 *                obrigatório.
 *
 * 3. Descadastro → `POST /api/newsletter/descadastrar/`
 *    - rota:     backend/newsletter/urls.py:9
 *    - view:     backend/newsletter/views.py:23-31 — `AllowAny`, token no corpo
 *                ou na query; 400 `{"detail": "Token inválido."}` quando não
 *                casa, o que torna o caminho de erro verificável.
 *
 * 4. Confirmação → `POST /api/newsletter/confirmar/` (double opt-in)
 *    - rota:     backend/newsletter/urls.py
 *    - view:     `newsletter.views.ConfirmarView` — `AllowAny`, mesmo throttle,
 *                e resposta 200 ÚNICA para token válido, inválido, expirado ou
 *                já usado (é o que impede o endpoint de ser um oráculo de
 *                "esta pessoa está inscrita?"). 400 só sem token nenhum.
 *
 * O CAMINHO PÚBLICO NÃO ENVIA `periodo`: esse campo só existe em
 * `newsletter/inscrever/` (backend/newsletter/models.py:28-32), então a
 * seleção de período só aparece para quem tem conta — nada é escolhido e
 * descartado em silêncio.
 *
 * OS TRÊS ESTADOS DA INSCRIÇÃO (o que mudou em 2026-10-02)
 * ========================================================
 * Antes do double opt-in, a inscrição era imediata e havia UM estado de
 * sucesso. Agora há três, e esta é a parte do formulário que mais precisava de
 * cuidado:
 *
 *   - **pendente** (`estado: "pendente"`) — o pedido foi registrado e um e-mail
 *     de confirmação foi enviado. A pessoa NÃO recebe newsletter ainda, e a
 *     mensagem precisa dizer isso, porque "Inscrição confirmada. Bom leitura!"
 *     seria mentira: ela não está confirmada.
 *   - **confirmado** (`estado: "confirmada"`) — só quando a pessoa reenvia o
 *     formulário e o clique anterior já aconteceu.
 *   - **recusado sem canal** (503) — o portal recusou e NADA foi gravado. A
 *     mensagem vem do backend e diz o que falta.
 *
 * O texto exibido é o `detail` do backend em todos os três, pelo mesmo motivo
 * que o caminho público já faz: quem sabe o que aconteceu é quem sabe o que
 * aconteceu. Este arquivo NÃO traduz nem resume a resposta — ele mostra.
 * A única decisão local é ESCOLHER A CLASSE CSS a partir do `estado`.
 */

import { useEffect, useId, useRef, useState } from "react";import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useAuth } from "@/lib/auth-context";
import * as api from "@/lib/api";
import { classeDoEstadoNewsletter } from "@/lib/estado-newsletter";

const CATS = ["geral", "política", "economia", "tecnologia", "esportes", "cultura", "saúde", "mundo", "cidades"];

/**
 * O texto de sucesso que a pessoa lê quando o backend não manda nenhum.
 *
 * Ele existe para o caso em que `detail` vier ausente — e o texto é o de
 * PENDENTE, não o de confirmada. A asimetria é deliberada: se o backend
 * responder 2xx e a UI não souber o estado, "pedido registrado, confira o
 * e-mail" continua sendo verdade (é o que o 2xx significa), enquanto
 * "inscrição confirmada" pode não ser. Entre as duaslies um texto que erra
 * para o lado de prometer demais, que é a direção perigosa.
 */
const SUCESSO_SEM_DETALHE =
  "Pedido registrado. Se a sua conta ainda não tem a newsletter, enviamos um e-mail com o link de confirmação: nada da newsletter é enviado até você clicar nele.";

function validarEmail(bruto: string): string | null {
  const email = bruto.trim();
  if (!email) return "Informe seu e-mail.";
  if (email.length > 254) return "E-mail muito longo.";
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) return "Informe um e-mail válido.";
  return null;
}

/**
 * A anotação que acompanha o estado pendente, e que some quando a inscrição
 * está confirmada.
 *
 * Sem ela, uma pessoa que acabou de se inscrever vê "Pedido registrado" e
 * fica esperando um e-mail que ela já não sabe se está chegando. Com ela, o
 * formulário diz explicitamente qual é o próximo passo e o que acontece se
 * ela não cumprir. É a diferença entre "informado" e "deixado no vácuo".
 */
function AvisoDeConfirmacaoPendente({ email }: { email: string }) {
  return (
    <p className="text-xs text-[var(--cor-texto-suave)]">
      Enviamos o link de confirmação para <span className="font-medium text-[var(--cor-texto)]">{email}</span>.{" "}
      A newsletter só começa a chegar depois do clique. Se o e-mail não chegar em alguns minutos, confira a pasta de spam.
    </p>
  );
}

export default function NewsletterForm() {
  const { token } = useAuth();
  const idEmail = useId();
  const idNome = useId();

  const [email, setEmail] = useState("");
  const [nome, setNome] = useState("");
  const [cats, setCats] = useState<string[]>([]);
  const [periodo, setPeriodo] = useState<api.PeriodoNewsletter>("manha");

  const [erroEmail, setErroEmail] = useState<string | null>(null);
  const [erroNome, setErroNome] = useState<string | null>(null);
  const [erroGeral, setErroGeral] = useState<string | null>(null);
  const [ok, setOk] = useState<string | null>(null);
  /**
   * O estado da inscrição, guardado SEPARADAMENTE da mensagem.
   *
   * A mensagem é o que a pessoa lê; o estado é o que a UI precisa para
   * escolher a cor e para o botão virar "Reenviar confirmação". Guardar os
   * dois juntos (só a mensagem) obrigaria a UI a fazer `includes` de texto
   * português para descobrir o estado — e isso quebra no dia em que alguém
   * mudar uma palavra do texto.
   */
  const [estado, setEstado] = useState<api.EstadoInscricaoNewsletter | null>(null);
  const [enviando, setEnviando] = useState(false);
  /**
   * O e-mail para quem a inscrição foi feita, guardado para o aviso de
   * pendência.
   *
   * Antes o campo era limpo depois de qualquer 2xx. Com o double opt-in isso
   * seria errado: o campo limpo some com o endereço, e o aviso "confira o
   * e-mail que enviamos para X" ficaria sem X. A pessoa não teria como
   * conferir se o e-mail chegou na caixa certa — que é a primeira coisa que se
   * pergunta quando o e-mail não chega.
   *
   * O campo de texto, em si, é limpo: repetir um endereço na tela depois de
   * inscribed é ruído — o que fica é o aviso, com o endereço que a pessoa
   * digitou.
   */
  const [emailDaInscricao, setEmailDaInscricao] = useState<string | null>(null);

  const emVoo = useRef(false);
  const refEmail = useRef<HTMLInputElement>(null);
  const refNome = useRef<HTMLInputElement>(null);
  const refGeral = useRef<HTMLParagraphElement>(null);
  const refSucesso = useRef<HTMLParagraphElement>(null);

  // Foco da região de status em `useEffect`, não logo após o `setState`: o ref
  // só existe a partir do render que monta a mensagem, então `.focus()` dentro
  // do handler veria `null` e o foco não se moveria.
  useEffect(() => {
    if (erroGeral) refGeral.current?.focus();
  }, [erroGeral]);
  useEffect(() => {
    if (ok) refSucesso.current?.focus();
  }, [ok]);

  const alternarCategoria = (c: string) => {
    if (enviando) return;
    setCats((atuais) => (atuais.includes(c) ? atuais.filter((i) => i !== c) : [...atuais, c]));
  };

  async function enviar(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (emVoo.current) return; // duplo clique → uma requisição só

    setOk(null);
    setEstado(null);
    setEmailDaInscricao(null);
    setErroGeral(null);
    setErroEmail(null);
    setErroNome(null);

    const erroDeEmail = validarEmail(email);
    if (erroDeEmail) {
      setErroEmail(erroDeEmail);
      refEmail.current?.focus();
      return;
    }
    // `nome` só é exigido no caminho público, porque é o
    // `landing/serializers.py:5` que o torna obrigatório.
    const precisaNome = !token;
    const nomeLimpo = nome.trim();
    if (precisaNome && !nomeLimpo) {
      setErroNome("Informe seu nome.");
      refNome.current?.focus();
      return;
    }
    if (nomeLimpo.length > 150) {
      setErroNome("Use no máximo 150 caracteres.");
      refNome.current?.focus();
      return;
    }

    emVoo.current = true;
    setEnviando(true);
    try {
      if (token) {
        const resposta = await api.inscreverNewsletter(token, {
          tipo: cats.length > 0 ? "categoria" : "padrao",
          categorias: cats,
          periodo,
        });
        // O `detail` do backend é o texto da pessoa, e o `estado` escolhe a
        // cor. Ver a nota do cabeçalho sobre os três estados.
        //
        // "Bom leitura" só é dizer quando a pessoa está CONFIRMADA. A versão
        // anterior deste arquivo dizia isso em TODO 2xx — o que, depois do
        // double opt-in, seria uma afirmação falsa em toda inscrição nova.
        setEstado(resposta.estado ?? (resposta.confirmada ? "confirmada" : "pendente"));
        setOk(resposta.detail?.trim() || SUCESSO_SEM_DETALHE);
        setEmailDaInscricao(email.trim());
      } else {
        const resposta = await api.inscreverListaEspera({
          nome: nomeLimpo,
          email: email.trim(),
          interesses: cats,
          aceite_comunicacao: true,
        });
        // 201 "Cadastro ... realizado." ou 200 "Este e-mail já está na lista
        // de espera." — nos dois casos o backend confirmou, então a mensagem
        // mostrada é a dele.
        //
        // O caminho público NÃO tem double opt-in: a lista de espera não envia
        // newsletter nenhuma, e a ninguém. `estado="confirmada"` aqui quer
        // dizer "o cadastro foi registrado e não há nada mais a fazer" — que
        // é o que é verdade, e é por isso que a cor é a de sucesso cheia.
        setEstado("confirmada");
        setOk(
          resposta?.detail
            ? `${resposta.detail} Se você entrar com este e-mail, a newsletter é ativada na sua conta.`
            : "Cadastro registrado. Se você entrar com este e-mail, a newsletter é ativada na sua conta."
        );
      }
      // Só limpa depois da confirmação real do servidor.
      setEmail("");
      setNome("");
      setCats([]);
    } catch (erro) {
      // O 503 do portão cai aqui como `ApiError`, e a mensagem do backend
      // (`DETALHE_SEM_CANAL`) diz o que falta E que nada foi gravado. Não há
      // um ramo especial para 503 porque o tratamento genérico de `ApiError`
      // já mostra exatamente a mensagem que o backend mandou — que é a única
      // pessoa que sabe o que está faltando do lado do servidor.
      const mensagem =
        erro instanceof api.ApiError
          ? erro.message
          : "Não foi possível concluir agora. Tente novamente.";
      setErroGeral(mensagem);
    } finally {
      emVoo.current = false;
      setEnviando(false);
    }
  }

  return (
    <form onSubmit={enviar} noValidate className="space-y-3" aria-busy={enviando}>
      {/*
        `nome` só aparece (e só é obrigatório) no caminho público: com conta
        logada, `newsletter/inscrever/` vincula a inscrição ao usuário e o
        nome vem do cadastro.
      */}
      {!token && (
        <div className="space-y-2">
          <Label htmlFor={idNome}>Nome</Label>
          <Input
            id={idNome}
            ref={refNome}
            name="nome"
            value={nome}
            onChange={(e) => setNome(e.target.value)}
            placeholder="Seu nome..."
            autoComplete="name"
            maxLength={150}
            disabled={enviando}
            aria-invalid={erroNome ? true : undefined}
            aria-describedby={erroNome ? `${idNome}-erro` : undefined}
            className="bg-[var(--cor-fundo-card)]"
          />
          {erroNome && (
            <p id={`${idNome}-erro`} className="text-xs text-[var(--cor-erro)]">
              {erroNome}
            </p>
          )}
        </div>
      )}

      <div className="space-y-2">
        <Label htmlFor={idEmail}>Email</Label>
        <Input
          id={idEmail}
          ref={refEmail}
          name="email"
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="seu@email.com"
          autoComplete="email"
          maxLength={254}
          disabled={enviando}
          aria-invalid={erroEmail ? true : undefined}
          aria-describedby={erroEmail ? `${idEmail}-erro` : undefined}
          className="bg-[var(--cor-fundo-card)]"
        />
        {erroEmail && (
          <p id={`${idEmail}-erro`} className="text-xs text-[var(--cor-erro)]">
            {erroEmail}
          </p>
        )}
      </div>

      <fieldset className="space-y-1.5" disabled={enviando}>
        <legend className="text-sm font-medium text-[var(--cor-texto)]">
          Editorias (opcional)
        </legend>
        <div className="flex flex-wrap gap-1.5">
          {CATS.map((c) => {
            const marcada = cats.includes(c);
            return (
              <button
                key={c}
                type="button"
                onClick={() => alternarCategoria(c)}
                aria-pressed={marcada}
                className={`rounded-full border px-2.5 py-0.5 text-xs font-medium capitalize transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)] ${
                  marcada
                    ? "border-[var(--cor-primaria)] bg-[var(--cor-primaria)] text-[var(--cor-texto-invertido)]"
                    : "border-[var(--cor-borda)] text-[var(--cor-texto)] hover:bg-[var(--cor-primaria-suave)]"
                }`}
              >
                {c}
              </button>
            );
          })}
        </div>
        <p className="text-xs text-[var(--cor-texto-suave)]">
          Sem seleção você recebe o resumo geral.
        </p>
      </fieldset>

      {/* `periodo` existe só em `newsletter/inscrever/` (modelo da newsletter),
          não no registro público — por isso some para visitante anônimo em vez
          de aceitar uma escolha que seria jogada fora. */}
      {token && (
        <fieldset className="space-y-1.5" disabled={enviando}>
          <legend className="text-sm font-medium text-[var(--cor-texto)]">
            Horário de envio
          </legend>
          <div className="flex gap-1.5">
            {(["manha", "noite"] as const).map((p) => (
              <button
                key={p}
                type="button"
                onClick={() => setPeriodo(p)}
                aria-pressed={periodo === p}
                className={`rounded-full border px-3 py-1 text-xs font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)] ${
                  periodo === p
                    ? "border-[var(--cor-primaria)] bg-[var(--cor-primaria)] text-[var(--cor-texto-invertido)]"
                    : "border-[var(--cor-borda)] text-[var(--cor-texto)] hover:bg-[var(--cor-primaria-suave)]"
                }`}
              >
                {p === "manha" ? "Manhã" : "Noite"}
              </button>
            ))}
          </div>
        </fieldset>
      )}

      {erroGeral && (
        <p
          ref={refGeral}
          role="alert"
          tabIndex={-1}
          className="rounded-md border border-[var(--cor-erro)] bg-[var(--cor-erro-suave)] px-3 py-2 text-sm text-[var(--cor-erro)]"
        >
          {erroGeral}
        </p>
      )}
      {ok && (
        <div
          ref={refSucesso}
          role="status"
          aria-live="polite"
          tabIndex={-1}
          className={`rounded-md border px-3 py-2 text-sm ${classeDoEstadoNewsletter(estado)}`}
        >
          {ok}
          {/* O aviso do próximo passo só aparece enquanto a confirmação está
              pendente. Quando está confirmada, "confirme no seu e-mail" seria
              um pedido impossível. */}
          {estado === "pendente" && emailDaInscricao && (
            <AvisoDeConfirmacaoPendente email={emailDaInscricao} />
          )}
        </div>
      )}

      <Button
        type="submit"
        disabled={enviando}
        className="min-h-[44px] bg-[var(--cor-primaria)] text-[var(--cor-texto-invertido)]"
      >
        {enviando
          ? "Enviando..."
          : estado === "pendente"
            // O rótulo muda porque a ação mudou: pressionar de novo não é
            // "me inscrever" (ela já se inscreveu), é "reenviar o link" — que é
            // a resposta certa para quem não achou o e-mail.
            ? "Reenviar confirmação"
            : "Quero receber"}
      </Button>
    </form>
  );
}

/**
 * Descadastro pelo token do link de descadastro do envio
 * (`POST /api/newsletter/descadastrar/`, backend/newsletter/urls.py:9). Sem
 * isso, o e-mail recebido na prática não tinha caminho de saída pela UI.
 */
export function DescadastrarForm() {
  const idToken = useId();
  const [tokenDesc, setTokenDesc] = useState("");
  const [erro, setErro] = useState<string | null>(null);
  const [ok, setOk] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);
  const emVoo = useRef(false);
  const refToken = useRef<HTMLInputElement>(null);
  const refMsg = useRef<HTMLParagraphElement>(null);

  // Mesmo motivo do formulário acima: o foco precisa acontecer depois que a
  // mensagem é montada, não no meio do handler.
  useEffect(() => {
    if (erro || ok) refMsg.current?.focus();
  }, [erro, ok]);

  // O link de descadastro chega como `?token=...`. Lido em `useEffect` (e não
  // com `useSearchParams`) para não exigir boundary de Suspense na build.
  useEffect(() => {
    try {
      const vindo = new URLSearchParams(window.location.search).get("token");
      if (vindo) setTokenDesc(vindo);
    } catch {
      /* query string inválida: segue com o campo em branco */
    }
  }, []);

  async function enviar(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (emVoo.current) return;
    setOk(null);
    setErro(null);

    const limpo = tokenDesc.trim();
    if (!limpo) {
      setErro("Cole o token do link de descadastro ou informe seu e-mail de inscrição.");
      refToken.current?.focus();
      return;
    }

    emVoo.current = true;
    setEnviando(true);
    try {
      const resposta = await api.descadastrarNewsletter(limpo);
      setOk(resposta?.detail || "Descadastro realizado.");
      setTokenDesc("");
    } catch (erro) {
      // 400 "Token inválido." chega como ApiError — erro real do backend.
      const mensagem =
        erro instanceof api.ApiError
          ? erro.message
          : "Não foi possível concluir agora. Tente novamente.";
      setErro(mensagem);
    } finally {
      emVoo.current = false;
      setEnviando(false);
    }
  }

  return (
    <form onSubmit={enviar} noValidate className="space-y-2" aria-busy={enviando}>
      <div className="space-y-2">
        <Label htmlFor={idToken}>Token de descadastro</Label>
        <Input
          id={idToken}
          ref={refToken}
          name="token_descadastro"
          value={tokenDesc}
          onChange={(e) => setTokenDesc(e.target.value)}
          placeholder="token do link de descadastro"
          autoComplete="off"
          disabled={enviando}
          className="bg-[var(--cor-fundo-card)]"
        />
      </div>
      {erro && (
        <p
          ref={refMsg}
          role="alert"
          tabIndex={-1}
          className="rounded-md border border-[var(--cor-erro)] bg-[var(--cor-erro-suave)] px-3 py-2 text-sm text-[var(--cor-erro)]"
        >
          {erro}
        </p>
      )}
      {ok && (
        <p
          ref={refMsg}
          role="status"
          aria-live="polite"
          tabIndex={-1}
          className="rounded-md border border-[var(--cor-sucesso)] bg-[var(--cor-sucesso-suave)] px-3 py-2 text-sm text-[var(--cor-sucesso)]"
        >
          {ok}
        </p>
      )}
      <Button
        type="submit"
        disabled={enviando}
        className="min-h-[44px] bg-[var(--cor-primaria)] text-[var(--cor-texto-invertido)]"
      >
        {enviando ? "Descadastrando..." : "Descadastrar"}
      </Button>
    </form>
  );
}
