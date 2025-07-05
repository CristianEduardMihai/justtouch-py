# JustTouch - NFC File Sharing App

JustTouch is a mobile application built with Python and Kivy that allows users to share files between devices using NFC (Near Field Communication) technology and peer-to-peer (P2P) transfer protocols.

## Features

- **NFC-based Discovery**: Simply touch two phones together to initiate file sharing
- **P2P File Transfer**: Direct device-to-device file transfer using WebRTC or TCP
- ~~**Cross-Platform**: Works on both Android and iOS devices~~
- **Secure Transfer**: Files are transferred directly between devices without cloud storage

## How It Works

1. **Sender**: Select files to share and tap "Send Files"
2. **NFC Touch**: Touch the two devices together to exchange session information
3. **P2P Transfer**: Files are transferred directly using local network connection