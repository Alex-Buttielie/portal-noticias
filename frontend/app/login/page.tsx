"use client";

import { useState, type FormEvent } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { useToast } from "@/components/ToastProvider";
import { ApiError } from "@/lib/api";
import { Button } from "@/components/ui/Button";
import { CampoTexto } from "@/components/ui/FormField";
import { ErrorState } from "@/components/ui/Estados";

export default function PaginaLogin() {
  const router = useRouter();
  const { fazerLogin } = useAuth();
  const { notificar } = useToast();
  const [email, setEmail] = useState("");
  const [senha, setSenha] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);

  async function aoSubmeter(evento: FormEvent) {
    evento.preventDefault();
    setErro(null);
    setEnviando(true);
    try {
      await fazerLogin(email, senha);
      notificar("Login realizado com sucesso. Bem-vindo de volta!", "sucesso");
      router.push("/");
    } catch (e) {
      setErro(e instanceof ApiError ? e.message : "Não foi possível entrar.");
    } finally {
      setEnviando(false);
    }
  }

  return (
    <div className="formulario">
      <h1>Entrar</h1>
      {erro && <ErrorState mensagem={erro} />}
      <form onSubmit={aoSubmeter}>
        <CampoTexto id="email" rotulo="E-mail" type="email" required autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} />
        <CampoTexto id="senha" rotulo="Senha" type="password" required autoComplete="current-password" value={senha} onChange={(e) => setSenha(e.target.value)} />
        <Button type="submit" carregando={enviando}>
          Entrar
        </Button>
      </form>
      <p className="texto-suave" style={{ marginTop: "1rem" }}>
        <Link href="/recuperar-senha">Esqueci minha senha</Link>
      </p>
      <p className="texto-suave">
        Não tem conta? <Link href="/cadastro">Cadastre-se</Link>
      </p>
    </div>
  );
}
