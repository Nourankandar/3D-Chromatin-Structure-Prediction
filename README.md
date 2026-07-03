# 🧬 3D Chromatin Structure Prediction (ChromoGen-based)

# 📌 Overview
This project aims to predict the 3D conformation of chromatin directly from DNA sequences and DNase-seq data. By leveraging a two-stage generative AI model (Transformer-based Encoder + Diffusion-based Decoder), we provide a cost-effective and rapid alternative to traditional Hi-C lab experiments.

Research Context: Developed for the "BioTherapeutics Research Center"  as a  project at the Faculty of Information Technology Engineering.

# 🚀 Key FeaturesSequence-to-Structure: 
1 - Predicts 3D coordinates (x, y, z) from genomic sequences.
2 - Virtual Hi-C Generation: Predicts high-resolution contact maps as an 3
3 - intermediate step.Disease Analysis: Specialized modules to study structural changes in specific genetic disorders.
4 - Web Dashboard: A Django-powered interface for medical researchers to visualize and manage predictions.

# 🏗️ Project Architecture
The project is divided into two main components:

AI Engine: Built with PyTorch, utilizing EPCOT for sequence embedding and a Diffusion Model for distance map generation.

Django Backend: Manages patient data, handles asynchronous prediction tasks (via Celery/Redis), and serves the 3D visualization.


# 🛠️ Tech Stack
AI: PyTorch, Transformers, Diffusers, NumPy, SciPy.

Backend: Django, Django REST Framework.

Asynchronous Tasks: Celery, Redis.

Data Handling: h5py, pyBigWig, Biopython.

Visualization: 3Dmol.js or NGLview (Three.js).


📖 Getting Started


# Clone the repo
git clone https://github.com/YourUsername/Chromatin3D_Project.git


2. Create a Virtual Environment
It is recommended to use a virtual environment to manage dependencies:

# On Windows
python -m venv venv
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

. Database Setup (Django)
Apply migrations to create the database schema:

cd backend
python manage.py makemigrations
python manage.py migrate


# Run the Development Server
python manage.py runserver
