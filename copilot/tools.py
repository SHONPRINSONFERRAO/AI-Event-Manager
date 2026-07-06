"""Tools for the Smart Event Planning Copilot.

Each function contains detailed docstrings so that Google Antigravity Agents
can correctly understand, select, and invoke them with appropriate arguments.
"""

from typing import Dict, Any, List

def budget_allocation_tool(budget: float, event_type: str, guest_count: int, currency: str = "") -> Dict[str, Any]:
    """Allocates the event budget across standard categories based on event type and guest count.

    Args:
        budget: The total budget for the event (in the user's chosen currency).
        event_type: The type of event (e.g., "wedding", "corporate", "birthday").
        guest_count: The number of expected guests.
        currency: The currency symbol or code (e.g., "USD", "INR", "GBP"). Used for display only.

    Returns:
        A dictionary containing the budget allocation breakdown.
    """
    event_type = event_type.lower()
    currency = currency.strip() or ""

    # Define allocation percentages based on event type
    if "wedding" in event_type:
        allocations = {
            "Venue & Setup": 0.30,
            "Catering (Food & Beverage)": 0.35,
            "Decoration & Florals": 0.12,
            "Entertainment & Media": 0.10,
            "Contingency": 0.13
        }
    elif "corporate" in event_type:
        allocations = {
            "Venue & AV Production": 0.40,
            "Catering (F&B)": 0.25,
            "Branding & Collaterals": 0.15,
            "Speakers & Entertainment": 0.10,
            "Contingency": 0.10
        }
    else:  # default e.g., birthday, social
        allocations = {
            "Venue & Theme Setup": 0.25,
            "Catering & Cake": 0.35,
            "Decor & Party Favors": 0.15,
            "Entertainment/Activities": 0.15,
            "Contingency": 0.10
        }

    breakdown = {}
    for category, pct in allocations.items():
        breakdown[category] = round(budget * pct, 2)

    per_person = round(budget / guest_count, 2) if guest_count > 0 else 0

    return {
        "event_type": event_type,
        "currency": currency,
        "total_budget": budget,
        "per_person_budget": per_person,
        "guest_count": guest_count,
        "allocations": breakdown
    }


def cost_estimation_tool(
    venue_cost: float,
    food_cost_per_person: float,
    decor_cost: float,
    entertainment_cost: float,
    guest_count: int,
    currency: str = ""
) -> Dict[str, Any]:
    """Estimates the total cost for an event based on component costs.

    Args:
        venue_cost: Fixed cost of hiring the venue.
        food_cost_per_person: Cost of food and beverage per person.
        decor_cost: Total cost for flowers, styling, and setups.
        entertainment_cost: Cost for musicians, DJ, speakers, etc.
        guest_count: Number of guests.
        currency: The currency code/symbol for display (e.g., "USD", "EUR").

    Returns:
        A dictionary containing the itemized cost breakdown and total estimated budget.
    """
    total_food_cost = food_cost_per_person * guest_count
    subtotal = venue_cost + total_food_cost + decor_cost + entertainment_cost
    contingency = round(subtotal * 0.10, 2)
    total_estimated = subtotal + contingency

    return {
        "currency": currency,
        "itemized": {
            "Venue Hire": venue_cost,
            "Catering": total_food_cost,
            "Decor & Setup": decor_cost,
            "Entertainment": entertainment_cost,
            "Contingency (10%)": contingency
        },
        "total_estimated": total_estimated,
        "guest_count": guest_count
    }


