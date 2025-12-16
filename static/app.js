/**
 * Minimal client-side behavior:
 * - Info dialog open/close
 * - Geolocation weather fetch ("Get Weather Near Me")
 * - Create record (CRUD) via API, then navigate to record detail
 *
 * Notes:
 * - We use local amCharts animated SVG icons (static/icons/amcharts/...)
 * - The mapping function mapOwmToAmChartsSvg(iconCode) MUST be loaded before this file.
 */
(function () {
  // -----------------------
  // Get Weather spinner controls
  // -----------------------
  const searchForm = document.getElementById("searchForm");
  const searchStatus = document.getElementById("searchStatus");

  if (searchForm && searchStatus) {
    searchForm.addEventListener("submit", () => {
      // Show loading indicator immediately
      searchStatus.style.display = "block";

      // Optional: disable the submit button so user can't spam-click
      const submitBtn = searchForm.querySelector('button[type="submit"]');
      if (submitBtn) submitBtn.disabled = true;
    });
  }

  // -----------------------
  // Info dialog controls
  // -----------------------
  const infoBtn = document.getElementById("infoBtn");
  const infoDialog = document.getElementById("infoDialog");
  const closeInfo = document.getElementById("closeInfo");

  if (infoBtn && infoDialog && closeInfo) {
    infoBtn.addEventListener("click", () => infoDialog.showModal());
    closeInfo.addEventListener("click", () => infoDialog.close());
  }

  // -----------------------
  // search field info dialog controls
  // -----------------------
  const formatInfoBtn = document.getElementById("formatInfoBtn");
  const formatInfoDialog = document.getElementById("formatInfoDialog");
  const closeFormatInfo = document.getElementById("closeFormatInfo");

  if (formatInfoBtn && formatInfoDialog && closeFormatInfo) {
    formatInfoBtn.addEventListener("click", () => formatInfoDialog.showModal());
    closeFormatInfo.addEventListener("click", () => formatInfoDialog.close());
  }

  // -----------------------
  // Geolocation -> weather
  // -----------------------
  const geoBtn = document.getElementById("geoBtn");
  const geoStatus = document.getElementById("geoStatus");
  const geoResult = document.getElementById("geoResult");

  /**
   * Returns a local amCharts icon URL for an OpenWeather icon code (e.g. "01d").
   * Falls back to a generic icon if mapping is missing.
   */
  function getAmChartsIconUrl(openWeatherIconCode) {
    // Always fall back to something that exists in your folder
    const FALLBACK = "cloudy.svg";

    try {
      const file = mapOwmToAmChartsSvg(openWeatherIconCode);
      return `/static/icons/amcharts/${file || FALLBACK}`;
    } catch (e) {
      console.warn("Icon mapping failed:", openWeatherIconCode, e);
      return `/static/icons/amcharts/${FALLBACK}`;
    }
  }

  /**
  * precipitation helper
  */
  function accumulatePrecipByDate(raw) {
    const tzOffset = raw?.city?.timezone ?? 0;
    const items = raw?.list ?? [];

    const totals = new Map(); // YYYY-MM-DD -> mm

    for (const it of items) {
      const d = new Date((it.dt + tzOffset) * 1000);
      const dateKey = d.toISOString().slice(0, 10);

      const rain = Number(it?.rain?.["3h"] ?? 0);
      const snow = Number(it?.snow?.["3h"] ?? 0);
      const mm = rain + snow;

      totals.set(dateKey, (totals.get(dateKey) ?? 0) + mm);
  }
    return totals;
}


  /**
   * Creates a small HTML card for:
   * - current weather
   * - 5-day forecast (daily summary)
   * Uses amCharts icons instead of OpenWeather-hosted PNGs.
   */

  function renderWeatherCard(payload) {
    // display of location in current-location
    const loc = payload.resolved || {};
    const locationLine = [
      loc.name || "Current Location",
      loc.state || "",
      loc.country || "",
    ].filter(Boolean).join(", ");

    //precipitation accumulation map
    const precipByDate = payload.forecast_3h
      ? accumulatePrecipByDate(payload.forecast_3h)
      : new Map();

    const w = payload.current.weather[0];
    const days = payload.five_day || []; // <-- this was missing in your snippet

    const currentIconUrl = getAmChartsIconUrl(w.icon);

    // Prefer a human-friendly label from the backend if available
    // We'll add this field in the backend in the next section.
    const locationLabel =
      payload.resolved?.label ||
      payload.resolved?.name ||
      "Your current location";

    const daysHtml = days
      .map((d) => {
        const dateKey = d.date; // MUST be YYYY-MM-DD
        const precipMm = precipByDate.get(dateKey) ?? 0;

        const dayIconUrl = getAmChartsIconUrl(d.icon);
        // pop_pct comes from backend (0..100). Allow 0 to display as "0%".
        const popText = (d.pop_pct === 0 || typeof d.pop_pct === "number")
          ? `${d.pop_pct}%`
          : "--";

        return `
          <div style="border:1px solid #ddd;border-radius:8px;padding:8px;">
            <div><b>${d.dow} — ${d.date_display}</b></div>

            <img class="amcharts-icon"
                 src="${dayIconUrl}"
                 alt="weather icon"
                 style="width:100px;height:100px;" />

            <div style="color:#666;">${d.description}</div>
            <div>🌧 Chance of precipitation: <b>${popText}</b></div>
            <div>💧 Total precip: ${precipMm.toFixed(1)} mm</div>
            <div>Low: ${d.tmin}°F</div>
            <div>High: ${d.tmax}°F</div>
          </div>
        `;
      })
      .join("");


    console.log("Current:", w.main, w.description, "icon:", w.icon);

    return `
      <div style="margin-bottom:8px;color:#666;">
        <b>Current location:</b> ${locationLabel}
      </div>

      <div style="display:flex;align-items:center;gap:10px;">
        <img class="amcharts-icon"
             alt="weather icon"
             src="${currentIconUrl}"
             style="width:100px;height:100px;object-fit:contain;" />
        <div>
          <div><b>${w.main}</b> — ${w.description}</div>
          <div>Temp: ${payload.current.main.temp}°F (feels like ${payload.current.main.feels_like}°F)</div>
          <div>Humidity: ${payload.current.main.humidity}% | Wind: ${payload.current.wind.speed} mph</div>
        </div>
      </div>

      <hr/>

      <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:10px;">
        ${daysHtml}
      </div>
    `;
  }

  if (geoBtn) {
    geoBtn.addEventListener("click", () => {
      geoStatus.textContent = "";
      geoResult.style.display = "none";
      geoResult.innerHTML = "";

      if (!navigator.geolocation) {
        geoStatus.textContent = "Geolocation not supported in this browser.";
        return;
      }

      geoStatus.textContent = "Getting your location…";

      navigator.geolocation.getCurrentPosition(
        async (pos) => {
          try {
            const { latitude, longitude } = pos.coords;
            geoStatus.textContent = "Fetching weather…";

            const resp = await fetch(
              `/api/weather/by-coords?lat=${latitude}&lon=${longitude}`
            //`/api/weather/by-coords?lat=55.0084&lon=82.9357`
            );
            const data = await resp.json();

            if (!resp.ok) {
              throw new Error(data.detail || "Weather fetch failed.");
            }

            geoResult.innerHTML = renderWeatherCard(data);
            geoResult.style.display = "block";
            geoStatus.textContent = "";
          } catch (e) {
            geoStatus.textContent = e.message;
          }
        },
        () => {
          geoStatus.textContent = "Location permission denied or unavailable.";
        },
        { enableHighAccuracy: true, timeout: 8000 }
      );
    });
  }

  // -----------------------
  // CRUD create record
  // -----------------------
  const createBtn = document.getElementById("createBtn");
  const createStatus = document.getElementById("createStatus");
  const locInput = document.getElementById("loc");
  const start = document.getElementById("start");
  const end = document.getElementById("end");

  if (createBtn) {
    createBtn.addEventListener("click", async () => {
      createStatus.textContent = "";

      try {
        const payload = {
          location: locInput.value.trim(),
          start_date: start.value,
          end_date: end.value,
        };

        const resp = await fetch("/api/records", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });

        const data = await resp.json();
        if (!resp.ok) {
          throw new Error(data.detail || "Create failed.");
        }

        createStatus.textContent = `Created record #${data.id}. Opening…`;
        window.location.href = `/records/${data.id}`;
      } catch (e) {
        createStatus.textContent = e.message;
      }
    });
  }
})();