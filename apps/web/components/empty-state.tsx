import { cn } from "@/lib/utils";

export function EmptyState({
  title,
  children,
  className,
}: {
  title: string;
  children?: React.ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "rounded-md border border-dashed border-line px-4 py-5",
        className,
      )}
    >
      <p className="font-medium text-silver">{title}</p>
      {children ? <p className="mt-1 text-sm text-mist">{children}</p> : null}
    </div>
  );
}