def venue_recommendation_tool(
    event_type: str,
    guest_count: int,
    budget: float,
    location: str = "",
    currency: str = ""
) -> List[Dict[str, Any]]:
    """Recommends suitable venue types and tiers based on event type, guest count, budget, and location.

    This tool generates generic venue recommendations by matching the event scale
    (budget per head and guest count) to appropriate venue categories. The agent
    should incorporate the actual location when presenting suggestions to the user.

    Args:
        event_type: The type of event (e.g., "wedding", "corporate", "birthday").
        guest_count: The number of guests attending.
        budget: The total budget for the event.
        location: The city or country for the event (optional, used for context).
        currency: The currency code for display (e.g., "USD", "INR").

    Returns:
        A list of venue recommendation dictionaries with tier, type, capacity guidance, and tips.
    """
    event_type = event_type.lower()
    location_str = location.strip() or "your chosen city"
    currency_str = currency.strip() or ""
    per_head = budget / guest_count if guest_count > 0 else 0

    # Define generic venue tiers based on relative per-head spend
    venue_pool = [
        {
            "tier": "Luxury / 5-Star",
            "types": ["wedding", "corporate", "gala"],
            "guest_range": (50, 800),
            "per_head_min": 150,
            "description": f"Top-tier hotel ballrooms, resort event halls, and exclusive private venues in {location_str}. Expect premium catering, dedicated event managers, and full AV.",
            "tips": "Book 6–12 months in advance. Negotiate a package that includes decor and F&B.",
        },
        {
            "tier": "Mid-Range / Boutique",
            "types": ["wedding", "corporate", "birthday", "social"],
            "guest_range": (30, 400),
            "per_head_min": 50,
            "description": f"4-star hotels, boutique event spaces, rooftop venues, and club halls in {location_str}. Good quality at a fraction of luxury cost.",
            "tips": "Ideal for most events. Ask about weekend vs. weekday pricing—weekday rates can be 30–40% cheaper.",
        },
        {
            "tier": "Budget / Community",
            "types": ["birthday", "social", "corporate", "wedding"],
            "guest_range": (10, 200),
            "per_head_min": 0,
            "description": f"Banquet halls, community centers, restaurant private dining rooms, and outdoor pavilions in {location_str}. Cost-effective and flexible.",
            "tips": "Bring your own decorator and caterer to save significantly. Negotiate a flat hire fee.",
        },
        {
            "tier": "Outdoor / Experiential",
            "types": ["birthday", "wedding", "social", "corporate"],
            "guest_range": (20, 500),
            "per_head_min": 20,
            "description": f"Parks, beachfronts, farmhouses, rooftop terraces, and heritage gardens in or near {location_str}.",
            "tips": "Always have a weather contingency plan (tent/marquee). Check local permit requirements.",
        },
        {
            "tier": "Virtual / Hybrid",
            "types": ["corporate", "social"],
            "guest_range": (10, 10000),
            "per_head_min": 0,
            "description": "Online platforms (Zoom, Hopin, Microsoft Teams) or hybrid setups combining a physical venue with live streaming.",
            "tips": "Great for international audiences. Invest in a good streaming setup and moderator team.",
        },
    ]

    results = []
    for v in venue_pool:
        type_match = any(t in event_type for t in v["types"]) or event_type in v["types"]
        cap_match = v["guest_range"][0] <= guest_count <= v["guest_range"][1]
        budget_match = per_head >= v["per_head_min"]

        if type_match and cap_match and budget_match:
            results.append({
                "tier": v["tier"],
                "description": v["description"],
                "recommended_for": f"{guest_count} guests",
                "tips": v["tips"],
                "estimated_venue_cost": f"~{currency_str} {round(budget * 0.30):,} – {round(budget * 0.45):,} (30–45% of total budget)"
            })

    if not results:
        # Fallback: always return at least the budget tier
        results.append({
            "tier": "Budget / Community",
            "description": f"Banquet halls, community spaces, and restaurant private rooms in {location_str}.",
            "recommended_for": f"{guest_count} guests",
            "tips": "Negotiate flat hire fees. Bring your own vendors to reduce costs.",
            "estimated_venue_cost": f"~{currency_str} {round(budget * 0.25):,} – {round(budget * 0.35):,}"
        })

    return results


def guest_capacity_validation_tool(venue_name: str, guest_count: int) -> Dict[str, Any]:
    """Validates whether a given venue or venue tier can accommodate the expected guest count.

    Args:
        venue_name: The name or tier of the venue to validate (e.g., "Luxury Ballroom", "Boutique Hall").
        guest_count: The expected number of guests.

    Returns:
        A dictionary with validation status, capacity guidance, and any warnings.
    """
    # Generic capacity ranges by venue tier keywords
    tier_capacities = {
        "luxury": (100, 800),
        "5-star": (100, 800),
        "ballroom": (80, 600),
        "mid-range": (30, 400),
        "boutique": (30, 300),
        "budget": (10, 200),
        "community": (10, 200),
        "outdoor": (20, 500),
        "virtual": (10, 10000),
        "hybrid": (10, 10000),
        "rooftop": (20, 200),
        "restaurant": (10, 150),
    }

    matched_min, matched_max = 10, 500  # sensible defaults
    matched_tier = "general venue"

    for keyword, (mn, mx) in tier_capacities.items():
        if keyword in venue_name.lower():
            matched_min = mn
            matched_max = mx
            matched_tier = keyword
            break

    status = "VALID"
    warning = None

    if guest_count > matched_max:
        status = "OVERCAPACITY"
        warning = f"Guest count ({guest_count}) exceeds the typical maximum for a {matched_tier} ({matched_max}). Consider a larger venue."
    elif guest_count < matched_min:
        status = "UNDER_MINIMUM"
        warning = f"Guest count ({guest_count}) is below the typical minimum for a {matched_tier} ({matched_min}). A smaller, more intimate space may be more appropriate."

    return {
        "venue_name": venue_name,
        "status": status,
        "guest_count": guest_count,
        "typical_capacity_range": f"{matched_min}–{matched_max}",
        "warning": warning
    }


