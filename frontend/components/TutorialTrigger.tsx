"use client"
import { Button } from "@/components/ui/button"
import { HelpCircle } from "lucide-react"
export function TutorialTrigger({ className }: { className?: string }) {
  return (
    <Button variant="ghost" size="sm" className={className} onClick={() => window.dispatchEvent(new CustomEvent("tutorial:abrir"))}>
      <HelpCircle className="h-4 w-4" />
      Como usar?
    </Button>
  )
}
