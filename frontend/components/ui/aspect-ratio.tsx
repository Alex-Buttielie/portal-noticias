import * as React from "react"
const AspectRatio = ({ ratio = 16 / 9, className, style, children, ...props }: React.HTMLAttributes<HTMLDivElement> & { ratio?: number }) => (
  <div style={{ position: "relative", width: "100%", paddingBottom: `${100 / ratio}%`, ...style } as React.CSSProperties} className={className} {...props}>
    <div style={{ position: "absolute", inset: 0 }}>{children}</div>
  </div>
)
AspectRatio.displayName = "AspectRatio"
export { AspectRatio }
