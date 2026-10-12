import { ImageResponse } from "next/og";

export const size = { width: 180, height: 180 };
export const contentType = "image/png";

/** Ícone para adicionar à tela inicial (iOS/Android) — mesma marca do favicon, em tamanho maior. */
export default function AppleIcon() {
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
        }}
      >
        <svg width="100" height="100" viewBox="0 0 40 40">
          <path d="M6 30V18Q6 8 18 6V11Q11 13 11 18H17V30Z" fill="#2DD4BF" />
          <path d="M21 30V18Q21 8 33 6V11Q26 13 26 18H32V30Z" fill="#5EEAD4" />
        </svg>
      </div>
    ),
    { ...size }
  );
}
