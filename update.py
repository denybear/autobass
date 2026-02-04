import os
import re
import io
import uuid
import shutil
import socket
from pathlib import Path

import httplib2
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseDownload  # chunked downloads [5](https://googleapis.github.io/google-api-python-client/docs/epy/googleapiclient.http.MediaIoBaseDownload-class.html)

FOLDER_MIME = "application/vnd.google-apps.folder"


def _extract_drive_id(url_or_id: str) -> str | None:
	"""Extract Drive ID from common folder/file URL formats, or accept a raw ID."""
	if not url_or_id:
		return None
	s = url_or_id.strip()

	# raw ID case
	if re.fullmatch(r"[-\w]{10,}", s) and "http" not in s:
		return s

	# URL patterns: /folders/<ID>, ?id=<ID>, /d/<ID>
	m = re.search(r"(?:/folders/|id=|/d/)([^/?&\s]+)", s)
	return m.group(1) if m else None


def download_public_drive_folder(
	folder_url_or_id: str,
	api_key: str,
	dest_root: str | os.PathLike = ".",
	*,
	timeout_sec: float = 5.0,
	erase_existing: bool = True,
) -> str | None:
	"""
	Download a *publicly accessible* Google Drive folder recursively using an API key.

	Returns:
	  - local folder path (str) on success
	  - None on failure (no network, timeout, not a folder, no permission, etc.)

	Notes:
	  - API key access cannot read private folders/files. [1](https://googleapis.github.io/google-api-python-client/docs/start.html)
	  - Recursion uses files.list with q="'<id>' in parents". [2](https://developers.google.com/workspace/drive/api/reference/rest/v3/files/list)[3](https://stackoverflow.com/questions/60177954/google-drive-api-v3-is-there-anyway-to-list-of-files-and-folders-from-a-root-fo)[4](https://developers.google.com/workspace/drive/api/guides/search-files)
	"""
	folder_id = _extract_drive_id(folder_url_or_id)
	if not folder_id or not api_key:
		return None

	# Per-request timeout is set when constructing httplib2.Http [6](http://httplib2.readthedocs.io/en/latest/libhttplib2.html)[7](https://googleapis.dev/python/google-auth-httplib2/latest/google_auth_httplib2.html)
	http = httplib2.Http(timeout=timeout_sec)
	service = build("drive", "v3", developerKey=api_key, http=http, cache_discovery=False)

	# 1) Validate folder + get name
	try:
		meta = service.files().get(
			fileId=folder_id,
			fields="id,name,mimeType",
			supportsAllDrives=True,
		).execute()
	except (HttpError, socket.timeout, socket.gaierror, OSError):
		return None

	if meta.get("mimeType") != FOLDER_MIME:
		return None

	folder_name = meta.get("name") or f"drive_folder_{folder_id}"
	dest_root = Path(dest_root)
	final_path = dest_root / folder_name

	# 2) Stage download first (do not touch existing until success)
	staging_parent = dest_root / f".gdrive_staging_{folder_name}_{uuid.uuid4().hex}"
	staging_parent.mkdir(parents=True, exist_ok=False)
	staging_folder = staging_parent / folder_name
	staging_folder.mkdir(parents=True, exist_ok=False)

	def list_children(parent_id: str):
		# files.list supports q filtering; we use "'<id>' in parents and trashed=false" [2](https://developers.google.com/workspace/drive/api/reference/rest/v3/files/list)[4](https://developers.google.com/workspace/drive/api/guides/search-files)
		page_token = None
		while True:
			resp = service.files().list(
				q=f"'{parent_id}' in parents and trashed=false",
				fields="nextPageToken,files(id,name,mimeType)",
				pageSize=1000,
				pageToken=page_token,
				includeItemsFromAllDrives=True,
				supportsAllDrives=True,
			).execute()
			for f in resp.get("files", []):
				yield f
			page_token = resp.get("nextPageToken")
			if not page_token:
				break

	def download_file(file_id: str, out_path: Path):
		out_path.parent.mkdir(parents=True, exist_ok=True)
		request = service.files().get_media(fileId=file_id, supportsAllDrives=True)
		with io.FileIO(out_path, "wb") as fh:
			downloader = MediaIoBaseDownload(fh, request, chunksize=1024 * 1024)  # [5](https://googleapis.github.io/google-api-python-client/docs/epy/googleapiclient.http.MediaIoBaseDownload-class.html)
			done = False
			while not done:
				_, done = downloader.next_chunk(num_retries=0)

	# 3) Traverse + download
	try:
		stack = [(folder_id, staging_folder)]
		while stack:
			current_id, current_local = stack.pop()
			for item in list_children(current_id):
				name = item.get("name") or item["id"]
				mime = item.get("mimeType")
				item_id = item["id"]
				local_path = current_local / name

				if mime == FOLDER_MIME:
					local_path.mkdir(parents=True, exist_ok=True)
					stack.append((item_id, local_path))
				else:
					download_file(item_id, local_path)

	except (HttpError, socket.timeout, socket.gaierror, OSError):
		shutil.rmtree(staging_parent, ignore_errors=True)
		return None
	except Exception:
		shutil.rmtree(staging_parent, ignore_errors=True)
		return None

	# 4) Commit (replace existing only after successful staging)
	try:
		if final_path.exists():
			if not erase_existing:
				shutil.rmtree(staging_parent, ignore_errors=True)
				return str(final_path)

			# remove only now
			if final_path.is_dir():
				shutil.rmtree(final_path)
			else:
				final_path.unlink()

		shutil.move(str(staging_folder), str(final_path))
		shutil.rmtree(staging_parent, ignore_errors=True)
		return str(final_path)

	except Exception:
		shutil.rmtree(staging_parent, ignore_errors=True)
		return None
``