import streamlit as st
import os
import time
import requests
import tkinter as tk
from tkinter import filedialog

st.set_page_config(page_title="Zenodo Uploader (Draft 23406926)", layout="centered")

st.title("🚀 Zenodo High-Speed Dataset Uploader")
st.subheader("Target Draft: `23406926`")

# --- CONFIGURE CREDENTIALS ---
DRAFT_ID = "23406926"
DEFAULT_TOKEN = "HTF1PCwSBLydHPObkicUVH47aTvSDNTOXDKG0u3UskvJVWVhgvwYlDDAZv50" 
# -----------------------------

token_input = st.text_input(
    "Zenodo Personal Access Token",
    value=DEFAULT_TOKEN,
    type="password"
)

# Initialize session state for selected file path
if "selected_file" not in st.session_state:
    st.session_state.selected_file = ""

# File Picker Section
st.write("### Choose Dataset File")
col1, col2 = st.columns([1, 3])

with col1:
    if st.button("📁 Browse File"):
        # Create a hidden Tkinter window to open native OS file dialog
        root = tk.Tk()
        root.withdraw()
        root.wm_attributes('-topmost', 1)  # Bring window to front
        selected = filedialog.askopenfilename(
            parent=root,
            title="Select your 2GB Dataset",
            filetypes=[("ZIP / Archive Files", "*.zip *.tar *.gz *.7z"), ("All Files", "*.*")]
        )
        root.destroy()
        
        if selected:
            st.session_state.selected_file = selected

with col2:
    if st.session_state.selected_file:
        file_size_gb = os.path.getsize(st.session_state.selected_file) / (1024**3)
        st.success(f"Selected: **{os.path.basename(st.session_state.selected_file)}** ({file_size_gb:.2f} GB)")
    else:
        st.info("No file selected yet. Click 'Browse File'.")

clean_path = st.session_state.selected_file

# Upload Button
if st.button("Start High-Speed Direct Upload", type="primary"):
    if not token_input:
        st.error("Please provide your Zenodo Access Token.")
    elif not clean_path or not os.path.isfile(clean_path):
        st.error("Please select a valid file first!")
    else:
        file_size = os.path.getsize(clean_path)
        file_name = os.path.basename(clean_path)
        headers = {"Authorization": f"Bearer {token_input.strip()}"}

        st.info(f"Uploading **{file_name}** ({file_size / (1024**3):.2f} GB) to Draft `{DRAFT_ID}`...")

        # ---------------------------------------------------------
        # Step 1: Initialize Upload Endpoint
        # ---------------------------------------------------------
        upload_mode = "rdm"
        target_put_url = None
        commit_url = None

        with st.spinner("Connecting to Zenodo draft 23406926..."):
            dep_url = f"https://zenodo.org/api/deposit/depositions/{DRAFT_ID}"
            r = requests.get(dep_url, headers=headers)
            
            if r.status_code == 200 and "bucket" in r.json().get("links", {}):
                upload_mode = "bucket"
                bucket_url = r.json()["links"]["bucket"]
                target_put_url = f"{bucket_url}/{file_name}"
            else:
                rdm_init_url = f"https://zenodo.org/api/records/{DRAFT_ID}/draft/files"
                init_resp = requests.post(
                    rdm_init_url, 
                    headers={**headers, "Content-Type": "application/json"},
                    json=[{"key": file_name}]
                )
                
                if init_resp.status_code == 400:
                    del_url = f"https://zenodo.org/api/records/{DRAFT_ID}/draft/files/{file_name}"
                    requests.delete(del_url, headers=headers)
                    init_resp = requests.post(
                        rdm_init_url, 
                        headers={**headers, "Content-Type": "application/json"},
                        json=[{"key": file_name}]
                    )

                if init_resp.status_code not in [200, 201]:
                    st.error(f"Failed to initiate draft file (HTTP {init_resp.status_code}): {init_resp.text}")
                    st.stop()

                target_put_url = f"https://zenodo.org/api/records/{DRAFT_ID}/draft/files/{file_name}/content"
                commit_url = f"https://zenodo.org/api/records/{DRAFT_ID}/draft/files/{file_name}/commit"

        # ---------------------------------------------------------
        # Step 2: Live Progress & Speed Tracker
        # ---------------------------------------------------------
        progress_bar = st.progress(0.0)
        status_text = st.empty()
        speed_text = st.empty()

        class ProgressReader:
            def __init__(self, file_obj, total):
                self.file_obj = file_obj
                self.total = total
                self.uploaded = 0
                self.last_time = time.time()
                self.last_uploaded = 0

            def read(self, size=2 * 1024 * 1024):  # 2MB chunks for maximum speed
                chunk = self.file_obj.read(size)
                if not chunk:
                    return b""
                
                self.uploaded += len(chunk)
                now = time.time()
                elapsed = now - self.last_time

                if elapsed >= 0.5 or self.uploaded >= self.total:
                    delta_bytes = self.uploaded - self.last_uploaded
                    speed_mbps = (delta_bytes / (1024 * 1024)) / elapsed if elapsed > 0 else 0
                    pct = min(self.uploaded / self.total, 1.0)

                    progress_bar.progress(pct)
                    status_text.markdown(
                        f"**Progress:** `{pct * 100:.1f}%` ({self.uploaded / (1024**3):.2f} GB / {self.total / (1024**3):.2f} GB)"
                    )
                    speed_text.markdown(f"**Live Upload Speed:** `{speed_mbps:.2f} MB/s`")

                    self.last_time = now
                    self.last_uploaded = self.uploaded

                return chunk

            def __len__(self):
                return self.total

        # ---------------------------------------------------------
        # Step 3: Stream Directly to Zenodo
        # ---------------------------------------------------------
        try:
            with open(clean_path, "rb") as f:
                upload_stream = ProgressReader(f, file_size)
                stream_headers = {
                    **headers,
                    "Content-Type": "application/octet-stream"
                }

                put_resp = requests.put(
                    target_put_url,
                    data=upload_stream,
                    headers=stream_headers
                )

            if put_resp.status_code in [200, 201]:
                if upload_mode == "rdm" and commit_url:
                    commit_resp = requests.post(commit_url, headers=headers)
                    if commit_resp.status_code not in [200, 201]:
                        st.error(f"Commit failed: {commit_resp.text}")
                        st.stop()

                progress_bar.progress(1.0)
                st.success(f" Successfully uploaded to Draft {DRAFT_ID}!")
                st.balloons()
                st.info("Now refresh your Zenodo browser tab. The file will be there under your reserved DOI.")
            else:
                st.error(f"Upload failed (HTTP {put_resp.status_code}): {put_resp.text}")

        except Exception as e:
            st.error(f"Error during upload: {e}")
