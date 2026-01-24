# Pin People - Tech Playground Challenge

A robust, data-driven solution for Employee Experience analytics.
Built with Python 3.11, Flask, PostgreSQL, and AI-powered Sentiment Analysis.

## 🚀 Getting Started

### Prerequisites
* Docker & Docker Compose
* Git

### 🛠 Database Setup & Ingestion (Task 1)

This project uses **PostgreSQL 17** containerized. The schema is designed with 3NF normalization and includes indexing for performance optimization.

1. **Clone and Configure**
   ```bash
   git clone <repo_url>
   cd tech-playground-challenge
   cp .env.example .env
   

docker-compose exec web flask db-init
docker-compose exec web flask trigger-ingestion