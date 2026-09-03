"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useAuth } from "@/lib/auth-context";
import { useToast } from "@/components/ToastProvider";
import * as api from "@/lib/api";

/**
 * Conteúdo interativo da página de perfil de autor — extraído de `page.tsx`
 * (implementation-contract.md run 20260903-1134-seo-lgpd-design-system,
 * escopo A) para que `page.tsx` possa virar um Server Component com
 * `generateMetadata`/JSON-LD (metadata não pode ser exportado por um
 * Client Component). Mesmo padrão já usado no projeto em
 * `app/verificar-email/VerificarEmailConteudo.tsx` e
 * `app/redefinir-senha/RedefinirSenhaConteudo.tsx`. Comportamento
 * inalterado em relação à versão anterior.
 */
export default function PerfilAutorConteudo({ id }: { id: string }) {
  const { token } = useAuth();
  const { notificar } = useToast();
  const autorId = Number(id);

  const [perfil, setPerfil] = useState<api.PerfilAutorPublico | null>(null);
  const [seguindo, setSeguindo] = useState(false);
  const [carregando, setCarregando] = useState(true);
  const [erro, setErro] = useState<string | null>(null);
  const [processandoSeguir, setProcessandoSeguir] = useState(false);

  useEffect(() => {
    api
      .obterPerfilAutor(autorId)
      .then(setPerfil)
      .catch((e: unknown) => {
        setErro(e instanceof api.ApiError ? e.message : "Não foi possível carregar o perfil.");
      })
      .finally(() => setCarregando(false));
  }, [autorId]);

  // Atualização otimista: a interface reflete a ação imediatamente, sem
  // esperar a resposta do servidor, e só desfaz se a chamada falhar —
  // sensação de resposta instantânea em vez de um botão "travado".
  async function alternarSeguir() {
    if (!token || !perfil) return;
    const estavaSeguindo = seguindo;

    setSeguindo(!estavaSeguindo);
    setPerfil((atual) =>
      atual
        ? {
            ...atual,
            numero_seguidores: atual.numero_seguidores + (estavaSeguindo ? -1 : 1),
          }
        : atual
    );
    setProcessandoSeguir(true);

    try {
      if (estavaSeguindo) {
        await api.deixarDeSeguirAutor(token, autorId);
        notificar(`Você deixou de seguir ${perfil.nome || "este autor"}.`, "info");
      } else {
        await api.seguirAutor(token, autorId);
        notificar(`Agora você segue ${perfil.nome || "este autor"}.`, "sucesso");
      }
    } catch (e) {
      // reverte a atualização otimista
      setSeguindo(estavaSeguindo);
      setPerfil((atual) =>
        atual
          ? {
              ...atual,
              numero_seguidores: atual.numero_seguidores + (estavaSeguindo ? 1 : -1),
            }
          : atual
      );
      notificar(
        e instanceof api.ApiError ? e.message : "Não foi possível atualizar agora.",
        "erro"
      );
    } finally {
      setProcessandoSeguir(false);
    }
  }

  if (carregando) return <p className="texto-suave">Carregando...</p>;
  if (erro || !perfil) return <p className="mensagem-erro">{erro || "Perfil não encontrado."}</p>;

  return (
    <div>
      <h1>
        {perfil.nome || `Autor #${perfil.id}`}{" "}
        {perfil.credenciado && <span className="selo-premium">Jornalista credenciado</span>}
      </h1>
      <p className="texto-suave">
        {perfil.numero_seguidores} seguidor{perfil.numero_seguidores === 1 ? "" : "es"}
      </p>

      {token && (
        <button type="button" className="botao botao-secundario" onClick={alternarSeguir} disabled={processandoSeguir}>
          {seguindo ? "Deixar de seguir" : "Seguir"}
        </button>
      )}

      <h2 style={{ fontSize: "1.1rem", marginTop: "1.5rem" }}>Publicações</h2>
      {perfil.publicacoes.length === 0 && <p className="texto-suave">Nenhuma publicação ainda.</p>}
      {perfil.publicacoes.map((publicacao) => (
        <Link
          key={publicacao.id}
          href={`/comunidade/${publicacao.id}`}
          style={{ textDecoration: "none", color: "inherit" }}
        >
          <article className="cartao">
            <h3 className="cartao-titulo">{publicacao.titulo}</h3>
          </article>
        </Link>
      ))}
    </div>
  );
}
