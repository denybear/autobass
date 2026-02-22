# autobass
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

## Installation
<ins>make sure the following python modules are installed:</ins>   
```
sudo apt install pulseaudio pulseaudio-utils
sudo apt install fluidsynth
sudo apt install python3-googleapi
sudo apt install python3-httplib2
sudo apt install python3-pygame
sudo apt install python3-mido
sudo apt install python3-rtmidi
````

<ins>install google API key:</ins>   
1. install google API key: `https://console.cloud.google.com/welcome?pli=1&project=autobass`   
2. select: **API & Services --> Click on Credentials --> Display key for autobass**   
3. assign key to GOOGLE_API_KEY environment variable: `nano ~/.bashrc`   
4. at the end of file, insert:
```
export GOOGLE_API_KEY=****value****
source ~/.bashrc
```

## Autorun at startup
1. Define crontab to automatically run synthiboocli.sh at each boot  
```
crontab -e
```
then add the following line at the end of the crontab table:  
```
@reboot sh /home/pi/syntwo.sh  
```
remember to save (ctrl-O) and exit (ctrl-X).  

2. Just to make sure you did not mess with crontab, check what you have done  
```
crontab -l
```
your line should be there.  
Once this is done, you can reboot your headless PI, everything should work fine...
```
sudo reboot now
```   





