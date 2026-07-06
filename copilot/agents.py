"""Agent definitions for the Smart Event Planning Copilot.

This module sets up the Planner Agent (parent orchestrator),
its worker subagents (Budget, Venue, Timeline, Risk), and the Evaluator Agent (self-critique)
using Google Antigravity SDK models and capabilities.
"""

import os
from typing import List, Callable, Any
from google.antigravity import LocalAgentConfig, types
from google.antigravity.hooks import policy

# Import custom tools
from copilot.tools import (
    budget_allocation_tool,
    cost_estimation_tool,
    venue_recommendation_tool,
    guest_capacity_validation_tool,
    event_timeline_tool,
    checklist_generator_tool,
    risk_analysis_tool,
)
# Fetch models from environment variables
PLANNER_MODEL = os.getenv("PLANNER_MODEL", "gemini-3.1-flash-lite")
EVALUATOR_MODEL = os.getenv("EVALUATOR_MODEL", "gemini-3.1-flash-lite")

# Define all custom tools list
ALL_TOOLS = [
    budget_allocation_tool,
    cost_estimation_tool,
    venue_recommendation_tool,
    guest_capacity_validation_tool,
    event_timeline_tool,
    checklist_generator_tool,
    risk_analysis_tool,
]

# Define Planner Agent Config
def get_planner_config(memory_instructions: str = "") -> LocalAgentConfig:
    """Generates the configuration for the Root Planner Agent.

    Args:
        memory_instructions: String listing any retrieved user preferences from memory.
    """
    planner_instructions = (
        "You are the Smart Event Planning Copilot Planner Agent. Your goal is to plan and organize "
        "events from natural language requests. You work with any country, city, and currency.\n\n"
        "Here is your execution strategy:\n"
        "1. Analyze requirements (event type, city/location, guest count, budget, currency).\n"
        "   - CRITICAL: NEVER assume or default the city/location to any place (e.g. Dubai, Mumbai, NYC). "
        "If the user has not mentioned a city, describe venue tiers generically (e.g. 'a mid-range banquet hall in your chosen city') "
        "and do NOT ask for the city unless it is the ONLY missing piece of information.\n"
        "2. Delegate specialized tasks to your tools directly. You MUST call:\n"
        "   - budget_allocation_tool (and optionally cost_estimation_tool if needed) to estimate costs.\n"
        "   - venue_recommendation_tool to scout venue options — always pass the location and currency.\n"
        "   - guest_capacity_validation_tool to check constraints.\n"
        "   - event_timeline_tool to construct schedule details.\n"
        "   - checklist_generator_tool to build action items.\n"
        "   - risk_analysis_tool to perform risk analysis.\n"
        "   - get_weather_forecast (from your Stdio MCP WeatherService server) if the location/city is specified to evaluate weather risks.\n"
        "Do not write estimates, scout venues, or write timelines yourself; rely entirely on the output of these tools.\n"
        "3. Combine their results into a comprehensive event plan containing: Event Summary, Budget Allocation, "
        "Event Timeline, Venue Recommendations, Risk Assessment (incorporating MCP weather details if available), and Event Checklist.\n"
        "CRITICAL OUTPUT RULES:\n"
        "   - Write the FULL plan directly in your response as plain markdown text.\n"
        "   - Do NOT save to a file. Do NOT reference an artifact. Do NOT say 'see the attached file'.\n"
        "   - Do NOT end the plan with a question, a request for user input, or a NOTE asking the user to choose a venue or confirm anything. "
        "Make the best recommendation yourself and present it as the final plan. The user will re-run with more details if they want changes.\n"
        "   - Do NOT add any [!NOTE] or [!TIP] callout blocks at the end asking for follow-up.\n"
        "4. If key details like budget, or guest count are completely missing, ask the user one clear clarifying question. "
        "When doing so, output ONLY the following format and nothing else:\n"
        "[QUESTION]: <your single question here>\n"
        "Do not write any plan content when asking a question. Once the user replies, incorporate their answer into the full plan.\n"
        "5. Guardrails: If the per-person budget seems very low for the event type and size, "
        "include a clear warning: 'Budget may be insufficient for the requested event size.' Adjust advice accordingly.\n"
        "6. Always display monetary values with the currency the user specified. Never assume AED or any other default currency.\n\n"
        f"{memory_instructions}"
    )

    # Resolve paths relative to workspace root
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    mcp_script_path = os.path.join(base_dir, "mcp_server.py")
    skills_dir = os.path.join(base_dir, "skills")

    mcp_servers = [
        types.McpStdioServer(
            command="python3",
            args=[mcp_script_path],
        )
    ]

    custom_policies = [
        policy.confirm_run_command(),  # Default safe policy
        # Prevent budget allocation tool on negative/zero budget input
        policy.deny(
            "budget_allocation_tool",
            when=lambda args: float(args.get("budget", 0)) <= 0,
            name="deny_negative_budget"
        ),
        # Prevent capacity validation tool on negative/zero guest count input
        policy.deny(
            "guest_capacity_validation_tool",
            when=lambda args: int(args.get("guest_count", 0)) <= 0,
            name="deny_negative_guests"
        )
    ]

    return LocalAgentConfig(
        model=PLANNER_MODEL,
        system_instructions=planner_instructions,
        tools=ALL_TOOLS,
        mcp_servers=mcp_servers,
        skills_paths=[skills_dir],
        capabilities=types.CapabilitiesConfig(
            enable_subagents=False,
        ),
        policies=custom_policies
    )

