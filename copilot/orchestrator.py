"""Orchestration pipeline for the Smart Event Planning Copilot.

This module coordinates:
1. Memory retrieval and preference injection.
2. The primary planning phase using the Planner Agent and worker subagents.
3. Observability tracing via custom hooks.
4. The critique phase using the Evaluator Agent.
"""

import asyncio
import os
import time
import re
from typing import Dict, Any, List, Optional
from google.antigravity import Agent, LocalAgentConfig, types
from google.antigravity.hooks import hooks

# Import agents, tools, and memory managers
from copilot.agents import get_planner_config, get_evaluator_config
from copilot.memory import _memory_manager

class ExecutionTracer:
    """Stores execution logs, tool invocations, and subagent handoffs for observability."""
    
    def __init__(self, on_log=None):
        self.logs: List[Dict[str, Any]] = []
        self.start_time = time.time()
        self.on_log = on_log
        
    def add_log(self, category: str, message: str, details: Optional[Dict[str, Any]] = None):
        elapsed = time.time() - self.start_time
        self.logs.append({
            "timestamp": f"{elapsed:.2f}s",
            "category": category,
            "message": message,
            "details": details or {}
        })
        if self.on_log:
            self.on_log(category, message, details)

    def get_hooks(self) -> List[Any]:
        """Returns instance-bound hook classes to pass to LocalAgentConfig."""
        tracer = self
        
        class SessionStartHook(hooks.OnSessionStartHook):
            async def run(self, context: hooks.HookContext, data: None) -> None:
                tracer.add_log("Session", "Agent session started.")
                
        class SessionEndHook(hooks.OnSessionEndHook):
            async def run(self, context: hooks.HookContext, data: None) -> None:
                tracer.add_log("Session", "Agent session ended.")
                
        class PreTurnHook(hooks.PreTurnHook):
            async def run(self, context: hooks.HookContext, data: types.Content) -> types.HookResult:
                tracer.add_log("Turn", "User turn started.", {"prompt": str(data)})
                return types.HookResult(allow=True)
                
        class PostTurnHook(hooks.PostTurnHook):
            async def run(self, context: hooks.HookContext, data: str) -> None:
                tracer.add_log("Turn", "Agent turn completed.", {"response_length": len(data)})
                
        class PreToolCallHook(hooks.PreToolCallDecideHook):
            async def run(self, context: hooks.HookContext, data: types.ToolCall) -> types.HookResult:
                tool_name = str(data.name)
                tracer.add_log("Tool Call", f"Calling tool: {tool_name}", {
                    "tool": tool_name,
                    "arguments": data.args
                })
                return types.HookResult(allow=True)
                
        class PostToolCallHook(hooks.PostToolCallHook):
            async def run(self, context: hooks.HookContext, data: types.ToolResult) -> None:
                tool_name = str(data.name)
                tracer.add_log("Tool Result", f"Tool {tool_name} returned successfully.", {
                    "result": str(data.result)[:300] + "..." if data.result else ""
                })
                    
        class ToolErrorHook(hooks.OnToolErrorHook):
            async def run(self, context: hooks.HookContext, data: Exception) -> Optional[str]:
                tracer.add_log("Tool Error", f"Tool execution failed with error: {str(data)}")
                return None  # Let default error handler proceed
                
        return [
            SessionStartHook(),
            SessionEndHook(),
            PreTurnHook(),
            PostTurnHook(),
            PreToolCallHook(),
            PostToolCallHook(),
            ToolErrorHook()
        ]


