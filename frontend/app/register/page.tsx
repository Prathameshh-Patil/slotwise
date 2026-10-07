import { Suspense } from "react";

import { AuthForm } from "@/components/auth-form";

// AuthForm reads ?next= from the URL, which needs a Suspense boundary
export default function RegisterPage() {
  return (
    <Suspense>
      <AuthForm mode="register" />
    </Suspense>
  );
}
