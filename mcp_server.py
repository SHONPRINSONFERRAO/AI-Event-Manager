from mcp.server.fastmcp import FastMCP

# Initialize FastMCP Server
mcp = FastMCP("WeatherService")

@mcp.tool()
def get_weather_forecast(location: str) -> str:
    """Gets the weather forecast for a given location to aid in outdoor event risk assessment.

    Args:
        location: The city/region to get weather for (e.g., 'London', 'New York').
    """
    loc = location.strip().lower()
    if "london" in loc:
        return "London: Rain expected in the afternoon, 16°C. Recommended to prepare indoor contingencies or tents."
    elif "mumbai" in loc:
        return "Mumbai: Humid and warm, 32°C. Scattered clouds. Ideal for air-conditioned indoor banquets or covered rooftops."
    elif "new york" in loc:
        return "New York: Clear skies, 22°C. Perfect for outdoor parks or open rooftops."
    elif "singapore" in loc:
        return "Singapore: Afternoon thundershowers, 29°C. High humidity. Outdoor venues require heavy shelter options."
    elif "dubai" in loc:
        return "Dubai: Sunny and clear, 41°C. Very hot. Indoor ballroom highly recommended."
    else:
        return f"{location.title()}: Partly cloudy, mild temperatures (approx 20°C). Favorable for most indoor/outdoor setups. Check local forecasts on the event day."

if __name__ == "__main__":
    mcp.run()
