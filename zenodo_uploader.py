import streamlit as st
import os
import time
import requests

st.set_page_config(page_title="Zenodo Direct Uploader", layout="centered")

st.title("⚡ Direct High-Speed Zenodo Uploader")
st.caption("Streams directly from your PC's storage to Zenodo API (No intermediate servers).")

DRAFT_ID = "23406926"

token = st.text_input("Zenodo Access Token", type="password")
file_path_input = st.text_input("File Path on your PC", placeholder=r"C:\path\to\tomato fruit detection dataset.zip")

if st.button("Start Direct Upload", type="primary"):
    path = file_path_input.strip('\"').strip('\'').strip()

    if not token:
        st.error("Please enter your Zenodo Token.")
    elif not path or not os.path.isfile(path):
        st.error("File not found! Make sure the path is correct.")
    else:
        file_name = os.path.basename(path)
        file_size = os.path.getsize(path)
        headers = {"Authorization": f"Bearer {token.strip()}"}

        st.info(f"Uploading **{file_name}** ({file_size / (1024**3):.2f} GB) directly to Draft `{DRAFT_ID}`...")

        # 1. Initialize draft file in Zenodo
        with st.spinner("Connecting directly to Zenodo..."):
            init_url = f"https://zenodo.org/api/records/{DRAFT_ID}/draft/files"
            init_res = requests.post(init_url, headers={**headers, "Content-Type": "application/json"}, json=[{"key": file_name}])
            
            # If partially uploaded earlier, clear it first
            if init_res.status_code == 400:
                requests.delete(f"https://zenodo.org/api/records/{DRAFT_ID}/draft/files/{file_name}", headers=headers)
                init_res = requests.post(init_url, headers={**headers, "Content-Type": "application/json"}, json=[{"key": file_name}])

            if init_res.status_code not in [200, 201]:
                st.error(f"Zenodo rejected request (HTTP {init_res.status_code}): {init_res.text}")
                st.stop()

            target_put_url = f"https://zenodo.org/api/records/{DRAFT_ID}/draft/files/{file_name}/content"
            commit_url = f"https://zenodo.org/api/records/{DRAFT_ID}/draft/files/{file_name}/commit"

        # 2. Live Speed & Progress Monitor
        progress_bar = st.progress(0.0)
        status_text = st.empty()
        speed_text = st.empty()

        class DirectStream:
            def __init__(self, f_obj, total):
                self.f_obj = f_obj
                self.total = total
                self.sent = 0
                self.last_time = time.time()
                self.last_sent = 0

            def read(self, chunk_size=4 * 1024 * 1024):  # 4MB chunks for max network speed
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

        # 3. Stream data
        try:
            with open(path, "rb") as f:
                res = requests.put(
                    target_put_url,
                    data=DirectStream(f, file_size),
                    headers={**headers, "Content-Type": "application/octet-stream"}
                )

            if res.status_code in [200, 201]:
                requests.post(commit_url, headers=headers)
                progress_bar.progress(1.0)
                st.success(f" Upload Complete! File added to Draft {DRAFT_ID} under your existing reserved DOI.")
                st.balloons()
            else:
                st.error(f"Upload failed: {res.text}")
        except Exception as e:
            st.error(f"Error: {e}")
