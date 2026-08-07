import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from config import settings, PROJECT_ROOT

SYS_PATH = PROJECT_ROOT / settings.acronyms_sys_path
USER_PATH = PROJECT_ROOT / settings.acronyms_user_path


@dataclass
class AcronymEntry:
    acronym: str
    fullForm: str
    description: str = ""
    category: str = ""
    metadata: Optional[Dict[str, Any]] = None

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "AcronymEntry":
        return AcronymEntry(
            acronym=str(d.get("acronym") or ""),
            fullForm=str(d.get("fullForm") or ""),
            description=str(d.get("description") or ""),
            category=str(d.get("category") or ""),
            metadata=dict(d.get("metadata") or {}),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "acronym": self.acronym,
            "fullForm": self.fullForm,
            "description": self.description,
            "category": self.category,
            "metadata": self.metadata or {},
        }


class AcronymDB:
    """Hybrid JSON DB wrapper.
    Reads from a read-only system database and read-write user database.
    Writes strictly to the user database (acc.json).
    """

    def __init__(self, sys_path: Path = SYS_PATH, user_path: Path = USER_PATH):
        self.sys_path = Path(sys_path)
        self.user_path = Path(user_path)
        self._sys_data: Dict[str, Any] = {}
        self._user_data: Dict[str, Any] = {}
        self._sys_acronyms: List[Dict[str, Any]] = []
        self._user_acronyms: List[Dict[str, Any]] = []
        self._acronyms: List[Dict[str, Any]] = []
        self.reload()

    def reload(self) -> None:
        # Load system acronyms (read-only)
        if self.sys_path.exists():
            try:
                raw_sys = json.loads(self.sys_path.read_text(encoding="utf-8"))
                self._sys_data = raw_sys if isinstance(raw_sys, dict) else {"acronyms": []}
                self._sys_acronyms = list(self._sys_data.get("acronyms") or [])
            except Exception as e:
                print(f"Error loading system acronyms: {e}")
                self._sys_acronyms = []
        else:
            self._sys_acronyms = []

        # Load user acronyms (read-write)
        if not self.user_path.exists():
            self._user_data = {"version": "1.0", "metadata": {}, "acronyms": []}
            self._user_acronyms = []
            self._persist()
        else:
            try:
                raw_user = json.loads(self.user_path.read_text(encoding="utf-8"))
                self._user_data = raw_user if isinstance(raw_user, dict) else {"metadata": {}, "acronyms": []}
                self._user_acronyms = list(self._user_data.get("acronyms") or [])
            except Exception as e:
                print(f"Error loading user acronyms: {e}")
                self._user_acronyms = []

        # Merge them (User takes precedence / dedup by acronym + fullForm)
        self._merge_databases()

    def _merge_databases(self) -> None:
        merged = {}
        # 1. Add system ones
        for e in self._sys_acronyms:
            acr = self._normalize_acronym(str(e.get("acronym") or ""))
            ff = str(e.get("fullForm") or "").strip()
            if acr and ff:
                merged[(acr.lower(), ff.lower())] = e

        # 2. Add user ones (overwriting system ones)
        for e in self._user_acronyms:
            acr = self._normalize_acronym(str(e.get("acronym") or ""))
            ff = str(e.get("fullForm") or "").strip()
            if acr and ff:
                merged[(acr.lower(), ff.lower())] = e

        self._acronyms = list(merged.values())

    def _persist(self) -> None:
        self._user_data["acronyms"] = self._user_acronyms
        self.user_path.write_text(json.dumps(self._user_data, ensure_ascii=False, indent=2), encoding="utf-8")

    def _normalize_acronym(self, acronym: str) -> str:
        return (acronym or "").strip()

    def all(self) -> List[Dict[str, Any]]:
        return list(self._acronyms)

    def get_entries(self, acronym: str) -> List[Dict[str, Any]]:
        key = self._normalize_acronym(acronym)
        if not key:
            return []
        return [e for e in self._acronyms if str(e.get("acronym") or "").strip().lower() == key.lower()]

    def upsert(self, entry: Dict[str, Any]) -> None:
        """Upsert into USER database only, then rebuild merged view."""
        e = dict(entry)
        key_acr = self._normalize_acronym(str(e.get("acronym") or ""))
        key_ff = str(e.get("fullForm") or "").strip()
        if not key_acr or not key_ff:
            raise ValueError("entry requires 'acronym' and 'fullForm'")

        replaced = False
        new_list = []
        for old in self._user_acronyms:
            old_acr = self._normalize_acronym(str(old.get("acronym") or ""))
            old_ff = str(old.get("fullForm") or "").strip()
            if old_acr.lower() == key_acr.lower() and old_ff.lower() == key_ff.lower():
                new_list.append(e)
                replaced = True
            else:
                new_list.append(old)

        if not replaced:
            new_list.append(e)

        self._user_acronyms = new_list
        self._persist()
        self._merge_databases()

    def delete(self, acronym: str, fullForm: Optional[str] = None) -> int:
        """Delete from USER database only, then rebuild merged view."""
        key_acr = self._normalize_acronym(acronym)
        if not key_acr:
            return 0

        before = len(self._user_acronyms)
        if fullForm is None:
            self._user_acronyms = [
                e for e in self._user_acronyms
                if str(e.get("acronym") or "").strip().lower() != key_acr.lower()
            ]
        else:
            key_ff = str(fullForm).strip()
            self._user_acronyms = [
                e
                for e in self._user_acronyms
                if not (
                    self._normalize_acronym(str(e.get("acronym") or "")).lower() == key_acr.lower()
                    and str(e.get("fullForm") or "").strip().lower() == key_ff.lower()
                )
            ]

        deleted = before - len(self._user_acronyms)
        if deleted:
            self._persist()
            self._merge_databases()
        return deleted

    def clear_all(self) -> None:
        """Clears user database only."""
        self._user_data["acronyms"] = []
        self._user_acronyms = []
        self._persist()
        self._merge_databases()
