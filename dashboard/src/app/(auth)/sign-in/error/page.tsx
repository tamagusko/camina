import Link from "next/link";

export default function SignInErrorPage() {
  return (
    <main className="flex min-h-[100dvh] flex-col items-center justify-center px-6">
      <h1 className="text-section mb-2">Sign-in was refused</h1>
      <p className="text-body text-body-gray mb-6 max-w-md text-center">
        Your email is not on the allow list, or sign-in was cancelled.
      </p>
      <Link href="/sign-in" className="btn-secondary">
        Try again
      </Link>
    </main>
  );
}
