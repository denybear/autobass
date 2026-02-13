# autobass
## Status of the project
Paused, as it seems there are some issues getting fluidsynth playing midi files (Python via pyfluidsynth). Program features are all functional, but I don't get any sound at all as fluidsynth don't play the noteon requests; however it seems fluidsynth gets the midi requests (program change requests work). Maybe an issue with fluidsynth, it may work with a newer version.
I may revive the project (either in python, either in C).

## Object
autobass is a musical software. Its aim is to play bass lines, while the musician is doing something else.
The basslines are midi files; a bassline can be split into several midi files, such as: verse, chorus, bridge, etc; or chord Am, chord D, etc.
midi files are collated into a "song". A "playlist" is a collection of many songs.
The split playlist-songs-midi files is detailed in a json file (playlist.json).

## Requirements
* RPI 3 or more
* display
* midi control surface (AKAI LPD8 mk2)
* small 320x480 LCD screen

## Autobass features
* song details displayed on dedicated screen (midi files, song name, previous/next song, current tempo, bass sound, volume %)
* play a midi file (part of a song) by pressing a pad on control
* stop the playing by pressing a pad
* tap-tempo by pressing a pad
* move through the playlist with a knob
* fine adjust the tempo with a knob
* adjust volume with a knob
* change bass sound (acoustic, fingered, picked, etc) with a knob
* dedicated sf2 soundfont file with many bass sounds


