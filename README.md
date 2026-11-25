# Raspodoo: The Odoo-to-Office IoT Bridge

**Raspodoo** is a high-performance IoT bridge that connects your Odoo ERP with the physical world. When a landmark event occurs in Odoo—like a high-value Sales Order confirmation or a successful payment—Raspodoo triggers tactile and audible feedback in your office environment, celebrating every win in real-time.

---

## Project Overview

Raspodoo transforms digital transactions into physical celebrations. By listening to Odoo Webhooks, a Raspberry Pi interprets business data and drives hardware components:
- **Visual/Mechanical:** A servo motor strikes a physical service bell.
- **Audio:** A piezo buzzer plays 8-bit melodic sound effects.
- **Meme hardware:** A "This Is Fine" dog toy triggered by a short GPIO pulse.

---

## Hardware Setup & Wiring

The project utilizes the Raspberry Pi GPIO headers. We use the **pigpio** library for precise, hardware-timed PWM (Pulse Width Modulation) to ensure smooth servo movement and clear audio tones.

### Wiring Diagram (BCM)

| Component | Wire Color | Raspberry Pi Pin | GPIO Number | Function |
| :--- | :--- | :--- | :--- | :--- |
| **Servo Motor** | Red | Pin 2 or 4 | - | 5V Power |
| | Brown / Black | Pin 6 or 9 | - | Ground (GND) |
| | Orange / Yellow / White | Pin 12 | **GPIO 18** | PWM Signal |
| **Piezo Buzzer** | Red (Long Leg) | Pin 33 | **GPIO 13** | PWM Signal (+) |
| | Black (Short Leg)| Pin 34 | - | Ground (-) |
| **This Is Fine** | Purple (signal) | Pin 16 | **GPIO 23** | ~0.4s HIGH pulse |
| | Blue (GND) | Pin 14 | - | Ground (-) |

