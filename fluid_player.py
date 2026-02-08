import threading
import time
import fluidsynth
import pretty_midi
import mido

class LiveFsPlayer:
	DRUM_CHANNEL = 9  # MIDI channel 10 in human terms; 0-based index

	def __init__(self, sf2_path: str, audio_driver: str = "default", output_device: str = "hw:0"):
		self.fs = fluidsynth.Synth()

		# Start FluidSynth with the specified output device
		self.fs.start(driver=audio_driver, options=f"audio_device={output_device}")

		self.sfid = self.fs.sfload(sf2_path)
		self.set_all_instruments(bank=0, preset=0, skip_drums=True)

		for ch in range(16):
			if ch != 9:
				self.fs.program_select(ch, self.sfid, 0, 0)

		self.speed = 1.0
		self._events = []
		self._stop = threading.Event()
		self._thread = None
		self._loop = True

	def set_speed(self, speed: float):
		self.speed = max(0.1, min(speed, 4.0))

	def play(self, midi_path: str, loop: bool = True) -> float:
		"""
		Preloads MIDI, starts playback, returns reference BPM
		"""

		# 1) compute reference BPM once
		pm = pretty_midi.PrettyMIDI(midi_path)
		reference_bpm = pm.estimate_tempo()

		# 2) preload MIDI events ONCE (gapless looping key)
		self._events = self._preload_events(midi_path)

		self.stop()
		self._loop = loop
		self._stop.clear()
		self._thread = threading.Thread(target=self._run, daemon=True)
		self._thread.start()

		return reference_bpm

	def stop(self):
		if self._thread and self._thread.is_alive():
			self._stop.set()
			self._thread.join(timeout=1.0)
		self._thread = None

	def _preload_events(self, midi_path):
		mid = mido.MidiFile(midi_path)
		return [(msg.time, msg) for msg in mid]

	def _run(self):
		while not self._stop.is_set():
			for delta, msg in self._events:
				if self._stop.is_set():
					return

				if delta > 0:
					time.sleep(delta / self.speed)

				if getattr(msg, "is_meta", False):
					continue

				ch = getattr(msg, "channel", 0)

				if msg.type == "note_on":
					if msg.velocity == 0:
						self.fs.noteoff(ch, msg.note)
					else:
						self.fs.noteon(ch, msg.note, msg.velocity)

				elif msg.type == "note_off":
					self.fs.noteoff(ch, msg.note)

				elif msg.type == "program_change":
					self.fs.program_select(ch, self.sfid, 0, msg.program)

				elif msg.type == "control_change":
					if hasattr(self.fs, "cc"):
						self.fs.cc(ch, msg.control, msg.value)

			if not self._loop:
				return

	def set_instrument(self, channel: int, bank: int, preset: int):
		"""
		Set ONE channel to a specific instrument preset in the currently loaded SF2.

		Uses FluidSynth program_select(chan, sfid, bank, preset). [1](https://pypi.org/project/pyfluidsynth/)[3](https://www.fluidsynth.org/api/group__midi__messages.html)
		"""
		channel = int(channel)
		bank = int(bank)
		preset = int(preset)

		if not (0 <= channel <= 15):
			raise ValueError("channel must be 0..15")
		if not (0 <= preset <= 127):
			# Preset range depends on the SF2, but 0..127 is the standard GM range.
			raise ValueError("preset should usually be 0..127")
		if bank < 0:
			raise ValueError("bank must be >= 0")

		self.fs.program_select(channel, self.sfid, bank, preset)  # [1](https://pypi.org/project/pyfluidsynth/)[3](https://www.fluidsynth.org/api/group__midi__messages.html)

	def set_all_instruments(self, bank: int, preset: int, skip_drums: bool = True):
		"""
		Set ALL channels to a specific instrument preset.
		By default, skip the drum channel (channel 9 == MIDI ch 10).

		Uses program_select per channel. [1](https://pypi.org/project/pyfluidsynth/)[3](https://www.fluidsynth.org/api/group__midi__messages.html)
		"""
		bank = int(bank)
		preset = int(preset)

		for ch in range(16):
			if skip_drums and ch == self.DRUM_CHANNEL:
				continue
			self.fs.program_select(ch, self.sfid, bank, preset)  # [1](https://pypi.org/project/pyfluidsynth/)[3](https://www.fluidsynth.org/api/group__midi__messages.html)

	def set_master_volume(self, volume: float):
		"""
		Set master output volume.

		volume:
		  0.0   = silence
		  0.2   = typical default
		  1.0   = loud
		  >1.0  = very loud (use carefully)
		"""
		volume = max(0.0, min(float(volume), 10.0))
		self.fs.set_gain(volume)
