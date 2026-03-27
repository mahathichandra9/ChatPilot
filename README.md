# 🚗 ChatPilot

### Conversational Autonomous Driving Agent

---

## 📌 Overview

ChatPilot is an AI-powered autonomous driving system that combines **vision, language, and planning** to enable **human-like interaction with vehicles**.

Unlike traditional rule-based systems, ChatPilot allows users to **control navigation using natural voice commands**, making autonomous systems more intuitive, adaptive, and user-friendly.

---

## 🎯 Problem Statement

* Traditional autonomous systems are **rigid and rule-based**
* Limited ability to handle **dynamic, real-world scenarios**
* Lack of **context-aware conversational interaction**
* Existing AI systems struggle with **long-horizon decision making**

---

## 💡 Solution

ChatPilot introduces a **multi-modal AI agent** that integrates:

* 🎤 Voice-based interaction
* 👁️ Visual perception
* 🧠 Language understanding
* 🛣️ Intelligent planning & control

This enables **context-aware navigation with real-time feedback and adaptability**.

---

## 🧠 System Architecture

<p align="center">
  <img src="images/chatpilot arch.jpg" alt="System Architecture" width="700">
</p>

### Core Autonomous Agent (Python Stack)

* Simulation Environment: CARLA
* Perception Module: OpenCV
* Video-Language Model: PyTorch / TensorFlow
* Reasoning Engine: Ray RLlib
* Motion Planner
* Logging System: InfluxDB

### Communication Layer

* MQTT protocol for real-time messaging
* JSON-based structured data exchange

### User Interface

* Flutter mobile application
* Voice input and feedback display

---

## 🔄 Workflow

<p align="center">
  <img src="images/chatpilot workflow.jpg" alt="Workflow Diagram" width="700">
</p>

1. User provides a voice command
2. Speech is converted to text
3. Intent and navigation data are extracted
4. Data is transmitted via MQTT
5. AI agent processes input using perception + reasoning
6. Route planning is performed
7. Obstacle detection ensures safe navigation
8. Motion commands are executed
9. Feedback is sent back to the user

---

## 🛠️ Tech Stack

### Languages

* Python
* Dart (Flutter)

### Libraries & Frameworks

* OpenCV
* PyTorch / TensorFlow
* paho-mqtt
* DroneKit
* MAVProxy
* RPLidar

### Tools & Platforms

* CARLA Simulator
* Jetson Xavier (Edge Device)
* VS Code

---

## 📐 Algorithms & Concepts

* **A*** Algorithm → Efficient path planning
* **Haversine Formula** → Distance calculation
* **Reinforcement Learning** → Intelligent decision making
* **Computer Vision** → Scene understanding
* **Natural Language Processing** → Command interpretation

---

## 🚀 Key Features

* Natural voice-controlled navigation
* Real-time obstacle detection and avoidance
* Intelligent route planning
* Continuous feedback system
* Multi-modal AI integration (vision + language)
* Scalable architecture for simulation and real-world deployment

---

## 🌍 Applications

* Autonomous vehicles
* Smart delivery robots
* Warehouse automation
* Assistive mobility systems

---

## 🔮 Future Scope

* Context-aware conversational memory
* Enhanced perception with advanced models
* Full LLM-based reasoning integration
* Improved real-world deployment scalability

---

## ⭐ Conclusion

ChatPilot showcases how combining **AI, robotics, and conversational intelligence** can create next-generation systems that are not only autonomous but also **interactive, adaptive, and user-centric**.

---
