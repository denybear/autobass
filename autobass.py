import sys
import time
import statistics

sys.path.append('./')
import pygame
import os
import random
import rtmidi


from collections import deque
import update
import song
import draw
import fluid_player


"""
installs:

sudo apt install fluidsynth
sudo apt install python3-googleapi
sudo apt install python3-httplib2
sudo apt install python3-pygame
sudo apt install python3-mido
sudo apt install python3-rtmidi

install google API key:
https://console.cloud.google.com/welcome?pli=1&project=autobass
Select API & Services.
Click on Credentials.
display key for autobass
assign key to GOOGLE_API_KEY environment variable:

nano ~/.bashrc
at the end of file, insert:
export GOOGLE_API_KEY=****value****
source ~/.bashrc

"""


# Main variablesfrom mido.backends.rtmidi import Input

running = True
referenceTempo = 120.0	# initial tempo of midi file
tempoRatio = 1.0		# to play slower or faster
tapTempoRatio = None	# to play slower or faster
knobTempoRatio = 0.0	# to play slower or faster
playListIndex = 0
audioVolume = 0.5
noteOnMapping = {0:["tap tempo"], 1:["stop"], 2:["pad","0"], 3:["pad","1"], 4:["pad","2"], 5:["pad","3"], 6:["pad","4"], 7:["pad","5"], 8:["pad","6"]}
ccMapping = {0:["volume"], 1:["tempo"], 2:["playlist"], 3:["sound"]}
soundMapping = {"Acoustic 1":0, "Acoustic 2":1, "Fingered 1":2, "Fingered 2":3, "Fretless 1": 4, "Fretless 2": 5, "Picked 1": 6, "Picked 2": 7,  "Slap 1": 8,  "Slap 2": 9,  "Synth 1": 10,  "Synth 2": 11}
soundName = "Acoustic 1";
assetPath = "/home/pi/autobass/autobass_playlist/"
playingSong = None		# used to display the pad currently playing in fluo yellow
playingPad = None


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


# class for handling midi messages from rtmidi
def midiCallback(msg, data=None):
	messageType = (msg [0][0]) & 0xF0
	messageNote = (msg [0][1]) & 0x7F
	messageVelocity = (msg [0][2]) & 0x7F
	if messageType == 0x90 and messageVelocity > 0:		# Note on
		try:
			lst = noteOnMapping [messageNote]
			eq.record_event("note on", lst)
		except KeyError:
			pass
	elif messageType == 0xB0:							# Control Change (CC)
		try:
			lst = ccMapping [messageNote][:]			# [:] will force a copy of the list, otherwise the reference only is copied
			lst.append (str(messageVelocity))
			eq.record_event("cc", lst)
		except KeyError:
			pass



########
# MAIN #
########

# get latest playlist and midi files from google drive (public access)
API_KEY = os.environ["GOOGLE_API_KEY"]  # GOOGLE_API_KEY is an environment variable where the key is stored

path = update.download_public_drive_folder(
	"https://drive.google.com/drive/folders/1io1W0YnH7mI1X7S5Q3wC6OUZZVxWNRpT",
	api_key=API_KEY,
	dest_root="/home/pi/autobass/",
	timeout_sec=10,
)


if path is None:
	print("Drive folder not downloaded (offline/timeout/not public/not a folder). Continuing…")
else:
	print("Downloaded to:", path)

# Create a list of Song objects from playlist.json
playList = song.load_song_configs_from_file(assetPath + "playlist.json")
first = playList[0]

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
player = fluid_player.LiveFsPlayer(assetPath + "autobass.sf2", "pulseaudio")

# Create an instance of RtMidiIn, open MIDI input device
midiIn = rtmidi.MidiIn()
availablePorts = midiIn.get_ports()

portNumber = None
if availablePorts:
	for i in range (0, len (availablePorts)):
		if "LPD8 mk2" in availablePorts [i]:	# entry device fixed at AKAI LPD8 mk2
			portNumber = i

if portNumber is None:
	sys.exit ()

