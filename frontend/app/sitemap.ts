import type { MetadataRoute } from "next";
import { SITE_URL } from "@/lib/site";
export default function sitemap(): MetadataRoute.Sitemap {
  const base = SITE_URL.replace(/\/$/, "");
  const now = new Date();
  const rotas = ["", "/editorias", "/ao-vivo", "/buscar", "/sobre", "/contato", "/termos", "/privacidade", "/cookies", "/arquivo", "/newsletter", "/categoria/politica", "/categoria/economia", "/categoria/tecnologia"];
  return rotas.map((r) => ({ url: `${base}${r || "/"}`, lastModified: now, changeFrequency: r === "" ? "hourly" : "weekly", priority: r === "" ? 1 : 0.7 }));
}
