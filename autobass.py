import sys
import time
import statistics

sys.path.append('./')
import pygame
import os
import random
import mido

from collections import deque
import update
import song
import draw
import fluid_player

#TO DO
#display pad that is playing (optional)

"""
installs:

sudo apt install fluidsynth

#CREATE VIRTUAL ENVIRONMENT
sudo apt update
sudo apt install python3 python3-pip python3-venv
mkdir my_project
cd my_project
python3 -m venv env
source env/bin/activate
pip install <module_name>
deactivate

#INSTALL PACKAGES
pip install pretty_midi pyfluidsynth mido python-rtmidi
pip install pygame
pip install httplib2
pip install google-api-python-client
"""


# Main variables
running = True
referenceTempo = 120	# initial tempo of midi file
tempoRatio = 1.0		# to play slower or faster
tapTempoRatio = None	# to play slower or faster
knobTempoRatio = 1.0	# to play slower or faster
playListIndex = 0
audioVolume = 0.5
noteOnMapping = {0:["tap tempo"], 1:["stop"], 2:["pad","0"], 3:["pad","1"], 4:["pad","2"], 5:["pad","3"], 6:["pad","4"], 7:["pad","5"], 8:["pad","6"]}
ccMapping = {0:["volume"], 1:["tempo"], 2:["playlist"], 3:["sound"]}
soundMapping = {"Acoustic 1":0, "Acoustic 2":1, "Fingered 1":2, "Fingered 2":3, "Fretless 1": 4, "Fretless 2": 5, "Picked 1": 6, "Picked 2": 7,  "Slap 1": 8,  "Slap 2": 9,  "Synth 1": 10,  "Synth 2": 11}
soundName = "Acoustic 1";
assetPath = "./autobass_playlist"



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

# get latest playlist and midi files from google drive (public access)
API_KEY = os.environ["GOOGLE_API_KEY"]  # GOOGLE_API_KEY is an environment variable where the key is stored

path = update.download_public_drive_folder(
	"https://drive.google.com/drive/folders/1io1W0YnH7mI1X7S5Q3wC6OUZZVxWNRpT",
	api_key=API_KEY,
	dest_root="./",
	timeout_sec=10,
)


if path is None:
	print("Drive folder not downloaded (offline/timeout/not public/not a folder). Continuing…")
else:
	print("Downloaded to:", path)

# Create a list of Song objects from playlist.json
playList = song.load_song_configs_from_file(assetPath + "/playlist.json")

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
player = fluid_player.LiveFsPlayer("autobass.sf2", "alsa", "default")

# List all available MIDI input devices
print("Available MIDI input devices:")
for i, name in enumerate(mido.get_input_names()):
	if "LPD8 mk2" in name:				 # entry device fixed at AKAI LPD8 mk2
		input_device_name = name
	print(f"{i}: {name}")

# Initialize the input port
input_port = mido.open_input(input_device_name)
print(f"Listening on {input_device_name}...")

# Set event queue
eq = EventQueue()		# event queue to manage the events happening in the main loop

# force default volume
player.set_master_volume(audioVolume)
# force display of 1st song in playlist and video
eq.record_event("cc", ["playlist","0"])
tap = TapTempo(referenceTempo)


try:
	while running:

		# Handle Pygame events
		for event in pygame.event.get():
			if event.type == pygame.QUIT:
				running = False

			elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
				running = False

		# Handle midi events
		while input_port.poll():
			message = input_port.receive()  # Get the message if available

			if message.type == 'note_on' and message.velocity > 0:
				try:
					lst = noteOnMapping [message.note]
					eq.record_event("note on", lst)
				except KeyError:
					pass
			elif message.type == 'control_change':
				try:
					lst = ccMapping [message.control][:]	#[:] will force a copy of the list, otherwise the reference only is copied
					lst.append (str(message.value))
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
				for i in range (0,6):
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
				pygame.display.flip()

			# note on events
			if next_event.label == "note on":
				# stop
				if next_event.values [0] == "stop":
					print ("stop")
					player.stop()
					eq.record_event("display", [])

				# tap tempo
				if next_event.values [0] == "tap tempo":
					print ("tap")
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
						print ("playing :" + assetPath + "/" + playList [playListIndex].path + pads [padNumber].file)
						player.set_all_instruments(bank=0, preset=soundMapping [soundName], skip_drums=True)
						referenceTempo = player.play(assetPath + "/" + playList [playListIndex].path + pads [padNumber].file, loop=True)
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
					idx = int ((idx * len (playList)) / 127.0)		# index in playlist is between 0 and length of playlist
					idx = max (idx, 0)								# avoid negative values
					idx = min (idx, len(playList) - 1)				# avoid values >= length of playlist
					playListIndex = idx
					soundName = playList [playListIndex].sound
					eq.record_event ("display", [])					# display new song names

				# sound
				if next_event.values [0] == "sound":
					snd = float (next_event.values [1])				# velocity between 0-127
					snd = int ((snd * len (soundMapping)) / 127.0) 	# index in soundfont is between 0 and length of dictionary
					snd = max (snd, 0)								# avoid negative values
					snd = min (snd, len(soundMapping) - 1)			# avoid values >= length of dictionary
					for k, v in soundMapping.items():
						if v == snd:
							soundName = k
							break
					#player.set_instrument(channel=0, bank=0, preset=40)
					player.set_all_instruments(bank=0, preset=soundMapping [soundName], skip_drums=True)
					eq.record_event ("display", [])					# display new sound

		# Keep loop responsive
		pygame.time.wait(30)


except KeyboardInterrupt:
    print("Exiting...")


finally:
	# Cleanup
	# stop audio
	player.stop()
	input_port.close()  # Ensure that the midi port is closed on exit
	# Disable input grabbing before exiting
	pygame.event.set_grab(False)
	pygame.mouse.set_visible (True)
	pygame.quit()
