from __future__ import annotations

from dataclasses import dataclass
from typing import List, Any, Dict
import json
from pathlib import Path


@dataclass(frozen=True)
class Pad:
	name: str
	color: str   # keep as "0xRRGGBB" string (or convert to int; see below)
	file: str

	@staticmethod
	def from_dict(d: Dict[str, Any]) -> "Pad":
		return Pad(
			name=d["name"],
			color=d["color"],
			file=d["file"],
		)

	def color_as_int(self) -> int:
		"""Convert '0xRRGGBB' to integer (e.g. '0xFF0000' -> 16711680)."""
		return int(self.color, 16)

	def color_as_tuple(self) -> tuple[int, int, int]:
		value = int(self.color, 16)
		return (value >> 16) & 0xFF, (value >> 8) & 0xFF, value & 0xFF



@dataclass(frozen=True)
class SongConfig:
	song: str
	tempo: int
	sound: str
	path: str
	pads: List[Pad]

	@staticmethod
	def from_dict(d: Dict[str, Any]) -> "SongConfig":
		return SongConfig(
			song=d["song"],
			tempo=int(d["tempo"]),
			sound=d["sound"],
			path=d["path"],
			pads=[Pad.from_dict(p) for p in d.get("pads", [])],
		)


def load_song_configs_from_str(json_text: str) -> List[SongConfig]:
	"""Load from a JSON string into a list of SongConfig objects."""
	raw = json.loads(json_text)
	if not isinstance(raw, list):
		raise ValueError("Expected top-level JSON array (a list).")
	return [SongConfig.from_dict(item) for item in raw]


def load_song_configs_from_file(file_path: str | Path) -> List[SongConfig]:
	"""Load from a .json file into a list of SongConfig objects."""
	file_path = Path(file_path)
	raw = json.loads(file_path.read_text(encoding="utf-8"))
	if not isinstance(raw, list):
		raise ValueError("Expected top-level JSON array (a list).")
	return [SongConfig.from_dict(item) for item in raw]
