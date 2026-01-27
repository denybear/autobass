import sys
import time
sys.path.append('./')
import pygame
import pygame.midi

import os
import json
import random
import threading
from collections import deque
from playlist_update import sync_remote_file


NOTE_ON  = 0x90  # 144
NOTE_OFF = 0x80  # 128
CC       = 0xB0  # 176

# Global variables
audio_thread = None
cap = None
videoPath = "./video/"
audioPath = "./audio/"
running = True
playing = False
dragging = None
rotaryChangesVolume = True
audioVolume = 0.5
videoRate = 0.5
playListIndex = 0
colorNoError = [0, 128, 0]
colorError = [255, 0, 0]
colorWarning = [255, 165, 0]
isMonitoring = True		# displays a small duplicate of secondary screen on primary screen for monitoring purposes

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


# object representing a tuple: name of the song, name of the video/picture, name of samples 
class Song:
	def __init__(self, song="", video="", sample=["","","","","","","","",""], startPosition="beginning"):
		self.song = song
		self.video = video
		self.sample = sample
		self.startPosition = startPosition

	def __repr__(self):
		return f"Song(song={self.song}, video={self.video}, sample={self.sample}, startPosition={self.startPosition})"


# function for the audio thread
def play_audio(audio_file):
	try:
		pygame.mixer.music.load(audio_file)
	except pygame.error:
		# file does not exist
		return False
	pygame.mixer.music.set_endevent(pygame.USEREVENT)	# pygame event is triggered after playing is complete
	pygame.mixer.music.play()
	return True

def stop_audio():
	pygame.mixer.music.stop()

def start_audio_thread(audio_file):
	global audio_thread
	stop_audio()

	if not os.path.isfile(audio_file):
		# file does not exist
		return False

	audio_thread = threading.Thread(target=play_audio, args=(audio_file,))
	audio_thread.start()
	return True


	
########
# MAIN #
########

# check online & update playlist if required
updated, msg = sync_remote_file(
	"https://github.com/denybear/AFPlayer/blob/main/playlist.json",
	local_filename="playlist.json",  # will save into the current directory
	timeout=3.0
)
print(updated, msg)

# Load the JSON data from the file
with open('./playlist.json', 'r', encoding='utf-8') as file:
	data = json.load(file)

# Create a list of Song objects
playList = [Song(item['song'], item['video'], item['sample'], item['startPosition']) for item in data]
# read, for each song, the midi files etc




# Pygame init (we'll create a tiny hidden window so the event loop works)
pygame.init()
screen = pygame.display.set_mode((1, 1))  # no UI; just to pump events
pygame.display.set_caption("MIDI Event Loop")

# Create windows
os.environ['SDL_VIDEO_WINDOW_POS'] = '%i, %i' % (0, 0)			# force window positionning to primary display at 0,0
screen = pygame.display.set_mode((480, 320), pygame.NOFRAME)	# fixed display size 480 x 320
# force all inputs to be in the pygame window, and hide mouse
pygame.mouse.set_visible (False)
pygame.event.set_grab (True)


