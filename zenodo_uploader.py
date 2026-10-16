import streamlit as st
import os
import time
import requests

st.set_page_config(page_title="Zenodo Uploader (Draft 23357090)", layout="centered")

st.title("Zenodo High-Speed Dataset Uploader")
st.subheader("Target Draft: `23406926`")

# --- CONFIGURE YOUR CREDENTIALS HERE ---
DRAFT_ID = "23357090"
# Paste your token between the quotes below:
ZENODO_TOKEN = "HTF1PCwSBLydHPObkicUVH47aTvSDNTOXDKG0u3UskvJVWVhgvwYlDDAZv50"
# ---------------------------------------

token_input = st.text_input(
    "Zenodo Personal Access Token",
    value=ZENODO_TOKEN if ZENODO_TOKEN != "PASTE_YOUR_ACCESS_TOKEN_HERE" else "",
    type="password"
)

file_path = st.text_input(
    "Absolute Path to Dataset on your PC", 
    placeholder=r"C:\Users\YourUser\Downloads\tomato fruit detection dataset.zip"
)

if st.button("Start High-Speed Direct Upload", type="primary"):
    # Strip accidental quotes from copied paths
    clean_path = file_path.strip('\"').strip('\'')

    if not token_input:
        st.error("Please provide your Zenodo Access Token.")
    elif not clean_path or not os.path.isfile(clean_path):
        st.error("Invalid file path! Please check that the file exists at that exact path.")
    else:
        file_size = os.path.getsize(clean_path)
        file_name = os.path.basename(clean_path)
        headers = {"Authorization": f"Bearer {token_input}"}

        st.info(f"Uploading **{file_name}** ({file_size / (1024**3):.2f} GB) to Draft `{DRAFT_ID}`...")

        # 1. Fetch the direct upload bucket for this draft
        with st.spinner("Connecting to Zenodo draft endpoint..."):
            dep_url = f"https://zenodo.org/api/deposit/depositions/{DRAFT_ID}"
            r = requests.get(dep_url, headers=headers)
            
            if r.status_code != 200:
                # Fallback check for new RDM record drafts
                dep_url = f"https://zenodo.org/api/records/{DRAFT_ID}/draft"
                r = requests.get(dep_url, headers=headers)

            if r.status_code != 200:
                st.error(f"Failed to access draft {DRAFT_ID} (HTTP {r.status_code}): {r.text}")
                st.stop()

            dep_data = r.json()
            bucket_url = dep_data.get("links", {}).get("bucket")
            
            # Target URL
            if bucket_url:
                target_url = f"{bucket_url}/{file_name}"
            else:
                target_url = f"https://zenodo.org/api/records/{DRAFT_ID}/draft/files/{file_name}/content"

        # 2. Setup Progress Tracker
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

            def read(self, size=1024 * 1024):  # 1MB chunks for optimal speed
                chunk = self.file_obj.read(size)
                if not chunk:
                    return b""
                
                self.uploaded += len(chunk)
                now = time.time()
                elapsed = now - self.last_time

                # Refresh display every 0.5 seconds
                if elapsed >= 0.5 or self.uploaded >= self.total:
                    delta_bytes = self.uploaded - self.last_uploaded
                    speed_mbps = (delta_bytes / (1024 * 1024)) / elapsed if elapsed > 0 else 0
                    percent = min(self.uploaded / self.total, 1.0)

                    progress_bar.progress(percent)
                    status_text.markdown(
                        f"**Progress:** `{percent * 100:.1f}%` ({self.uploaded / (1024**3):.2f} GB / {self.total / (1024**3):.2f} GB)"
                    )
                    speed_text.markdown(f"**Upload Speed:** `{speed_mbps:.2f} MB/s`")

                    self.last_time = now
                    self.last_uploaded = self.uploaded

                return chunk

            def __len__(self):
                return self.total

        # 3. Stream data directly to Zenodo
        try:
            with open(clean_path, "rb") as f:
                upload_stream = ProgressReader(f, file_size)
                
                # Direct streaming PUT request
                resp = requests.put(
                    target_url,
                    data=upload_stream,
                    headers=headers
                )

            if resp.status_code in [200, 201]:
                st.success("Successfully uploaded to Draft 23357090!")
                st.balloons()
                st.info("You can now go back to Zenodo and refresh the page. Your 2GB dataset will appear under the exact same reserved DOI.")
            else:
                st.error(f"Upload failed (HTTP {resp.status_code}): {resp.text}")

        except Exception as e:
            st.error(f"Error while uploading: {e}")
