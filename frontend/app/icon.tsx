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
        <svg width="20" height="20" viewBox="0 0 512 512">
          <path
            d="M112.64 383.43 V256.00 Q112.64 149.81 240.07 128.57 V181.67 Q165.74 202.90 165.74 256.00 H229.45 V383.43 Z"
            fill="#2DD4BF"
          />
          <path
            d="M271.93 383.43 V256.00 Q271.93 149.81 399.36 128.57 V181.67 Q325.03 202.90 325.03 256.00 H388.74 V383.43 Z"
            fill="#5EEAD4"
          />
        </svg>
      </div>
    ),
    { ...size }
  );
}
