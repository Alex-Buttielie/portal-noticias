"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { KeyRound, CheckCircle2 } from "lucide-react";
import { useAuth } from "@/lib/auth-context";
import * as api from "@/lib/api";

export default function Page() {
  const { token, usuario, atualizarToken, atualizarUsuario } = useAuth();
  const r = useRouter();
  const [erro, setErro] = useState<string | null>(null);
  const [ok, setOk] = useState(false);
  const { register, handleSubmit, watch, formState: { errors, isSubmitting } } = useForm<{ senha_atual: string; nova_senha: string; confirmar: string }>({
    defaultValues: { senha_atual: "", nova_senha: "", confirmar: "" },
  });
  const nova = watch("nova_senha");

  const onSubmit = async (d: { senha_atual: string; nova_senha: string; confirmar: string }) => {
    setErro(null);
    if (d.nova_senha !== d.confirmar) { setErro("A confirmação não confere com a nova senha."); return; }
    if (!token) { setErro("Sessão expirada. Entre novamente."); return; }
    try {
      const resposta = await api.trocarSenha(token, { senha_atual: d.senha_atual, nova_senha: d.nova_senha });
      atualizarToken(resposta.token);
      if (usuario) atualizarUsuario({ ...usuario, deve_trocar_senha: false });
      setOk(true);
      setTimeout(() => r.push("/minha-conta"), 1200);
    } catch (e: unknown) {
      setErro(e instanceof Error ? e.message : "Não foi possível trocar a senha.");
    }
  };

  if (ok) {
    return (
      <div className="mx-auto max-w-md py-10">
        <Card className="border-[var(--cor-borda)] bg-[var(--cor-fundo-card)]">
          <CardContent className="p-6 text-center">
            <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-[var(--cor-sucesso-suave)] text-[var(--cor-sucesso)]"><CheckCircle2 className="h-6 w-6" /></div>
            <p className="mt-3 font-medium text-[var(--cor-texto)]">Senha atualizada!</p>
            <p className="mt-1 text-sm text-[var(--cor-texto-suave)]">Levando você para sua conta…</p>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-md space-y-4 py-6">
      <div className="hud-line" aria-hidden />
      <Card className="border-[var(--cor-borda)] bg-[var(--cor-fundo-card)]">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-[var(--cor-texto)]"><KeyRound className="h-5 w-5 text-[var(--cor-primaria)]" /> Crie sua senha</CardTitle>
          <CardDescription className="text-[var(--cor-texto-suave)]">Primeiro acesso: defina uma senha só sua para continuar.</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4" noValidate>
            <div className="space-y-2">
              <Label htmlFor="senha_atual">Senha atual (temporária)</Label>
              <Input id="senha_atual" type="password" autoComplete="current-password" placeholder="••••••••" {...register("senha_atual", { required: "Informe a senha atual" })} aria-invalid={!!errors.senha_atual} />
              {errors.senha_atual && <p className="text-xs font-medium text-[var(--cor-erro)]">{errors.senha_atual.message as string}</p>}
            </div>
            <div className="space-y-2">
              <Label htmlFor="nova_senha">Nova senha</Label>
              <Input id="nova_senha" type="password" autoComplete="new-password" placeholder="Mínimo 8 caracteres" {...register("nova_senha", { required: "Informe a nova senha", minLength: { value: 8, message: "Mínimo 8 caracteres" } })} aria-invalid={!!errors.nova_senha} />
              {errors.nova_senha && <p className="text-xs font-medium text-[var(--cor-erro)]">{errors.nova_senha.message as string}</p>}
            </div>
            <div className="space-y-2">
              <Label htmlFor="confirmar">Confirmar nova senha</Label>
              <Input id="confirmar" type="password" autoComplete="new-password" placeholder="Repita a nova senha" {...register("confirmar", { required: "Confirme a nova senha", validate: (v) => v === nova || "As senhas não conferem" })} aria-invalid={!!errors.confirmar} />
              {errors.confirmar && <p className="text-xs font-medium text-[var(--cor-erro)]">{errors.confirmar.message as string}</p>}
            </div>
            {erro && <p role="alert" className="rounded-md border border-[var(--cor-erro)] bg-[var(--cor-erro-suave)] px-3 py-2 text-sm text-[var(--cor-erro)]">{erro}</p>}
            <Button type="submit" disabled={isSubmitting} className="w-full bg-[var(--cor-primaria)] text-[var(--cor-texto-invertido)] hover:bg-[var(--cor-primaria-hover)] min-h-[44px]">{isSubmitting ? "Salvando…" : "Definir senha e entrar"}</Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
