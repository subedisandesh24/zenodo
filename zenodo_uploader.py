import streamlit as st
import time
import requests

st.set_page_config(page_title="Zenodo Uploader (Draft 23406926)", layout="centered")

st.title("🚀 Zenodo High-Speed Dataset Uploader")
st.subheader("Target Draft: `23406926`")

DRAFT_ID = "23406926"

token_input = st.text_input(
    "Zenodo Personal Access Token",
    type="password",
    help="Your token from Zenodo > Applications > Personal access tokens"
)

uploaded_file = st.file_uploader(
    "Choose your dataset (.zip)", 
    type=["zip", "tar", "gz", "7z"]
)

if uploaded_file is not None:
    file_size_gb = uploaded_file.size / (1024**3)
    st.info(f"Selected: **{uploaded_file.name}** ({file_size_gb:.2f} GB)")

if st.button("Start High-Speed Upload to Zenodo", type="primary"):
    if not token_input:
        st.error("Please enter your Zenodo Access Token.")
    elif uploaded_file is None:
        st.error("Please select a file to upload.")
    else:
        file_name = uploaded_file.name
        file_size = uploaded_file.size
        headers = {"Authorization": f"Bearer {token_input.strip()}"}

        upload_mode = "rdm"
        target_put_url = None
        commit_url = None

        with st.spinner("Connecting to Zenodo draft 23406926..."):
            # Check classic bucket first
            dep_url = f"https://zenodo.org/api/deposit/depositions/{DRAFT_ID}"
            r = requests.get(dep_url, headers=headers)
            
            if r.status_code == 200 and "bucket" in r.json().get("links", {}):
                upload_mode = "bucket"
                bucket_url = r.json()["links"]["bucket"]
                target_put_url = f"{bucket_url}/{file_name}"
            else:
                # Modern InvenioRDM upload flow
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
                    st.error(f"Failed to initiate file (HTTP {init_resp.status_code}): {init_resp.text}")
                    st.stop()

                target_put_url = f"https://zenodo.org/api/records/{DRAFT_ID}/draft/files/{file_name}/content"
                commit_url = f"https://zenodo.org/api/records/{DRAFT_ID}/draft/files/{file_name}/commit"

        # Setup Progress Tracking
        progress_bar = st.progress(0.0)
        status_text = st.empty()
        speed_text = st.empty()

        class StreamWrapper:
            def __init__(self, f_obj, total):
                self.f_obj = f_obj
                self.total = total
                self.uploaded = 0
                self.last_time = time.time()
                self.last_uploaded = 0

            def read(self, size=2 * 1024 * 1024):
                chunk = self.f_obj.read(size)
                if not chunk:
                    return b""
                self.uploaded += len(chunk)
                now = time.time()
                elapsed = now - self.last_time

                if elapsed >= 0.5 or self.uploaded >= self.total:
                    delta = self.uploaded - self.last_uploaded
                    speed = (delta / (1024 * 1024)) / elapsed if elapsed > 0 else 0
                    pct = min(self.uploaded / self.total, 1.0)
                    progress_bar.progress(pct)
                    status_text.markdown(f"**Progress:** `{pct * 100:.1f}%` ({self.uploaded / (1024**3):.2f} GB / {self.total / (1024**3):.2f} GB)")
                    speed_text.markdown(f"**Speed:** `{speed:.2f} MB/s`")
                    self.last_time = now
                    self.last_uploaded = self.uploaded

                return chunk

            def __len__(self):
                return self.total

        try:
            uploaded_file.seek(0)
            wrapped_stream = StreamWrapper(uploaded_file, file_size)
            
            put_resp = requests.put(
                target_put_url,
                data=wrapped_stream,
                headers={**headers, "Content-Type": "application/octet-stream"}
            )

            if put_resp.status_code in [200, 201]:
                if upload_mode == "rdm" and commit_url:
                    requests.post(commit_url, headers=headers)

                progress_bar.progress(1.0)
                st.success(f" Upload Complete to Draft {DRAFT_ID}!")
                st.balloons()
            else:
                st.error(f"Upload failed (HTTP {put_resp.status_code}): {put_resp.text}")

        except Exception as e:
            st.error(f"Error during upload: {e}")
