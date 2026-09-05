"use client";
import { useEffect, useState } from "react";
import { useAuth } from "@/lib/auth-context";
import * as api from "@/lib/api";
export default function AdminAssinaturasPage() {
  const { token } = useAuth();
  const [statusFiltro, setStatusFiltro] = useState("");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [dados, setDados] = useState<api.Paginated<api.AdminAssinatura> | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [carregando, setCarregando] = useState(true);
  async function carregar() {
    if (!token) return;
    setCarregando(true);
    try { setDados(await api.adminListarAssinaturas(token, { status: statusFiltro || undefined, search: search || undefined, page })); setErro(null); }
    catch (e) { setErro(e instanceof api.ApiError ? e.message : "Erro ao carregar."); }
    finally { setCarregando(false); }
  }
  useEffect(() => { void carregar(); }, [token, page]);
  return (
    <div>
      <h1>Assinaturas</h1>
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 12 }}>
        <select value={statusFiltro} onChange={(e) => setStatusFiltro(e.target.value)}>
          <option value="">todos status</option><option value="ativa">ativa</option><option value="teste">teste</option><option value="pagamento_pendente">pagamento_pendente</option><option value="inadimplente">inadimplente</option><option value="cancelada">cancelada</option><option value="expirada">expirada</option><option value="encerrada">encerrada</option>
        </select>
        <input placeholder="Buscar email/nome" value={search} onChange={(e) => setSearch(e.target.value)} style={{ maxWidth: 220 }} />
        <button className="botao" onClick={() => { setPage(1); void carregar(); }}>Filtrar</button>
      </div>
      {erro && <p className="mensagem-erro">{erro}</p>}
      {carregando ? <p className="texto-suave">Carregando…</p> : (
        <>
          <div className="tabela-wrapper">
            <table className="tabela"><thead><tr><th>Usuário</th><th>Plano</th><th>Status</th><th>Preço</th></tr></thead>
              <tbody>{dados?.results.map((a) => (
                <tr key={a.id}><td>{a.user_email}</td><td>{a.plan.nome}</td><td>{a.status}</td><td>{a.preco_cobrado}</td></tr>
              ))}</tbody>
            </table>
          </div>
          <div className="paginacao">
            <button className="botao botao-secundario" disabled={!dados?.previous} onClick={() => setPage((p) => Math.max(1, p - 1))}>Anterior</button>
            <span className="texto-suave">pág {page} — {dados?.count ?? 0}</span>
            <button className="botao botao-secundario" disabled={!dados?.next} onClick={() => setPage((p) => p + 1)}>Próxima</button>
          </div>
        </>
      )}
    </div>
  );
}