def event_timeline_tool(event_type: str, lead_time_months: int = 6) -> Dict[str, List[str]]:
    """Generates a structured schedule/timeline of tasks leading up to the event date.

    Args:
        event_type: Type of event (e.g., "wedding", "corporate").
        lead_time_months: Number of months of lead time available.

    Returns:
        A dictionary mapping timeframes (e.g., "6 Months Before") to a list of tasks.
    """
    event_type = event_type.lower()

    timeline = {
        "Launch / Strategy Planning": [
            "Confirm total budget and guest count.",
            "Research and shortlist venue options in preferred location.",
            "Establish event theme and design goals."
        ],
        "3 Months Before": [
            "Finalize venue contract and pay deposit.",
            "Book key vendors (Catering, AV/Setup, Entertainment).",
            "Send out Save-the-Dates or initial RSVPs."
        ],
        "1 Month Before": [
            "Confirm guest RSVP list and seating chart.",
            "Review and approve menus and decoration plans.",
            "Run-through timeline with vendors and media production team."
        ],
        "1 Week Before": [
            "Final head count confirmation with caterers.",
            "Brief setup crew on load-in schedules and styling.",
            "Confirm final payments for all vendors."
        ],
        "Event Day": [
            "Conduct early morning venue walkthrough.",
            "Manage vendor setup and soundchecks.",
            "Execute event rundown (Greeting, Keynotes/Reception, Dining, Close)."
        ]
    }

    if "wedding" in event_type:
        timeline["Launch / Strategy Planning"].append("Select wedding attire and bridal party requirements.")
        timeline["3 Months Before"].append("Finalize florals, attire fittings, and wedding cake order.")
        timeline["1 Month Before"].append("Conduct wedding dress fittings and hair/makeup trials.")
        timeline["1 Week Before"].append("Wedding rehearsal and final host briefings.")
    elif "corporate" in event_type:
        timeline["Launch / Strategy Planning"].append("Define corporate goals, keynote topics, and VIP speakers.")
        timeline["3 Months Before"].append("Confirm speaker list, draft agendas, and begin guest registration.")
        timeline["1 Month Before"].append("Print banners, program guides, and finalize branding backdrops.")
        timeline["1 Week Before"].append("Perform rehearsal of presentations and tech check with AV team.")

    return timeline


def checklist_generator_tool(event_type: str, guest_count: int) -> List[str]:
    """Generates an actionable checklist for event preparation based on the size and type of event.

    Args:
        event_type: The type of event.
        guest_count: Expected guest count.

    Returns:
        A list of checklist item strings.
    """
    event_type = event_type.lower()

    checklist = [
        "Create shared spreadsheet for RSVP tracking.",
        "Sign contracts and secure liability policies.",
        "Review dietary restrictions (e.g., Vegan, Vegetarian, Gluten-free, religious requirements).",
        "Set up signages and directional banners.",
        "Prepare emergency contact list for all vendors."
    ]

    if guest_count > 200:
        checklist.append("Hire crowd control/security and arrange dedicated parking or transport.")
        checklist.append("Set up multiple buffet lines or check-in counters to avoid queues.")
    if guest_count > 100:
        checklist.append("Arrange host/usher team for check-in and guest guidance.")

    if "wedding" in event_type:
        checklist.extend([
            "Arrange bridal suite access.",
            "Confirm ring bearer and flower arrangements.",
            "Set up guestbook table and gift station.",
            "Brief DJ/Band on first dance and exit songs."
        ])
    elif "corporate" in event_type:
        checklist.extend([
            "Prepare VIP speaker badges and registration table.",
            "Set up high-speed Wi-Fi access for attendees.",
            "Confirm presentation slides compatibility with AV projector.",
            "Prepare speaker gift bags and certificates."
        ])
    elif "birthday" in event_type:
        checklist.extend([
            "Confirm birthday cake delivery time.",
            "Prepare party favors / goody bags.",
            "Arrange photographer for group photo."
        ])

    return checklist


def risk_analysis_tool(event_type: str, guest_count: int, budget: float) -> List[Dict[str, str]]:
    """Analyzes potential risks for an event based on type, guest count, and budget.

    Args:
        event_type: The type of event (e.g., "wedding", "corporate").
        guest_count: Expected guest count.
        budget: Total budget (any currency — comparisons are relative to per-head spend).

    Returns:
        A list of dictionaries containing identified risks and mitigation strategies.
    """
    event_type = event_type.lower()
    risks = []
    per_head = budget / guest_count if guest_count > 0 else 0

    # Budget risk: flag if per-head is very low (below a generic threshold)
    if per_head < 50:
        risks.append({
            "risk": "Tight Budget — Risk of Overrun",
            "mitigation": "Limit customization on decor, switch to buffet catering instead of plated, and scout community or publicly available venues to reduce hire costs."
        })

    if guest_count > 200:
        risks.append({
            "risk": "Guest Check-in Congestion",
            "mitigation": "Set up multiple QR check-in lanes, hire professional hosts/ushers, and send entry instructions in advance."
        })

    if "wedding" in event_type:
        risks.append({
            "risk": "Bridal Delay & Program Handoffs",
            "mitigation": "Buffer all timeline milestones by 15–20 minutes, assign a dedicated coordinator for program cues, and prepare backups for AV slides."
        })
    elif "corporate" in event_type:
        risks.append({
            "risk": "AV/Technical Slide Failures",
            "mitigation": "Conduct a technical rehearsal 1 hour before, store backups on a physical USB drive, and have a backup microphone ready."
        })
    else:
        risks.append({
            "risk": "Weather Disruption (Outdoor social events)",
            "mitigation": "Secure indoor reserve space or arrange weather-proofing elements like tents/canopies."
        })

    return risks
