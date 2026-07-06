"""Streamlit frontend for the Smart Event Planning Copilot.

Provides a web UI to test scenarios, manage preferences,
and watch multi-agent execution traces in real-time.
"""

import streamlit as st
import streamlit.components.v1 as components
import asyncio
import time
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv(override=True)

import queue
import threading
import logging

class QueueHandler(logging.Handler):
    """Custom logging handler to push standard python logs (warnings, errors) to the Streamlit UI queue."""
    def __init__(self, log_queue):
        super().__init__()
        self.log_queue = log_queue
        
    def emit(self, record):
        msg = self.format(record)
        self.log_queue.put(("SystemLog", msg))

def run_pipeline_threaded(run_func, prompt):
    """Runs the pipeline in a background thread, pushing logs to a queue to keep Streamlit responsive."""
    log_queue = queue.Queue()
    result_holder = {}
    
    def target():
        # Redirect all warning/error logs to our Streamlit queue
        handler = QueueHandler(log_queue)
        handler.setFormatter(logging.Formatter('%(message)s'))
        root_logger = logging.getLogger()
        # Set level to capture warnings/errors
        root_logger.addHandler(handler)
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        def on_log(category: str, message: str, details=None):
            log_queue.put((category, message))
            
        try:
            res = loop.run_until_complete(run_func(prompt, on_log=on_log))
            result_holder["result"] = res
        except Exception as e:
            result_holder["error"] = e
        finally:
            root_logger.removeHandler(handler)
            tasks = [t for t in asyncio.all_tasks(loop) if not t.done()]
            for task in tasks:
                task.cancel()
            if tasks:
                loop.run_until_complete(asyncio.gather(*tasks, return_exceptions=True))
            loop.close()
            
    thread = threading.Thread(target=target)
    thread.start()
    return thread, log_queue, result_holder

def st_mermaid(code: str):
    """Renders a Mermaid diagram in Streamlit using a HTML component and CDN script."""
    html_code = f"""
    <div class="mermaid">
        {code}
    </div>
    <script type="module">
        import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs';
        mermaid.initialize({{ startOnLoad: true, theme: 'dark' }});
    </script>
    """
    components.html(html_code, height=600, scrolling=True)

# Initialize session state for persistent results across toggles
if "result" not in st.session_state:
    st.session_state["result"] = None

