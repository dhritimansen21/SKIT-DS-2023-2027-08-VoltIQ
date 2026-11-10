# VoltIQ ⚡

**Real-Time Electricity Usage Forecasting & Theft Detection System**

VoltIQ is a hardware-integrated system that combines low-cost IoT sensing with machine learning to forecast electricity consumption and detect theft or anomalies in real time. It pairs an ESP32-based sensing unit with an ML-powered dashboard, and can automatically cut off load when theft is confirmed.

---

## 📌 Overview

Traditional electricity meters lack real-time anomaly detection and give no predictive insight into usage. VoltIQ addresses this by combining low-cost ESP32-based hardware sensing with ML models for consumption forecasting and theft/anomaly classification — enabling real-time detection of irregularities through an interactive dashboard, with an automated relay-based cutoff for confirmed theft events.

**SDG Alignment:** SDG 7 — Affordable and Clean Energy

---

## 🎯 Objectives

1. Design and build a low-cost ESP32-based hardware unit for real-time voltage and current sensing.
2. Develop ML models for accurate short-term electricity usage forecasting.
3. Detect anomalies and electricity theft using anomaly detection and classification models.
4. Implement an automated load-cutoff mechanism for confirmed theft events.
5. Build an interactive dashboard visualizing usage trends, forecasts, and alerts in real time.

---

## 🛠️ Tech Stack

### Hardware
| Component | Purpose |
|---|---|
| ESP32 Microcontroller | Core processing unit for sensor data acquisition |
| ZMPT101B Voltage Sensor | Real-time voltage measurement |
| SCT-013 Current Clamp | Non-invasive current measurement |
| DS3231 RTC Module | Real-time timestamping of readings |
| microSD Module | Local data buffering during connectivity gaps |
| I2C LCD Display | On-device live status display |
| Relay / Load-Cutoff Module | Automated load disconnection on theft detection |

### Software
| Tool | Purpose |
|---|---|
| Python (Streamlit) | Interactive ML dashboard |
| Prophet / XGBoost | Usage forecasting |
| Isolation Forest | Anomaly detection |
| XGBoost / Random Forest | Theft classification |
| SMOTE | Class balancing for imbalanced theft data |

---

## ✨ Features

- Real-time voltage & current sensing with accurate timestamping
- Local data buffering to microSD for connectivity resilience
- ML-based short-term electricity usage forecasting
- Anomaly detection for irregular usage patterns
- Theft classification with automated relay-based load cutoff
- On-device LCD status display
- Interactive Streamlit dashboard for live monitoring, forecasts, and alerts

---

## 🗺️ Project Roadmap

The project follows an 8-sprint structure across a 12-month timeline (Aug 2026 – Mar 2027), with core development completed by December and Jan–Mar reserved for testing, deployment, and documentation.

| Sprint | Focus | Timeline |
|---|---|---|
| 1 | Setup & Environment Configuration | Aug 1 – Aug 20 |
| 2 | Hardware Assembly & Sensor Integration | Aug 1 – Sep 15 |
| 3 | Data Pipeline & Storage | Aug 1 – Oct 10 |
| 4 | ML Forecasting Model | Aug 1 – Oct 15 |
| 5 | Theft Classification, Testing & Deployment | Oct 16 – Mar 31 |
| 6 | Frontend/Dashboard Design, Testing & Deployment | Aug 21 – Mar 31 |
| 7 | Dashboard-Backend Integration, Testing & Deployment | Sep 16 – Mar 31 |
| 8 | System Integration, Testing & Deployment | Oct 11 – Mar 31 |

**Jan–Mar** covers system testing & debugging, deployment & field trial, and feedback incorporation with final documentation.

---

## 🏗️ System Architecture

```
[ESP32 + Sensors] → [microSD Buffer / RTC Timestamp] → [Data Export Pipeline]
                                                              │
                                                              ▼
                                          [ML Models: Forecasting | Anomaly | Theft Classification]
                                                              │
                                                              ▼
                                    [Relay Cutoff] ←──── [Streamlit Dashboard: Live view, Forecasts, Alerts]
```

---

## 📁 Repository Structure

```
voltiq/
├── hardware/           # ESP32 firmware, sensor wiring & calibration scripts
├── data_pipeline/      # Data schema, buffering, and export scripts
├── models/             # Forecasting, anomaly detection & theft classification models
├── dashboard/          # Streamlit dashboard application
├── docs/               # Project documentation, diagrams, and reports
└── README.md
```

*(Adjust this to match your actual folder layout as the repo grows.)*

---

## 🚀 Getting Started

### Prerequisites
- Python 3.9+
- ESP32 development environment (Arduino IDE / PlatformIO)
- Required Python packages: `streamlit`, `xgboost`, `prophet`, `scikit-learn`, `imbalanced-learn` (SMOTE), `pandas`, `numpy`

### Installation
```bash
git clone https://github.com/dhritimansen21/voltiq.git
cd voltiq
pip install -r requirements.txt
```

### Running the Dashboard
```bash
streamlit run dashboard/app.py
```

---

## 👥 Team

| Name | Roll No. | Role |
|---|---|---|
| Devanshi Mann | 23ESKCX028 | Team Lead |
| Dhritiman Sen | 23ESKCX029 | Member — ML Forecasting & Theft Classification |
| Divyanshu Sharma | 23ESKCX031 | Member — Hardware & Dashboard-Backend Integration |
| Charchit Sharma | 23ESKCX022 | Member — Data Pipeline & System Integration |

**Mentor:** Harpreet Singh Gill, Associate Professor

---

## 🏫 Academic Context

Final-year B.Tech (Data Science) project, Swami Keshvanand Institute of Technology, Management & Gramothan (SKIT), Jaipur — Department of Computer Science & Engineering, Session 2026–27.

---


