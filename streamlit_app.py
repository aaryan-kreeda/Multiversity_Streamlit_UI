"""
Streamlit Frontend for TOC Generation and Script Generation Microservices
This minimal UI calls two microservices:
1. TOC Generation Service (async with callback OR synchronous)
2. Script Generation Service (batch processing)
"""

import streamlit as st
import httpx
import asyncio
import pandas as pd
import json
import time
from typing import Dict, List, Any
from dotenv import load_dotenv
import os

# Load environment variables
# For main branch (dev): load .dev.env only
if os.path.exists(".dev.env"):
    load_dotenv(".dev.env")
else:
    load_dotenv()

# Get environment variables (supports both .env file and Streamlit Secrets)
TOC_SERVICE_URL = os.getenv("TOC_SERVICE_URL") or st.secrets.get("TOC_SERVICE_URL", None)
SCRIPT_SERVICE_URL = os.getenv("SCRIPT_SERVICE_URL") or st.secrets.get("SCRIPT_SERVICE_URL", None)

TOC_CREATE_SYNC_ENDPOINT = f"{TOC_SERVICE_URL}/create-course-sync"
SCRIPT_BATCH_ENDPOINT = f"{SCRIPT_SERVICE_URL}/generate-scripts-batch-streamlit"
SCRIPT_SINGLE_ENDPOINT = f"{SCRIPT_SERVICE_URL}/generate-script-streamlit"

# ---------- Defensive helpers ----------
def safe_list(value):
    """Return a list if value is a list-like; otherwise return empty list."""
    if isinstance(value, list):
        return value
    return []

def safe_dict(value):
    """Return a dict if value is a dict; otherwise return empty dict."""
    if isinstance(value, dict):
        return value
    return {}

def safe_str(value, max_len=None):
    """Return a safe string for display and slicing."""
    if value is None:
        s = ""
    else:
        s = str(value)
    if max_len is not None and len(s) > max_len:
        s = s[:max_len] + "..."
    return s
def safe_len(obj):
    """Return len(obj) if possible, else 0."""
    try:
        return len(obj)
    except Exception:
        return 0


# ----------------------------------------


# PAGE CONFIGURATION

st.set_page_config(
    page_title="Course & Script Generator",
    page_icon="📚",
    layout="wide"
)

# ASYNC HTTP HELPERS

async def call_toc_create_sync(payload: Dict) -> Dict:
    """Call synchronous TOC creation endpoint (waits for full response)"""
    async with httpx.AsyncClient(timeout=300.0) as client:
        response = await client.post(TOC_CREATE_SYNC_ENDPOINT, json=payload)
        return {"status_code": response.status_code, "data": response.json()}


async def call_script_batch(payload: Dict) -> Dict:
    """Call batch script generation endpoint"""
    async with httpx.AsyncClient(timeout=300.0) as client:
        response = await client.post(SCRIPT_BATCH_ENDPOINT, json=payload)
        return {"status_code": response.status_code, "data": response.json()}

async def call_script_single(payload: Dict) -> Dict:
    """Call single script generation endpoint"""
    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(SCRIPT_SINGLE_ENDPOINT, json=payload)
        return {"status_code": response.status_code, "data": response.json()}

