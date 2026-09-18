// Tipos centrais do módulo de dispositivos.
// Mantém vocabulário fechado para evitar divergência entre detecção,
// provider, navegação e grade adaptativa.

export type ClasseDispositivo = "mobile" | "tablet" | "desktop" | "tv";

export type SistemaOperacional =
  | "ios"
  | "android"
  | "windows"
  | "macos"
  | "linux"
  | "outro";

export type TipoEntrada = "touch" | "mouse" | "hibrido";

export type Orientacao = "portrait" | "landscape";

export type PerfilDispositivo = {
  classe: ClasseDispositivo;
  so: SistemaOperacional;
  entrada: TipoEntrada;
  orientacao: Orientacao;
  largura: number;
  /** altura da viewport em px (para distinguir celular em paisagem de tablet) */
  altura: number;
  /** true quando rodando como PWA instalado (standalone) */
  standalone: boolean;
  /** true quando o dispositivo tem notch/gestos (safe-area relevante) */
  temSafeArea: boolean;
};

export const PERFIL_PADRAO_DESKTOP: PerfilDispositivo = {
  classe: "desktop",
  so: "outro",
  entrada: "mouse",
  orientacao: "landscape",
  largura: 1280,
  altura: 800,
  standalone: false,
  temSafeArea: false,
};
