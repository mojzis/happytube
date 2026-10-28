// htmx swaps nothing on a 4xx/5xx (except 422, the form error). Show the server's
// plain-text message in the alert region of the form that sent the request (or the
// page's one), as text, never HTML; clear it on the next request.
function alertBox(elt) {
  return elt.closest("form")?.querySelector(".htmx-error") ?? document.getElementById("htmx-error");
}
document.addEventListener("htmx:beforeRequest", (e) => { alertBox(e.detail.elt).hidden = true; });
document.addEventListener("htmx:responseError", (e) => {
  const box = alertBox(e.detail.elt);
  box.textContent = e.detail.xhr.responseText || `Error ${e.detail.xhr.status}`;
  box.hidden = false;
});
document.addEventListener("htmx:sendError", (e) => {
  const box = alertBox(e.detail.elt);
  box.textContent = "The review server did not answer. Is happytube serve still running?";
  box.hidden = false;
});
