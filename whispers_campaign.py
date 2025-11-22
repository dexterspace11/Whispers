import streamlit as st
import json
import uuid
import os
from datetime import datetime
from urllib.parse import urlencode, urlparse, urlunparse, parse_qs
import networkx as nx
import matplotlib.pyplot as plt

# -------------------------
# Config
# -------------------------
st.set_page_config(page_title="Whisper Remix Hub", page_icon="🧵", layout="wide")

# Set your deployment base URL here once you host it online (e.g., https://yourapp.streamlit.app).
# For local prototyping, this will default to localhost and the current port, which may vary.
DEFAULT_BASE_URL = "http://localhost:8501"
BASE_URL = st.sidebar.text_input("Base URL (used to generate share links)", DEFAULT_BASE_URL)

DATA_FILE = "whispers.json"

# -------------------------
# Data helpers
# -------------------------
def load_whispers():
    if not os.path.exists(DATA_FILE):
        return {}
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def save_whispers(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def new_id():
    return str(uuid.uuid4())

def now_iso():
    return datetime.utcnow().isoformat() + "Z"

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
    # Build a URL with ?id=<wid> and view=detail for deep links
    parsed = urlparse(base_url)
    query = {"id": wid, "view": "detail"}
    new_query = urlencode(query)
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path or "/", "", new_query, ""))

def make_snippet(message, wid, base_url):
    link = make_link_for_id(base_url, wid)
    return f"{message}\nRemix here → {link}"

# -------------------------
# Load data
# -------------------------
whispers = load_whispers()

# -------------------------
# URL routing via query params
# -------------------------
params = st.experimental_get_query_params()
current_view = params.get("view", ["home"])[0]
current_id = params.get("id", [None])[0]

# -------------------------
# UI: Header
# -------------------------
st.title("🧵 Whisper Remix Hub")
st.caption("Create immutable whisper anchors, remix by extending, and track lineage with unique links.")

# -------------------------
# Sidebar: quick navigation
# -------------------------
st.sidebar.markdown("### Navigation")
if st.sidebar.button("Home"):
    st.experimental_set_query_params(view="home")
if st.sidebar.button("All whispers"):
    st.experimental_set_query_params(view="browse")
if st.sidebar.button("Tree view"):
    st.experimental_set_query_params(view="tree")

# -------------------------
# Create Whisper
# -------------------------
st.markdown("### Create a new whisper")
col1, col2, col3 = st.columns([1, 2, 1])

with col1:
    motif = st.text_input("Motif (optional)", placeholder="🌱 / 🔥 / 🧵")
with col2:
    phrase = st.text_input("Message (short, remixable)", placeholder="Growth begins in silence.")
with col3:
    author = st.text_input("Author (optional)", placeholder="Dexter")

create_btn = st.button("Create whisper")
if create_btn:
    message = build_whisper_message(motif, phrase).strip()
    if not message:
        st.error("Please enter a motif and/or a message.")
    else:
        wid = new_id()
        whispers[wid] = {
            "id": wid,
            "message": message,
            "motif": motif,
            "phrase": phrase,
            "parent": None,
            "children": [],
            "author": author.strip() if author else None,
            "timestamp": now_iso(),
        }
        save_whispers(whispers)
        st.success("Whisper created.")
        # Jump to its detail page
        st.experimental_set_query_params(view="detail", id=wid)

st.markdown("---")

# -------------------------
# Detail / Remix view
# -------------------------
def render_detail(wid):
    if wid not in whispers:
        st.error("Whisper not found.")
        return
    w = whispers[wid]
    st.markdown("### Whisper detail")
    st.write(f"**Message:** {w['message']}")
    st.write(f"**Author:** {w.get('author') or 'Anonymous'}")
    st.write(f"**Timestamp:** {w.get('timestamp')}")
    share_link = make_link_for_id(BASE_URL, wid)
    snippet = make_snippet(w["message"], wid, BASE_URL)

    st.markdown("#### Share")
    st.write("Use this link to invite remixes:")
    st.code(share_link, language="text")
    st.write("Copy-ready snippet for social media:")
    st.code(snippet, language="text")

    st.markdown("#### Remix")
    st.write("Remix by extending the message. You cannot alter the parent — only add your continuation.")
    remix_add = st.text_area(
        "Add your continuation (keep it short and distinct)",
        placeholder="... but community makes it grow."
    )
    remix_author = st.text_input("Your name or handle (optional)")
    remix_btn = st.button("Submit remix")

    if remix_btn:
        continuation = (remix_add or "").strip()
        if not continuation:
            st.error("Please add a continuation to remix.")
        else:
            new_wid = new_id()
            new_message = f"{w['message']} → {continuation}"
            whispers[new_wid] = {
                "id": new_wid,
                "message": new_message,
                "motif": w.get("motif"),
                "phrase": None,  # continuation only
                "parent": wid,
                "children": [],
                "author": (remix_author or "").strip() or None,
                "timestamp": now_iso(),
            }
            # Link child immutably
            whispers[wid]["children"].append(new_wid)
            save_whispers(whispers)
            st.success("Remix created.")
            # Jump to new remix detail
            st.experimental_set_query_params(view="detail", id=new_wid)

    st.markdown("#### Children (remixes)")
    kids = w.get("children", [])
    if not kids:
        st.info("No remixes yet. Be the first to extend this whisper.")
    else:
        for cid in kids:
            child = whispers.get(cid)
            if not child: 
                continue
            link = make_link_for_id(BASE_URL, cid)
            st.markdown(f"- **{child['message']}**")
            st.caption(f"By {child.get('author') or 'Anonymous'} at {child.get('timestamp')} • Link: {link}")