async def run_event_planner_pipeline(prompt: str, on_log=None) -> Dict[str, Any]:
    """Runs the complete event planning copilot pipeline.

    Retrives memory -> Sets up Planner Agent -> Delegates to Worker subagents ->
    Runs independent Evaluator Agent -> Compiles package.
    """
    tracer = ExecutionTracer(on_log=on_log)
    
    # 1. Retrieve user preferences from memory
    tracer.add_log("Memory", "Retrieving user planning preferences from disk.")
    memory_instruction = _memory_manager.format_as_instruction()
    if memory_instruction:
        tracer.add_log("Memory", "Loaded past preferences.", _memory_manager.get_all())
    else:
        tracer.add_log("Memory", "No past preferences found on disk.")
        
    # 2. Configure Planner Agent with Memory
    planner_config = get_planner_config(memory_instruction)
    # Register our execution tracer hooks
    planner_config.hooks = tracer.get_hooks()
    
    tracer.add_log("Pipeline", "Initializing Planner Agent and local Python tools.")
    
    # ── Record timestamp BEFORE the agent runs so we can detect new files ──
    run_start_time = time.time()

    # 3. Execute Planning Phase
    draft_plan = ""
    planner_usage = None
    try:
        async with Agent(planner_config) as planner_agent:
            tracer.add_log("Pipeline", "Planner Agent session opened. Planning event...")
            response = await planner_agent.chat(prompt)

            # Print thoughts in console (optional for notebook / logging)
            async for thought in response.thoughts:
                print(f"[Planner Thought] {thought}", end="", flush=True)
                if on_log:
                    on_log("Thought", thought)

            draft_plan = await response.text()
            planner_usage = response.usage_metadata
            tracer.add_log("Pipeline", "Planning complete. Event draft plan compiled.")

    except Exception as e:
        tracer.add_log("Error", f"Planning failed during execution: {str(e)}")
        raise e

    # ── Artifact resolution ────────────────────────────────────────────────────
    # The agent sometimes saves the plan as a .md file and returns only a link.
    # Strategy 1: check if draft_plan looks like just a summary/link (no plan sections)
    _plan_has_content = any(
        kw in draft_plan
        for kw in ["Budget", "Venue", "Timeline", "Checklist", "Risk", "##", "**Event"]
    )

    if not _plan_has_content:
        tracer.add_log("Pipeline", "Response appears to be a file reference — searching for artifact...")

        # Strategy 2: find the newest .md file written since the run started
        workspace_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        newest_file = None
        newest_mtime = run_start_time - 1  # must be newer than our start

        skip_dirs = {".git", "__pycache__", "node_modules", ".venv", "venv"}
        for root, dirs, files in os.walk(workspace_root):
            dirs[:] = [d for d in dirs if d not in skip_dirs]
            for fname in files:
                if not fname.endswith(".md"):
                    continue
                full_path = os.path.join(root, fname)
                try:
                    mtime = os.path.getmtime(full_path)
                    if mtime > newest_mtime:
                        newest_mtime = mtime
                        newest_file = full_path
                except OSError:
                    pass

        # Strategy 3: also try any path/link mentioned explicitly in the response
        explicit_link = re.search(
            r"\[.*?\]\((.*?\.md)\)|file://(.*?\.md)|([\w./\- ]+\.md)",
            draft_plan
        )
        if explicit_link:
            candidate = (
                explicit_link.group(1) or
                explicit_link.group(2) or
                explicit_link.group(3) or ""
            ).strip()
            for base in [candidate, os.path.join(workspace_root, candidate)]:
                if os.path.isfile(base):
                    newest_file = base
                    break

        if newest_file:
            try:
                with open(newest_file, "r", encoding="utf-8") as f:
                    draft_plan = f.read()
                tracer.add_log("Pipeline", f"Artifact plan loaded from: {newest_file}")
            except Exception as read_err:
                tracer.add_log("Error", f"Could not read artifact file {newest_file}: {read_err}")
        else:
            tracer.add_log("Pipeline", "No artifact file found — using raw agent response.")
    # ──────────────────────────────────────────────────────────────────────────

    # Check if the planner returned a clarifying question instead of a plan
    question_match = re.match(r"^\s*\[QUESTION\]:\s*(.+)", draft_plan, re.IGNORECASE | re.DOTALL)
    if question_match:
        question_text = question_match.group(1).strip()
        tracer.add_log("Pipeline", f"Planner is requesting clarification: {question_text}")
        summary = parse_event_summary("", prompt)
        return {
            "question": question_text,
            "summary": summary,
            "draft_plan": "",
            "evaluation_report": "",
            "tracer_logs": tracer.logs,
            "usage": {"planner": planner_usage, "evaluator": None}
        }

    # 4. Execute Evaluation Phase (only when we have a full plan)
    tracer.add_log("Pipeline", "Initializing Evaluator Agent for self-critique.")
    evaluator_config = get_evaluator_config()
    critique_report = ""
    evaluator_usage = None
    
    try:
        async with Agent(evaluator_config) as evaluator_agent:
            tracer.add_log("Pipeline", "Evaluator Agent session opened. critiquing draft plan...")
            eval_response = await evaluator_agent.chat(
                f"Please review and critique this event plan:\n\n{draft_plan}"
            )
            critique_report = await eval_response.text()
            evaluator_usage = eval_response.usage_metadata
            tracer.add_log("Pipeline", "Evaluation completed successfully.")
    except Exception as e:
        tracer.add_log("Error", f"Evaluation failed during execution: {str(e)}")
        critique_report = "Error: Evaluation agent could not critique the plan."
        
    # 5. Extract Details for Final Output Package
    summary = parse_event_summary(draft_plan, prompt)
    
    return {
        "question": None,
        "summary": summary,
        "draft_plan": draft_plan,
        "evaluation_report": critique_report,
        "tracer_logs": tracer.logs,
        "usage": {
            "planner": planner_usage,
            "evaluator": evaluator_usage
        }
    }


