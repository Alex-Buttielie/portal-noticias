"use client";
import Link from "next/link";
const CARDS = [
  { href: "/admin/usuarios", titulo: "Usuários", desc: "Buscar, filtrar e gerenciar contas" },
  { href: "/admin/fila", titulo: "Fila editorial", desc: "Aprovar ou rejeitar notícias pendentes" },
  { href: "/admin/planos", titulo: "Planos & Limites", desc: "Preços e recursos Free/Premium" },
  { href: "/admin/assinaturas", titulo: "Assinaturas", desc: "Filtros por status e histórico" },
  { href: "/admin/moderacao", titulo: "Moderação", desc: "Denúncias e ações" },
  { href: "/admin/metricas", titulo: "Métricas", desc: "Dashboards do negócio" },
];
export default function AdminHome() {
  return (
    <div>
      <h1>Painel de controle</h1>
      <p className="texto-suave">Gestão completa — apenas administradores.</p>
      <div className="grade-cartoes" style={{ marginTop: 16 }}>
        {CARDS.map((c) => (
          <Link key={c.href} href={c.href} className="cartao" style={{ textDecoration: "none", color: "inherit" }}>
            <h3 className="cartao-titulo">{c.titulo}</h3>
            <p className="texto-suave">{c.desc}</p>
          </Link>
        ))}
      </div>
    </div>
  );
}
