import sys
import time
import statistics

sys.path.append('./')
import pygame
import pygame.midi
import os
import random

from collections import deque
import playlist_update
import song
import draw
import player

#TO DO
#display pad that is playing (optional)
#create sf2 with only bass sounds

#pip install pretty_midi pyfluidsynth simpleaudio numpy
# and install fluidsynth on your OS (package manager)


NOTE_ON  = 0x90  # 144
NOTE_OFF = 0x80  # 128
CC	   = 0xB0  # 176

# Main variables
running = True
referenceTempo = 120	# initial tempo of midi file
tempoRatio = 1.0		# to play slower or faster
tapTempoRatio = 1.0		# to play slower or faster
knobTempoRatio = 1.0	# to play slower or faster
playListIndex = 0
audioVolume = 0.5
soundMapping = {"rock":0, "pop":1, "soul":2, "jazz":3, "synth": 4}
soundName = "rock";



# class for handling events in the main loop
class Event:
	def __init__(self, label, values):
		if not isinstance(values, (list, dict)):
			raise ValueError("Values must be a list or dictionary.")
		self.label = label
		self.values = values

class EventQueue:
	def __init__(self):
		self.queue = deque()

	def record_event(self, label, values):
		"""Create an Event and add it to the queue."""
		event = Event(label, values)
		self.queue.append(event)

	def get_next_event(self):
		"""Retrieve and remove the next Event from the queue."""
		if self.queue:
			return self.queue.popleft()
		return None

	def peek_next_event(self):
		"""Retrieve the next Event without removing it."""
		if self.queue:
			return self.queue[0]
		return None

	def is_empty(self):
		"""Check if the queue is empty."""
		return len(self.queue) == 0

	def size(self):
		"""Return the number of events in the queue."""
		return len(self.queue)


# class for handling tap tempo
class TapTempo:
	def __init__(self, reference_bpm, max_taps=6, timeout=2.0):
		self.reference_bpm = reference_bpm
		self.max_taps = max_taps
		self.timeout = timeout
		self.taps = []

	def tap(self):
		now = time.monotonic()

		if self.taps and now - self.taps[-1] > self.timeout:
			self.taps.clear()

		self.taps.append(now)
		self.taps = self.taps[-self.max_taps:]

		if len(self.taps) < 2:
			return None

		intervals = [
			self.taps[i] - self.taps[i - 1]
			for i in range(1, len(self.taps))
		]

		avg = statistics.median(intervals)
		tapped_bpm = 60.0 / avg

		return tapped_bpm / self.reference_bpm



	
########
# MAIN #
########

# check online & update playlist if required
updated, msg = playlist_update.sync_remote_file(
	"https://github.com/denybear/autobass/blob/main/playlist.json",
	local_filename="playlist.json",  # will save into the current directory
	timeout=3.0
)
print(updated, msg)

# Create a list of Song objects from playlist.json
playList = song.load_song_configs_from_file("playlist.json")

first = playList[0]
print(first.song, first.tempo, first.sound, first.path)

for pad in first.pads:
	print(pad.name, pad.color, pad.file, pad.color_as_int())


# Pygame init (we'll create a tiny hidden window so the event loop works)
pygame.init()
eventScreen = pygame.display.set_mode((1, 1))  					# no UI; just to pump events
pygame.display.set_caption("MIDI Event Loop")

# Create windows
os.environ['SDL_VIDEO_WINDOW_POS'] = '%i, %i' % (0, 0)			# force window positionning to primary display at 0,0
screen = pygame.display.set_mode((480, 320), pygame.NOFRAME)	# fixed display size 480 x 320
# force all inputs to be in the pygame window, and hide mouse
pygame.mouse.set_visible (False)
pygame.event.set_grab (True)

# Open player & load soundfont
player = LiveFsPlayer("MySoundFont.sf2")

# Main loop
eq = EventQueue()		# event queue to manage the events happening in the main loop
# force display of 1st song in playlist and video
eq.record_event("cc", ["playlist","0"])
tap = TapTempo(referenceTempo)


