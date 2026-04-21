import { cn } from "@/lib/cn";

interface PillProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?: "default" | "mock" | "active";
}

export function Pill({ className, variant = "default", ...props }: PillProps) {
  return (
    <div
      className={cn(
        "inline-flex items-center gap-2 rounded-pill px-4 py-2 text-caption font-medium",
        variant === "default" && "bg-chip-gray text-black",
        variant === "active" && "bg-black text-white",
        variant === "mock" && "bg-black text-white uppercase tracking-wide",
        className
      )}
      {...props}
    />
  );
}
