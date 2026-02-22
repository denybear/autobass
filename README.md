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
1. create a service file:
```
sudo nano /etc/systemd/user/mon_script.service`
```
2. type a file like this:
```
[Unit]
Description=autobass python script
After=default.target

[Service]
Environment="GOOGLE_API_KEY=****value****"
Environment="XDG_RUNTIME_DIR=/run/user/%u"
ExecStart=/usr/bin/python3 /home/pi/autobass/autobass.py
WorkingDirectory=/home/pi/autobass
StandardOutput=journal
StandardError=journal
Restart=on-failure

[Install]
WantedBy=default.target
```
3. activate the service:
```
systemctl --user enable mon_script.service
systemctl --user start mon_script.service
```
4. check service status:
```
systemctl --user status mon_script.service
```
5. your service should run at startup
6. in case of issues, check the log:
```
journalctl --user -u mon_script.service
journalctl --user -xe
```






