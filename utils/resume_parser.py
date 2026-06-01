# ─────────────────────────────────────────────
#  utils/resume_parser.py
#  Extracts text, skills, and projects from a
#  candidate's resume PDF using pdfplumber.
# ─────────────────────────────────────────────

import io
import re
import pdfplumber


# ── Master tech skill vocabulary ─────────────
# Rule-based matching: any of these tokens found
# in the resume text (case-insensitive) are reported.
KNOWN_SKILLS: list[str] = [
    # Languages
    "Python", "Java", "JavaScript", "TypeScript", "C", "C++", "C#", "Go",
    "Rust", "Kotlin", "Swift", "Ruby", "PHP", "Scala", "R", "MATLAB",
    "Bash", "Shell", "Perl", "Dart",
    # Web / Frontend
    "HTML", "CSS", "React", "Angular", "Vue", "Next.js", "Nuxt.js",
    "Svelte", "jQuery", "Bootstrap", "Tailwind", "SASS", "LESS",
    "Webpack", "Vite", "Redux", "GraphQL",
    # Backend / Frameworks
    "Django", "Flask", "FastAPI", "Spring", "Spring Boot", "Express",
    "Node.js", "NestJS", "Laravel", "Rails", "ASP.NET", "Gin", "Fiber",
    # Databases
    "SQL", "MySQL", "PostgreSQL", "SQLite", "Oracle", "MongoDB",
    "Redis", "Cassandra", "DynamoDB", "Elasticsearch", "Firebase",
    "Neo4j", "CouchDB", "MariaDB",
    # Cloud / DevOps
    "AWS", "Azure", "GCP", "Google Cloud", "Docker", "Kubernetes",
    "Terraform", "Ansible", "Jenkins", "GitHub Actions", "CircleCI",
    "Travis CI", "Helm", "Prometheus", "Grafana", "Nginx", "Apache",
    # ML / AI / Data
    "Machine Learning", "Deep Learning", "NLP", "Computer Vision",
    "TensorFlow", "PyTorch", "Keras", "Scikit-learn", "Pandas",
    "NumPy", "Matplotlib", "Seaborn", "OpenCV", "Hugging Face",
    "LangChain", "Gemini", "OpenAI", "Spark", "Hadoop", "Kafka",
    "Airflow", "dbt", "Power BI", "Tableau", "Looker",
    # Mobile
    "Android", "iOS", "React Native", "Flutter", "Xamarin",
    # Tools / Practices
    "Git", "GitHub", "GitLab", "Bitbucket", "Jira", "Confluence",
    "Postman", "REST", "REST API", "gRPC", "WebSocket", "OAuth",
    "JWT", "CI/CD", "Agile", "Scrum", "Linux", "Unix",
    # Testing
    "Jest", "Pytest", "Selenium", "Cypress", "JUnit", "Mocha",
    "Playwright", "Testing",
    # Misc
    "Microservices", "System Design", "Data Structures", "Algorithms",
    "OOP", "Functional Programming", "Design Patterns", "SOLID",
    #Extras
    "DSA", "LLM", "RAG", "Vector Database", "ChromaDB", "FAISS", "PySpark",
]


def extract_text_from_pdf(uploaded_file) -> str:
    """
    Extract all text from an uploaded PDF file object.

    Args:
        uploaded_file: A file-like object (e.g. from st.file_uploader).

    Returns:
        A single string containing all extracted text, pages joined by newlines.
        Returns empty string if extraction fails.
    """
    text_chunks: list[str] = []
    try:
        raw_bytes = uploaded_file.read()
        with pdfplumber.open(io.BytesIO(raw_bytes)) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text and page_text.strip():
                    text_chunks.append(page_text.strip())
    except Exception as e:
        print(f"[resume_parser] PDF extraction error: {e}")
        return ""
    return "\n\n".join(text_chunks)


def extract_skills_from_text(text: str) -> list[str]:
    """
    Match known tech skills against resume text using case-insensitive
    whole-word / token matching.

    Args:
        text: Raw resume text string.

    Returns:
        Deduplicated, sorted list of matched skill strings.
    """
    if not text:
        return []

    found: set[str] = set()
    text_lower = text.lower()

    for skill in KNOWN_SKILLS:
        # Build a pattern that matches the skill as a standalone token.
        # Escape special regex chars (e.g. "C++", "Next.js").
        escaped = re.escape(skill.lower())
        pattern = rf"(?<![a-z0-9]){escaped}(?![a-z0-9])"
        if re.search(pattern, text_lower):
            found.add(skill)

    return sorted(found)


def extract_projects_from_text(text: str) -> list[str]:
    """
    Heuristically extract project names / descriptions from resume text.

    Strategy:
      1. Look for a "Projects" / "Personal Projects" section header.
      2. Grab non-empty lines until the next major section header.
      3. Return up to 5 project snippets (first 120 chars each).

    Args:
        text: Raw resume text string.

    Returns:
        List of project description snippets (may be empty).
    """
    if not text:
        return []

    projects: list[str] = []

    # Common section headers that might follow the projects section
    next_section_pattern = re.compile(
        r"^\s*(education|experience|work experience|skills|certifications|"
        r"achievements|awards|publications|references|summary|objective)\s*$",
        re.IGNORECASE,
    )

    lines = text.splitlines()
    in_projects_section = False

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        # Detect projects section start
        if re.match(
            r"^(projects?|personal projects?|academic projects?|key projects?)\s*$",
            stripped,
            re.IGNORECASE,
        ):
            in_projects_section = True
            continue

        # Detect next section → stop collecting
        if in_projects_section and next_section_pattern.match(stripped):
            break

        if in_projects_section and len(stripped) > 10:
            snippet = stripped[:120] + ("…" if len(stripped) > 120 else "")
            projects.append(snippet)
            if len(projects) >= 5:
                break

    return projects


def parse_resume(uploaded_file) -> dict:
    """
    Full pipeline: extract text → extract skills → extract projects.

    Args:
        uploaded_file: File-like object from Streamlit uploader.

    Returns:
        {
            "text":     str,        # full raw resume text
            "skills":   list[str],  # matched tech skills
            "projects": list[str],  # project snippets (may be [])
        }
    """
    text = extract_text_from_pdf(uploaded_file)
    skills = extract_skills_from_text(text)
    projects = extract_projects_from_text(text)

    return {
        "text":     text,
        "skills":   skills,
        "projects": projects,
    }