# DISPLAY HELPERS
def display_toc_hierarchical(toc_data: Dict, course_hours: float = None):
    """
    Display TOC in hierarchical table format: Maintopic → Subtopic → Subnode
    This version is defensive against None values and unexpected types.
    
    Args:
        toc_data: TOC data dictionary
        course_hours: Total course hours from course_metadata (optional)
    """
    toc_data = safe_dict(toc_data)
    maintopics = safe_list(toc_data.get("maintopics_with_subtopics"))

    if not maintopics:
        st.warning("No TOC data available (empty or malformed structure).")
        with st.expander("View raw TOC object (debug)"):
            st.write(toc_data)
        return

    st.markdown("### 📋 Course Structure")

    rows = []
    for maintopic_entry in maintopics:
        if not isinstance(maintopic_entry, dict):
            rows.append({
                "Level": "⚠️ Error",
                "Number": "",
                "Title": safe_str(maintopic_entry),
                "Description": "",
                "Duration": ""
            })
            continue

        maintopic = safe_dict(maintopic_entry.get("maintopic"))
        subtopics = safe_list(maintopic_entry.get("subtopics"))

        maintopic_num = maintopic.get("maintopic_number", "")
        # Handle both int and str for maintopic_number
        if isinstance(maintopic_num, int):
            maintopic_num = str(maintopic_num)
        maintopic_title = maintopic.get("title", "Untitled")
        maintopic_duration = maintopic.get("duration", "N/A")
        maintopic_desc = safe_str(maintopic.get("description", ""), max_len=80)

        rows.append({
            "Level": "📚 Maintopic",
            "Number": f"**{maintopic_num}**" if maintopic_num else "",
            "Title": f"**{maintopic_title}**",
            "Description": maintopic_desc,
            "Duration": maintopic_duration
        })

        for subtopic in subtopics:
            if not isinstance(subtopic, dict):
                rows.append({
                    "Level": "  ⚠️ Error",
                    "Number": "",
                    "Title": safe_str(subtopic),
                    "Description": "",
                    "Duration": ""
                })
                continue

            subtopic_num = subtopic.get("subtopic_number", "")
            # Handle both int and str for subtopic_number
            if isinstance(subtopic_num, int):
                subtopic_num = str(subtopic_num)
            subtopic_title = subtopic.get("title", "Untitled")
            subtopic_desc = safe_str(subtopic.get("description", ""), max_len=80)
            subtopic_duration = subtopic.get("duration_minutes", 0)

            subnodes = safe_list(subtopic.get("subnodes"))
            rows.append({
                "Level": "  📖 Subtopic",
                "Number": f"{maintopic_num}.{subtopic_num}" if maintopic_num or subtopic_num else "",
                "Title": subtopic_title,
                "Description": subtopic_desc,
                "Duration": f"{subtopic_duration} min" if subtopic_duration else "-"
            })

            for subnode in subnodes:
                title = ""
                duration_str = ""
                if isinstance(subnode, dict):
                    # New format: subnode is an object with title and duration_minutes
                    title = subnode.get("title") or subnode.get("name") or str(subnode)
                    duration_minutes = subnode.get("duration_minutes", 0)
                    if duration_minutes:
                        duration_str = f"{duration_minutes} min"
                else:
                    title = safe_str(subnode)
                rows.append({
                    "Level": "    • Subnode",
                    "Number": "",
                    "Title": title,
                    "Description": "",
                    "Duration": duration_str
                })

    # Create DataFrame
    df = pd.DataFrame(rows)
    
    # Display as table
    st.dataframe(
        df,
        width='stretch',
        height=600,
        column_config={
            "Level": st.column_config.TextColumn("Level", width="small"),
            "Number": st.column_config.TextColumn("No.", width="small"),
            "Title": st.column_config.TextColumn("Title", width="large"),
            "Description": st.column_config.TextColumn("Description", width="large"),
            "Duration": st.column_config.TextColumn("Duration", width="small"),
        },
        hide_index=True,
    )
    
    # Show summary stats (defensive calculations)
    st.markdown("---")
    st.markdown("### 📊 Course Summary")

    # Use safe iteration (ignore non-dict entries)
    sane_maintopics = [m for m in maintopics if isinstance(m, dict)]
    maintopic_count = len(sane_maintopics)

    # Count subtopics defensively (only valid dict entries)
    subtopic_count = 0
    for m in sane_maintopics:
        subtopics = safe_list(m.get("subtopics"))
        for sub in subtopics:
            if isinstance(sub, dict):
                subtopic_count += 1

    # Count subnodes defensively (only valid dict entries)
    subnode_count = 0
    for m in sane_maintopics:
        for sub in safe_list(m.get("subtopics")):
            if isinstance(sub, dict):
                subnodes = safe_list(sub.get("subnodes"))
                for subnode in subnodes:
                    if isinstance(subnode, dict):
                        subnode_count += 1

    # Use course_hours from metadata if provided, otherwise calculate from subtopics
    if course_hours is not None and course_hours > 0:
        total_hours = course_hours
    else:
        # Calculate total duration defensively from subtopics as fallback
        total_minutes = 0
        for m in sane_maintopics:
            for sub in safe_list(m.get("subtopics")):
                if isinstance(sub, dict):
                    duration = sub.get("duration_minutes", 0) or 0
                    if isinstance(duration, (int, float)):
                        total_minutes += duration
        total_hours = total_minutes / 60 if total_minutes > 0 else 0

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Maintopics", maintopic_count)
    with col2:
        st.metric("Subtopics", subtopic_count)
    with col3:
        st.metric("Subnodes", subnode_count)
    with col4:
        if total_hours > 0:
            st.metric("Total Duration", f"{total_hours:.1f}h")
        else:
            st.metric("Total Duration", "N/A")

