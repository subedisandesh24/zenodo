import streamlit as st
import time
import requests

st.set_page_config(page_title="Zenodo Uploader (Draft 23406926)", layout="centered")

st.title("⚡ Zenodo High-Speed Dataset Uploader")
st.subheader("Target Draft: `23406926`")

DRAFT_ID = "23406926"

token = st.text_input(
    "Zenodo Personal Access Token", 
    type="password",
    help="Your token from Zenodo > Applications > Personal access tokens"
)

# Native Streamlit "Browse files" button
uploaded_file = st.file_uploader(
    "Click below to browse and select your file", 
    type=["zip", "tar", "gz", "7z"]
)

if uploaded_file is not None:
    file_size_gb = uploaded_file.size / (1024**3)
    st.success(f"Selected: **{uploaded_file.name}** ({file_size_gb:.2f} GB)")

if st.button("Start High-Speed Upload", type="primary"):
    if not token:
        st.error("Please enter your Zenodo Token.")
    elif uploaded_file is None:
        st.error("Please select a file using the Browse button above.")
    else:
        file_name = uploaded_file.name
        file_size = uploaded_file.size
        headers = {"Authorization": f"Bearer {token.strip()}"}

        st.info(f"Connecting to Draft `{DRAFT_ID}`...")

        # 1. Initialize Zenodo draft file
        with st.spinner("Preparing Zenodo endpoint..."):
            init_url = f"https://zenodo.org/api/records/{DRAFT_ID}/draft/files"
            init_res = requests.post(init_url, headers={**headers, "Content-Type": "application/json"}, json=[{"key": file_name}])
            
            # If an earlier stuck file exists, clear it
            if init_res.status_code == 400:
                requests.delete(f"https://zenodo.org/api/records/{DRAFT_ID}/draft/files/{file_name}", headers=headers)
                init_res = requests.post(init_url, headers={**headers, "Content-Type": "application/json"}, json=[{"key": file_name}])

            if init_res.status_code not in [200, 201]:
                st.error(f"Failed to prepare Zenodo draft: {init_res.text}")
                st.stop()

            target_put_url = f"https://zenodo.org/api/records/{DRAFT_ID}/draft/files/{file_name}/content"
            commit_url = f"https://zenodo.org/api/records/{DRAFT_ID}/draft/files/{file_name}/commit"

        # 2. Progress Tracker
        progress_bar = st.progress(0.0)
        status_text = st.empty()
        speed_text = st.empty()

        class StreamWrapper:
            def __init__(self, f_obj, total):
                self.f_obj = f_obj
                self.total = total
                self.sent = 0
                self.last_time = time.time()
                self.last_sent = 0

            def read(self, chunk_size=4 * 1024 * 1024):  # 4MB chunks for fast throughput
                data = self.f_obj.read(chunk_size)
                if not data:
                    return b""
                self.sent += len(data)
                now = time.time()
                elapsed = now - self.last_time

                if elapsed >= 0.5 or self.sent >= self.total:
                    speed = ((self.sent - self.last_sent) / (1024 * 1024)) / elapsed if elapsed > 0 else 0
                    pct = min(self.sent / self.total, 1.0)
                    progress_bar.progress(pct)
                    status_text.markdown(f"**Progress:** `{pct * 100:.1f}%` ({self.sent / (1024**3):.2f} GB / {self.total / (1024**3):.2f} GB)")
                    speed_text.markdown(f"**Upload Speed:** `{speed:.2f} MB/s`")
                    self.last_time = now
                    self.last_sent = self.sent

                return data

            def __len__(self):
                return self.total

        # 3. Stream directly to Zenodo
        try:
            uploaded_file.seek(0)
            res = requests.put(
                target_put_url,
                data=StreamWrapper(uploaded_file, file_size),
                headers={**headers, "Content-Type": "application/octet-stream"}
            )

            if res.status_code in [200, 201]:
                requests.post(commit_url, headers=headers)
                progress_bar.progress(1.0)
                st.success(f" Upload Complete! File added to Draft {DRAFT_ID} under your reserved DOI.")
                st.balloons()
            else:
                st.error(f"Upload failed: {res.text}")
        except Exception as e:
            st.error(f"Error: {e}")
