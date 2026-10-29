function statusMessage(text) {
  const element = document.querySelector("#global-status");
  if (element) {
    element.textContent = text;
    element.hidden = false;
  }
}
document.addEventListener("htmx:configRequest", (event) => {
  const token = document.querySelector(
    "input[name=csrfmiddlewaretoken]",
  )?.value;
  if (token) event.detail.headers["X-CSRFToken"] = token;
});
document.addEventListener("htmx:beforeSwap", (event) => {
  if (event.detail.xhr.status === 422) {
    event.detail.shouldSwap = true;
    event.detail.isError = false;
  }
  if (event.detail.xhr.status === 429)
    statusMessage(
      "Demasiados intentos. Espera unos minutos antes de continuar.",
    );
});
document.addEventListener("htmx:afterSwap", (event) => {
  if (event.detail.target?.id === "main") {
    const main = document.querySelector("#main");
    main?.focus({ preventScroll: true });
    window.scrollTo({ top: 0, behavior: "instant" });
  }
  enhanceMobileFilters();
});
function enhanceMobileFilters() {
  if (!window.matchMedia("(max-width: 700px)").matches) return;
  document.querySelectorAll(".filter-panel details").forEach((details) => {
    if (!details.dataset.enhanced && !details.querySelector(".errorlist"))
      details.open = false;
    details.dataset.enhanced = "true";
  });
}
document.addEventListener("DOMContentLoaded", enhanceMobileFilters);
document.addEventListener("htmx:sendError", () =>
  statusMessage(
    "No hay conexión. Tus cambios no se confirmaron; vuelve a intentarlo.",
  ),
);
document.addEventListener("htmx:responseError", (event) => {
  if (event.detail.xhr.status !== 422)
    statusMessage(
      "No pudimos completar la acción. Revisa la conexión y vuelve a intentarlo.",
    );
});
document.addEventListener("change", async (event) => {
  if (event.target.matches("input[type=file]")) {
    const input = event.target;
    input.parentElement.querySelector("[data-photo-preview]")?.remove();
    const file = input.files?.[0];
    if (file && ["image/jpeg", "image/png", "image/webp"].includes(file.type)) {
      const preview = document.createElement("img");
      const url = URL.createObjectURL(file);
      preview.dataset.photoPreview = "true";
      preview.alt = "Vista previa de la foto seleccionada";
      preview.style.cssText =
        "display:block;max-height:220px;margin-top:12px;border-radius:8px";
      preview.onload = () => URL.revokeObjectURL(url);
      preview.onerror = () => {
        URL.revokeObjectURL(url);
        preview.remove();
      };
      preview.src = url;
      input.insertAdjacentElement("afterend", preview);
    }
  }
  const state = event.target.closest("[data-location-state]");
  const locality = event.target.closest("[data-location-locality]");
  if (state) {
    const form = state.closest("form");
    const target = form?.querySelector("[data-location-locality]");
    if (!target) return;
    const selected = state.value;
    target.innerHTML = '<option value="">Cargando ciudades…</option>';
    try {
      const response = await fetch(
        `/ubicaciones/ciudades/?state=${encodeURIComponent(selected)}`,
      );
      if (!response.ok) throw new Error("locations");
      const html = await response.text();
      if (state.value === selected) target.innerHTML = html;
    } catch {
      target.innerHTML =
        '<option value="">No se pudo cargar. Reintenta el estado.</option>';
    }
    const zone = form?.querySelector("[data-location-zone]");
    if (zone) zone.innerHTML = '<option value="">Todas las zonas</option>';
  }
  if (locality) {
    const zone = locality
      .closest("form")
      ?.querySelector("[data-location-zone]");
    if (!zone) return;
    const selected = locality.value;
    try {
      const response = await fetch(
        `/ubicaciones/zonas/?locality=${encodeURIComponent(selected)}`,
      );
      if (!response.ok) throw new Error("zones");
      const html = await response.text();
      if (locality.value === selected) zone.innerHTML = html;
    } catch {
      statusMessage(
        "No se pudieron cargar las zonas. Vuelve a elegir la ciudad.",
      );
    }
  }
});
