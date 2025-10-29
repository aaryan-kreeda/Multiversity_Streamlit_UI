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
load_dotenv()

TOC_SERVICE_URL = st.secrets.get("TOC_SERVICE_URL") or os.getenv("TOC_SERVICE_URL")
SCRIPT_SERVICE_URL = st.secrets.get("SCRIPT_SERVICE_URL") or os.getenv("SCRIPT_SERVICE_URL")


TOC_CREATE_ENDPOINT = f"{TOC_SERVICE_URL}/create-course"
TOC_CREATE_SYNC_ENDPOINT = f"{TOC_SERVICE_URL}/create-course-sync"
TOC_UPDATE_ENDPOINT = f"{TOC_SERVICE_URL}/update-toc"
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

async def call_toc_create(payload: Dict) -> Dict:
    """Call TOC creation endpoint (returns immediately with 202)"""
    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(TOC_CREATE_ENDPOINT, json=payload)
        return {"status_code": response.status_code, "data": response.json()}

async def call_toc_update(payload: Dict) -> Dict:
    """Call TOC update endpoint (synchronous response)"""
    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(TOC_UPDATE_ENDPOINT, json=payload)
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
def display_toc_hierarchical(toc_data: Dict):
    """
    Display TOC in hierarchical table format: Maintopic → Subtopic → Subnode
    This version is defensive against None values and unexpected types.
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
                "Duration": "",
                "Difficulty": ""
            })
            continue

        maintopic = safe_dict(maintopic_entry.get("maintopic"))
        subtopics = safe_list(maintopic_entry.get("subtopics"))

        maintopic_num = maintopic.get("maintopic_number", "")
        maintopic_title = maintopic.get("title", "Untitled")
        maintopic_duration = maintopic.get("duration", "N/A")
        maintopic_difficulty = maintopic.get("difficulty_level", "")
        maintopic_desc = safe_str(maintopic.get("description", ""), max_len=80)

        rows.append({
            "Level": "📚 Maintopic",
            "Number": f"**{maintopic_num}**" if maintopic_num else "",
            "Title": f"**{maintopic_title}**",
            "Description": maintopic_desc,
            "Duration": maintopic_duration,
            "Difficulty": maintopic_difficulty or "-"
        })

        for subtopic in subtopics:
            if not isinstance(subtopic, dict):
                rows.append({
                    "Level": "  ⚠️ Error",
                    "Number": "",
                    "Title": safe_str(subtopic),
                    "Description": "",
                    "Duration": "",
                    "Difficulty": ""
                })
                continue

            subtopic_num = subtopic.get("subtopic_number", "")
            subtopic_title = subtopic.get("title", "Untitled")
            subtopic_desc = safe_str(subtopic.get("description", ""), max_len=80)
            subtopic_duration = subtopic.get("duration_minutes", 0)

            subnodes = safe_list(subtopic.get("subnodes"))
            rows.append({
                "Level": "  📖 Subtopic",
                "Number": f"{maintopic_num}.{subtopic_num}" if maintopic_num or subtopic_num else "",
                "Title": subtopic_title,
                "Description": subtopic_desc,
                "Duration": f"{subtopic_duration} min" if subtopic_duration else "-",
                "Difficulty": "-"
            })

            for subnode in subnodes:
                title = ""
                if isinstance(subnode, dict):
                    title = subnode.get("title") or subnode.get("name") or str(subnode)
                else:
                    title = safe_str(subnode)
                rows.append({
                    "Level": "    • Subnode",
                    "Number": "",
                    "Title": title,
                    "Description": "",
                    "Duration": "",
                    "Difficulty": ""
                })

    df = pd.DataFrame(rows)

    # Display as table - use width=None (or an integer)
    st.dataframe(
        df,
        width='stretch',
        height=600,
        hide_index=True
    )

    # Summary - use safe iteration (ignore non-dict entries)
    sane_maintopics = [m for m in maintopics if isinstance(m, dict)]
    maintopic_count = len(sane_maintopics)
    subtopic_count = sum(len(safe_list(m.get("subtopics"))) for m in sane_maintopics)
    subnode_count = sum(len(safe_list(sub.get("subnodes"))) for m in sane_maintopics for sub in safe_list(m.get("subtopics")))

    # total duration
    total_minutes = 0
    for m in sane_maintopics:
        for sub in safe_list(m.get("subtopics")):
            duration = sub.get("duration_minutes", 0) if isinstance(sub, dict) else 0
            if isinstance(duration, (int, float)):
                total_minutes += duration
    total_hours = total_minutes / 60 if total_minutes > 0 else 0

    st.markdown("---")
    st.markdown("### 📊 Course Summary")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Maintopics", maintopic_count)
    with col2:
        st.metric("Subtopics", subtopic_count)
    with col3:
        st.metric("Subnodes", subnode_count)
    with col4:
        st.metric("Total Duration", f"{total_hours:.1f}h" if total_hours else "N/A")

    
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
            "Difficulty": st.column_config.TextColumn("Difficulty", width="small"),
        },
        hide_index=True,
    )
    
    # Show summary stats (defensive calculations)
    st.markdown("---")
    st.markdown("### 📊 Course Summary")

    col1, col2, col3, col4 = st.columns(4)

    # Use previously sanitized maintopics list (sane_maintopics) where possible
    maintopic_count = len(sane_maintopics)

    # Count subtopics defensively
    subtopic_count = 0
    for m in sane_maintopics:
        subtopic_count += safe_len(m.get("subtopics"))

    # Count subnodes defensively
    subnode_count = 0
    for m in sane_maintopics:
        for sub in safe_list(m.get("subtopics")):
            if isinstance(sub, dict):
                subnode_count += safe_len(sub.get("subnodes"))
            else:
                # if sub is a list-like, count its items; otherwise ignore
                subnode_count += safe_len(sub) if isinstance(sub, (list, tuple)) else 0

    # Calculate total duration defensively
    total_minutes = 0
    for m in sane_maintopics:
        for sub in safe_list(m.get("subtopics")):
            if isinstance(sub, dict):
                duration = sub.get("duration_minutes", 0) or 0
                if isinstance(duration, (int, float)):
                    total_minutes += duration

    total_hours = total_minutes / 60 if total_minutes > 0 else 0

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
                    "duration": 5,
                    "subnodes": []
                })
                continue

            subtopic_num = subtopic.get("subtopic_number", "")
            subtopic_title = subtopic.get("title", "")
            subtopic_desc = subtopic.get("description", "") or ""
            subtopic_duration = subtopic.get("duration_minutes", 5) or 5
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
        learner_path = st.selectbox("Learner Path", ["Professional", "Beginner", "Intermediate", "Advanced"], key="toc_path")
    
    with col2:
        callback_url = st.text_input("Callback URL (optional, for async mode)", value="", key="toc_callback")
        regionality = st.text_input("Regionality", value="Global", key="toc_region")
        objectives = st.text_area("Learning Objectives (one per line)", 
                                  value="Master Python fundamentals\nBuild real-world applications", 
                                  key="toc_objectives")
        subtopics = st.text_area("Subtopics (one per line)", value="", key="toc_subtopics")
        notes = st.text_area("Additional Notes", value="No additional notes", key="toc_notes")
    
    col_btn1, col_btn2 = st.columns(2)
    
    with col_btn1:
        if st.button("🚀 Generate TOC (Synchronous)", type="primary", key="btn_create_toc_sync"):
            with st.spinner("Generating TOC... This may take 30-60 seconds..."):
                payload = {
                    "project_id": project_id,
                    "question_id": question_id,
                    "topic": topic,
                    "course_hours": course_hours,
                    "learner_path": learner_path,
                    "callback_url": None,
                    "regionality": regionality,
                    "objective": objectives.split("\n") if objectives else [],
                    "course_subtopics": subtopics.split("\n") if subtopics else [],
                    "notes": notes
                }
                
                try:
                    start_time = time.time()
                    result = asyncio.run(call_toc_create_sync(payload))
                    elapsed = time.time() - start_time
                    
                    if result["status_code"] == 200:
                        st.session_state.toc_response = result["data"]
                        
                        data = result["data"]
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
                        
                        # Store the TOC data in session state
                        st.session_state.toc_response = result["data"]
                        
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
    
    with col_btn2:
        if st.button("⚡ Start Async Generation", key="btn_create_toc_async"):
            with st.spinner("Sending async TOC creation request..."):
                payload = {
                    "project_id": project_id,
                    "question_id": question_id,
                    "topic": topic,
                    "course_hours": course_hours,
                    "learner_path": learner_path,
                    "callback_url": callback_url if callback_url else None,
                    "regionality": regionality,
                    "objective": objectives.split("\n") if objectives else [],
                    "course_subtopics": subtopics.split("\n") if subtopics else [],
                    "notes": notes
                }
                
                try:
                    result = asyncio.run(call_toc_create(payload))
                    
                    if result["status_code"] == 202:
                        st.success("✅ TOC generation started! (Status: 202 Accepted)")
                        st.info("The service is processing in the background. Check your callback URL for results.")
                        st.json(result["data"])
                    else:
                        st.warning(f"Received status code: {result['status_code']}")
                        st.json(result["data"])
                except Exception as e:
                    st.error(f"❌ Error: {str(e)}")
    
    # Only display TOC when first generated
    if st.session_state.toc_response:
        st.markdown("---")
        st.subheader("Generated Table of Contents")
        
        # Display TOC as hierarchical view
        toc_data = st.session_state.toc_response.get("toc") or {}
        if toc_data and toc_data.get("maintopics_with_subtopics"):
            try:
                display_toc_hierarchical(toc_data)
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
        
        # Extract subtopics for dropdown
        available_subtopics = extract_subtopics_from_toc(toc_data)
        
        if not available_subtopics:
            st.error("❌ No subtopics found in the TOC. Please regenerate the TOC.")
        else:
            st.success(f"✅ Found {len(available_subtopics)} subtopics from TOC")
            
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
                region = st.text_input("Region", value="Pan India", key="script_region")
                learners_path = st.selectbox(
                    "Learner's Path", 
                    ["Beginner", "Intermediate", "Advanced", "Professional"],
                    index=["Beginner", "Intermediate", "Advanced", "Professional"].index(
                        course_metadata.get('learner_path', 'Professional')
                    ),
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
            
            # Subtopic selection
            st.subheader("Select Subtopics for Script Generation")
            
            # Create options for multiselect
            subtopic_options = [sub["display_name"] for sub in available_subtopics]
            
            # Multiselect for subtopics
            selected_display_names = st.multiselect(
                "Choose subtopics (you can select multiple):",
                options=subtopic_options,
                default=[],
                help="Select one or more subtopics to generate scripts for",
                key="subtopic_multiselect"
            )
            
            # Show selected subtopics details
            if selected_display_names:
                st.markdown("### Selected Subtopics Preview")
                
                selected_subtopics = [
                    sub for sub in available_subtopics 
                    if sub["display_name"] in selected_display_names
                ]
                
                # Display as a table
                preview_data = []
                for sub in selected_subtopics:
                    preview_data.append({
                        "Number": sub["full_number"],
                        "Title": sub["subtopic_title"],
                        "Maintopic": sub["maintopic_title"],
                        "Duration": f"{sub['duration']} min",
                        "Description": safe_str(sub.get("description"), max_len=50)

                    })
                
                preview_df = pd.DataFrame(preview_data)
                st.dataframe(preview_df, width='stretch', hide_index=True)
                
                st.info(f"💡 Total scripts to generate: {len(selected_subtopics)}")
                
                # Generate Scripts Button
                if st.button("🚀 Generate Scripts for Selected Subtopics", type="primary", key="btn_generate_scripts"):
                    with st.spinner(f"Generating {len(selected_subtopics)} scripts concurrently..."):
                        # Build batch request payload
                        batch_scripts = []
                        for sub in selected_subtopics:
                            batch_scripts.append({
                                "region": region,
                                "sub_topic": sub["subtopic_title"],
                                "learners_path": learners_path,
                                "description": sub["description"] or f"Educational content for {sub['subtopic_title']}",
                                "duration": sub["duration"],
                                "script_type": default_script_type
                            })
                        
                        payload = {"scripts": batch_scripts}
                        
                        try:
                            start_time = time.time()
                            result = asyncio.run(call_script_batch(payload))
                            elapsed = time.time() - start_time
                            
                            if result["status_code"] == 200:
                                data = result["data"]
                                st.success(f"✅ Batch completed in {elapsed:.2f}s | Success: {data['successful']} | Failed: {data['failed']}")
                                
                                # Display successful scripts
                                if data["scripts"]:
                                    st.markdown("### ✅ Generated Scripts")
                                    
                                    for idx, script in enumerate(data["scripts"], 1):
                                        # Find corresponding subtopic info
                                        matching_sub = next(
                                            (s for s in selected_subtopics if s["subtopic_title"] == script["sub_topic"]),
                                            None
                                        )
                                        
                                        header_text = f"{idx}. {script['sub_topic']} ({script['script_type']})"
                                        if matching_sub:
                                            header_text = f"{idx}. [{matching_sub['full_number']}] {script['sub_topic']} ({script['script_type']})"
                                        
                                        with st.expander(header_text, expanded=False):
                                            st.text_area(
                                                "Script Content", 
                                                value=script["script"], 
                                                height=400, 
                                                key=f"output_{idx}_{script['sub_topic']}"
                                            )
                                
                                # Display errors
                                if data["errors"]:
                                    st.markdown("### ❌ Errors")
                                    for error in data["errors"]:
                                        st.error(f"**{error.get('sub_topic', 'Unknown')}**: {error.get('error', 'Unknown error')}")
                                
                                st.session_state.script_response = result
                            else:
                                st.error(f"❌ Error: Status {result['status_code']}")
                                st.json(result["data"])
                        except Exception as e:
                            st.error(f"❌ Error: {str(e)}")
            else:
                st.info("👆 Please select at least one subtopic from the dropdown above")

# SIDEBAR: API STATUS & INFO
with st.sidebar:
    st.header("🔧 Service Info")
    
    st.markdown("**TOC Service**")
    st.code(TOC_SERVICE_URL, language="text")
    st.caption("Endpoints: /create-course (async), /create-course-sync (sync), /update-toc")
    
    st.markdown("**Script Service**")
    st.code(SCRIPT_SERVICE_URL, language="text")
    st.caption("Endpoints: /generate-script, /generate-scripts-batch")
    
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