For a detailed reference on Raspberry Pi pins, see the [Seeed Studio GPIO Pinout Guide](https://www.seeedstudio.com/blog/2020/02/19/how-to-use-raspberry-pi-gpio-pins-python-tutorial/).

---

## Software Architecture

### A. System Dependencies
The Raspberry Pi runs **Raspberry Pi OS**. Key technical requirements include:
*   **Python 3 & Flask:** Handles the web server logic and webhook routing.
*   **Pigpio Daemon:** A C-library service for interfacing with GPIO. Must be active (`sudo pigpiod`).
*   **Git:** Enables version control and the automated deployment workflow.

### B. Python Application (`webhook_kuuntelija.py`)
A lightweight Flask server listening on **port 5000**. It features several key endpoints:

| Endpoint | Trigger Event | Logic / Action |
| :--- | :--- | :--- |
| `/servo` | Sales Order Confirmed | Parses `amount_untaxed`. <br>• < 20k€: 1 Ring <br>• ≥ 20k€: 1 Ring per 10k€. Optional `?style=hard\|soft\|double\|linger`. Each hit: wind-up mid → strike 70° → hold mid (PWM on). |
| `/servo/home` | Maintenance | Hold mid (`REST_DEG`) under power. `?relax=1` cuts PWM (drops to full hang). |
| `/servo/goto?deg=N` | Calibration | Absolute angle 0–90°. Default relax after hold; `?relax=0` holds while you match the hang photo. |
| `/servo/strike` | Manual test | `?hits=N&style=hard` — strike without Odoo amount math. |
| `/piezo` | Invoices / Payments | Plays sounds based on `?sound=` parameter: <br>`coin`, `success`, `r2d2`, `alert`, `startup`, `birthday`, `startreck`, `imperial`, `jingle`, `maamme`, `finlandia`. |
| `/display`| Generic Events | Logs messages to the terminal (OLED support coming soon). |
| `/reset` | Maintenance | Alias of `/servo/home` (hang + PWM off). |
| `/thisisfine` | Chaos / memes | Pulses GPIO 23 HIGH for ~0.4s to trigger the This Is Fine dog. |

### C. Ngrok Connectivity
To expose the local Raspberry Pi server to the internet for Odoo webhooks:
*   **Static Domain:** `<your-ngrok-url>.ngrok-free.dev`
*   **Tunneling:** Ngrok forwards public HTTPS traffic to `localhost:5000`.

---

## Continuous Deployment (Auto-Update)

Raspodoo features a git-based CD workflow. You don't need to manually update code on the Pi.

1.  **Edit** code on your local development machine.
2.  **Push** changes to the GitHub repository (`git push`).
3.  **Restart** the service on the Pi (`sudo systemctl restart webhook_kuuntelija`).

The Systemd service (`/etc/systemd/system/webhook_kuuntelija.service`) is configured to pull the latest changes before starting:
```ini
ExecStartPre=/usr/bin/git fetch --all
ExecStartPre=/usr/bin/git reset --hard origin/main
```

---

## Odoo Integration Strategy

Since Odoo's webhook payload is often rigid, we use **URL Parameters** to pass specific instructions to the Pi.

*   **Scenario (Invoice Paid):** Trigger an Automation Rule when Payment Status is "Paid".
    *   **URL:** `https://your-ngrok-url/piezo?sound=coin`
*   **Scenario (New Sale):** Trigger on Sales Order confirmation.
    *   **URL:** `https://your-ngrok-url/servo`
    *   *The Pi will automatically parse the Odoo JSON body to determine the sale value.*
*   **Scenario (This Is Fine):** Trigger when things are on fire (metaphorically).
    *   **URL:** `https://your-ngrok-url/thisisfine`

---

## Maintenance Cheatsheet

### Service Management
```bash
# Restart and trigger auto-update
sudo systemctl restart webhook_kuuntelija.service

# Check status and logs
systemctl status webhook_kuuntelija.service
journalctl -u webhook_kuuntelija.service -f
```

### Manual Hardware Testing (via pigs)
```bash
# Move Servo to ISKU (Down)
pigs hp 18 50 100000

# Move Servo to LEPO (Up)
pigs hp 18 50 50000

# Play a short beep on Piezo
pigs hp 13 1000 500000 && sleep 0.2 && pigs hp 13 0 0

# Trigger This Is Fine dog (GPIO 23 pulse)
pigs w 23 1 && sleep 0.4 && pigs w 23 0
```

### Servo strike = two-phase

Soft `0°` is idle mid (~45° physical, PWM held). Soft `70°` hits the gong. Each hard hit: mid → 70° → mid (stays; no 160–170° drop). Full gravity hang only if you explicitly `?relax=1` / PWM off.

### Webhook smoke tests
```bash
# This Is Fine
curl -X POST "https://your-ngrok-url/thisisfine" \
  -H "Content-Type: application/json" -d '{}'

# Servo: park to hang + PWM off
curl -X POST "https://your-ngrok-url/servo/home" \
  -H "Content-Type: application/json" -d '{}'

# Calibrate: 0 ≈ hang (angled), ~45 ≈ on gong, 90 ≈ strike
curl -X POST "https://your-ngrok-url/servo/goto?deg=0&relax=0" \
  -H "Content-Type: application/json" -d '{}'
curl -X POST "https://your-ngrok-url/servo/goto?deg=45&relax=0" \
  -H "Content-Type: application/json" -d '{}'
curl -X POST "https://your-ngrok-url/servo/goto?deg=90&relax=0" \
  -H "Content-Type: application/json" -d '{}'

# Servo: soft strike (ends in hang + relax)
curl -X POST "https://your-ngrok-url/servo/strike?hits=1&style=soft" \
  -H "Content-Type: application/json" -d '{}'

# Servo: Odoo-style with linger
curl -X POST "https://your-ngrok-url/servo?style=linger" \
  -H "Content-Type: application/json" -d '{"amount_untaxed": 5000}'
```

