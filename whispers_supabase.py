import streamlit as st
import uuid
from datetime import datetime, timezone
from urllib.parse import urlencode, urlparse, urlunparse
import networkx as nx
import matplotlib.pyplot as plt
import requests

# -----------------------------------------------------------
# Streamlit Config
# -----------------------------------------------------------
st.set_page_config(page_title="Whisper Remix Hub", page_icon="🧵", layout="wide")

# -----------------------------------------------------------
# Supabase Config
# -----------------------------------------------------------
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json"
}

TABLE_URL = f"{SUPABASE_URL}/rest/v1/whispers"

DEFAULT_BASE_URL = "http://localhost:8501"
BASE_URL = st.sidebar.text_input("Base URL (used to generate share links)", DEFAULT_BASE_URL)

# -----------------------------------------------------------
# Helpers
# -----------------------------------------------------------
def new_id():
    return str(uuid.uuid4())

def now_iso():
    # timezone-aware per Streamlit warning
    return datetime.now(timezone.utc).isoformat()

def build_whisper_message(motif, phrase):
    motif = (motif or "").strip()
    phrase = (phrase or "").strip()
    if motif and phrase:
        return f"{motif} {phrase}"
    elif motif:
        return motif
    else:
        return phrase

def make_link_for_id(base_url, wid):
    parsed = urlparse(base_url)
    query = {"id": wid, "view": "detail"}
    new_query = urlencode(query)
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path or "/", "", new_query, ""))

def make_snippet(message, wid, base_url):
    link = make_link_for_id(base_url, wid)
    return f"{message}\nRemix here → {link}"

# -----------------------------------------------------------
# Supabase CRUD
# -----------------------------------------------------------
def supabase_create_whisper(data):
    r = requests.post(TABLE_URL, headers=HEADERS, json=data)
    try:
        resp_json = r.json()
    except Exception:
        st.error(f"Supabase create error (non-JSON response): {r.text}")
        return None

    if r.status_code >= 300:
        st.error(f"Supabase create error: {resp_json}")
        return None

    if isinstance(resp_json, list) and len(resp_json) > 0:
        return resp_json[0]
    return resp_json

def supabase_get_all():
    r = requests.get(TABLE_URL + "?select=*", headers=HEADERS)
    if r.status_code != 200:
        st.error("Supabase read error.")
        return []
    try:
        items = r.json()
    except Exception:
        st.error(f"Supabase get_all error: {r.text}")
        return []
    # normalize null children
    for w in items:
        if w.get("children") is None:
            w["children"] = []
    return items

def supabase_get_by_id(wid):
    r = requests.get(f"{TABLE_URL}?id=eq.{wid}", headers=HEADERS)
    if r.status_code != 200:
        st.error(f"Supabase get_by_id error: {r.text}")
        return None

    try:
        items = r.json()
    except Exception:
        st.error(f"Supabase get_by_id JSON decode error: {r.text}")
        return None

    if not items:
        return None

    w = items[0]
    if w.get("children") is None:
        w["children"] = []
    return w

def supabase_update_children(parent_id, child_id):
    parent = supabase_get_by_id(parent_id)
    if not parent:
        st.error("Parent not found for updating children.")
        return

    children = parent.get("children") or []
    if child_id not in children:
        children.append(child_id)

    r = requests.patch(
        f"{TABLE_URL}?id=eq.{parent_id}",
        headers=HEADERS,
        json={"children": children}
    )

    if r.status_code >= 300:
        st.error(f"Supabase update children error: {r.text}")

# -----------------------------------------------------------
# URL Routing (updated API)
# -----------------------------------------------------------
params = st.query_params
current_view = params.get("view", "home")
current_id = params.get("id")

# -----------------------------------------------------------
# UI Header
# -----------------------------------------------------------
st.title("🧵 Whisper Remix Hub")
st.caption("Create immutable whispers, remix by extending, and track lineage with unique links.")

# -----------------------------------------------------------
# Sidebar Navigation
# -----------------------------------------------------------
st.sidebar.markdown("### Navigation")
if st.sidebar.button("Home"):
    st.query_params(view="home")
if st.sidebar.button("All whispers"):
    st.query_params(view="browse")
if st.sidebar.button("Tree view"):
    st.query_params(view="tree")

# -----------------------------------------------------------
# Create Whisper
# -----------------------------------------------------------
st.markdown("### Create a new whisper")
col1, col2, col3 = st.columns([1, 2, 1])

with col1:
    motif = st.text_input("Motif (optional)", placeholder="🌱 / 🔥 / 🧵")

with col2:
    phrase = st.text_input("Message (short, remixable)", placeholder="Growth begins in silence.")

with col3:
    author = st.text_input("Author (optional)", placeholder="Dexter")

if st.button("Create whisper"):
    message = build_whisper_message(motif, phrase).strip()

    if not message:
        st.error("Please enter a motif and/or a message.")
    else:
        wid = new_id()
        data = {
            "id": wid,
            "message": message,
            "motif": motif,
            "phrase": phrase,          # ← fixed column must exist
            "parent": None,
            "children": [],
            "author": author.strip() if author else None,
            "timestamp": now_iso(),
        }

        created = supabase_create_whisper(data)
        if created:
            st.success("Whisper created.")
            st.query_params(view="detail", id=wid)

# -----------------------------------------------------------
# The rest of your UI functions remain unchanged
# (render_detail, render_browse, render_tree, router)
# -----------------------------------------------------------
