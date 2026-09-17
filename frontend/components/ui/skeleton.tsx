import { cn } from "@/lib/utils"
function Skeleton({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) { return <div className={cn("animate-pulse rounded-[var(--raio-md)] bg-[var(--cor-skeleton-base)]", className)} {...props} /> }
export { Skeleton }
