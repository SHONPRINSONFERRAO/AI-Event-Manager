import asyncio
import os
from dotenv import load_dotenv

load_dotenv()

async def main():
    print("Starting pipeline test...")
    prompt = "Plan a wedding reception in Dubai for 250 guests with a budget of AED 80,000."
    print("Prompt defined. Running pipeline...")
    try:
        from copilot.agents import get_planner_config, get_evaluator_config
        from copilot.memory import _memory_manager
        from google.antigravity import Agent
        
        print("Imports complete.")
        print("1. Retrieving memory...")
        memory_instruction = _memory_manager.format_as_instruction()
        print("2. Memory retrieved. Configuring planner agent...")
        planner_config = get_planner_config(memory_instruction)
        
        print("Opening Agent context...")
        async with Agent(planner_config) as planner_agent:
            print("Agent session opened. Sending chat...")
            response = await planner_agent.chat(prompt)
            print("Chat response initiated.")
            # Skip thoughts
            print("Skipping thoughts. Getting text...")
            draft_plan = await response.text()
            print("Text received!")
        
        print("Pipeline finished successfully!")
    except Exception as e:
        print("Pipeline failed:", type(e), e)

if __name__ == "__main__":
    asyncio.run(main())
