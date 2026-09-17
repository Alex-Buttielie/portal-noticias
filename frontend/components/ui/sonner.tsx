"use client"
import { Toaster as Sonner, toast } from "sonner"
type ToasterProps = React.ComponentProps<typeof Sonner>
const Toaster = ({ ...props }: ToasterProps) => <Sonner theme="light" className="toaster group" toastOptions={{ classNames: { toast: "group-[.toaster]:bg-[var(--cor-fundo-card)] group-[.toaster]:text-[var(--cor-texto)] group-[.toaster]:border-[var(--cor-borda)] group-[.toaster]:shadow-[var(--sombra-2)]" } }} {...props} />
export { Toaster, toast }
