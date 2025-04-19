# AI Desk Research Assistant

## Overview

This project is a web application that allows users to perform desk research on a given topic. It uses Gemini API to generate answers to questions based on a set of documents.

Workflow:
1. User uploads documents (PDF, DOCX, PPTX, TXT)
2. User adds a research query.
3. User starts the research.
4. The app processes the documents and generates a research report.
5. User can download the research report.

## Installation


1. Create a virtual environment:

```bash
python -m venv venv
```

2. Activate the virtual environment:

```bash
source venv/bin/activate
```

3. Install dependencies:

```bash
pip install -r requirements.txt
```

4. Create a `.env` file and add your Gemini API key:

```bash
GEMINI_API_KEY=your_api_key
```

1. Migrate the database (SQLite is used as a default database):

```bash
python manage.py migrate
```

6. Run the development server:

```bash
python manage.py runserver
```