# Main loop
eq = EventQueue()		# event queue to manage the events happening in the main loop
# force display of 1st song in playlist and video
eq.record_event("key", ["first song"])


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
				noteOnMapping = {00:["tap tempo"], 01:["stop"], 02:["pad","0"], 03:["pad","1"], 04:["pad","2"], 05:["pad","3"], 06:["pad","4"], 07:["pad","5"], 08:["pad","6"], 09:["pad","7"], 10:["pad","8"], 11:["pad","9"], 12:["pad","10"], 13:["pad","11"], 14:["pad","12"]}
				ccMapping = {00:["volume"], 01:["playlist"], 02:["tempo"], 14:["sound"]}

				# e.data1 = status byte, e.data2 = data1, e.data3 = data2
				status = event.status     # raw status byte (includes channel)
				data1  = event.data1      # note/controller number
				data2  = event.data2      # velocity/value
				channel = status & 0x0F
				message = status & 0xF0

				if message == NOTE_ON and data2 > 0:
					print(f"NOTE ON  ch={channel+1:02d} note={data1} vel={data2}")
					try:
						eq.record_event("note on", noteOnMapping [data1])
					except KeyError:
						pass
				elif message == NOTE_OFF or (message == NOTE_ON and data2 == 0):
					# Treat Note On with velocity 0 as Note Off (MIDI convention)
					print(f"NOTE OFF ch={channel+1:02d} note={data1} vel={data2}")
				elif message == CC:
					print(f"CC       ch={channel+1:02d} cc#={data1} value={data2}")
					try:
						eq.record_event("cc", ccMapping [data1])
					except KeyError:
						pass


		# Handle main loop events
		next_event = eq.get_next_event()
		if next_event:		# make sure there is an event to process

			# display events
			if next_event.label == "display":
				slider_info = displaySongInfo (screen, playList [playListIndex], volume_percent=audioVolume, rate_percent=videoRate, previous_entry=playList [playListPrevious].song, next_entry=playList [playListNext].song, highlight_config=next_event.values)


			# key events
			if next_event.label == "note on":

				# previous
				if next_event.values [0] == "previous" or next_event.values [0] == "first song":
					# get video file name that is currently playing
					try:
						previousVideoFileName = videoPath + playList [playListIndex].video
					except (ValueError, IndexError):
						previousVideoFileName = ""
					# in case of 1st song, force display of video by specifying no previous video
					if next_event.values [0] == "first song":
						previousVideoFileName = ""
					# previous in playlist
					playListIndex = max(playListIndex - 1, 0)
					playListPrevious = max(playListIndex - 1, 0)
					playListNext = min(playListIndex + 1, len(playList) - 1)
					# record new event to update the display
					eq.record_event("display", {
						"video_rate": {"font_size": 0.04, "bold": True, "italic": False, "inverse": False, "color": videoColor, "font_name": "arial", "spacing": 1.0},
						"audio_volume": {"font_size": 0.04, "bold": True, "italic": False, "inverse": False, "color": audioColor, "font_name": "arial", "spacing": 1.0}
					})
					
				# next
				if next_event.values [0] == "next":
					# get video file name that is currently playing
					try:
						previousVideoFileName = videoPath + playList [playListIndex].video
					except (ValueError, IndexError):
						previousVideoFileName = ""
					# next in playlist
					playListIndex = min(playListIndex + 1, len(playList) - 1)
					playListPrevious = max(playListIndex - 1, 0)
					playListNext = min(playListIndex + 1, len(playList) - 1)
					# record new event to update the display
					eq.record_event("display", {
						"video_rate": {"font_size": 0.04, "bold": True, "italic": False, "inverse": False, "color": videoColor, "font_name": "arial", "spacing": 1.0},
						"audio_volume": {"font_size": 0.04, "bold": True, "italic": False, "inverse": False, "color": audioColor, "font_name": "arial", "spacing": 1.0}
					})

				# sample keys
				if next_event.values [0] == "sample":
					# get actual sample filename from playlist; check whether empty
					try:
						sampleFileName = audioPath + playList [playListIndex].sample [int (next_event.values [1]) - 1]
					except (ValueError, IndexError):
						sampleFileName = ""

					# check if playing or not; if playing, we should stop the audio first (update of the display will be done in stop event processing)
					if playing:
						eq.record_event("audio", ["stop"])
					# if not playing, then we should initiate playing
					else:
						sampleString = "sample" + next_event.values [1]
						eq.record_event("audio", ["play", sampleString, sampleFileName])

				# audio volume -, audio volume +
				if next_event.values [0] in ("vol-","vol+","vid-","vid+"):
				
					if next_event.values [0] == "vol-":
						audioVolume = max (0, audioVolume - 0.02)
						if isAudioHW:
							pygame.mixer.music.set_volume (audioVolume)

					# audio volume +
					if next_event.values [0] == "vol+":
						audioVolume = min (audioVolume + 0.02, 1.0)
						if isAudioHW:
							pygame.mixer.music.set_volume (audioVolume)

					# record new event to update the display, based on the result of audioColor, videoColor and playing (sample exists or not)
					highlight_config = {
						"video_rate": {"font_size": 0.04, "bold": True, "italic": False, "inverse": False, "color": videoColor, "font_name": "arial", "spacing": 1.0},
						"audio_volume": {"font_size": 0.04, "bold": True, "italic": False, "inverse": False, "color": audioColor, "font_name": "arial", "spacing": 1.0}
					}
					if playing:
						highlight_config [sampleString] = {"font_size": 0.05, "bold": False, "italic": False, "inverse": True, "color": (0, 100, 0), "font_name": "couriernew", "spacing": 1.5}
					eq.record_event("display", highlight_config)


			# audio events
			if next_event.label == "audio":

				# stop
				if next_event.values [0] == "stop":
					if isAudioHW: stop_audio()
					playing = False
					audioColor = colorNoError
					# record new event to update the display
					eq.record_event("display", {
						"video_rate": {"font_size": 0.04, "bold": True, "italic": False, "inverse": False, "color": videoColor, "font_name": "arial", "spacing": 1.0},
						"audio_volume": {"font_size": 0.04, "bold": True, "italic": False, "inverse": False, "color": audioColor, "font_name": "arial", "spacing": 1.0}
					})

				# play
				if next_event.values [0] == "play":
					# attempt to open audio file and play it
					sampleString = next_event.values [1]
					sampleFileName = next_event.values [2]
					playing = start_audio_thread (sampleFileName) if isAudioHW else False
					audioColor = colorNoError if playing else colorWarning
					# record new event to update the display, based on the result of videoColor and playing (sample exists or not)
					highlight_config = {
						"video_rate": {"font_size": 0.04, "bold": True, "italic": False, "inverse": False, "color": videoColor, "font_name": "arial", "spacing": 1.0},
						"audio_volume": {"font_size": 0.04, "bold": True, "italic": False, "inverse": False, "color": audioColor, "font_name": "arial", "spacing": 1.0}
					}
					if playing:
						highlight_config [sampleString] = {"font_size": 0.05, "bold": False, "italic": False, "inverse": True, "color": (0, 100, 0), "font_name": "couriernew", "spacing": 1.5}
					eq.record_event("display", highlight_config)


		# Perform non-event based functions, ie. video display and key capture

		# Keep loop responsive
		pygame.time.wait(5)


finally:
	# Cleanup
	try:
		inp.close()
	except Exception:
		pass
	if isAudioHW: stop_audio()
	# Disable input grabbing before exiting
	pygame.event.set_grab(False)
	pygame.mouse.set_visible (True)
	pygame.midi.quit()
	pygame.quit()
