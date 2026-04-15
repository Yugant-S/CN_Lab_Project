# Real-time Multi Client TCP Chat System

## Overview
This project implements a Real-time Multi Client TCP Chat System using sockets in Python. It allows multiple clients to connect to a server and engage in real-time text-based communication.

## Features
- **Multi-client support**: Connect multiple clients simultaneously.
- **Real-time communication**: Messages are sent and received in real time.
- **User-friendly interface**: Simple command-line interface for easy interaction.
- **Secure connections**: Supports encrypted communication using SSL (optional).

## Technologies Used
- **Python 3.x**: Primary programming language for development.
- **Socket Programming**: For network communication.
- **Threading**: To handle multiple clients efficiently.

## Getting Started
Follow these instructions to set up the project locally.

### Prerequisites
- Python 3.x installed
- Basic knowledge of Python programming

### Installation
1. Clone the repository:
   ```bash
   git clone https://github.com/Yugant-S/CN_Lab_Project.git
   ```
2. Navigate to the project directory:
   ```bash
   cd CN_Lab_Project
   ```
3. Install any required packages (if any):
   ```bash
   pip install -r requirements.txt
   ```

### Usage
1. Open terminal.
2. Do ipconfig and find ipv4 address.
3. Replace DEFAULT_SERVER_IP in client.py
4. Start the server:
   ```bash
   python server.py
   ```
5. In separate terminals, start multiple clients:
   ```bash
   python client.py
   ```
6. Follow the on-screen instructions to send messages.

### Screenshots
- Server Running
<img width="833" height="330" alt="image" src="https://github.com/user-attachments/assets/601fac51-6160-4435-bdfb-77938ea5e11f" />

- Room Selection
<img width="717" height="703" alt="image" src="https://github.com/user-attachments/assets/10c5c5a5-bd1c-4c85-8629-92ca1f25f571" />

- Private Room - Password Protected
<img width="716" height="694" alt="image" src="https://github.com/user-attachments/assets/30cd9039-62e0-45e0-ba79-999836f20c10" />

- Group Messaging
<img width="940" height="697" alt="image" src="https://github.com/user-attachments/assets/3e7fa4a5-d0b9-42b3-bb3f-62bba1518e1f" />

- Upload
<img width="940" height="695" alt="image" src="https://github.com/user-attachments/assets/cd8ef3aa-f5f5-4a32-ac67-90b879ca99d9" />

- Download
<img width="940" height="697" alt="image" src="https://github.com/user-attachments/assets/149696f0-17f8-4b7b-83ab-80dd57647460" />


## Contributing
Contributions are welcome! Feel free to submit a pull request or report issues.

## Author
- Sujal Sande (2026)
- Vivek Gupta (2026)
- Yugant Sonwani (2026)
  
## Acknowledgments
- Thanks to the open-source community for their resources and support.
