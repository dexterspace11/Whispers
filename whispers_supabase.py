import streamlit as st
import uuid
from datetime import datetime
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
SUPABASE_URL = st.secrets["https://vuatvbbutswnpeovrfql.supabase.co"]
SUPABASE_KEY = st.secrets["sb_publishable_y81OLrISVT-FtvbnZipGag_RiSy_g29"]

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
    if r.status_code >= 300:
        st.error(f"Supabase create error: {r.text}")
        return None
    return r.json()[0]

def supabase_update_children(parent_id, child_id):
    parent = supabase_get_by_id(parent_id)
    if not parent:
        st.error("Parent not found for updating children.")
        return
    children = parent.get("children") or []
    children.append(child_id)
    r = requests.patch(f"{TABLE_URL}?id=eq.{parent_id}", headers=HEADERS, json={"children": children})
    if r.status_code >= 300:
        st.error(f"Supabase update children error: {r.text}")

def supabase_get_all():
    r = requests.get(TABLE_URL + "?select=*", headers=HEADERS)
    if r.status_code != 200:
        st.error("Supabase read error.")
        return []
    for w in r.json():
        if w.get("children") is None:
            w["children"] = []
    return r.json()

def supabase_get_by_id(wid):
    r = requests.get(f"{TABLE_URL}?id=eq.{wid}", headers=HEADERS)
    if r.status_code != 200 or len(r.json()) == 0:
        return None
    w = r.json()[0]
    if w.get("children") is None:
        w["children"] = []
    return w

# -----------------------------------------------------------
# URL Routing
# -----------------------------------------------------------
params = st.experimental_get_query_params()
current_view = params.get("view", ["home"])[0]
current_id = params.get("id", [None])[0]

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
    st.experimental_set_query_params(view="home")
if st.sidebar.button("All whispers"):
    st.experimental_set_query_params(view="browse")
if st.sidebar.button("Tree view"):
    st.experimental_set_query_params(view="tree")

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
            "phrase": phrase,
            "parent": None,
            "children": [],
            "author": author.strip() if author else None,
            "timestamp": now_iso(),
        }
        created = supabase_create_whisper(data)
        if created:
            st.success("Whisper created.")
            st.experimental_set_query_params(view="detail", id=wid)

st.markdown("---")

# -----------------------------------------------------------
# Detail / Remix View
# -----------------------------------------------------------
def render_detail(wid):
    w = supabase_get_by_id(wid)
    if not w:
        st.error("Whisper not found.")
        return

    st.markdown("### Whisper detail")
    st.write(f"**Message:** {w['message']}")
    st.write(f"**Author:** {w.get('author') or 'Anonymous'}")
    st.write(f"**Timestamp:** {w.get('timestamp')}")

    share_link = make_link_for_id(BASE_URL, wid)
    snippet = make_snippet(w["message"], wid, BASE_URL)

    st.markdown("#### Share")
    st.code(share_link, language="text")
    st.code(snippet, language="text")

    # Remix
    st.markdown("#### Remix")
    remix_add = st.text_area(
        "Add your continuation (keep it short and distinct)",
        placeholder="... but community makes it grow."
    )
    remix_author = st.text_input("Your name or handle (optional)")

    if st.button("Submit remix"):
        continuation = remix_add.strip()
        if not continuation:
            st.error("Please add a continuation.")
            return

        new_wid = new_id()
        new_msg = f"{w['message']} → {continuation}"

        new_child = {
            "id": new_wid,
            "message": new_msg,
            "motif": w.get("motif"),
            "phrase": None,
            "parent": wid,
            "children": [],
            "author": (remix_author or "").strip() or None,
            "timestamp": now_iso()
        }

        # Save child & update parent
        created = supabase_create_whisper(new_child)
        if created:
            supabase_update_children(wid, new_wid)
            st.success("Remix created.")
            st.experimental_set_query_params(view="detail", id=new_wid)

    # Children
    st.markdown("#### Children (remixes)")
    kids = w.get("children") or []
    if not kids:
        st.info("No remixes yet.")
    else:
        for cid in kids:
            child = supabase_get_by_id(cid)
            if not child: continue
            link = make_link_for_id(BASE_URL, cid)
            st.markdown(f"- **{child['message']}**")
            st.caption(f"By {child.get('author') or 'Anonymous'} at {child.get('timestamp')} • Link: {link}")

