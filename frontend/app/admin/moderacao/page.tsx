"use client";
import { useEffect, useState } from "react";
import { useAuth } from "@/lib/auth-context";
import * as api from "@/lib/api";
export default function AdminModeracaoPage() {
  const { token } = useAuth();
  const [statusFiltro, setStatusFiltro] = useState("");
  const [page, setPage] = useState(1);
  const [dados, setDados] = useState<api.Paginated<{ id: number; motivo: string; detalhe: string; status: string; denunciante_email: string; criado_em: string; alvo_repr: string | null }> | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [carregando, setCarregando] = useState(true);
  async function carregar() {
    if (!token) return;
    setCarregando(true);
    try { setDados(await api.adminListarDenuncias(token, { status: statusFiltro || undefined, page })); setErro(null); }
    catch (e) { setErro(e instanceof api.ApiError ? e.message : "Erro ao carregar."); }
    finally { setCarregando(false); }
  }
  useEffect(() => { void carregar(); }, [token, statusFiltro, page]);
  async function agir(id: number) {
    if (!token) return;
    const motivo = window.prompt("Motivo da ação:");
    if (!motivo) return;
    const tipo = window.prompt("Tipo (aviso, remocao_conteudo, bloqueio_temporario, bloqueio_permanente):", "aviso") || "aviso";
    await api.adminAplicarAcaoDenuncia(token, id, { tipo, motivo, procedente: true });
    await carregar();
  }
  return (
    <div>
      <h1>Moderação</h1>
      <div style={{ display: "flex", gap: 8, marginBottom: 12 }}>
        <select value={statusFiltro} onChange={(e) => { setStatusFiltro(e.target.value); setPage(1); }}>
          <option value="">todos</option><option value="pendente">pendente</option><option value="procedente">procedente</option><option value="improcedente">improcedente</option>
        </select>
        <button className="botao" onClick={() => void carregar()}>Atualizar</button>
      </div>
      {erro && <p className="mensagem-erro">{erro}</p>}
      {carregando ? <p className="texto-suave">Carregando…</p> : (
        <>
          <div className="tabela-wrapper">
            <table className="tabela"><thead><tr><th>#</th><th>Motivo</th><th>Status</th><th>Denunciante</th><th>Alvo</th><th>Ação</th></tr></thead>
              <tbody>{dados?.results.map((d) => (
                <tr key={d.id}><td>{d.id}</td><td>{d.motivo}</td><td>{d.status}</td><td>{d.denunciante_email}</td><td>{d.alvo_repr ?? "—"}</td>
                  <td><button className="botao" onClick={() => agir(d.id)}>Aplicar ação</button></td>
                </tr>
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
