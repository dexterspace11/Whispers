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
st.set_page_config(
    page_title="Whisper Remix Hub",
    page_icon="🧵",
    layout="wide"
)

# -----------------------------------------------------------
# Supabase Config
# -----------------------------------------------------------
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation"   # <-- FIXED: ensures JSON response
}

TABLE_URL = f"{SUPABASE_URL}/rest/v1/whispers"

DEFAULT_BASE_URL = "http://localhost:8501"
BASE_URL = st.sidebar.text_input(
    "Base URL (used to generate share links)",
    DEFAULT_BASE_URL
)

# -----------------------------------------------------------
# Helpers
# -----------------------------------------------------------
def new_id():
    return str(uuid.uuid4())


def now_iso():
    # FIXED: timezone-aware UTC
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
# Supabase CRUD Functions
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


def supabase_update_children(parent_id, child_id):
    parent = supabase_get_by_id(parent_id)
    if not parent:
        st.error("Parent not found for updating children.")
        return

    children = parent.get("children") or []
    children.append(child_id)

    r = requests.patch(
        f"{TABLE_URL}?id=eq.{parent_id}",
        headers=HEADERS,
        json={"children": children}
    )

    if r.status_code >= 300:
        st.error(f"Supabase update children error: {r.text}")


def supabase_get_all():
    r = requests.get(TABLE_URL + "?select=*", headers=HEADERS)

    if r.status_code != 200:
        st.error("Supabase read error.")
        return []

    try:
        data = r.json()
    except Exception:
        st.error(f"Supabase get_all JSON decode error: {r.text}")
        return []

    for w in data:
        if w.get("children") is None:
            w["children"] = []

    return data


def supabase_get_by_id(wid):
    r = requests.get(f"{TABLE_URL}?id=eq.{wid}", headers=HEADERS)

    if r.status_code != 200:
        st.error("Supabase get_by_id error.")
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

# -----------------------------------------------------------
# URL Routing
# -----------------------------------------------------------
params = st.query_params
current_view = params.get("view", "home")
current_id = params.get("id", None)

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

c1, c2, c3 = st.columns([1, 2, 1])

with c1:
    motif = st.text_input("Motif (optional)", placeholder="🌱 / 🔥 / 🧵")

with c2:
    phrase = st.text_input("Message (short, remixable)", placeholder="Growth begins in silence.")

with c3:
    author = st.text_input("Author (optional)", placeholder="Dexter")

if st.button("Create whisper"):
    message = build_whisper_message(motif, phrase).strip()

    if not message:
        st.error("Please enter a motif and/or a message.")
    else:
        wid = new_id()

        whisper = {
            "id": wid,
            "message": message,
            "motif": motif,
            "phrase": phrase,
            "parent": None,
            "children": [],
            "author": (author.strip() if author else None),
            "timestamp": now_iso(),
        }

        created = supabase_create_whisper(whisper)

        if created:
            st.success("Whisper created.")
            st.query_params(view="detail", id=wid)

# -----------------------------------------------------------
# Views
# -----------------------------------------------------------
def view_detail(wid):
    w = supabase_get_by_id(wid)
    if not w:
        st.error("Whisper not found.")
        return

    st.subheader("Whisper Details")
    st.write(f"**Motif:** {w['motif']}")
    st.write(f"**Message:** {w['phrase']}")
    st.write(f"**Author:** {w.get('author')}")
    st.write(f"**Timestamp:** {w['timestamp']}")
    st.write("---")

    snippet = make_snippet(w["message"], wid, BASE_URL)
    st.code(snippet, language="markdown")

    st.write("---")
    st.write("### Remix this Whisper")
    remix_phrase = st.text_input("Add your variation", "")
    remix_author = st.text_input("Author (optional)", "")

    if st.button("Submit Remix"):
        child_id = new_id()
        combined = build_whisper_message(w["motif"], remix_phrase)

        new_data = {
            "id": child_id,
            "message": combined,
            "motif": w["motif"],
            "phrase": remix_phrase,
            "parent": w["id"],
            "children": [],
            "author": (remix_author.strip() if remix_author else None),
            "timestamp": now_iso(),
        }

        created = supabase_create_whisper(new_data)
        if created:
            supabase_update_children(w["id"], child_id)
            st.success("Remix created.")
            st.query_params(view="detail", id=child_id)


def view_browse():
    st.subheader("All Whispers")
    all_w = supabase_get_all()

    for w in all_w:
        st.markdown(f"### {w['message']}")
        st.write(f"Author: {w.get('author')}")
        st.write(f"Timestamp: {w['timestamp']}")
        link = make_link_for_id(BASE_URL, w["id"])
        st.markdown(f"[Open →]({link})")
        st.write("---")


def view_tree():
    st.subheader("Whisper Lineage Tree")

    all_w = supabase_get_all()
    G = nx.DiGraph()

    for w in all_w:
        G.add_node(w["id"], label=w["message"])
        for c in w["children"]:
            G.add_edge(w["id"], c)

    plt.figure(figsize=(15, 10))
    pos = nx.spring_layout(G, seed=42)

    nx.draw(
        G,
        pos,
        with_labels=False,
        node_size=1200,
        node_color="lightblue",
        edge_color="gray"
    )

    labels = {n: G.nodes[n].get("label", "")[:50] for n in G.nodes}
    nx.draw_networkx_labels(G, pos, labels, font_size=8)

    st.pyplot(plt)

# -----------------------------------------------------------
# Router
# -----------------------------------------------------------
if current_view == "detail" and current_id:
    view_detail(current_id)
elif current_view == "browse":
    view_browse()
elif current_view == "tree":
    view_tree()
else:
    st.subheader("Welcome to the Whisper Remix Hub")
    st.write("Create whispers, remix with friends, and watch ideas evolve.")