# -------------------------
# Browse all whispers
# -------------------------
def render_browse():
    st.markdown("### All whispers")
    if not whispers:
        st.info("No whispers yet. Create one above.")
        return
    # Root-first, then remixes
    roots = [w for w in whispers.values() if w["parent"] is None]
    remixes = [w for w in whispers.values() if w["parent"] is not None]

    st.markdown("#### Roots")
    for w in sorted(roots, key=lambda x: x["timestamp"], reverse=True):
        link = make_link_for_id(BASE_URL, w["id"])
        st.markdown(f"- **{w['message']}**")
        st.caption(f"By {w.get('author') or 'Anonymous'} • {w.get('timestamp')} • Link: {link}")
        # Quick button to jump to detail
        if st.button(f"View → {w['id']}", key=f"view_{w['id']}"):
            st.experimental_set_query_params(view="detail", id=w["id"])

    st.markdown("#### Remixes")
    for w in sorted(remixes, key=lambda x: x["timestamp"], reverse=True):
        link = make_link_for_id(BASE_URL, w["id"])
        parent = whispers.get(w["parent"])
        parent_msg = parent["message"] if parent else "(unknown)"
        st.markdown(f"- **{w['message']}**")
        st.caption(f"By {w.get('author') or 'Anonymous'} • {w.get('timestamp')} • Parent: {parent_msg} • Link: {link}")
        if st.button(f"View → {w['id']}", key=f"view_{w['id']}"):
            st.experimental_set_query_params(view="detail", id=w["id"])

# -------------------------
# Tree visualization
# -------------------------
def render_tree():
    st.markdown("### Whisper lineage tree")
    if not whispers:
        st.info("No whispers yet.")
        return

    # Build graph
    G = nx.DiGraph()
    for w in whispers.values():
        label = w["message"]
        G.add_node(w["id"], label=label)
        if w["parent"]:
            G.add_edge(w["parent"], w["id"])

    # Draw
    fig, ax = plt.subplots(figsize=(10, 6))
    pos = nx.spring_layout(G, seed=42, k=1.2)
    nx.draw(G, pos, ax=ax, with_labels=False, node_size=600, node_color="#91c9ff", arrows=True, arrowstyle="-|>", arrowsize=12)
    labels = {n: G.nodes[n]["label"][:50] + ("…" if len(G.nodes[n]["label"]) > 50 else "") for n in G.nodes}
    nx.draw_networkx_labels(G, pos, labels=labels, font_size=8)
    st.pyplot(fig)

    # Select a node to view
    st.markdown("#### Jump to a whisper")
    options = {w["message"][:80]: w["id"] for w in whispers.values()}
    if options:
        choice = st.selectbox("Select whisper", list(options.keys()))
        if st.button("View selected"):
            st.experimental_set_query_params(view="detail", id=options[choice])

# -------------------------
# Router
# -------------------------
if current_view == "detail" and current_id:
    render_detail(current_id)
elif current_view == "browse":
    render_browse()
elif current_view == "tree":
    render_tree()
else:
    # Home: show quick tips and recent roots
    st.markdown("### How it works")
    st.markdown(
        "- **Immutable anchors**: originals cannot be edited.\n"
        "- **Remix-only**: extend with your continuation; the parent stays untouched.\n"
        "- **Unique links**: every whisper has a deep link (?id=UUID) for remix.\n"
        "- **Copy-ready snippets**: post back to social platforms to spread."
    )
    st.markdown("### Recent roots")
    roots = [w for w in whispers.values() if w["parent"] is None]
    if not roots:
        st.info("No root whispers yet. Create one above.")
    else:
        for w in sorted(roots, key=lambda x: x["timestamp"], reverse=True)[:10]:
            link = make_link_for_id(BASE_URL, w["id"])
            st.markdown(f"- **{w['message']}**")
            st.caption(f"By {w.get('author') or 'Anonymous'} • {w.get('timestamp')} • Link: {link}")
            if st.button(f"View → {w['id']}", key=f"home_view_{w['id']}"):
                st.experimental_set_query_params(view="detail", id=w["id"])