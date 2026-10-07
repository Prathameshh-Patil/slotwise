import { Suspense } from "react";

import { AuthForm } from "@/components/auth-form";

// AuthForm reads ?next= from the URL, which needs a Suspense boundary
export default function LoginPage() {
  return (
    <Suspense>
      <AuthForm mode="login" />
    </Suspense>
  );
}