# -----------------------------------------------------------
# Browse View
# -----------------------------------------------------------
def render_browse():
    all_w = supabase_get_all()
    roots = [w for w in all_w if w["parent"] is None]
    remixes = [w for w in all_w if w["parent"] is not None]

    st.markdown("### All whispers")
    st.markdown("#### Roots")
    for w in sorted(roots, key=lambda x: x["timestamp"], reverse=True):
        link = make_link_for_id(BASE_URL, w["id"])
        st.markdown(f"- **{w['message']}**")
        st.caption(f"By {w.get('author') or 'Anonymous'} • {w['timestamp']} • Link: {link}")
        if st.button(f"View → {w['id']}", key=f"view_{w['id']}"):
            st.experimental_set_query_params(view="detail", id=w["id"])

    st.markdown("#### Remixes")
    for w in sorted(remixes, key=lambda x: x["timestamp"], reverse=True):
        parent = supabase_get_by_id(w["parent"])
        parent_msg = parent["message"] if parent else "(unknown)"
        link = make_link_for_id(BASE_URL, w["id"])
        st.markdown(f"- **{w['message']}**")
        st.caption(
            f"By {w.get('author') or 'Anonymous'} • {w['timestamp']} • Parent: {parent_msg} • Link: {link}"
        )
        if st.button(f"View → {w['id']}", key=f"view2_{w['id']}"):
            st.experimental_set_query_params(view="detail", id=w["id"])

# -----------------------------------------------------------
# Tree View
# -----------------------------------------------------------
def render_tree():
    st.markdown("### Whisper lineage tree")
    all_w = supabase_get_all()
    if not all_w:
        st.info("No whispers yet.")
        return

    G = nx.DiGraph()
    for w in all_w:
        G.add_node(w["id"], label=w["message"])
        if w["parent"]:
            G.add_edge(w["parent"], w["id"])

    fig, ax = plt.subplots(figsize=(10, 6))
    pos = nx.spring_layout(G, seed=42)
    nx.draw(G, pos, ax=ax, with_labels=False, node_size=600, node_color="#91c9ff")
    labels = {n: G.nodes[n]["label"][:50] for n in G.nodes}
    nx.draw_networkx_labels(G, pos, labels=labels, font_size=8)
    st.pyplot(fig)

    # Jump to a whisper
    st.markdown("#### Jump to a whisper")
    options = {w["message"][:80]: w["id"] for w in all_w}
    if options:
        choice = st.selectbox("Select whisper", list(options.keys()))
        if st.button("View selected"):
            st.experimental_set_query_params(view="detail", id=options[choice])

# -----------------------------------------------------------
# Router
# -----------------------------------------------------------
if current_view == "detail" and current_id:
    render_detail(current_id)
elif current_view == "browse":
    render_browse()
elif current_view == "tree":
    render_tree()
else:
    st.markdown("### How it works")
    st.markdown(
        "- **Immutable anchors**: originals cannot be edited.\n"
        "- **Remixes only extend the chain**, parent never changes.\n"
        "- **Unique links**: shareable via ?id=<UUID>.\n"
        "- **Works with multiple users simultaneously.**"
    )

    all_w = supabase_get_all()
    roots = [w for w in all_w if w["parent"] is None]
    st.markdown("### Recent roots")
    for w in sorted(roots, key=lambda x: x["timestamp"], reverse=True)[:10]:
        link = make_link_for_id(BASE_URL, w["id"])
        st.markdown(f"- **{w['message']}**")
        st.caption(f"By {w.get('author') or 'Anonymous'} • {w['timestamp']} • Link: {link}")
        if st.button(f"View → {w['id']}", key=f"root_{w['id']}"):
            st.experimental_set_query_params(view="detail", id=w["id"])
