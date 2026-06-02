import mimetypes
import shutil
import uuid
from pathlib import Path
from typing import List, Optional, Tuple

from fastapi import UploadFile

from .schemas import FileMetadata


class FileStore:
    def __init__(self, base_dir: str, api_prefix: str) -> None:
        self.base_dir = Path(base_dir)
        self.api_prefix = api_prefix.rstrip("/")

    def _user_dir(self, user_id: str) -> Path:
        return self.base_dir / user_id

    def _safe_name(self, name: str) -> str:
        base_name = Path(name).name
        return base_name or "file"

    def _parse_filename(self, stored_name: str) -> Tuple[str, str]:
        if "__" in stored_name:
            file_id, original_name = stored_name.split("__", 1)
            return file_id, original_name
        return "", stored_name

    def _build_url(self, filename: str) -> str:
        return f"{self.api_prefix}/files/{filename}"

    def _resolve_content_type(self, name: str, fallback: Optional[str] = None) -> str:
        return fallback or mimetypes.guess_type(name)[0] or "application/octet-stream"

    def save_upload(self, upload: UploadFile, user_id: str) -> FileMetadata:
        user_dir = self._user_dir(user_id)
        user_dir.mkdir(parents=True, exist_ok=True)
        file_id = uuid.uuid4().hex
        safe_name = self._safe_name(upload.filename or "file")
        stored_name = f"{file_id}__{safe_name}"
        target_path = user_dir / stored_name
        with target_path.open("wb") as buffer:
            shutil.copyfileobj(upload.file, buffer)
        size = target_path.stat().st_size
        return FileMetadata(
            id=file_id,
            name=safe_name,
            size=size,
            type=self._resolve_content_type(safe_name, upload.content_type),
            url=self._build_url(stored_name),
            filename=stored_name,
        )

    def list_files(self, user_id: str) -> List[FileMetadata]:
        user_dir = self._user_dir(user_id)
        if not user_dir.exists():
            return []
        results: List[FileMetadata] = []
        for entry in sorted(user_dir.iterdir(), key=lambda path: path.name):
            if not entry.is_file():
                continue
            file_id, name = self._parse_filename(entry.name)
            size = entry.stat().st_size
            results.append(
                FileMetadata(
                    id=file_id,
                    name=name,
                    size=size,
                    type=self._resolve_content_type(name),
                    url=self._build_url(entry.name),
                    filename=entry.name,
                )
            )
        return results

    def get_file_path(self, user_id: str, filename: str) -> Optional[Path]:
        safe_name = Path(filename).name
        if safe_name != filename:
            return None
        target_path = self._user_dir(user_id) / safe_name
        if not target_path.exists() or not target_path.is_file():
            return None
        return target_path

    def delete_user_files(self, user_id: str) -> None:
        user_dir = self._user_dir(user_id)
        if not user_dir.exists():
            return
        base_dir = self.base_dir.resolve()
        user_dir_resolved = user_dir.resolve()
        if user_dir_resolved == base_dir:
            return
        if not user_dir_resolved.is_relative_to(base_dir):
            return
        shutil.rmtree(user_dir_resolved)