def extract_subtopics_from_toc(toc_data: Dict) -> List[Dict]:
    """
    Extract all subtopics from TOC for script generation dropdown (defensive).
    """
    toc_data = safe_dict(toc_data)
    maintopics = safe_list(toc_data.get("maintopics_with_subtopics"))
    subtopics_list = []

    for maintopic_entry in maintopics:
        if not isinstance(maintopic_entry, dict):
            continue
        maintopic = safe_dict(maintopic_entry.get("maintopic"))
        subtopics = safe_list(maintopic_entry.get("subtopics"))
        maintopic_num = maintopic.get("maintopic_number", "")
        # Handle both int and str for maintopic_number
        if isinstance(maintopic_num, int):
            maintopic_num = str(maintopic_num)
        maintopic_title = maintopic.get("title", "")

        for subtopic in subtopics:
            if not isinstance(subtopic, dict):
                # If it's a string, create a minimal entry
                title = safe_str(subtopic)
                subtopics_list.append({
                    "maintopic_number": maintopic_num,
                    "maintopic_title": maintopic_title,
                    "subtopic_number": "",
                    "subtopic_title": title,
                    "full_number": f"{maintopic_num}.",
                    "display_name": f"{maintopic_num}. - {title}",
                    "description": "",
                    "duration": 0,
                    "subnodes": []
                })
                continue

            subtopic_num = subtopic.get("subtopic_number", "")
            # Handle both int and str for subtopic_number
            if isinstance(subtopic_num, int):
                subtopic_num = str(subtopic_num)
            subtopic_title = subtopic.get("title", "")
            subtopic_desc = subtopic.get("description", "") or ""
            subtopic_duration = subtopic.get("duration_minutes", 0)
            subnodes = safe_list(subtopic.get("subnodes"))

            subtopics_list.append({
                "maintopic_number": maintopic_num,
                "maintopic_title": maintopic_title,
                "subtopic_number": subtopic_num,
                "subtopic_title": subtopic_title,
                "full_number": f"{maintopic_num}.{subtopic_num}" if (maintopic_num or subtopic_num) else "",
                "display_name": f"{maintopic_num}.{subtopic_num} - {subtopic_title}" if subtopic_num else f"{maintopic_num}. - {subtopic_title}",
                "description": subtopic_desc,
                "duration": subtopic_duration,
                "subnodes": subnodes
            })

    return subtopics_list

def extract_subnodes_from_toc(toc_data: Dict) -> List[Dict]:
    """
    Extract all subnodes from TOC for script generation dropdown (defensive).
    Returns list of subnodes with their hierarchy information.
    """
    toc_data = safe_dict(toc_data)
    maintopics = safe_list(toc_data.get("maintopics_with_subtopics"))
    subnodes_list = []

    for maintopic_entry in maintopics:
        if not isinstance(maintopic_entry, dict):
            continue
        maintopic = safe_dict(maintopic_entry.get("maintopic"))
        subtopics = safe_list(maintopic_entry.get("subtopics"))
        maintopic_num = maintopic.get("maintopic_number", "")
        # Handle both int and str for maintopic_number
        if isinstance(maintopic_num, int):
            maintopic_num = str(maintopic_num)
        maintopic_title = maintopic.get("title", "")

        for subtopic in subtopics:
            if not isinstance(subtopic, dict):
                continue
            
            subtopic_num = subtopic.get("subtopic_number", "")
            # Handle both int and str for subtopic_number
            if isinstance(subtopic_num, int):
                subtopic_num = str(subtopic_num)
            subtopic_title = subtopic.get("title", "")
            subnodes = safe_list(subtopic.get("subnodes"))

            # Extract subnodes with their index
            for subnode_idx, subnode in enumerate(subnodes, 1):
                if isinstance(subnode, dict):
                    subnode_title = subnode.get("title", "") or subnode.get("name", "") or str(subnode)
                    subnode_duration = subnode.get("duration_minutes", 0)
                else:
                    subnode_title = safe_str(subnode)
                    subnode_duration = 0
                
                # Create full number like "1.2.1"
                full_number = f"{maintopic_num}.{subtopic_num}.{subnode_idx}" if (maintopic_num and subtopic_num) else ""
                
                subnodes_list.append({
                    "maintopic_number": maintopic_num,
                    "maintopic_title": maintopic_title,
                    "subtopic_number": subtopic_num,
                    "subtopic_title": subtopic_title,
                    "subnode_index": subnode_idx,
                    "subnode_title": subnode_title,
                    "full_number": full_number,
                    "display_name": f"{full_number} - {subnode_title}" if full_number else subnode_title,
                    "description": "",  # Subnodes typically don't have descriptions
                    "duration": subnode_duration,
                    "level": "subnode"
                })

    return subnodes_list


