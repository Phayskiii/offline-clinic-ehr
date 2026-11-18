# Offline Clinic Patient Health Record System

**Cross-Platform Local Electronic Health Record (EHR) Application**

A lightweight, self-contained medical record management system built with Python, Flask, and SQLite. Designed for clinics and mobile setups lacking reliable internet connectivity, the application runs locally on both desktop computers and Android tablets.

## Key Features

- **Alphabetized Patient Dashboard:** Displays registered patients in alphabetical order with real-time search by name for fast record retrieval.
- **Structured Patient Profiles:** Supports detailed patient demographics (last, first, middle, and suffix fields, age, sex, address) with inline profile editing.
- **Date-Organized Clinical Visits:** Tracks chronological consultation entries including clinical history, physical examination notes, and prescriptions.
- **Separated Medical Image Management:** Separates patient profile photos from laboratory result scans, supporting both gallery uploads and direct camera capture as well as quick uploads for legacy records.
- **Offline SQLite Persistence:** Stores all records in a single local SQLite database file for zero-configuration deployment and straightforward local backups.
- **Desktop & Android Tablet Support:** Runs natively on Windows/Linux PCs and on Android tablets via a local Pydroid 3 Python server.

## Tech Stack

- **Backend:** Python, Flask
- **Database:** SQLite
- **Frontend:** HTML, CSS
- **Mobile Runtime:** Pydroid 3 (Android)

## Getting Started

1. Clone this repository and enter the project directory:
   ```bash
   git clone [https://github.com/YOUR_USERNAME/offline-clinic-ehr.git](https://github.com/YOUR_USERNAME/offline-clinic-ehr.git)

   cd offline-clinic-ehr
2. Start the local Flask server:
   ```bash
   python app.py

3. Open a browser on your PC or Android tablet and navigate to http://127.0.0.1:5000.

## Developer

**Devrick Fosh V. Atok** — Full-Stack Developer
