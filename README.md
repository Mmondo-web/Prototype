# MMONDO Web Application

**MMONDO** is a platform that allows users to browse tours and view detailed information about each experience. Administrators can easily manage tour listings, ensuring up-to-date and accurate offerings. Our website connects East African tour operators with customers in the European market, helping bridge the gap and open new opportunities for them in the international tourism sector.

---

## 🛠 Technologies Used

- **Backend:** Python, FastAPI
- **Frontend:** HTML, CSS, JavaScript, Bootstrap, Tailwind
- **Database:** MySQL (SQLite for development/testing)
- **Containerization:** Docker, Docker Compose
- **CI/CD intergration:** Github Actions for pytesting and deployment


---

## 📁 Project Structure

```
├── app/                    # Main application folder
│   ├── templates/          # HTML templates
│   ├── static/             # Static files (CSS, JS, images)
│   ├── main.py             # FastAPI application entry point
│   ├── models.py           # Database models
│   ├── routes.py           # Application routes
│   └── ...                 # Other Python modules
├── static/                 # Public static assets
├── test.db                 # SQLite database file
├── .gitignore
├── Dockerfile              # Docker configuration
├── docker-compose.yaml     # Docker Compose config
├── requirements.txt        # Python dependencies
├── start.sh                # Startup script
├── Tests/                  # pytest tests
└── .github/workflows/      # GitHub Actions workflows
```

---

## 👨‍💻 Developers

- **Backend:** Rhyan Lubega
- **Frontend:** Boaz Onyango
- **Database & Product Manager:** Oscar Kyamuwendo
- **Business Role:** George Mutale

---

## 🌟 Special Features

- Secure payment using bank cards and PayPal
- Terminal system for secure admin creation
- Quick tour booking system
- Tokenized emails for password recovery & support
- Email system for tour updates and receiving receipts
- Newsletter integration
- Live AI-powered chatbot

---

## ⚙️ Setup and Running the Project

### Prerequisites

- Python 3.8+
- pip
- Docker (optional)
- Docker Compose (optional)

---
## 🔐 Admin & Super Admin Management

MMONDO uses a role-based access system to manage platform permissions.

### User Roles

- Customer: Default role on public registration

- Admin: Manages tours, bookings, newsletters, and platform content

- Super Admin: Creates and manages admin accounts

### Admin Creation

Admins can only be created by a Super Admin via:
####  /admin/register

This endpoint is protected and cannot be accessed by normal users.

### Super Admin Creation

A Super Admin can be created via:
####  /superadmin/create

- This route is strictly restricted and intended for:

- Initial system setup

- Terminal-based execution

Secure environment-based access
## 🚀 Running the App

### ✅ Using Uvicorn (Local)

1. **Start the app:**

```bash
python -m venv venv && source venv/bin/activate && pip install -r requirements.txt && python -m uvicorn app.main:app --reload --host localhost
```

2. **Superdmin Sign-In:**

Use the following credentials:

- **Email:** `george.mutale345@stud.th-deg.de`
- **Password:** `Administer01@#`


3. **Admin Sign-In:**

Use the following credentials:

- **Email:** `mutalegeorge367@gmail.com`
- **Password:** `Operator02@#`

Alternatively, create a new admin via terminal:


4. **Customer Sign-In:**

Use the following credentials:

- **Email:** `george.mutale@stud.th-deg.de`
- **Password:** `Tourist01@#`

---

### 🐳 Using Docker

> Docker creates a separate database. You must manually create admin and customer accounts inside the container.

1. **Build and run the services:**

```bash
chmod +x start.sh
./start.sh
```

2. **Customer Sign-Up/Login:**  
   Use the app interface to register and log in.

3. **Stop the services:**

```bash
Ctrl + C
# Or stop the container manually
docker ps
docker stop <container_id>
```

---

## 🤝 Contributing

We welcome contributions!

### Steps to Contribute

1. Fork the repository
2. Create a new feature branch: `git checkout -b feature-name`
3. Commit your changes: `git commit -m "Description of changes"`
4. Push to your fork: `git push origin feature-name`
5. Open a pull request

Please follow standard coding practices and ensure your code passes tests.

---

## 📄 License

Specify the license for the project here. (e.g., MIT, Apache 2.0)
