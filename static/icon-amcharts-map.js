/**
 * Map OpenWeather icon codes to amCharts animated SVG filenames.
 * Uses amCharts naming conventions (hyphenated, numbered variants).
 * TODO: add distinction between broken/overcast clouds; day and night card?; also, add fog image;
 **/
function mapOwmToAmChartsSvg(iconCode) {
  switch (iconCode) {

    // Clear sky
    case "01d": return "day.svg";
    case "01n": return "night.svg";

    // Few clouds / partly cloudy
    case "02d": return "cloudy-day-1.svg";
    case "02n": return "cloudy-night-1.svg";

    // Scattered / broken clouds
    case "03d":
    case "03n":
    case "04d":
    case "04n":
      return "cloudy.svg";

    // Shower rain
    case "09d":
    case "09n":
      return "rainy-6.svg";

    // Rain
    case "10d":
    case "10n":
      return "rainy-3.svg";

    // Thunderstorm
    case "11d":
    case "11n":
      return "thunder.svg";

    // Snow
    case "13d":
    case "13n":
      return "snowy-6.svg";

    // Mist / fog / haze
    case "50d":
    case "50n":
      return "cloudy.svg";

    // Safe fallback
    default:
      return "cloudy.svg";
  }
}