# MAIN UI
st.title("📚 Course TOC & Script Generator")
st.markdown("---")

# Initialize session state
if "toc_response" not in st.session_state:
    st.session_state.toc_response = None
if "script_response" not in st.session_state:
    st.session_state.script_response = None
if "selected_subtopics_for_scripts" not in st.session_state:
    st.session_state.selected_subtopics_for_scripts = []
if "toc_request_in_progress" not in st.session_state:
    st.session_state.toc_request_in_progress = False
if "script_request_in_progress" not in st.session_state:
    st.session_state.script_request_in_progress = False

# TAB 1: TOC GENERATION
tab1, tab2 = st.tabs(["🎯 Generate TOC", "📝 Generate Scripts"])

with tab1:
    st.header("Table of Contents Generation")
    
    col1, col2 = st.columns(2)
    
    with col1:
        project_id = st.text_input("Project ID", value="proj_001", key="toc_project_id")
        question_id = st.text_input("Question ID", value="q_001", key="toc_question_id")
        topic = st.text_input("Course Topic", value="Python Programming", key="toc_topic")
        course_hours = st.number_input("Course Duration (hours)", min_value=1, max_value=100, value=10, key="toc_hours")
        learner_path = st.selectbox("Learner Path", ["Professional", "Student", "Entrepreneur"], key="toc_path")
        course_type = st.selectbox("Course Type", ["module", "session"], index=0, key="toc_course_type")
    
    with col2:
        regionality = st.text_input("Regionality", value="Global", key="toc_region")
        objectives = st.text_area("Learning Objectives (one per line)", 
                                  value="Master Python fundamentals\nBuild real-world applications", 
                                  key="toc_objectives")
        subtopics = st.text_area("Subtopics (one per line)", value="", key="toc_subtopics")
        learning_outputs = st.text_area("Learning Outputs (one per line, optional)", value="", key="toc_learning_outputs")
        notes = st.text_area("Additional Notes", value="No additional notes", key="toc_notes")
    
    # Check if request is already in progress
    if st.session_state.toc_request_in_progress:
        st.warning("⏳ TOC generation is already in progress. Please wait...")
        st.button("🚀 Generate TOC", type="primary", key="btn_create_toc_sync", disabled=True)
    else:
        if st.button("🚀 Generate TOC", type="primary", key="btn_create_toc_sync"):
            # Set flag to prevent duplicate requests
            st.session_state.toc_request_in_progress = True
            
            with st.spinner("Generating TOC... This may take 1-3 minutes..."):
                payload = {
                    "topic": topic,
                    "course_hours": course_hours,
                    "learner_path": learner_path,
                    "course_type": course_type,
                    "objective": objectives.split("\n") if objectives else [],
                    "course_subtopics": subtopics.split("\n") if subtopics else [],
                    "learning_outputs": learning_outputs.split("\n") if learning_outputs else None,
                    "notes": notes if notes else None,
                    "regionality": regionality if regionality else None,
                    "question_id": question_id if question_id else None,
                    "project_id": project_id if project_id else None
                }
                # Remove None values to keep payload clean
                payload = {k: v for k, v in payload.items() if v is not None}
                
                try:
                    start_time = time.time()
                    result = asyncio.run(call_toc_create_sync(payload))
                    elapsed = time.time() - start_time
                    
                    if result["status_code"] == 200:
                        data = result["data"]
                        
                        # Check for success field in response
                        if data.get("success", True):
                            st.session_state.toc_response = data
                            st.success(f"✅ TOC generated successfully in {elapsed:.2f}s!")
                            
                            # Display generation metrics
                            col_m1, col_m2, col_m3 = st.columns(3)
                            with col_m1:
                                maintopics_count = len(data.get("toc", {}).get("maintopics_with_subtopics", []))
                                st.metric("Maintopics", maintopics_count)
                            with col_m2:
                                cost = data.get("cost_summary", {}).get("total_cost_usd", 0)
                                st.metric("Cost", f"${cost:.4f}")
                            with col_m3:
                                exec_time = data.get("execution_time_s", 0)
                                st.metric("Execution Time", f"{exec_time}s")
                            
                            st.markdown("---")
                            
                            # Rerun to refresh UI and display the new TOC
                            st.rerun()
                        else:
                            # Error response format
                            error_msg = data.get("message", "Unknown error")
                            st.error(f"❌ Error: {error_msg}")
                            st.json(data)
                    else:
                        st.error(f"❌ Error: Status {result['status_code']}")
                        st.json(result["data"])
                except httpx.HTTPStatusError as e:
                    st.error(f"❌ HTTP Error: {e.response.status_code}")
                    st.error(f"Response: {e.response.text}")
                except httpx.RequestError as e:
                    st.error(f"❌ Request Error: {str(e)}")
                    if hasattr(e, 'request'):
                        st.error(f"URL attempted: {e.request.url}")
                    import traceback
                    st.code(traceback.format_exc())
                except Exception as e:
                    st.error(f"❌ Error: {str(e)}")
                    import traceback
                    st.code(traceback.format_exc())
                finally:
                    # Always reset the flag when request completes (success or error)
                    st.session_state.toc_request_in_progress = False
    
    # Only display TOC when first generated
    if st.session_state.toc_response:
        st.markdown("---")
        st.subheader("Generated Table of Contents")
        
        # Display TOC as hierarchical view
        toc_data = st.session_state.toc_response.get("toc") or {}
        course_metadata = st.session_state.toc_response.get("course_metadata", {})
        course_hours = course_metadata.get("course_hours")
        
        if toc_data and toc_data.get("maintopics_with_subtopics"):
            try:
                display_toc_hierarchical(toc_data, course_hours=course_hours)
            except Exception as display_error:
                st.error(f"Error displaying TOC: {str(display_error)}")
                with st.expander("View raw TOC data"):
                    st.json(toc_data)

        
        with st.expander("View Full Response JSON", expanded=False):
            st.json(st.session_state.toc_response)

