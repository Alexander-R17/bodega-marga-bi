import {dashboardUrl, firebaseConfig} from "./config.js";

const link = document.getElementById("dashboard-link");
let validUrl;
try {
  const url = new URL(dashboardUrl);
  if (url.protocol === "https:") validUrl = url.href;
} catch {}
if (validUrl) {
  link.href = validUrl;
  link.classList.remove("disabled");
  link.removeAttribute("aria-disabled");
  document.getElementById("deployment-status").textContent = "Acceso privado con tu cuenta asignada.";
}

let analytics;
async function enableAnalytics() {
  try {
    const [{initializeApp}, {getAnalytics, isSupported, logEvent}] = await Promise.all([
      import("https://www.gstatic.com/firebasejs/10.14.1/firebase-app.js"),
      import("https://www.gstatic.com/firebasejs/10.14.1/firebase-analytics.js")
    ]);
    if (await isSupported()) {
      analytics = getAnalytics(initializeApp(firebaseConfig));
      link.addEventListener("click", () => {if(validUrl) logEvent(analytics, "abrir_dashboard");});
    }
  } catch {
    // Una falla de medición no bloquea el enlace de la tienda.
  }
}
const consent = document.getElementById("consent");
let preference;
try { preference = localStorage.getItem("marga_measurement"); } catch {}
if (preference) consent.hidden = true;
if (preference === "accepted") enableAnalytics();
function choose(value) {
  try {localStorage.setItem("marga_measurement",value);} catch {}
  consent.hidden = true;
  if(value === "accepted") enableAnalytics();
}
document.getElementById("accept").onclick=()=>choose("accepted");
document.getElementById("reject").onclick=()=>choose("rejected");
