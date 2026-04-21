import { redirect } from "next/navigation";

// Default city redirect (declared in vercel.ts too — this is a belt-and-braces
// fallback for local dev where Vercel redirects don't run).
export default function RootPage() {
  redirect("/dublin");
}
