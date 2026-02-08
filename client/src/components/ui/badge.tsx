import * as React from "react"
import { cn } from "@/lib/utils"

const Badge = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement> & {
    variant?: "default" | "secondary" | "destructive" | "success"
  }
>(({ className, variant = "default", ...props }, ref) => {
  const variantClasses = {
    default: "bg-primary hover:bg-primary/80",
    secondary: "bg-secondary hover:bg-secondary/80",
    destructive: "bg-destructive hover:bg-destructive/80",
    success: "bg-green-500 hover:bg-green-600"
  }

  return (
    <div
      ref={ref}
      className={cn(
        "inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2",
        variantClasses[variant],
        "text-white",
        className
      )}
      {...props}
    />
  )
})
Badge.displayName = "Badge"

export { Badge }