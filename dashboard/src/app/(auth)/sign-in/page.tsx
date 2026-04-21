import { signIn } from "@/lib/auth";

// Single-provider sign-in screen: Google only, pill CTA per DESIGN.md §4.
export default function SignInPage() {
  return (
    <main className="flex min-h-[100dvh] flex-col items-center justify-center px-6">
      <div className="w-full max-w-md">
        <h1 className="text-display mb-2">CAMINA</h1>
        <p className="text-body text-body-gray mb-8">
          Privacy-preserving urban mobility counts.
        </p>
        <form
          action={async () => {
            "use server";
            await signIn("google", { redirectTo: "/dublin" });
          }}
        >
          <button className="btn-primary w-full" type="submit">
            Continue with Google
          </button>
        </form>
        <p className="text-caption text-muted-gray mt-6">
          Access is restricted to allow-listed members. Contact the project lead if
          you believe you should have access.
        </p>
      </div>
    </main>
  );
}