# Set up page configurations
st.set_page_config(
    page_title="Smart Event Planning Copilot",
    page_icon="📅",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Premium styling — gradient wallpaper theme (yellow → hot pink → deep purple)
st.markdown("""
<link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;700;800&display=swap" rel="stylesheet">
<style>
    /* ─── GLOBAL RESET & FONT ─────────────────────────────────────── */
    html, body, [class*="css"] {
        font-family: 'Outfit', sans-serif !important;
    }

    /* ─── ANIMATED GRADIENT BACKGROUND ──────────────────────────── */
    .stApp {
        background: linear-gradient(135deg, #FFB347 0%, #FF4E8A 40%, #A020C8 75%, #5B0FA8 100%);
        background-size: 400% 400%;
        animation: gradientShift 12s ease infinite;
        min-height: 100vh;
    }
    @keyframes gradientShift {
        0%   { background-position: 0% 50%; }
        50%  { background-position: 100% 50%; }
        100% { background-position: 0% 50%; }
    }

    /* ─── MAIN CONTENT GLASS PANEL ───────────────────────────────── */
    .block-container {
        background: rgba(15, 5, 30, 0.55) !important;
        backdrop-filter: blur(28px) !important;
        -webkit-backdrop-filter: blur(28px) !important;
        border-radius: 24px !important;
        border: 1px solid rgba(255, 255, 255, 0.12) !important;
        padding: 2.5rem 3rem !important;
        box-shadow: 0 24px 80px rgba(80, 0, 120, 0.45) !important;
        margin-top: 1.5rem !important;
    }

    /* ─── TITLE ──────────────────────────────────────────────────── */
    .main-title {
        font-size: 3rem;
        font-weight: 800;
        background: linear-gradient(90deg, #FFD700, #FF69B4, #DA70D6);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        letter-spacing: -0.5px;
        margin-bottom: 0.1rem;
        text-shadow: none;
    }

    /* ─── METRIC / SUMMARY CARDS ────────────────────────────────── */
    .metric-card {
        background: rgba(255, 255, 255, 0.07);
        backdrop-filter: blur(16px);
        -webkit-backdrop-filter: blur(16px);
        border-radius: 16px;
        padding: 20px 22px;
        border: 1px solid rgba(255, 255, 255, 0.18);
        box-shadow: 0 8px 32px rgba(160, 32, 200, 0.25);
        margin-bottom: 10px;
        color: #ffffff;
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    }
    .metric-card:hover {
        transform: translateY(-3px);
        box-shadow: 0 12px 40px rgba(255, 78, 138, 0.4);
    }
    .metric-card b {
        font-size: 0.78rem;
        text-transform: uppercase;
        letter-spacing: 1.5px;
        color: rgba(255,255,255,0.55);
        font-weight: 600;
    }
    .metric-card span {
        color: #fff;
    }

    /* ─── TRACE LOG ─────────────────────────────────────────────── */
    .trace-log {
        font-family: 'Courier New', Courier, monospace;
        background: rgba(0, 0, 0, 0.35);
        color: #f9c6ff;
        padding: 12px 16px;
        border-radius: 10px;
        margin-bottom: 6px;
        font-size: 0.83rem;
        border: 1px solid rgba(218, 112, 214, 0.3);
    }

    /* ─── GENERAL TEXT ───────────────────────────────────────────── */
    p, li, span, label, .stMarkdown {
        color: rgba(255, 255, 255, 0.88) !important;
    }
    h1, h2, h3, h4 {
        color: #fff !important;
    }

    /* ─── TEXT INPUTS & TEXT AREA ────────────────────────────────── */
    /* Kill Streamlit's white wrapper backgrounds */
    .stTextArea > div,
    .stTextArea > div > div,
    .stTextInput > div,
    .stTextInput > div > div {
        background: transparent !important;
        border: none !important;
        box-shadow: none !important;
    }
    .stTextArea textarea,
    .stTextInput input {
        background: rgba(255, 255, 255, 0.06) !important;
        border: 1.5px solid rgba(255, 105, 180, 0.45) !important;
        border-radius: 12px !important;
        color: #fff !important;
        font-family: 'Outfit', sans-serif !important;
        transition: border-color 0.25s, box-shadow 0.25s;
    }
    .stTextArea textarea:focus,
    .stTextInput input:focus {
        background: rgba(255, 255, 255, 0.10) !important;
        border-color: #FF69B4 !important;
        box-shadow: 0 0 0 3px rgba(255, 105, 180, 0.2) !important;
        outline: none !important;
    }
    .stTextArea label,
    .stTextInput label {
        color: rgba(255,255,255,0.75) !important;
        font-weight: 600 !important;
        font-size: 0.9rem !important;
        letter-spacing: 0.3px !important;
        background: transparent !important;
    }

    /* ─── NUMBER INPUT ───────────────────────────────────────────── */
    /* Nuke every wrapper layer Streamlit generates */
    .stNumberInput,
    .stNumberInput > div,
    .stNumberInput > div > div,
    .stNumberInput > div > div > div,
    .stNumberInput [data-baseweb="input"],
    .stNumberInput [data-baseweb="base-input"] {
        background: transparent !important;
        background-color: transparent !important;
        border: none !important;
        box-shadow: none !important;
    }
    /* The actual <input> element */
    .stNumberInput input {
        background: rgba(255, 255, 255, 0.05) !important;
        background-color: rgba(255, 255, 255, 0.05) !important;
        border: 1.5px solid rgba(160, 32, 200, 0.55) !important;
        border-radius: 12px !important;
        color: #fff !important;
        font-family: 'Outfit', sans-serif !important;
        box-shadow: none !important;
    }
    .stNumberInput input:focus {
        background: rgba(255, 255, 255, 0.09) !important;
        border-color: #DA70D6 !important;
        box-shadow: 0 0 0 3px rgba(160, 32, 200, 0.2) !important;
    }
    .stNumberInput label {
        color: rgba(255,255,255,0.75) !important;
        font-weight: 600 !important;
        font-size: 0.9rem !important;
        background: transparent !important;
    }
    /* +/- stepper buttons */
    .stNumberInput button,
    .stNumberInput [data-testid="stNumberInputStepUp"],
    .stNumberInput [data-testid="stNumberInputStepDown"] {
        background: rgba(255, 255, 255, 0.07) !important;
        background-color: rgba(255, 255, 255, 0.07) !important;
        color: #fff !important;
        border-radius: 8px !important;
        border: 1px solid rgba(255,255,255,0.12) !important;
        box-shadow: none !important;
    }

    /* ─── SELECTBOX ──────────────────────────────────────────────── */
    /* Kill white wrapper */
    .stSelectbox > div,
    .stSelectbox > label {
        background: transparent !important;
    }
    .stSelectbox > div > div,
    .stSelectbox [data-baseweb="select"] > div {
        background: rgba(255, 255, 255, 0.06) !important;
        border: 1.5px solid rgba(160, 32, 200, 0.5) !important;
        border-radius: 12px !important;
        color: #fff !important;
        box-shadow: none !important;
    }
    /* Dropdown option list */
    [data-baseweb="popover"] ul,
    [data-baseweb="menu"] {
        background: rgba(40, 10, 60, 0.95) !important;
        border: 1px solid rgba(160,32,200,0.4) !important;
        border-radius: 12px !important;
    }
    [data-baseweb="menu"] li {
        color: #fff !important;
    }
    [data-baseweb="menu"] li:hover {
        background: rgba(255,78,138,0.2) !important;
    }
    .stSelectbox label {
        color: rgba(255,255,255,0.75) !important;
        font-weight: 600 !important;
        font-size: 0.9rem !important;
        background: transparent !important;
    }

    /* ─── PRIMARY BUTTON ─────────────────────────────────────────── */
    .stButton > button[kind="primary"] {
        background: linear-gradient(135deg, #FF4E8A, #A020C8) !important;
        color: #fff !important;
        border: none !important;
        border-radius: 14px !important;
        padding: 0.65rem 2rem !important;
        font-size: 1rem !important;
        font-weight: 700 !important;
        font-family: 'Outfit', sans-serif !important;
        letter-spacing: 0.3px !important;
        box-shadow: 0 6px 24px rgba(255, 78, 138, 0.45) !important;
        transition: transform 0.18s, box-shadow 0.18s !important;
    }
    .stButton > button[kind="primary"]:hover {
        transform: translateY(-2px) !important;
        box-shadow: 0 10px 32px rgba(160, 32, 200, 0.6) !important;
    }
    .stButton > button[kind="primary"]:active {
        transform: translateY(0px) !important;
    }

    /* ─── SECONDARY BUTTON ───────────────────────────────────────── */
    .stButton > button[kind="secondary"],
    .stButton > button {
        background: rgba(255, 255, 255, 0.1) !important;
        color: #fff !important;
        border: 1px solid rgba(255, 255, 255, 0.25) !important;
        border-radius: 12px !important;
        font-family: 'Outfit', sans-serif !important;
        font-weight: 600 !important;
        transition: background 0.18s, box-shadow 0.18s, transform 0.18s !important;
    }
    .stButton > button[kind="secondary"]:hover,
    .stButton > button:hover {
        background: rgba(255, 255, 255, 0.18) !important;
        box-shadow: 0 6px 22px rgba(160, 32, 200, 0.45) !important;
        transform: translateY(-1px) !important;
    }

    /* ─── DOWNLOAD BUTTON ────────────────────────────────────────── */
    [data-testid="stDownloadButton"] > button,
    [data-testid="stDownloadButton"] > a,
    .stDownloadButton > button,
    .stDownloadButton > a {
        background: rgba(255, 255, 255, 0.1) !important;
        color: #fff !important;
        border: 1px solid rgba(255, 255, 255, 0.25) !important;
        border-radius: 12px !important;
        font-family: 'Outfit', sans-serif !important;
        font-weight: 600 !important;
        width: 100% !important;
        transition: background 0.18s, box-shadow 0.18s, transform 0.18s !important;
    }
    [data-testid="stDownloadButton"] > button:hover,
    [data-testid="stDownloadButton"] > a:hover,
    .stDownloadButton > button:hover,
    .stDownloadButton > a:hover {
        background: rgba(255, 255, 255, 0.18) !important;
        box-shadow: 0 6px 22px rgba(160, 32, 200, 0.45) !important;
        transform: translateY(-1px) !important;
        color: #fff !important;
    }

    /* ─── INFO / ALERT BOXES ─────────────────────────────────────── */
    .stAlert {
        background: rgba(255, 78, 138, 0.12) !important;
        border: 1px solid rgba(255, 78, 138, 0.35) !important;
        border-radius: 14px !important;
        color: #fff !important;
    }

    /* ─── DIVIDER ────────────────────────────────────────────────── */
    hr {
        border-color: rgba(255, 255, 255, 0.12) !important;
    }

    /* ─── SPINNER ────────────────────────────────────────────────── */
    .stSpinner > div {
        border-top-color: #FF4E8A !important;
    }

    /* ─── EXPANDER ───────────────────────────────────────────────── */
    .streamlit-expanderHeader {
        background: rgba(255, 255, 255, 0.06) !important;
        border-radius: 10px !important;
        color: #fff !important;
        font-weight: 600 !important;
    }

    /* ─── HIDE STREAMLIT CHROME ──────────────────────────────────── */
    .stDeployButton { display: none !important; }
    header { visibility: hidden !important; }
    #MainMenu { visibility: hidden !important; }
    footer { visibility: hidden !important; }
</style>
""", unsafe_allow_html=True)

# Setup memory and load environment settings
from copilot.memory import _memory_manager

# Main page layout
st.markdown('''
<div style="margin-bottom: 1.5rem;">
    <h1 class="main-title">✨ Smart Event Planning Copilot</h1>
    <p style="color:rgba(255,255,255,0.5); font-size:1.05rem; margin-top:0.2rem; letter-spacing:0.3px;">
        Powered by Gemini · Planner &amp; Evaluator Agents · 5 Intelligent Tools
    </p>
</div>
''', unsafe_allow_html=True)

# Initialize session state for active prompt and results
if "active_desc" not in st.session_state:
    st.session_state["active_desc"] = "Plan a birthday party for my team."

# Developer Mode disabled by default
dev_mode = False

# Load active defaults from memory JSON if available
prefs = _memory_manager.get_all()

CURRENCIES = [
    "INR", "AED", "USD", "EUR", "GBP", "SGD", "AUD", "CAD",
    "SAR", "QAR", "KWD", "BHD", "OMR", "PKR", "BDT", "LKR",
    "MYR", "IDR", "THB", "PHP", "NGN", "KES", "ZAR", "EGP",
    "TRY", "JPY", "CNY", "KRW", "BRL", "MXN", "CHF", "SEK",
    "NOK", "DKK", "NZD"
]

default_guests = 100
if "guest_count_preferences" in prefs:
    try:
        default_guests = int(prefs["guest_count_preferences"])
    except ValueError:
        pass

default_budget = 5000
default_currency_idx = 0
if "budget_preferences" in prefs:
    budget_str = prefs["budget_preferences"]
    parts = budget_str.split()
    if len(parts) >= 2:
        curr = parts[0].upper()
        try:
            default_budget = int(parts[-1].replace(",", ""))
            if curr in CURRENCIES:
                default_currency_idx = CURRENCIES.index(curr)
        except ValueError:
            pass

# Structured Event Parameter Fields
col1, col2, col3 = st.columns(3)
guest_count = col1.number_input("Guests Count 👥", min_value=1, value=default_guests, step=10)
budget = col2.number_input("Budget Amount 💰", min_value=0, value=default_budget, step=500)
currency = col3.selectbox("Currency 🪙", CURRENCIES, index=default_currency_idx)
# ── Quick-start demo scenario buttons ────────────────────────────────────────
st.markdown("**⚡ Quick Scenarios:**")
scen_cols = st.columns(4)
SCENARIOS = [
    {"label": "🎂 Birthday",  "desc": "Plan a birthday party for 50 friends with fun activities and a cake.", "guests": 50,   "budget": 30000, "currency": "INR"},
    {"label": "👔 Corporate",  "desc": "Organise a corporate annual day conference with keynote speakers and networking.", "guests": 200,  "budget": 15000, "currency": "USD"},
    {"label": "💍 Wedding",    "desc": "Plan a traditional wedding reception dinner with live music and floral decor.", "guests": 150,  "budget": 8000,  "currency": "GBP"},
    {"label": "🎉 House Party","desc": "Throw a fun house-warming party with catering and a photo booth.", "guests": 30,   "budget": 50000, "currency": "INR"},
]
for i, s in enumerate(SCENARIOS):
    if scen_cols[i].button(s["label"], key=f"scenario_{i}", use_container_width=True):
        st.session_state["active_desc"] = s["desc"]
        st.session_state["scenario_guests"]   = s["guests"]
        st.session_state["scenario_budget"]   = s["budget"]
        st.session_state["scenario_currency"] = s["currency"]
        st.rerun()

st.write("")

# Apply scenario overrides if a quick-start button was just clicked
if "scenario_guests" in st.session_state:
    default_guests   = st.session_state.pop("scenario_guests")
    default_budget   = st.session_state.pop("scenario_budget")
    _sc = st.session_state.pop("scenario_currency")
    default_currency_idx = CURRENCIES.index(_sc) if _sc in CURRENCIES else 0

user_desc = st.text_area("Event Description / Outing Prompt:", value=st.session_state["active_desc"], height=80)
st.session_state["active_desc"] = user_desc

# Combine structured values and custom description into a single prompt for the model
user_prompt = f"{user_desc} for {guest_count} guests with a budget of {currency} {budget}."

# Import orchestrator when planning starts
import importlib
import copilot.orchestrator
importlib.reload(copilot.orchestrator)
from copilot.orchestrator import run_event_planner_pipeline

if st.button("Generate Event Plan 🚀", type="primary"):
    if not os.getenv("GEMINI_API_KEY"):
        st.error("Error: `GEMINI_API_KEY` is not set. Please set it in your environment or a `.env` file.")
    else:
        # Parse and save user inputs directly to preference memory on submission
        try:
            _memory_manager.update_preference("guest_count_preferences", str(guest_count))
            _memory_manager.update_preference("budget_preferences", f"{currency} {budget}")
            from copilot.orchestrator import parse_event_summary
            summary = parse_event_summary("", user_desc)
            if summary["location"] != "Unknown":
                _memory_manager.update_preference("preferred_city", summary["location"])
            if summary["event_type"] != "Unknown":
                _memory_manager.update_preference("event_type", summary["event_type"])
        except Exception:
            pass
            
        st.session_state["result"] = None
        st.session_state["history"] = []  # reset conversation for new plan

        # ── Live agent thought streaming ───────────────────────────────────
        thought_placeholder = st.empty()
        thought_lines = []

        def _update_thoughts(lines):
            if lines:
                thought_placeholder.markdown(
                    "<div style='"
                    "background:rgba(160,32,200,0.12);"
                    "border:1px solid rgba(160,32,200,0.35);"
                    "border-radius:12px;padding:0.8rem 1rem;"
                    "font-family:monospace;font-size:0.8rem;"
                    "color:rgba(255,255,255,0.75);max-height:180px;"
                    "overflow-y:auto;margin-bottom:0.8rem;'>"
                    "<b style='color:#DA70D6;'>🧠 Agent Thinking…</b><br>"
                    + "<br>".join(lines[-12:])  # show last 12 thought lines
                    + "</div>",
                    unsafe_allow_html=True,
                )

        with st.spinner("Orchestrating Planner Agent and tools to compile your Event Plan..."):
            try:
                thread, log_queue, result_holder = run_pipeline_threaded(run_event_planner_pipeline, user_prompt)

                while thread.is_alive():
                    while not log_queue.empty():
                        cat, msg = log_queue.get()
                        if cat == "Thought":
                            # Strip common prefix noise
                            clean = msg.strip().lstrip("[").rstrip("]")
                            if clean:
                                thought_lines.append(clean)
                                _update_thoughts(thought_lines)
                    time.sleep(0.08)

                while not log_queue.empty():
                    cat, msg = log_queue.get()
                    if cat == "Thought":
                        clean = msg.strip().lstrip("[").rstrip("]")
                        if clean:
                            thought_lines.append(clean)

                thought_placeholder.empty()  # clear thought stream once done
                
                # Retrieve the result or raise error if thread failed
                if "error" in result_holder:
                    raise result_holder["error"]
                
                # Save to session state and trigger rerun to draw output
                st.session_state["result"] = result_holder["result"]
                st.rerun()
                
            except Exception as ex:
                # ── #11 Friendly error card ──────────────────────────────
                err_str = str(ex)
                if any(k in err_str.lower() for k in ["api key", "apikey", "invalid", "401", "403", "authentication"]):
                    hint = "🔑 **Your API key looks invalid or expired.** Check your `.env` file and make sure `GEMINI_API_KEY` is set correctly."
                elif any(k in err_str.lower() for k in ["quota", "rate", "429", "resource exhausted"]):
                    hint = "⏱️ **Rate limit reached.** You've hit the Gemini API quota. Wait a minute and try again, or switch to a different API key."
                elif any(k in err_str.lower() for k in ["timeout", "deadline", "network", "connection"]):
                    hint = "🌐 **Network issue.** Check your internet connection and try again."
                else:
                    hint = "🔄 **Something went wrong.** Try simplifying your prompt or re-running."

                st.markdown(
                    f"""<div style="background:rgba(239,68,68,0.12);border:1px solid rgba(239,68,68,0.4);
                    border-radius:16px;padding:1.4rem 1.6rem;margin:1rem 0;">
                    <div style="color:#f87171;font-weight:800;font-size:1rem;margin-bottom:0.6rem;">
                    ❌ Pipeline Error</div>
                    <div style="color:rgba(255,255,255,0.85);margin-bottom:0.8rem;">{hint}</div>
                    <details><summary style="color:rgba(255,255,255,0.4);font-size:0.78rem;cursor:pointer;">Technical details</summary>
                    <pre style="color:rgba(255,255,255,0.35);font-size:0.72rem;margin-top:0.5rem;white-space:pre-wrap;">{err_str}</pre>
                    </details></div>""",
                    unsafe_allow_html=True,
                )

def _save_prefs_from_prompt(prompt_text):
    """Parse and persist user preferences found in a prompt."""
    try:
        from copilot.orchestrator import parse_event_summary
        s = parse_event_summary("", prompt_text)
        if s["location"] != "Unknown":
            _memory_manager.update_preference("preferred_city", s["location"])
        if s["event_type"] != "Unknown":
            _memory_manager.update_preference("event_type", s["event_type"])
        if s["guest_count"] != "Unknown":
            _memory_manager.update_preference("guest_count_preferences", s["guest_count"])
        if s["budget"] != "Unknown":
            _memory_manager.update_preference("budget_preferences", s["budget"])
    except Exception:
        pass

def _generate_pdf(summary: dict, draft_plan: str) -> bytes:
    """Generate a clean PDF of the event plan using fpdf2."""
    from fpdf import FPDF
    import re as _re

    class PDF(FPDF):
        def header(self):
            self.set_font("Helvetica", "B", 14)
            self.set_text_color(160, 32, 200)
            self.cell(0, 10, "Smart Event Planning Copilot", align="C", new_x="LMARGIN", new_y="NEXT")
            self.set_draw_color(160, 32, 200)
            self.line(10, self.get_y(), 200, self.get_y())
            self.ln(3)

        def footer(self):
            self.set_y(-15)
            self.set_font("Helvetica", "I", 8)
            self.set_text_color(150, 150, 150)
            self.cell(0, 10, f"Page {self.page_no()}", align="C")

    pdf = PDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)

    # Summary cards
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_text_color(80, 0, 120)
    pdf.cell(0, 8, "Event Overview", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(50, 50, 50)
    for label, key in [("Event Type", "event_type"), ("Location", "location"),
                       ("Guests", "guest_count"), ("Budget", "budget")]:
        pdf.cell(40, 7, f"{label}:", border=0)
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(0, 7, str(summary.get(key, "—")), new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 10)
    pdf.ln(4)

    # Plan body — strip markdown to plain text
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(30, 30, 30)
    plain = _re.sub(r"#{1,6}\s*", "", draft_plan)       # remove headings
    plain = _re.sub(r"\*\*(.+?)\*\*", r"\1", plain)      # bold
    plain = _re.sub(r"\*(.+?)\*", r"\1", plain)          # italic
    plain = _re.sub(r"`(.+?)`", r"\1", plain)            # code
    plain = _re.sub(r"\[(.+?)\]\(.+?\)", r"\1", plain)   # links
    for line in plain.split("\n"):
        line = line.strip()
        if not line:
            pdf.ln(2)
            continue
        try:
            pdf.multi_cell(0, 6, line)
        except Exception:
            pass  # skip un-encodable chars

    return bytes(pdf.output())


def _generate_ical(summary: dict, draft_plan: str) -> bytes:
    """Generate a .ics calendar file for the event."""
    from icalendar import Calendar, Event as ICalEvent
    from datetime import datetime, timedelta

    cal = Calendar()
    cal.add("prodid", "-//Smart Event Planning Copilot//EN")
    cal.add("version", "2.0")

    event = ICalEvent()
    event.add("summary", f"{summary.get('event_type', 'Event')} — {summary.get('location', '')}")
    # Default to 30 days from now if no date is in summary
    start_dt = datetime.now() + timedelta(days=30)
    event.add("dtstart", start_dt.date())
    event.add("dtend", (start_dt + timedelta(days=1)).date())
    event.add("description", f"Budget: {summary.get('budget','—')}  |  Guests: {summary.get('guest_count','—')}\n\n{draft_plan[:500]}…")
    event.add("location", summary.get("location", ""))
    cal.add_component(event)
    return cal.to_ical()


def _render_plan_turn(result, turn_idx):
    """Render one completed plan turn (summary cards + plan text + logs)."""
    import re as _re
    summary = result["summary"]
    draft_plan = result["draft_plan"]
    evaluation_report = result.get("evaluation_report", "")
    usage = result.get("usage", {})

    # ── #8 Quality Score Badge + #9 Cost Per Person + #12 Token pill ───────
    # Parse quality score from evaluator report
    score_val = None
    score_match = _re.search(r"Quality Score:\s*(\d+(?:\.\d+)?)/10", evaluation_report, _re.IGNORECASE)
    if score_match:
        score_val = float(score_match.group(1))

    # Parse cost per person
    cost_per_person = None
    try:
        budget_str = summary.get("budget", "")
        guest_str  = summary.get("guest_count", "")
        bnum = _re.search(r"[\d,]+", budget_str.replace(",", ""))
        gnum = _re.search(r"\d+", guest_str)
        if bnum and gnum:
            b = float(bnum.group().replace(",", ""))
            g = float(gnum.group())
            if g > 0:
                cpp = b / g
                # pull currency code/symbol from budget string
                cur_match = _re.match(r"([A-Z]{2,4}|[\u00a3\u20ac\u20b9\u00a5$])", budget_str.strip())
                cur_sym = cur_match.group(1) if cur_match else ""
                cost_per_person = f"{cur_sym} {cpp:,.0f}"
    except Exception:
        pass

    # Token count
    total_tokens = None
    try:
        p_usage = usage.get("planner")
        e_usage = usage.get("evaluator")
        total = 0
        for u in [p_usage, e_usage]:
            if u and hasattr(u, "total_token_count"):
                total += u.total_token_count
            elif isinstance(u, dict):
                total += u.get("total_token_count", 0)
        if total > 0:
            total_tokens = total
    except Exception:
        pass

    # Render top-of-results banner row
    badge_cols = st.columns([2, 2, 3] if cost_per_person else [2, 5])
    col_idx = 0

    if score_val is not None:
        color = "#22c55e" if score_val >= 7 else ("#f59e0b" if score_val >= 5 else "#ef4444")
        emoji = "🏆" if score_val >= 8 else ("👍" if score_val >= 6 else "⚠️")
        badge_cols[col_idx].markdown(
            f"""<div style="background:rgba(255,255,255,0.08);border:1px solid {color}44;
            border-radius:16px;padding:0.9rem 1rem;text-align:center;">
            <div style="font-size:0.72rem;color:rgba(255,255,255,0.55);text-transform:uppercase;
            letter-spacing:1px;margin-bottom:0.25rem;">AI Quality Score</div>
            <div style="font-size:2rem;font-weight:800;color:{color};line-height:1;">{emoji} {score_val:.1f}<span style="font-size:1rem;color:rgba(255,255,255,0.4);">/10</span></div>
            </div>""",
            unsafe_allow_html=True,
        )
        col_idx += 1

    if cost_per_person:
        badge_cols[col_idx].markdown(
            f"""<div style="background:rgba(255,255,255,0.08);border:1px solid rgba(255,78,138,0.35);
            border-radius:16px;padding:0.9rem 1rem;text-align:center;">
            <div style="font-size:0.72rem;color:rgba(255,255,255,0.55);text-transform:uppercase;
            letter-spacing:1px;margin-bottom:0.25rem;">💸 Cost per Guest</div>
            <div style="font-size:1.7rem;font-weight:800;color:#FF4E8A;line-height:1;">{cost_per_person}</div>
            </div>""",
            unsafe_allow_html=True,
        )
        col_idx += 1

    if total_tokens:
        badge_cols[col_idx].markdown(
            f"""<div style="background:rgba(255,255,255,0.06);border:1px solid rgba(255,255,255,0.12);
            border-radius:16px;padding:0.9rem 1rem;text-align:center;">
            <div style="font-size:0.72rem;color:rgba(255,255,255,0.55);text-transform:uppercase;
            letter-spacing:1px;margin-bottom:0.25rem;">⚡ Tokens Used</div>
            <div style="font-size:1.5rem;font-weight:700;color:rgba(255,255,255,0.75);line-height:1;">~{total_tokens:,}</div>
            <div style="font-size:0.68rem;color:rgba(255,255,255,0.35);margin-top:2px;">planner + evaluator</div>
            </div>""",
            unsafe_allow_html=True,
        )

    st.write("")
    # ────────────────────────────────────────────────────────────────────

    st.subheader("📋 Event Summary")
    sc1, sc2, sc3, sc4 = st.columns(4)
    sc1.markdown(f'<div class="metric-card"><b>Event Type</b><br><span style="font-size:1.3rem;font-weight:bold;">{summary["event_type"]}</span></div>', unsafe_allow_html=True)
    sc2.markdown(f'<div class="metric-card"><b>Location</b><br><span style="font-size:1.3rem;font-weight:bold;">{summary["location"]}</span></div>', unsafe_allow_html=True)
    sc3.markdown(f'<div class="metric-card"><b>Guests</b><br><span style="font-size:1.3rem;font-weight:bold;">{summary["guest_count"]}</span></div>', unsafe_allow_html=True)
    sc4.markdown(f'<div class="metric-card"><b>Budget</b><br><span style="font-size:1.3rem;font-weight:bold;">{summary["budget"]}</span></div>', unsafe_allow_html=True)

    st.write("")
    st.subheader("📄 Generated Event Package")
    st.markdown(draft_plan)

    # ── Export buttons ──────────────────────────────────────────────────────────
    st.write("")
    exp_col1, exp_col2, _ = st.columns([1, 1, 3])
    with exp_col1:
        try:
            pdf_bytes = _generate_pdf(summary, draft_plan)
            st.download_button(
                label="📥 Download PDF",
                data=pdf_bytes,
                file_name=f"event_plan_{turn_idx+1}.pdf",
                mime="application/pdf",
                key=f"pdf_dl_{turn_idx}",
                use_container_width=True,
            )
        except Exception as pdf_err:
            st.caption(f"PDF unavailable: {pdf_err}")
    with exp_col2:
        try:
            ical_bytes = _generate_ical(summary, draft_plan)
            st.download_button(
                label="📅 Add to Calendar",
                data=ical_bytes,
                file_name=f"event_{turn_idx+1}.ics",
                mime="text/calendar",
                key=f"ical_dl_{turn_idx}",
                use_container_width=True,
            )
        except Exception as ical_err:
            st.caption(f"Calendar unavailable: {ical_err}")
    # ──────────────────────────────────────────────────────────────────────────

    # Hackathon Concept Verification Logs
    st.write("---")
    st.subheader("🪵 Hackathon Concept Verification Logs")
    st.caption("Execution proof of key agentic concepts for evaluation:")
    for log in result["tracer_logs"]:
        cat, msg = log["category"], log["message"]
        if cat == "Memory":
            st.markdown(f"🧠 **[Memory Retrieval]** *({log['timestamp']})* — {msg}")
        elif cat == "Tool Call":
            st.markdown(f"🛠️ **[Tool Call: {log['details'].get('tool','Tool')}]** *({log['timestamp']})* — {msg}")
            if log["details"].get("arguments"):
                st.caption(f"Arguments: `{log['details']['arguments']}`")
        elif cat == "Tool Result":
            st.markdown(f"✅ **[Tool Output Received]** *({log['timestamp']})* — {msg}")
        elif cat == "Pipeline" and "Planner" in msg:
            st.markdown(f"🤖 **[Planner Agent Execution]** *({log['timestamp']})* — {msg}")
        elif cat == "Pipeline" and "Evaluator" in msg:
            st.markdown(f"⚖️ **[Evaluator Critique Execution]** *({log['timestamp']})* — {msg}")

    # ── Evaluator full report ──────────────────────────────────────────────
    if evaluation_report:
        st.write("")
        # Parse criterion scores for visual breakdown
        import re as _re2
        criteria_scores = _re2.findall(
            r"-\s+(.+?):\s*(\d+(?:\.\d+)?)/2", evaluation_report
        )
        if criteria_scores:
            st.markdown("**⚖️ Evaluator Criterion Breakdown**")
            crit_cols = st.columns(len(criteria_scores))
            for i, (crit_name, crit_score) in enumerate(criteria_scores):
                sv = float(crit_score)
                dot = "🟢" if sv >= 1.5 else ("🟡" if sv >= 1 else "🔴")
                crit_cols[i].markdown(
                    f"<div style='background:rgba(255,255,255,0.06);border-radius:10px;"
                    f"padding:0.5rem 0.6rem;text-align:center;font-size:0.78rem;'>"
                    f"<div style='color:rgba(255,255,255,0.5);margin-bottom:3px;'>{crit_name}</div>"
                    f"<div style='font-weight:700;font-size:1rem;'>{dot} {sv:.0f}/2</div>"
                    f"</div>",
                    unsafe_allow_html=True,
                )
        with st.expander("📋 Full Evaluator Report", expanded=False):
            st.markdown(evaluation_report)

# ─── Conversation history: list of {"type": "plan"|"clarification", "result": ..., "prompt": ...}
if "history" not in st.session_state:
    st.session_state["history"] = []

# ─── Seed history from the first result if it arrived via Generate button
if st.session_state["result"] is not None and not st.session_state["history"]:
    r = st.session_state["result"]
    st.session_state["history"].append({
        "type": "clarification" if r.get("question") else "plan",
        "result": r,
        "prompt": user_prompt,
    })
    st.session_state["result"] = None

# ─── Render all history turns
for turn_idx, turn in enumerate(st.session_state["history"]):
    result = turn["result"]
    draft_plan = result["draft_plan"]
    is_q = bool(result.get("question"))

    if is_q:
        # Show the copilot's question as a styled info box
        st.markdown(f"""
        <div style="background:rgba(255,78,138,0.12);border:1px solid rgba(255,105,180,0.4);
                    border-radius:16px;padding:1.2rem 1.5rem;margin:1rem 0;">
            <p style="color:#FF69B4;font-weight:700;font-size:0.85rem;
                      text-transform:uppercase;letter-spacing:1px;margin:0 0 0.5rem;">
                💬 Copilot needs a bit more info
            </p>
            <p style="color:#fff;margin:0;font-size:1.05rem;">{result["question"]}</p>
        </div>
        """, unsafe_allow_html=True)

        # Only show the answer input on the LAST (most recent) clarification turn
        if turn_idx == len(st.session_state["history"]) - 1:
            answer = st.text_input(
                "Your answer:",
                placeholder="e.g. yes, proceed / use lower-cost venues / add a DJ",
                key=f"clarify_answer_{turn_idx}"
            )
            if st.button("Send Answer & Continue ➤", type="primary", key=f"clarify_btn_{turn_idx}"):
                if answer:
                    combined = f"{turn['prompt']}. User replied: {answer}"
                    _save_prefs_from_prompt(combined)
                    with st.spinner("Copilot is processing your answer..."):
                        try:
                            thread, log_queue, holder = run_pipeline_threaded(
                                run_event_planner_pipeline, combined
                            )
                            while thread.is_alive():
                                while not log_queue.empty():
                                    log_queue.get()
                                time.sleep(0.1)
                            while not log_queue.empty():
                                log_queue.get()
                            if "error" in holder:
                                raise holder["error"]
                            new_result = holder["result"]
                            new_type = "clarification" if new_result.get("question") else "plan"
                            st.session_state["history"].append({
                                "type": new_type,
                                "result": new_result,
                                "prompt": combined,
                            })
                            st.rerun()
                        except Exception as ex:
                            st.error(f"Execution failed: {ex}")
    else:
        # Render a full plan turn
        _render_plan_turn(result, turn_idx)

    # Visual separator between turns
    if turn_idx < len(st.session_state["history"]) - 1:
        st.markdown("""
        <div style="display:flex;align-items:center;margin:2rem 0;gap:1rem;">
            <div style="flex:1;height:1px;background:rgba(255,255,255,0.1);"></div>
            <span style="color:rgba(255,105,180,0.7);font-size:0.8rem;font-weight:600;white-space:nowrap;">
                ↓ Follow-up response
            </span>
            <div style="flex:1;height:1px;background:rgba(255,255,255,0.1);"></div>
        </div>
        """, unsafe_allow_html=True)
    
    # Developer tabs (Developer Mode only)
    if dev_mode:
        st.write("---")
        st.subheader("🛠️ Developer Insights Console")
        tab1, tab2 = st.tabs(["⚖️ Evaluator Critique Report", "📐 System Architecture"])
        
        with tab1:
            st.markdown(result["evaluation_report"])
            
        with tab2:
            st.markdown("### Copilot Agent & Tools Architecture")
            st_mermaid("""
            graph TD
                User([User Prompt]) --> Orchestrator[Orchestrator Pipeline]
                Orchestrator --> MemorySystem[(Memory Manager)]
                MemorySystem --> |Retrieve preferences| Orchestrator
                Orchestrator --> |Inject Memory & Prompt| PlannerAgent[Planner Agent]
                
                subgraph Planner Agent Tools Calling
                    PlannerAgent -->|calls| ToolBA[Budget Allocation Tool]
                    PlannerAgent -->|calls| ToolCE[Cost Estimation Tool]
                    PlannerAgent -->|calls| ToolVR[Venue Recommendation Tool]
                    PlannerAgent -->|calls| ToolCV[Capacity Validation Tool]
                    PlannerAgent -->|calls| ToolET[Event Timeline Tool]
                    PlannerAgent -->|calls| ToolCG[Checklist Generator Tool]
                    PlannerAgent -->|calls| ToolRA[Risk Analysis Tool]
                end

                PlannerAgent -->|Consolidates| DraftPlan[Draft Event Plan]
                DraftPlan -->|Passes to| EvaluatorAgent[Evaluator Agent]
                EvaluatorAgent -->|Self-Critique & Score| EvalReport[Evaluation Report]
                EvalReport -->|Compile| FinalPackage[Final Event Package]
                DraftPlan -->|Compile| FinalPackage
                FinalPackage --> Streamlit[Streamlit UI]
            """)

# Reload page after saving preferences
