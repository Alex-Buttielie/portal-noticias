import type { MetadataRoute } from "next";
import { SITE_NAME, SITE_DESCRIPTION } from "@/lib/site";
export default function manifest(): MetadataRoute.Manifest {
  return { name: SITE_NAME, short_name: "Portal", description: SITE_DESCRIPTION, start_url: "/", display: "standalone", background_color: "#FDFBF7", theme_color: "#0B0B1A", icons: [] };
}
