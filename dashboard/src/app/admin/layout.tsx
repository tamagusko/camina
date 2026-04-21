import Link from "next/link";
import { redirect } from "next/navigation";
import { requireAdmin } from "@/lib/auth";

const NAV = [
  { href: "/admin", label: "Overview" },
  { href: "/admin/sensors", label: "Sensors" },
  { href: "/admin/streets", label: "Streets" },
  { href: "/admin/members", label: "Members" },
  { href: "/admin/events", label: "Events" },
  { href: "/admin/audit", label: "Audit" },
] as const;

export default async function AdminLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const { session, isAdmin } = await requireAdmin();
  if (!session) redirect("/sign-in");
  if (!isAdmin) redirect("/dublin");

  return (
    <div className="min-h-[100dvh]">
      <header className="border-b border-chip-gray">
        <div className="mx-auto flex max-w-6xl items-center gap-4 px-6 py-4">
          <Link href="/admin" className="text-nav font-semibold">
            CAMINA · Admin
          </Link>
          <nav className="flex gap-1 overflow-x-auto">
            {NAV.map((i) => (
              <Link
                key={i.href}
                href={i.href as never}
                className="chip hover:bg-hover-light"
              >
                {i.label}
              </Link>
            ))}
          </nav>
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-6 py-10">{children}</main>
    </div>
  );
}
