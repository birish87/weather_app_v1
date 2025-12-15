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
  try {
    const file = mapOwmToAmChartsSvg(openWeatherIconCode);
    return `/static/icons/amcharts/${file || "cloudy.svg"}`;
  } catch (e) {
    console.warn("Icon mapping failed:", openWeatherIconCode);
    return "/static/icons/amcharts/cloudy.svg";
  }
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
        loc.country || ""
      ].filter(Boolean).join(", ");

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
        const dayIconUrl = getAmChartsIconUrl(d.icon);
        return `
          <div style="border:1px solid #ddd;border-radius:8px;padding:8px;">
            <div><b>${d.date}</b></div>
            <img class="amcharts-icon"
                 alt="weather icon"
                 src="${dayIconUrl}"
                 style="width:100px;height:100px;object-fit:contain;" />
            <div style="color:#666;">${d.description}</div>
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
  const loc = document.getElementById("loc");
  const start = document.getElementById("start");
  const end = document.getElementById("end");

  if (createBtn) {
    createBtn.addEventListener("click", async () => {
      createStatus.textContent = "";

      try {
        const payload = {
          location: loc.value.trim(),
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
