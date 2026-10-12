import { ImageResponse } from "next/og";

export const size = { width: 32, height: 32 };
export const contentType = "image/png";

/**
 * Favicon gerado em código (sem arte externa): mesma marca "Voz" do
 * componente Logomark, renderizada como PNG via next/og para a aba do
 * navegador. Grafite de fundo + aspas em esmeralda — identidade do portal.
 */
export default function Icon() {
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          background: "#111827",
          borderRadius: 7,
        }}
      >
        <svg width="20" height="20" viewBox="0 0 40 40">
          <path d="M6 30V18Q6 8 18 6V11Q11 13 11 18H17V30Z" fill="#2DD4BF" />
          <path d="M21 30V18Q21 8 33 6V11Q26 13 26 18H32V30Z" fill="#5EEAD4" />
        </svg>
      </div>
    ),
    { ...size }
  );
}
