import os
import sys
import time
import requests

DRAFT_ID = "23406926"

print("=" * 50)
print(f"Direct PC -> Zenodo Uploader (Draft {DRAFT_ID})")
print("=" * 50)

token = input("Enter your Zenodo Token: ").strip()
file_path = input("Drag and drop your .zip file here (or paste path): ").strip('\"').strip('\'').strip()

if not os.path.isfile(file_path):
    print("Error: File not found!")
    sys.exit(1)

file_name = os.path.basename(file_path)
file_size = os.path.getsize(file_path)
headers = {"Authorization": f"Bearer {token}"}

print(f"\nTarget File: {file_name} ({file_size / (1024**3):.2f} GB)")
print("Connecting directly to Zenodo...")

# Step 1: Tell Zenodo to prepare for the file
init_url = f"https://zenodo.org/api/records/{DRAFT_ID}/draft/files"
r = requests.post(init_url, headers={**headers, "Content-Type": "application/json"}, json=[{"key": file_name}])

if r.status_code == 400:
    # Clear any previous stuck attempt
    requests.delete(f"https://zenodo.org/api/records/{DRAFT_ID}/draft/files/{file_name}", headers=headers)
    r = requests.post(init_url, headers={**headers, "Content-Type": "application/json"}, json=[{"key": file_name}])

if r.status_code not in [200, 201]:
    print(f"Failed to initialize: {r.text}")
    sys.exit(1)

target_put_url = f"https://zenodo.org/api/records/{DRAFT_ID}/draft/files/{file_name}/content"
commit_url = f"https://zenodo.org/api/records/{DRAFT_ID}/draft/files/{file_name}/commit"

# Step 2: Upload Stream with real-time terminal progress
class ProgressReader:
    def __init__(self, f, total):
        self.f = f
        self.total = total
        self.sent = 0
        self.start_time = time.time()

    def read(self, chunk_size=4 * 1024 * 1024):  # Fast 4MB chunks
        chunk = self.f.read(chunk_size)
        if not chunk:
            return b""
        self.sent += len(chunk)
        elapsed = time.time() - self.start_time
        speed = (self.sent / (1024 * 1024)) / elapsed if elapsed > 0 else 0
        pct = (self.sent / self.total) * 100
        
        # Live terminal progress display
        sys.stdout.write(
            f"\rUploading: {pct:.1f}% | Sent: {self.sent / (1024**3):.2f}/{self.total / (1024**3):.2f} GB | Speed: {speed:.2f} MB/s"
        )
        sys.stdout.flush()
        return chunk

    def __len__(self):
        return self.total

print("Starting direct stream...\n")
with open(file_path, "rb") as f:
    upload_resp = requests.put(
        target_put_url,
        data=ProgressReader(f, file_size),
        headers={**headers, "Content-Type": "application/octet-stream"}
    )

if upload_resp.status_code in [200, 201]:
    # Step 3: Finalize
    requests.post(commit_url, headers=headers)
    print("\n\n Upload complete! Refresh your Zenodo page, the file is deposited under your reserved DOI.")
else:
    print(f"\nUpload failed: {upload_resp.text}")
