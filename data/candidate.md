# ALARA YILMAZ
**Location:** Istanbul, Turkey | **Email:** alara.yilmaz.aieng@email.com | **LinkedIn:** linkedin.com/in/alarayilmaz-ai | **GitHub:** github.com/alarayilmaz-dev

## SUMMARY
Software Engineer with 4 years of experience specializing in backend infrastructure and Applied AI. For the past 1.5 years, exclusively focused on building, evaluating, and deploying LLM-based autonomous agents in production environments. Proven track record of leveraging function calling, custom orchestration loops, and RAG architectures to automate complex business workflows. Deeply passionate about moving AI from chat interfaces to execution engines.

## EXPERIENCE

**Senior AI Engineer | LojistikZeka A.Ş.** *Istanbul, Turkey (Hybrid)* | *Oct 2022 – Present*
*   Architected and deployed an autonomous supply chain agent that dynamically reroutes shipments based on severe weather alerts and carrier API data, saving the company ₺15M in delay penalties annually.
*   Migrated a fragile LangChain-based pipeline to a custom, deterministic orchestration engine in Python, improving agent task completion rate from 68% to 94% while reducing latency by 40%.
*   Built a robust tool-calling infrastructure using heavily typed Pydantic models to guarantee valid JSON outputs from OpenAI (GPT-4) and Anthropic (Claude 3) models, virtually eliminating parsing errors in production.
*   Implemented a comprehensive LLM observability stack using LangSmith and custom Grafana dashboards to trace multi-step reasoning chains and monitor token usage and API costs.
*   Designed an automated evaluation pipeline (using a smaller model as a judge) to test system prompt modifications against a golden dataset of 5,000 historical user interactions prior to deployment.

**Backend Software Engineer | FinansAnaliz Teknoloji** *Istanbul, Turkey* | *July 2020 – Oct 2022*
*   Developed highly concurrent microservices in Python (FastAPI) and Go to process real-time financial data streams for institutional client dashboards.
*   Integrated enterprise vector databases (Pinecone) with legacy PostgreSQL stores to enable hybrid semantic search capabilities across millions of financial regulatory documents (SPK/BDDK regulations).
*   Reduced average database query latency by 35% through query optimization and implementing a Redis caching layer for frequently accessed materialized views.
*   Maintained infrastructure as code using Terraform and managed CI/CD pipelines via GitHub Actions deploying to AWS EKS.

## PROJECTS & OPEN SOURCE

**Auto-Dev-Reviewer (Open Source)**
*   Built an autonomous agent using AutoGen that acts as a secondary code reviewer on GitHub PRs. The agent pulls context, runs basic static analysis (via tools), and leaves line-by-line comments referencing project-specific style guides stored in a Qdrant vector database.
*   Gained over 800 stars on GitHub and adopted by 15+ tech teams in Turkey.

**Mistral Hackathon Winner (Best Agentic Application)**
*   Led a team of 3 from Bogazici University to build "LegalEagle," a multi-agent system that autonomously negotiated SaaS contracts by drafting redlines and summarizing risks against a user's acceptable risk profile, utilizing Mistral Large and open-weight embedding models.

## SKILLS
*   **Programming Languages:** Python (Expert), TypeScript / Node.js (Proficient), Go (Familiar), SQL
*   **Applied AI & Agents:** OpenAI API, Anthropic API, Mistral API, LangChain, LlamaIndex, AutoGen, CrewAI, Function Calling / Structured Output, Advanced RAG processing
*   **Backend & Infra:** FastAPI, Docker, Kubernetes, AWS (Lambda, ECS, S3), Redis, PostgreSQL
*   **Vector DBs & Tooling:** Pinecone, Qdrant, Weaviate, LangSmith, DeepEval, Git, Pydantic

## EDUCATION
**Bachelor of Science in Computer Engineering**
*Bogazici University, Istanbul, Turkey* | *Graduated: June 2020*
