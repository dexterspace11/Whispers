import streamlit as st
import uuid
from datetime import datetime, timezone
from urllib.parse import urlencode, urlparse, urlunparse
import networkx as nx
import matplotlib.pyplot as plt
import requests

# =========================================================
# Streamlit Config
# =========================================================
st.set_page_config(
    page_title="Whisper Remix Hub",
    page_icon="🧵",
    layout="wide"
)

# =========================================================
# Supabase Config
# =========================================================
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation"
}

TABLE_URL = f"{SUPABASE_URL}/rest/v1/whispers"

# Your deployed Streamlit URL:
BASE_URL = "https://whispersbetav2.streamlit.app"


# =========================================================
# Helpers
# =========================================================
def new_id():
    return str(uuid.uuid4())


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def build_whisper_message(parent_message, new_phrase):
    parent_message = (parent_message or "").strip()
    new_phrase = (new_phrase or "").strip()
    if parent_message and new_phrase:
        return f"{parent_message} → {new_phrase}"
    elif parent_message:
        return parent_message
    else:
        return new_phrase


def make_link_for_id(base_url, wid):
    parsed = urlparse(base_url)
    query = {"id": wid, "view": "detail"}
    new_query = urlencode(query)
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path or "/", "", new_query, ""))


def make_snippet(message, wid, motif, base_url=BASE_URL):
    """
    Motif must ALWAYS appear at the start of the snippet.
    """
    motif = (motif or "").strip()
    message = (message or "").strip()

    # prepend motif if missing
    if motif and not message.startswith(motif):
        formatted = f"{motif} {message}"
    else:
        formatted = message

    link = make_link_for_id(base_url, wid)
    return f"{formatted}\nRemix here → {link}"


# =========================================================
# Supabase CRUD
# =========================================================
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

    if isinstance(resp_json, list) and resp_json:
        return resp_json[0]
    return resp_json


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


# =========================================================
# Routing (kept experimental for Streamlit Cloud)
# =========================================================
params = st.experimental_get_query_params()
current_view = params.get("view", ["home"])[0]
current_id = params.get("id", [None])[0]


# =========================================================
# UI Header
# =========================================================
st.title("🧵 Whisper Remix Hub")
st.caption("Create whispers, remix with friends, and watch ideas evolve.")


# =========================================================
# Sidebar Navigation
# =========================================================
st.sidebar.markdown("### Navigation")
if st.sidebar.button("Home"):
    st.experimental_set_query_params(view="home")
if st.sidebar.button("All whispers"):
    st.experimental_set_query_params(view="browse")
if st.sidebar.button("Tree view"):
    st.experimental_set_query_params(view="tree")


# =========================================================
# Create Root Whisper
# =========================================================
st.markdown("### Create a new whisper")
c1, c2, c3 = st.columns([1, 2, 1])

with c1:
    motif = st.text_input("Motif / Emoji (optional)", placeholder="🌱 / 🔥 / 🎵")

with c2:
    phrase = st.text_input("Message", placeholder="Growth begins in silence.")

with c3:
    author = st.text_input("Author (optional)", placeholder="@username")


if st.button("Create whisper"):
    combined_message = build_whisper_message("", phrase).strip()

    if not combined_message:
        st.error("Message cannot be empty.")
    else:
        wid = new_id()
        whisper = {
            "id": wid,
            "message": combined_message,
            "motif": motif,
            "phrase": phrase,
            "author": author,
            "parent": None,
            "children": [],
            "timestamp": now_iso(),
        }

        created = supabase_create_whisper(whisper)
        if created:
            st.success("Whisper created.")

            snippet = make_snippet(combined_message, wid, motif)
            st.code(snippet, language="text")

            st.experimental_set_query_params(view="detail", id=wid)


# =========================================================
# Detail / Remix View
# =========================================================
def view_detail(wid):
    w = supabase_get_by_id(wid)
    if not w:
        st.error("Whisper not found.")
        return

    st.subheader("Whisper Details")

    st.write(f"**Message:** {w.get('message')}")
    st.write(f"**Motif:** {w.get('motif')}")
    st.write(f"**Author:** {w.get('author')}")
    st.write(f"**Timestamp:** {w.get('timestamp')}")
    st.write("---")

    # Copy snippet
    snippet = make_snippet(w.get("message"), wid, w.get("motif"))
    st.write("Copy-ready snippet:")
    st.code(snippet, language="text")

    # Mix UI
    st.write("---")
    st.write("### Remix this Whisper")
    remix_phrase = st.text_input("Continue the message", key=f"remix_{wid}")
    remix_author = st.text_input("Author (optional)", value=w.get("author") or "", key=f"author_{wid}")

    if st.button("Submit Remix", key=f"submit_{wid}"):
        child_id = new_id()
        new_message = build_whisper_message(w.get("message"), remix_phrase)

        new_data = {
            "id": child_id,
            "message": new_message,
            "motif": w.get("motif"),
            "phrase": remix_phrase,
            "author": remix_author,
            "parent": w.get("id"),
            "children": [],
            "timestamp": now_iso(),
        }

        created = supabase_create_whisper(new_data)
        if created:
            supabase_update_children(w["id"], child_id)
            st.success("Remix created!")

            snippet = make_snippet(new_message, child_id, w.get("motif"))
            st.code(snippet, language="text")

            st.experimental_set_query_params(view="detail", id=child_id)

    # Display children
    st.write("### Existing Remixes")
    for cid in w.get("children", []):
        child = supabase_get_by_id(cid)
        if child:
            st.markdown(f"- {child.get('message')}  \n**Author:** {child.get('author')}")
            st.code(make_snippet(child.get("message"), child.get("id"), child.get("motif")), language="text")


# =========================================================
# Browse All Whispers
# =========================================================
def view_browse():
    st.subheader("All Whispers")

    all_w = supabase_get_all()
    if not all_w:
        st.info("No whispers found.")
        return

    for w in sorted(all_w, key=lambda x: x["timestamp"], reverse=True):
        st.markdown(f"**{w.get('message')}**  \n*Author:* {w.get('author')}")
        snippet = make_snippet(w["message"], w["id"], w.get("motif"))
        st.code(snippet, language="text")


# =========================================================
# Tree View
# =========================================================
def view_tree():
    st.subheader("Whisper Lineage Tree")

    all_w = supabase_get_all()
    if not all_w:
        st.info("No whispers yet.")
        return

    G = nx.DiGraph()
    for w in all_w:
        G.add_node(w["id"], label=w["message"])
        for c in w.get("children", []):
            G.add_edge(w["id"], c)

    fig = plt.figure(figsize=(12, 8))
    pos = nx.spring_layout(G, seed=42)
    nx.draw(
        G,
        pos,
        with_labels=False,
        node_size=900,
        node_color="lightblue",
        edge_color="gray",
        arrows=True
    )
    labels = {n: G.nodes[n].get("label", "")[:40] for n in G.nodes}
    nx.draw_networkx_labels(G, pos, labels, font_size=7)
    st.pyplot(fig)


# =========================================================
# Router
# =========================================================
if current_view == "detail" and current_id:
    view_detail(current_id)
elif current_view == "browse":
    view_browse()
elif current_view == "tree":
    view_tree()
else:
    st.subheader("Welcome to the Whisper Remix Hub")
    st.write("Craft whispers, remix with others, and watch ideas evolve.")
