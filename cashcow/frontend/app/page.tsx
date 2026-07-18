import { UrlForm } from "@/features/url-form/url-form";

export default function HomePage() {
  return (
    <div className="mx-auto flex min-h-full max-w-xl items-center px-6 py-16">
      <div className="w-full">
        <UrlForm />
      </div>
    </div>
  );
}