# TAB 2: SCRIPT GENERATION FROM TOC
with tab2:
    st.header("Educational Script Generation")
    
    # Check if TOC exists
    if not st.session_state.toc_response:
        st.warning("⚠️ Please generate a TOC first in the 'Generate TOC' tab before creating scripts.")
        st.info("💡 Scripts are generated based on the subtopics in your course TOC.")
    else:
        toc_data = st.session_state.toc_response.get("toc", {})
        course_metadata = st.session_state.toc_response.get("course_metadata", {})
        
        # Extract subtopics and subnodes for dropdown
        available_subtopics = extract_subtopics_from_toc(toc_data)
        available_subnodes = extract_subnodes_from_toc(toc_data)
        
        if not available_subtopics and not available_subnodes:
            st.error("❌ No subtopics or subnodes found in the TOC. Please regenerate the TOC.")
        else:
            subtopic_count = len(available_subtopics) if available_subtopics else 0
            subnode_count = len(available_subnodes) if available_subnodes else 0
            st.success(f"✅ Found {subtopic_count} subtopics and {subnode_count} subnodes from TOC")
            
            # Display course metadata
            with st.expander("📚 Course Information", expanded=False):
                col_info1, col_info2 = st.columns(2)
                with col_info1:
                    st.write(f"**Title:** {course_metadata.get('title', 'N/A')}")
                    st.write(f"**Duration:** {course_metadata.get('course_hours', 'N/A')} hours")
                    st.write(f"**Learner Path:** {course_metadata.get('learner_path', 'N/A')}")
                with col_info2:
                    st.write(f"**Regionality:** {course_metadata.get('regionality', 'N/A')}")
                    objectives = course_metadata.get('course_objectives', [])
                    st.write(f"**Objectives:** {len(objectives)}")
            
            st.markdown("---")
            
            # Script generation settings
            st.subheader("Script Generation Settings")
            
            col_settings1, col_settings2 = st.columns(2)
            
            with col_settings1:
                # State and Region dropdowns (project level)
                col_state, col_region = st.columns(2)
                
                with col_state:
                    state = st.selectbox(
                        "State",
                        ["Pan India", "Maharashtra", "Haryana", "Odisha", "Tripura", "Bihar", "Madhya Pradesh", "Rajasthan"],
                        index=0,  # Default to "Pan India"
                        key="project_state"
                    )
                
                with col_region:
                    region = st.selectbox(
                        "Region (Optional)",
                        [None, "North", "South", "East", "West"],
                        index=0,  # Default to None
                        key="project_region",
                        help="Optional. Not used when State='Pan India'. When State is a specific state, this selects which region within that state to focus on."
                    )
                
                # Learner Path dropdown
                learner_path_options = ["Professional", "Student", "Entrepreneur"]
                default_learner_path = course_metadata.get('learner_path', 'Professional')
                try:
                    default_index = learner_path_options.index(default_learner_path)
                except ValueError:
                    default_index = 0  # Default to "Professional" if not found (now first in list)
                
                learners_path = st.selectbox(
                    "Learner's Path", 
                    learner_path_options,
                    index=default_index,
                    key="script_learner_path"
                )
            
            with col_settings2:
                default_script_type = st.selectbox(
                    "Default Script Type", 
                    ["Solo Narration", "Character Based", "Informative"],
                    key="default_script_type"
                )
                st.caption("This will be applied to all selected subtopics")
            
            st.markdown("---")
            
            # Subtopic and Subnode selection
            st.subheader("Select Subtopics and Subnodes for Script Generation")
            
            col_select1, col_select2 = st.columns(2)
            
            with col_select1:
                # Create options for subtopic multiselect
                subtopic_options = [sub["display_name"] for sub in available_subtopics] if available_subtopics else []
                
                # Multiselect for subtopics
                selected_subtopic_names = st.multiselect(
                    "Choose subtopics (you can select multiple):",
                    options=subtopic_options,
                    default=[],
                    help="Select one or more subtopics to generate scripts for",
                    key="subtopic_multiselect"
                )
            
            with col_select2:
                # Create options for subnode multiselect
                subnode_options = [sub["display_name"] for sub in available_subnodes] if available_subnodes else []
                
                # Multiselect for subnodes
                selected_subnode_names = st.multiselect(
                    "Choose subnodes (you can select multiple):",
                    options=subnode_options,
                    default=[],
                    help="Select one or more subnodes to generate scripts for",
                    key="subnode_multiselect"
                )
            
            # Combine selected subtopics and subnodes
            selected_subtopics = [
                sub for sub in available_subtopics 
                if sub["display_name"] in selected_subtopic_names
            ] if available_subtopics else []
            
            selected_subnodes = [
                sub for sub in available_subnodes 
                if sub["display_name"] in selected_subnode_names
            ] if available_subnodes else []
            
            # Show selected items details in single table maintaining hierarchy
            if selected_subtopics or selected_subnodes:
                st.markdown("### Selected Items Preview")
                
                # Display as a table maintaining hierarchy
                preview_data = []
                
                # Add subtopics first
                for sub in selected_subtopics:
                    preview_data.append({
                        "Number": sub["full_number"],
                        "Level": "Subtopic",
                        "Title": sub["subtopic_title"],
                        "Maintopic": sub["maintopic_title"],
                        "Duration": f"{sub['duration']} min" if sub['duration'] else "N/A",
                        "Description": safe_str(sub.get("description"), max_len=50)
                    })
                
                # Add subnodes (they will appear after their parent subtopics in the list)
                for subnode in selected_subnodes:
                    preview_data.append({
                        "Number": subnode["full_number"],
                        "Level": "Subnode",
                        "Title": subnode["subnode_title"],
                        "Maintopic": subnode["maintopic_title"],
                        "Duration": f"{subnode['duration']} min" if subnode['duration'] else "N/A",
                        "Description": safe_str(subnode.get("description"), max_len=50)
                    })
                
                if preview_data:
                    preview_df = pd.DataFrame(preview_data)
                    st.dataframe(preview_df, width='stretch', hide_index=True)
                    
                    total_items = len(selected_subtopics) + len(selected_subnodes)
                    st.info(f"💡 Total scripts to generate: {total_items} ({len(selected_subtopics)} subtopics + {len(selected_subnodes)} subnodes)")
                else:
                    st.info("👆 Please select at least one subtopic or subnode from the dropdowns above")
                
                # Generate Scripts Button
                total_selected = len(selected_subtopics) + len(selected_subnodes)
                
                # Check if request is already in progress
                if st.session_state.script_request_in_progress:
                    st.warning("⏳ Script generation is already in progress. Please wait...")
                    st.button("🚀 Generate Scripts for Selected Items", type="primary", key="btn_generate_scripts", disabled=True)
                else:
                    if st.button("🚀 Generate Scripts for Selected Items", type="primary", key="btn_generate_scripts"):
                        # Set flag to prevent duplicate requests
                        st.session_state.script_request_in_progress = True
                        
                        with st.spinner(f"Generating {total_selected} scripts concurrently..."):
                            # Build batch request payload
                            # Get project_id from TOC response, fallback to input field, or use default
                            toc_response_project_id = st.session_state.toc_response.get("project_id")
                            # Check if project_id from response is None or empty, then use input field value
                            if toc_response_project_id and str(toc_response_project_id).strip():
                                toc_project_id = str(toc_response_project_id).strip()
                            else:
                                # Fallback to the project_id from TOC generation input field
                                toc_project_id = st.session_state.get("toc_project_id", "proj_001")
                                if not toc_project_id or not str(toc_project_id).strip():
                                    toc_project_id = "proj_001"  # Final fallback
                            
                            batch_scripts = []
                            script_counter = 1
                            
                            # Extract state and region from session state
                            state_value = st.session_state.get("project_state", "Pan India")
                            region_value = st.session_state.get("project_region")
                            
                            # If state is "Pan India", ignore region
                            if state_value == "Pan India":
                                region_value = None
                            
                            # Add subtopics to batch
                            for sub in selected_subtopics:
                                batch_scripts.append({
                                    "sub_topic": sub["subtopic_title"],
                                    "learners_path": learners_path,
                                    "description": sub["description"] or f"Educational content for {sub['subtopic_title']}",
                                    "duration": sub["duration"],  # Use actual duration from TOC
                                    "script_type": default_script_type,
                                    "maintopic": sub.get("maintopic_title", ""),
                                    "level": "subtopic",
                                    "number": sub.get("full_number", ""),
                                    "script_id": f"script_{script_counter:03d}_{sub['subtopic_title'][:20].replace(' ', '_')}"
                                })
                                script_counter += 1
                            
                            # Add subnodes to batch
                            for subnode in selected_subnodes:
                                batch_scripts.append({
                                    "sub_topic": subnode["subnode_title"],
                                    "learners_path": learners_path,
                                    "description": subnode.get("description", "") or f"Educational content for {subnode['subnode_title']}",
                                    "duration": subnode["duration"],  # Use actual duration from TOC
                                    "script_type": default_script_type,
                                    "maintopic": subnode.get("maintopic_title", ""),
                                    "level": "subnode",
                                    "number": subnode.get("full_number", ""),
                                    "script_id": f"script_{script_counter:03d}_{subnode['subnode_title'][:20].replace(' ', '_')}"
                                })
                                script_counter += 1
                            
                            # Build payload with state and region at project level
                            payload = {
                                "project_id": toc_project_id,
                                "state": state_value,
                                "scripts": batch_scripts
                            }
                            
                            # Only add region if it's not None
                            if region_value is not None:
                                payload["region"] = region_value
                            
                            try:
                                start_time = time.time()
                                result = asyncio.run(call_script_batch(payload))
                                elapsed = time.time() - start_time
                                
                                if result["status_code"] == 200:
                                    data = result["data"]
                                    total_scripts = data.get("total_scripts", len(data.get("scripts", [])))
                                    successful = data.get("successful", 0)
                                    failed = data.get("failed", 0)
                                    st.success(f"✅ Batch completed in {elapsed:.2f}s | Total: {total_scripts} | Success: {successful} | Failed: {failed}")
                                    
                                    # Display successful scripts
                                    if data.get("scripts"):
                                        st.markdown("### ✅ Generated Scripts")
                                        
                                        for idx, script in enumerate(data["scripts"], 1):
                                            # Find corresponding subtopic or subnode info
                                            matching_sub = next(
                                                (s for s in selected_subtopics if s["subtopic_title"] == script["sub_topic"]),
                                                None
                                            )
                                            matching_subnode = next(
                                                (s for s in selected_subnodes if s["subnode_title"] == script["sub_topic"]),
                                                None
                                            ) if not matching_sub else None
                                            
                                            matching_item = matching_sub or matching_subnode
                                            
                                            header_text = f"{idx}. {script['sub_topic']} ({script['script_type']})"
                                            if matching_item:
                                                header_text = f"{idx}. [{matching_item['full_number']}] {script['sub_topic']} ({script['script_type']})"
                                            
                                            with st.expander(header_text, expanded=False):
                                                # Display character names if available (for Character Based scripts)
                                                if script.get("character_names"):
                                                    st.info(f"**Characters:** {', '.join(script['character_names'])}")
                                                st.text_area(
                                                    "Script Content", 
                                                    value=script["script"], 
                                                    height=400, 
                                                    key=f"output_{idx}_{script['sub_topic']}"
                                                )
                                    
                                    # Display detailed errors
                                    if failed > 0:
                                        st.markdown("### ❌ Script Generation Errors")
                                        errors = data.get("errors", [])
                                        if errors:
                                            for error in errors:
                                                if isinstance(error, dict):
                                                    error_msg = error.get("error", "Unknown error")
                                                    script_id = error.get("script_id", "Unknown")
                                                    sub_topic = error.get("sub_topic", "Unknown")
                                                    st.error(f"**Script ID:** {script_id} | **Sub-topic:** {sub_topic}\n\n**Error:** {error_msg}")
                                                else:
                                                    st.error(f"Error: {error}")
                                        else:
                                            # Fallback if errors array is missing but failed > 0
                                            st.error(f"❌ {failed} script(s) failed, but no detailed error information was provided.")
                                    
                                    # Also check for top-level batch errors
                                    if data.get("error"):
                                        st.markdown("### ❌ Batch Processing Error")
                                        st.error(f"**Batch Error:** {data.get('error')}")
                                    
                                    st.session_state.script_response = result
                                else:
                                    st.error(f"❌ Error: Status {result['status_code']}")
                                    st.json(result["data"])
                            except Exception as e:
                                st.error(f"❌ Error: {str(e)}")
                            finally:
                                # Always reset the flag when request completes (success or error)
                                st.session_state.script_request_in_progress = False
            else:
                st.info("👆 Please select at least one subtopic or subnode from the dropdowns above")

