import type { LucideIcon } from "lucide-react";
import { Home, Users, Compass, Crown, User } from "lucide-react";

export type NavItem = {
  href: string;
  label: string;
  icon: LucideIcon;
};

export const NAV_ITENS: NavItem[] = [
  { href: "/", label: "Início", icon: Home },
  { href: "/comunidade", label: "Comunidade", icon: Users },
  { href: "/radar", label: "Radar", icon: Compass },
  { href: "/planos", label: "Planos", icon: Crown },
];

export const NAV_ITEM_CONTA: NavItem = {
  href: "/minha-conta",
  label: "Conta",
  icon: User,
};

export const NAV_ITEM_LOGIN: NavItem = {
  href: "/login",
  label: "Entrar",
  icon: User,
};