try:
	# If you don't pass a device_id, use the system default
	if device_id is None:
		device_id = pygame.midi.get_default_input_id()
	if device_id == -1:
		print("No default MIDI input device found.")
		return

	print(f"Using MIDI input device #{device_id}")
	inp = pygame.midi.Input(device_id)


	while running:

		# If there is MIDI data waiting, read a small batch and post as pygame events
		if inp.poll():
			midi_events = inp.read(16)  # list of ([status, d1, d2, d3], timestamp)
			# Convert to pygame events and push into the event queue
			for midi_event in pygame.midi.midis2events(midi_events, inp.device_id):
				pygame.event.post(midi_event)


		# Handle Pygame events
		for event in pygame.event.get():
			if event.type == pygame.QUIT:
				running = False

			elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
				running = False
			
			elif event.type == pygame.midi.MIDIIN:
				noteOnMapping = {00:["tap tempo"], 01:["stop"], 02:["pad","0"], 03:["pad","1"], 04:["pad","2"], 05:["pad","3"], 06:["pad","4"], 07:["pad","5"], 08:["pad","6"]}
				ccMapping = {00:["volume"], 01:["tempo"], 02:["playlist"], 14:["sound"]}

				# e.data1 = status byte, e.data2 = data1, e.data3 = data2
				status = event.status	 # raw status byte (includes channel)
				data1  = event.data1	  # note/controller number
				data2  = event.data2	  # velocity/value
				channel = status & 0x0F
				message = status & 0xF0

				if message == NOTE_ON and data2 > 0:
					print(f"NOTE ON  ch={channel+1:02d} note={data1} vel={data2}")
					try:
						lst = noteOnMapping [data1]
						lst.append (str(data2))
						eq.record_event("note on", lst)
					except KeyError:
						pass
				elif message == NOTE_OFF or (message == NOTE_ON and data2 == 0):
					# Treat Note On with velocity 0 as Note Off (MIDI convention)
					print(f"NOTE OFF ch={channel+1:02d} note={data1} vel={data2}")
				elif message == CC:
					print(f"CC	   ch={channel+1:02d} cc#={data1} value={data2}")
					try:
						lst = []
						lst.append (ccMapping [data1])
						lst.append (str(data2))
						eq.record_event("cc", lst)
					except KeyError:
						pass


		# Handle main loop events
		next_event = eq.get_next_event()
		if next_event:		# make sure there is an event to process

			# display events
			if next_event.label == "display":
				squares = []
				square = {}
				# define pads to be displayed
				for i in range (0,6)
					square = {}
					try:
						square ["text"] = playList [playListIndex].pads [i].name
						square ["color"] = playList [playListIndex].pads [i].color_as_tuple()
					except Exception as e:
						square ["text"] = ""
						square ["color"] = (128,128,128)		# gray pads if not defined
					squares.append (square)
				# define song names
				previousSoung = playList [playListIndex - 1].song if playListIndex > 0 else ""
				nextSong = playList [playListIndex + 1].song if playListIndex < (len (playList) - 1) else ""
				currentSong = playList [playListIndex].song
				
				draw.draw_dashboard(
					screen=screen,
					squares=squares,
					volume_percent=audioVolume,
					tempo_bpm=int (referenceTempo * tempoRatio),
					sound=soundName,
					prev_song=previousSoung,
					current_song=currentSong,
					next_song=nextSong
				)				
				
				#HERE: required or not?
				pygame.display.flip()

			# note on events
			if next_event.label == "note on":
				# stop
				if next_event.values [0] == "stop":
					player.stop()
					eq.record_event("display", [])

				# tap tempo
				if next_event.values [0] == "tap tempo":
					tapTempoRatio = tap.tap()
					if tapTempoRatio is not None:
						tempoRatio = tapTempoRatio
						player.set_speed(tempoRatio)
		
				# pad
				if next_event.values [0] == "pad":
					padNumber = int (next_event.values [1])			# get pad number
					pads = playList [playListIndex].pads			# list of pads for the current song
					
					if (padNumber < len (pads)):					# make sure the pressed pad is specified in json as a pad
						#color = color_as_int (pads [padNumber].color)
						referenceTempo = player.play(pads [padNumber].file, loop=True)
						tap = TapTempo(referenceTempo)
						eq.record_event ("display", [])				# display pad that is playing

			# cc events
			if next_event.label == "cc":
				# volume
				if next_event.values [0] == "volume":
					vol = float (next_event.values [1])				# velocity between 0-127
					vol = vol / 127.0								# volume between 0.0-1.0
					audioVolume = vol
					player.set_master_volume(audioVolume)
					eq.record_event ("display", [])					# display new volume

				# tempo
				if next_event.values [0] == "tempo":
					temp = float (next_event.values [1])			# velocity between 0-127
					temp = (temp / 127.0) * 0.2						# tempo increment between 0.0-0.2
					temp = temp - 0.1								# tempo increment between -0.1 and +0.1
					knobTempoRatio = temp
					if tapTempoRatio is not None:
						tempoRatio = tapTempoRatio + knobTempoRatio
					else:
						tempoRatio = 1.0 + knobTempoRatio
					player.set_speed (tempoRatio)					# assign new tempo
					eq.record_event ("display", [])					# display new tempo

				# playlist
				if next_event.values [0] == "playlist":
					idx = float (next_event.values [1])				# velocity between 0-127
					idx = int (temp / 127.0) * len (playList)		# index in playlist is between 0 and length of playlist
					idx = max (idx, 0)								# avoid negative values
					idx = min (idx, len(playList) - 1)				# avoid values >= length of playlist
					playListIndex = idx
					eq.record_event ("display", [])					# display new song names

				# sound
				if next_event.values [0] == "sound":
					snd = float (next_event.values [1])				# velocity between 0-127
					snd = int (temp / 127.0) * len (soundMapping)	# index in soundfont is between 0 and length of dictionary
					snd = max (snd, 0)								# avoid negative values
					snd = min (snd, len(soundMapping) - 1)			# avoid values >= length of dictionary				
					soundName = [k for k, v in soundMapping.items() if v == snd]
					#player.set_instrument(channel=0, bank=0, preset=40)
					player.set_all_instruments(bank=0, preset=snd, skip_drums=True)
					eq.record_event ("display", [])					# display new sound

		# Keep loop responsive
		pygame.time.wait(5)


finally:
	# Cleanup
	try:
		inp.close()
	except Exception:
		pass
	# stop audio
	player.stop()
	player.close()
	# Disable input grabbing before exiting
	pygame.event.set_grab(False)
	pygame.mouse.set_visible (True)
	pygame.midi.quit()
	pygame.quit()