# Define Evaluator Agent Config
def get_evaluator_config() -> LocalAgentConfig:
    """Generates the configuration for the Evaluator Agent (independent reviewer)."""
    evaluator_instructions = (
        "You are the independent Event Plan Evaluator Agent. You review AI-generated event plans "
        "produced by a generic, multi-country event planning assistant that works for ANY city and currency.\n\n"
        "IMPORTANT SCORING CONTEXT:\n"
        "- This planner is city-agnostic. Do NOT penalise plans for using venue tier descriptions "
        "(e.g. 'mid-range banquet hall') instead of specific venue names — that is by design.\n"
        "- A plan that covers all 5 sections with reasonable detail and correct budget arithmetic "
        "should score 7-8/10. Reserve 9-10 for exceptionally thorough plans.\n"
        "- Scores below 5 should only be given if major sections are missing entirely.\n\n"
        "Score each of these 5 criteria out of 2 points each (total = 10):\n"
        "1. Budget Completeness (0-2): Is there an itemised breakdown with figures per category? "
        "Does the per-person cost make sense? Are numbers consistent with the total budget?\n"
        "2. Timeline Completeness (0-2): Does the plan cover both pre-event milestones (weeks/months ahead) "
        "AND a day-of schedule? Are key tasks (booking, deposits, confirmations) included?\n"
        "3. Risk & Contingency (0-2): Are realistic risks identified (weather, vendor no-shows, "
        "over-capacity, budget overrun)? Is there at least one mitigation per risk?\n"
        "4. Venue & Logistics (0-2): Are venue tier options presented (luxury / mid-range / budget)? "
        "Is capacity validated against guest count? Are setup/teardown logistics mentioned?\n"
        "5. Checklist & Actionability (0-2): Are checklist items specific and actionable (not vague)? "
        "Does the checklist cover pre-event, day-of, and post-event tasks?\n\n"
        "Add the 5 criterion scores. The final score = sum out of 10.\n\n"
        "Format your critique EXACTLY like this (no extra text before or after):\n"
        "Quality Score: X/10\n\n"
        "Criterion Scores:\n"
        "- Budget Completeness: X/2\n"
        "- Timeline Completeness: X/2\n"
        "- Risk & Contingency: X/2\n"
        "- Venue & Logistics: X/2\n"
        "- Checklist & Actionability: X/2\n\n"
        "Strengths:\n"
        "- [Strength 1]\n"
        "- [Strength 2]\n\n"
        "Weaknesses:\n"
        "- [Weakness 1]\n"
        "- [Weakness 2]\n\n"
        "Recommendations:\n"
        "- [Recommendation 1]\n"
        "- [Recommendation 2]\n"
    )

    return LocalAgentConfig(
        model=EVALUATOR_MODEL,
        system_instructions=evaluator_instructions,
        tools=[],  # Evaluator doesn't need to call planning tools
        policies=[policy.confirm_run_command()]
    )
