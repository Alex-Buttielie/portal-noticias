import Link from "next/link";
import { FileQuestion } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

export default function NotFound() {
  return (
    <div className="mx-auto flex min-h-[50vh] w-full max-w-xl flex-col items-center justify-center px-4 py-16">
      <Card className="w-full text-center">
        <CardHeader className="items-center">
          <span className="inline-flex h-12 w-12 items-center justify-center rounded-full bg-[var(--cor-primaria-suave)] text-[var(--cor-primaria)]">
            <FileQuestion className="h-6 w-6" aria-hidden="true" />
          </span>
          <CardTitle className="font-[var(--fonte-titulo)] text-xl sm:text-2xl">
            Você chegou a uma página que não existe
          </CardTitle>
          <CardDescription className="max-w-[40ch]">
            Confira o endereço ou volte ao início para acompanhar as últimas notícias.
          </CardDescription>
        </CardHeader>
        <CardContent className="grid gap-3 sm:grid-cols-2">
          <Button asChild tamanho="grande" className="w-full">
            <Link href="/">Voltar ao início</Link>
          </Button>
          <Button asChild variante="secundaria" tamanho="grande" className="w-full">
            <Link href="/planos">Conhecer o Premium</Link>
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