midiIn.open_port (portNumber)					# Change index if necessary to your device
midiIn.set_callback (midiCallback)				# set the callback

# Set event queue
eq = EventQueue()		# event queue to manage the events happening in the main loop

# force default volume
player.set_master_volume(audioVolume)
# force display of 1st song in playlist and video
tap = TapTempo(referenceTempo)
eq.record_event("cc", ["playlist","0"])
print ("Ready to roll!")

try:
	while running:

		# Handle Pygame events
		for event in pygame.event.get():
			if event.type == pygame.QUIT:
				running = False

			elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
				running = False
		
		# Handle main loop events
		next_event = eq.get_next_event()
		if next_event:		# make sure there is an event to process

			# display events
			if next_event.label == "display":
				squares = []
				square = {}

				# define song names
				previousSoung = playList [playListIndex - 1].song if playListIndex > 0 else ""
				nextSong = playList [playListIndex + 1].song if playListIndex < (len (playList) - 1) else ""
				currentSong = playList [playListIndex].song

				# define pads to be displayed
				for i in range (0,6):
					square = {}
					try:
						square ["text"] = playList [playListIndex].pads [i].name
						square ["color"] = playList [playListIndex].pads [i].color_as_tuple()
						# manage case of pad is currently playing: square will be fluo yellow
						if playingSong is not None:
							if playingSong == currentSong:
								if playingPad == i:
									square ["color"] = (255, 243, 0)
					except Exception as e:
						square ["text"] = ""
						square ["color"] = (128,128,128)		# gray pads if not defined
					squares.append (square)				
				
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
					player.stop()
					playingSong = None
					playingPad = None
					eq.record_event("display", [])

				# tap tempo
				if next_event.values [0] == "tap tempo":
					tapTempoRatio = tap.tap()
					if tapTempoRatio is not None:
						knobTempoRatio = 0.0
						tempoRatio = tapTempoRatio
						tempoRatio = max(0.1, min (tempoRatio, 4.0))		# speed boundaries
						player.set_speed (tempoRatio)
						eq.record_event ("display", [])				# display new tempo
		
				# pad
				if next_event.values [0] == "pad":
					padNumber = int (next_event.values [1])			# get pad number
					pads = playList [playListIndex].pads			# list of pads for the current song
					
					if (padNumber < len (pads)):					# make sure the pressed pad is specified in json as a pad
						#print ("playing :" + assetPath + playList [playListIndex].path + pads [padNumber].file)
						playingSong = playList [playListIndex].song
						playingPad = padNumber
						player.set_tempo (referenceTempo)
						player.set_speed (tempoRatio)
						player.set_all_instruments(bank=0, preset=soundMapping [soundName], skip_drums=True)
						player.queue_play(assetPath + playList [playListIndex].path + pads [padNumber].file)
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
					temp = (temp / 127.0) * 0.3						# tempo increment between 0.0-0.3
					temp = temp - 0.15								# tempo increment between -0.15 and +0.15
					knobTempoRatio = temp
					if tapTempoRatio is not None:
						tempoRatio = tapTempoRatio + knobTempoRatio
					else:
						tempoRatio = 1.0 + knobTempoRatio
					tempoRatio = max(0.1, min (tempoRatio, 4.0))		# speed boundaries
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
					referenceTempo = playList [playListIndex].tempo
					tempoRatio = 1.0								# reset tempo
					knobTempoRatio = 0.0							# useless but you never know
					tapTempoRatio = None					
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
					player.set_all_instruments(bank=0, preset=soundMapping [soundName], skip_drums=True)
					eq.record_event ("display", [])					# display new sound
		
		# Keep loop responsive
		pygame.time.wait(5)


except KeyboardInterrupt:
    print("Exiting...")


finally:
	# Cleanup
	# stop audio and midi in
	player.stop()
	midiIn.close_port()
	del midiIn
	# Disable input grabbing before exiting
	pygame.event.set_grab(False)
	pygame.mouse.set_visible (True)
	pygame.quit()