# SIDEBAR: API STATUS & INFO
with st.sidebar:
    st.header("🔧 Service Info")
    
    st.markdown("**TOC Service**")
    st.code(TOC_SERVICE_URL, language="text")
    st.caption("Endpoint: /create-course-sync")
    
    st.markdown("**Script Service**")
    st.code(SCRIPT_SERVICE_URL, language="text")
    st.caption("Endpoints: /generate-script-streamlit, /generate-scripts-batch-streamlit")
    
    st.markdown("---")
    
    st.markdown("### 📊 Current State")
    
    toc_status = "✅ TOC Available" if st.session_state.toc_response else "❌ No TOC"
    st.write(toc_status)
    
    if st.session_state.toc_response:
        toc_data = st.session_state.toc_response.get("toc", {})
        maintopics = toc_data.get("maintopics_with_subtopics", [])
        total_subtopics = sum(len(m.get("subtopics", [])) for m in maintopics)
        st.caption(f"Maintopics: {len(maintopics)}")
        st.caption(f"Subtopics: {total_subtopics}")
    
    script_status = "✅ Scripts Generated" if st.session_state.script_response else "❌ No Scripts"
    st.write(script_status)
    
    st.markdown("---")
    
    st.markdown("### 🗑️ Clear Data")
    if st.button("Clear TOC Response", key="btn_clear_toc"):
        st.session_state.toc_response = None
        st.rerun()
    
    if st.button("Clear Script Response", key="btn_clear_script"):
        st.session_state.script_response = None
        st.rerun()
    
    st.markdown("---")
    st.caption("Built with Streamlit + httpx + pandas")
