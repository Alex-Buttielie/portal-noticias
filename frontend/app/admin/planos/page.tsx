"use client";
import { useEffect, useState } from "react";
import { useAuth } from "@/lib/auth-context";
import * as api from "@/lib/api";
export default function AdminPlanosPage() {
  const { token } = useAuth();
  const [planos, setPlanos] = useState<api.Plano[]>([]);
  const [limites, setLimites] = useState<{ id: number; chave: string; plano: string; valor: string; descricao: string }[]>([]);
  const [erro, setErro] = useState<string | null>(null);
  const [novoPlano, setNovoPlano] = useState({ nome: "", preco: "", duracao_dias: "180" });
  async function carregar() {
    if (!token) return;
    try {
      const [p, l] = await Promise.all([api.adminListarPlanos(token), api.adminListarLimites(token)]);
      setPlanos((p as unknown as { results: api.Plano[] }).results ?? (p as unknown as api.Plano[]));
      setLimites((l as unknown as { results: typeof limites }).results ?? (l as unknown as typeof limites));
      setErro(null);
    } catch (e) { setErro(e instanceof api.ApiError ? e.message : "Erro ao carregar."); }
  }
  useEffect(() => { void carregar(); }, [token]);
  return (
    <div>
      <h1>Planos & Limites</h1>
      {erro && <p className="mensagem-erro">{erro}</p>}
      <h2>Planos</h2>
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 12 }}>
        <input placeholder="Nome" value={novoPlano.nome} onChange={(e) => setNovoPlano({ ...novoPlano, nome: e.target.value })} style={{ maxWidth: 160 }} />
        <input placeholder="Preço (30.00)" value={novoPlano.preco} onChange={(e) => setNovoPlano({ ...novoPlano, preco: e.target.value })} style={{ maxWidth: 120 }} />
        <input placeholder="Duração dias" value={novoPlano.duracao_dias} onChange={(e) => setNovoPlano({ ...novoPlano, duracao_dias: e.target.value })} style={{ maxWidth: 120 }} />
        <button className="botao" onClick={async () => {
          if (!token) return;
          await api.adminCriarPlano(token, { nome: novoPlano.nome, preco: novoPlano.preco, duracao_dias: Number(novoPlano.duracao_dias) });
          setNovoPlano({ nome: "", preco: "", duracao_dias: "180" }); await carregar();
        }}>Criar plano</button>
      </div>
      <div className="tabela-wrapper">
        <table className="tabela"><thead><tr><th>Nome</th><th>Preço</th><th>Dias</th><th>Ativo</th><th>Ações</th></tr></thead>
          <tbody>{planos.map((p) => (
            <tr key={p.id}><td>{p.nome}</td><td>{p.preco}</td><td>{p.duracao_dias}</td><td>{(p as unknown as { ativo: boolean }).ativo ? "sim" : "não"}</td>
              <td><button className="botao botao-secundario" onClick={async () => { if (!token) return; await api.adminAtualizarPlano(token, p.id, { ativo: !(p as unknown as { ativo: boolean }).ativo }); await carregar(); }}>{(p as unknown as { ativo: boolean }).ativo ? "Desativar" : "Ativar"}</button></td>
            </tr>
          ))}</tbody>
        </table>
      </div>
      <h2 style={{ marginTop: 24 }}>Limites Free/Premium</h2>
      <div className="tabela-wrapper">
        <table className="tabela"><thead><tr><th>Chave</th><th>Plano</th><th>Valor</th><th>Ação</th></tr></thead>
          <tbody>{limites.map((l) => (
            <tr key={l.id}><td>{l.chave}</td><td>{l.plano}</td><td>{l.valor}</td>
              <td><button className="botao botao-secundario" onClick={async () => {
                if (!token) return;
                const novo = window.prompt(`Novo valor para ${l.chave} (${l.plano}):`, l.valor);
                if (novo === null) return;
                await api.adminAtualizarLimite(token, l.id, { valor: novo }); await carregar();
              }}>Editar</button></td>
            </tr>
          ))}</tbody>
        </table>
      </div>
    </div>
  );
}
