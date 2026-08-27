export function UnavailablePanel({ title, description }: { readonly title: string; readonly description: string }) {
  return <section className="data-unavailable-panel" role="status"><h2>{title}</h2><p>{description}</p></section>
}
