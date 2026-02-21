import threading
import time
import pyfluidsynth
import mido

class SimpleMessage:
    def __init__(self, type: str, **kwargs):
        self.type = type  # Set the type property
        # Store additional attributes in the instance
        for key, value in kwargs.items():
            setattr(self, key, value)

    def __repr__(self):
        # Custom string representation for debugging
        return f"SimpleMessage(type='{self.type}', attributes={self.__dict__})"


class LiveFsPlayer:
    DRUM_CHANNEL = 9  # MIDI channel 10 in human terms; 0-based index

    def __init__(self, sf2_path: str, audio_driver: str = "default", output_device: str = "default"):
        self.fs = pyfluidsynth.Synth()
        self.fs.start(driver=audio_driver if output_device is None else audio_driver, device=output_device)

        self.sfid = self.fs.sfload(sf2_path)
        self.fs.program_select(0, self.sfid, 0, 0)
        self.set_all_instruments(bank=0, preset=0, skip_drums=True)

        self.speed = 1.0  # Playback speed multiplier
        self.external_tempo = 120  # External tempo in BPM
        self.ticks_per_beat = 480  # typical PPQN
        self._events = []
        self._stop = threading.Event()
        self._thread = None
        self.pending_file = None
        self.active_notes = {ch: [] for ch in range(16)}  # Track active notes per channel

    def set_tempo(self, bpm: float):
        """Set the external tempo in BPM."""
        self.external_tempo = bpm

    def set_speed(self, speed: float):
        """Set the playback speed."""
        self.speed = max(0.1, min(speed, 4.0))  # Enforce speed limits

    def queue_play(self, midi_path: str):
        """Queue a MIDI file to play."""
        self.pending_file = midi_path
        if self._thread is None or not self._thread.is_alive():
            self.play()

    def play(self):
        """Start playback or continue with the current events."""
        if self.pending_file:
            self._events = self._preload_events(self.pending_file)
            self.pending_file = None  # Clear pending file after loading
        self.stop()
        self._stop.clear()

        # Start playback thread
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        """Stop playback and all currently playing notes."""
        if self._thread and self._thread.is_alive():
            self._stop.set()  # Stop the thread
            self._thread.join(timeout=1.0)  # Wait for the thread to finish
            self._stop_active_notes()  # Stop all active notes
        self._thread = None

    def _stop_active_notes(self):
        """Stop all actively playing notes."""
        for ch in range(16):
            for note in self.active_notes[ch]:
                self.fs.noteoff(ch, note)
            self.active_notes[ch].clear()  # Clear the active notes once stopped

    def _preload_events(self, midi_path):
        """Preload MIDI events including bar change events. Resut is a list of times and related events """
        mid = mido.MidiFile(midi_path)
        self.ticks_per_beat = mid.ticks_per_beat                            # Get PPQN from MIDI file

        bar_mesg = SimpleMessage (type = 'bar_change', velocity=0, note=0)  # message to indicate bar change      
        events = []
        total_time = 0                                  # Accumulate time
        bar_duration = (4 / self.external_tempo) * 60   # Time for one bar in seconds
        next_bar_time = 0                               # time for next bar  
        
        for msg in mid:
            if msg.type not in {"program_change", "set_tempo"}:
                # Calculate the delta time in seconds based on ticks and speed
                total_time += msg.time              # msg.time is already in seconds
                
                if total_time >= next_bar_time:     # need to insert a bar event first
                    events.append ((next_bar_time, bar_mesg))
                    next_bar_time += bar_duration
                
                events.append ((total_time, msg))   # insert note event

        return events

    def _calculate_delay(self, delta):
        """Calculate the duration in seconds for the given delta time."""
        return delta / self.speed  # Convert delay based on speed

    def _run(self):
        current_time = 0.0
        next_event_index = 0
        last_time_check = time.time()
        
        previous_event_time = 0.0

        while not self._stop.is_set():
            now = time.time()
            elapsed_time = now - last_time_check
            last_time_check = now

            current_time += elapsed_time * self.speed  # Adjust current time with playback speed

            # Process MIDI events that are due
            while next_event_index < len(self._events):
                event_time, msg = self._events[next_event_index]

                if current_time >= event_time:
                    if msg.type == 'bar_change':
                        #print("Bar change")
                        if self.pending_file:  # New file is pending
                            # Stop all currently playing notes
                            self._stop_active_notes()  # Stop currently playing notes

                            # Load the new MIDI file and reset the timing
                            self._events = self._preload_events(self.pending_file)
                            next_event_index = 0  # Reset the event index
                            self.pending_file = None  # Clear the pending file
                            current_time = 0.0  # Reset current time for the new file
                            next_event_time = 0.0  # Reset next event time
                            continue  # Skip the rest of the loop and start over
                    else:
                        self._process_midi_event(msg)  # Process the current MIDI event

                    next_event_index += 1
                else:
                    break  # Exit if the current time hasn't reached the next event time

            time.sleep(0.001)  # Sleep for a short duration to avoid high CPU usage

            # Reset current timing for looping; only if all events have been consumed
            if next_event_index >= len(self._events):
                current_time = 0.0
                next_event_index = 0    # Reset the event index
                next_event_time = 0.0   # Reset next event time


    def _process_midi_event(self, msg):
        """Process a MIDI event according to its type."""
        ch = getattr(msg, 'channel', 0)
        if msg.type == "note_on":
            velocity = msg.velocity
            if velocity > 0:
                #print(f"Playing note {msg.note} on channel {ch} with velocity {velocity}")
                self.fs.noteon(ch, msg.note, velocity)
                self.active_notes[ch].append(msg.note)  # Track the active note
            else:
                self.fs.noteoff(ch, msg.note)
        elif msg.type == "note_off":
            self.fs.noteoff(ch, msg.note)
            if msg.note in self.active_notes[ch]:
                self.active_notes[ch].remove(msg.note)  # Remove the note from active notes

    def set_all_instruments(self, bank: int, preset: int, skip_drums: bool = True):
        """Set all channels to a specific instrument preset."""
        for ch in range(16):
            if skip_drums and ch == self.DRUM_CHANNEL:
                continue
            self.fs.program_select(ch, self.sfid, bank, preset)

    def set_master_volume(self, volume: float):
        """Set master output volume."""
        volume = max(0.0, min(float(volume), 1.0))
        self.fs.setting("synth.gain", volume)