def parse_event_summary(plan_text: str, original_prompt: str) -> Dict[str, str]:
    """Helper to parse key summary details from the draft plan using regex or fallback."""
    summary = {
        "event_type": "Unknown",
        "location": "Unknown",
        "guest_count": "Unknown",
        "budget": "Unknown"
    }
    
    # Try to extract from plan text using common patterns
    event_type_match = re.search(r"Event Type:\s*([^\n]+)", plan_text, re.IGNORECASE)
    location_match = re.search(r"(?:Location|City):\s*([^\n]+)", plan_text, re.IGNORECASE)
    guests_match = re.search(r"(?:Guest Count|Guests|Attendees):\s*([^\n]+)", plan_text, re.IGNORECASE)
    budget_match = re.search(r"Budget:\s*([^\n]+)", plan_text, re.IGNORECASE)
    
    if event_type_match:
        summary["event_type"] = event_type_match.group(1).strip().strip("*").strip()
    else:
        # Failsafe parsing from prompt
        for et in ["wedding", "corporate", "birthday", "conference", "party", "reception"]:
            if et in original_prompt.lower():
                summary["event_type"] = et.capitalize()
                break
                
    if location_match:
        summary["location"] = location_match.group(1).strip().strip("*").strip()
    else:
        # Match "in <Location>" or "at <Location>" followed by typical boundaries
        loc_match = re.search(r"\b(?:in|at)\s+([a-zA-Z\s]{2,15}?)\b(?:\s+for|\s+with|\s+to|\s+aed|\s+usd|\s+\d|$)", original_prompt, re.IGNORECASE)
        if loc_match:
            summary["location"] = loc_match.group(1).strip().title()
        else:
            for loc in ["dubai", "abu dhabi", "sharjah", "ajman", "fujeirah"]:
                if loc in original_prompt.lower():
                    summary["location"] = loc.capitalize()
                    break
                
    if guests_match:
        summary["guest_count"] = guests_match.group(1).strip().strip("*").strip()
    else:
        guests = re.search(r"(\d+)\s*(?:guests|attendees|people|persons|members|pax)", original_prompt, re.IGNORECASE)
        if guests:
            summary["guest_count"] = guests.group(1)
        else:
            # Fallback to scanning the generated plan text for guest counts
            guests_plan = re.search(r"(\d+)\s*(?:guests|attendees|people|persons|members|pax)", plan_text, re.IGNORECASE)
            if guests_plan:
                summary["guest_count"] = guests_plan.group(1).strip().strip("*").strip()
            
    if budget_match:
        summary["budget"] = budget_match.group(1).strip().strip("*").strip()
    else:
        # Match any currency code (3 letters) or common symbols followed by digits
        budget = re.search(
            r"(?:budget\s*(?:of|is|:)?\s*)"
            r"([A-Z]{2,4}|[$€£¥₹₩₪])\s*([\d,]+[kK]?)",
            original_prompt, re.IGNORECASE
        )
        if not budget:
            # Match digits followed by currency code/word
            budget = re.search(
                r"([\d,]+[kK]?)\s*([A-Z]{2,4}|[$€£¥₹₩₪]|dollars?|euros?|pounds?|rupees?|dirhams?|riyals?|yen|won)",
                original_prompt, re.IGNORECASE
            )
            if budget:
                summary["budget"] = f"{budget.group(2).upper()} {budget.group(1)}"
                budget = None  # skip the formatting block below
        if budget:
            currency_sym = budget.group(1)
            amount = budget.group(2)
            summary["budget"] = f"{currency_sym.upper()} {amount}"

        if summary["budget"] == "Unknown":
            # Final fallback: scan generated plan text for any budget line
            budget_plan = re.search(
                r"(?:budget\s*(?:of|is|:)?\s*)([A-Z$€£¥₹]{1,4}\s*[\d,]+)",
                plan_text, re.IGNORECASE
            )
            if budget_plan:
                summary["budget"] = budget_plan.group(1).strip().strip("*").strip()
            
    return summary
