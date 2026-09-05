"use client";
import { useEffect, useState } from "react";
import { useAuth } from "@/lib/auth-context";
import * as api from "@/lib/api";

export default function AdminUsuariosPage() {
  const { token } = useAuth();
  const [busca, setBusca] = useState("");
  const [papelFiltro, setPapelFiltro] = useState("");
  const [dados, setDados] = useState<api.Paginated<api.AdminUsuario> | null>(null);
  const [carregando, setCarregando] = useState(true);
  const [erro, setErro] = useState<string | null>(null);
  const [page, setPage] = useState(1);

  async function carregar() {
    if (!token) return;
    setCarregando(true);
    setErro(null);
    try {
      const r = await api.adminListarUsuarios(token, { search: busca || undefined, papel: papelFiltro || undefined, page });
      setDados(r);
    } catch (e) { setErro(e instanceof api.ApiError ? e.message : "Erro ao carregar."); }
    finally { setCarregando(false); }
  }
  useEffect(() => { void carregar(); }, [token, page]);
  async function atualizar(id: number, patch: { papel?: string; is_active?: boolean }) {
    if (!token) return;
    await api.adminAtualizarUsuario(token, id, patch);
    await carregar();
  }
  return (
    <div>
      <h1>Usuários</h1>
      <div style={{ display: "flex", gap: 8, marginBottom: 12, flexWrap: "wrap" }}>
        <input placeholder="Buscar email/nome" value={busca} onChange={(e) => setBusca(e.target.value)} style={{ maxWidth: 260 }} />
        <select value={papelFiltro} onChange={(e) => setPapelFiltro(e.target.value)}>
          <option value="">Todos papéis</option><option value="free">free</option><option value="premium">premium</option><option value="admin">admin</option>
        </select>
        <button className="botao" onClick={() => { setPage(1); void carregar(); }}>Buscar</button>
      </div>
      {erro && <p className="mensagem-erro">{erro}</p>}
      {carregando ? <p className="texto-suave">Carregando…</p> : (
        <>
          <div className="tabela-wrapper">
            <table className="tabela"><thead><tr><th>Email</th><th>Nome</th><th>Papel</th><th>Ativo</th><th>Ações</th></tr></thead>
              <tbody>{dados?.results.map((u) => (
                <tr key={u.id}><td>{u.email}</td><td>{u.nome}</td>
                  <td>
                    <select value={u.papel} onChange={(e) => atualizar(u.id, { papel: e.target.value })}>
                      <option value="free">free</option><option value="premium">premium</option><option value="admin">admin</option>
                    </select>
                  </td>
                  <td>{u.is_active ? "sim" : "não"}</td>
                  <td><button className="botao botao-secundario" onClick={() => atualizar(u.id, { is_active: !u.is_active })}>{u.is_active ? "Desativar" : "Ativar"}</button></td>
                </tr>
              ))}</tbody>
            </table>
          </div>
          <div className="paginacao">
            <button className="botao botao-secundario" disabled={!dados?.previous} onClick={() => setPage((p) => Math.max(1, p - 1))}>Anterior</button>
            <span className="texto-suave">pág {page} — {dados?.count ?? 0} total</span>
            <button className="botao botao-secundario" disabled={!dados?.next} onClick={() => setPage((p) => p + 1)}>Próxima</button>
          </div>
        </>
      )}
    </div>
  );
}
