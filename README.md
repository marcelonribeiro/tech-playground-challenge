# 📊 HR Analytics Platform

![Python Version](https://img.shields.io/badge/python-3.11-blue)
![Framework](https://img.shields.io/badge/flask-3.1.2-green)
![Coverage](https://img.shields.io/badge/coverage-85%25-brightgreen)
![Build Status](https://img.shields.io/badge/build-passing-success)
![Docker](https://img.shields.io/badge/docker-compose-orange)

Uma plataforma completa de **People Analytics** focada em transformar dados brutos de pesquisas de clima em inteligência acionável. 

O sistema vai além da visualização básica, implementando um pipeline de engenharia de dados robusto e utilizando **Inteligência Artificial (NLP)** para contrastar o que os colaboradores *dizem* (texto) versus como eles *pontuam* (scores).

---

## 📋 Checklist de Tarefas Realizadas

O projeto foi desenvolvido para cobrir todas as exigências do desafio técnico, incluindo os bônus e explorações criativas.

- [x] **Task 1: Basic Database** (Modelagem relacional no PostgreSQL 17 + SQLAlchemy 2.0: uso de Índices (`index=True`) para otimização de leitura e integração do `Flask-Migrate` (Alembic) para versionamento e evolução segura do esquema do banco sem perda de dados)
- [x] **Task 2: Basic Dashboard** (Interface web responsiva (Server-Side Rendering com Jinja2 + Bootstrap 5): filtros dinâmicos via URL (preservam estado ao compartilhar link) e UX moderna para dispositivos móveis)
- [x] **Task 3: Test Suite** (Suíte de testes robusta utilizando pytest: cobertura de **85%**, abrangendo as 3 camadas da pirâmide: Unitários (Lógica Matemática), Integração (API/Status Codes) e Lógica de Negócio (Pipeline de Ingestão e IA))
- [x] **Task 4: Docker Compose Setup** (Orquestração completa de 5 serviços: Web (Flask servido pelo gunicorn), Celery Worker, Celery Beat, Redis e Postgresql: `Dockerfile` Multi-stage para redução do tamanho da imagem final, que fica sem compiladores (já com os wheels prontos) e execução com usuário não-root (`appuser`) para segurança reforçada. Implementação de `Healthchecks` para garantir a ordem correta de inicialização (Web aguarda DB))
- [x] **Task 5: Exploratory Data Analysis** (A análise exploratória foi automatizada diretamente nos Dashboards)
- [x] **Task 6: Visualization - Company Level** (Visão focada em KPIs de conversão e distribuição de tempo de casa (Tenure): implementação de Gráficos de Radar comparativos para identificar lacunas culturais globais)
- [x] **Task 7: Visualization - Area Level** (Ferramenta de Benchmarking Cross-Department: Gráfico de Eixo Duplo (Dual Axis) que permite comparar Score Numérico (0-10) vs Sentimento da IA (1-5) lado a lado para todas as áreas)
- [x] **Task 8: Visualization - Employee Level** (Perfil individual confidencial com busca: "Tri-Layer Radar Chart" que compara o Indivíduo vs Média do Depto vs Média da Empresa num único gráfico visual, além de análise de sentimento específica para o comentário de eNPS)
- [x] **Task 9: Build a Simple API** (API RESTful segregada em Blueprint específico: paginação, filtros via query params, serialização robusta com Pydantic (DTOs) e documentação interativa integrada (`/api-docs`))
- [x] **Task 10: Sentiment Analysis** (Pipeline de NLP usando HuggingFace Transformers (modelo `bert-base-multilingual-uncased-sentiment`), processamento Assíncrono (Celery) e lógica de "Re-análise Inteligente" (só roda IA se o texto mudar, economizando recursos computacionais))
- [x] **Task 11: Report Generation** (Funcionalidade de Export/Print em certos dashboards)
- [x] **Task 12: Creative Exploration** (Análise de "Perception Gap": Criação de métricas comparativas e alertas visuais quando há discrepância entre a nota dada pelo colaborador e o sentimento detectado pela IA)

---

## ⚡ Quick Start

A aplicação é totalmente containerizada e utiliza um script de Auto-Bootstrap (`entrypoint.sh`). Ao subir os containers, o sistema automaticamente aguarda o banco, roda as migrações, baixa os dados e executa a IA.

### 1. Clonar e Configurar
Clone o repositório, entre na pasta e configure as variáveis de ambiente.

    git clone https://github.com/marcelonribeiro/tech-playground-challenge.git
    cd tech-playground-challenge
    
    # Cria o arquivo .env baseado no exemplo fornecido (Configurações pré-definidas para Docker local)
    cp .env.example .env

### 2. Rodar a Aplicação
Execute o comando abaixo. Isso irá construir as imagens, iniciar o Postgres, Redis, Celery (Worker+Beat) e a Aplicação Web.

    docker-compose up --build

*Aguarde alguns segundos na primeira execução para o download do modelo de IA e o processamento inicial dos dados.*

### 3. Acessar

- **Dashboard:** [http://localhost:5000](http://localhost:5000)
- **API Docs:** [http://localhost:5000/api-docs](http://localhost:5000/api-docs)

### 4. Rodar os Testes

Para validar a qualidade do código e ver o report de cobertura:

    docker-compose exec web pytest -v --cov=src --cov-report=html

---

## 🏗️ Architecture Decision Records (ADR)

Decisões técnicas tomadas visando um ciclo de vida de software longo, sustentável e escalável.

### 1. Framework: Flask
**Decisão:** Flask.
**Porquê:**
- **Flask vs Django:** Escolhi Flask por ser leve e flexível, permitindo selecionar as melhores bibliotecas para cada função (SQLAlchemy, Pydantic, Alembic). Django traria "baterias" desnecessárias para este escopo.
- **Flask vs FastAPI:** Embora FastAPI seja excelente para APIs puras, o foco do projeto é uma aplicação Full-stack com Renderização Server-Side (Jinja2) robusta e Dashboards integrados, onde o ecossistema Flask é extremamente maduro. A API é um complemento importante, mas não o único produto.

### 2. Pipeline de Ingestão Atômico & Idempotente
**Decisão:** Pipeline unificado com detecção de mudanças (Hashing lógico).
**Porquê:** Em sistemas de RH, o mesmo arquivo pode ser enviado várias vezes com correções. O pipeline atende a requisitos de consistência:
- **Idempotência:** O pipeline verifica linha a linha. Se o dado não mudou, ele pula (economiza processamento).
- **Atomicidade Lógica:** Utilizamos `db.session.flush()` para garantir que um registro só seja commitado no banco se a análise de sentimento da IA também tiver ocorrido. Não existem dados "meio processados".
- **Economia de Recursos:** Se o texto de um comentário mudar, a IA roda novamente. Se apenas a nota mudar, a IA é poupada. garante que o banco nunca tenha duplicatas e que a IA só rode quando estritamente necessário (economia de recursos).

### 3. Processamento Assíncrono e Agendamento (Celery + Redis)
**Decisão:** Arquitetura de Workers separada com Agendamento (Beat).
**Porquê:** Automação (ETL). Utilizei o Celery Beat para agendar a atualização dos dados diariamente. Isso simula um ambiente de produção onde os dados são vivos e atualizados recorrentemente, eliminando a necessidade de ferramentas complexas como Airflow para este escopo específico.

### 4. Modelo de Dados & Validação
**Decisão:** Pydantic para Ingestão (DTOs) vs SQLAlchemy para Persistência.
**Porquê:**
- **Pydantic**: Atua como "Guardrail" na entrada. Sanitiza os dados brutos do CSV (trata datas brasileiras `DD/MM/YYYY`, limpa strings vazias, valida e-mails) antes que eles toquem o domínio.
- **SQLAlchemy**: Garante a integridade referencial e tipagem no banco de dados.

### 5. Manipulação de Dados (Pandas)
**Decisão**: Uso da biblioteca Pandas para a etapa de Extração e Transformação.
**Porquê:** Pandas é o padrão da indústria para manipulação tabular e limpeza de dados (Data Cleaning). Ele facilita a leitura de CSVs complexos e o pré-processamento em lote antes da iteração de carga no banco.

### 6. Schema Evolution (Flask-Migrate)
**Decisão:** Uso de Migrations (Alembic).
**Porquê:** Projetos reais mudam. Comecei sem a tabela de sentimentos e depois a adicionei. O uso de `Flask-Migrate` permitiu evoluir o banco de dados sem perder os dados já ingeridos e sem precisar de "reset" manual, simulando um ambiente de produção real.

### 7. Integração Contínua (CI/CD)
**Decisão:** GitHub Actions.
**Porquê:** Optei por uma solução nativa e sem servidor (Serverless) para garantir a qualidade do código.
- **Workflow:** Criamos um pipeline (`ci.yml`) que é acionado automaticamente a cada *Push* ou *Pull Request* para a branch `main`.
- **Ambiente Isolado:** O Action provisiona um ambiente Ubuntu limpo e utiliza **Service Containers** para subir uma instância de Redis volátil, permitindo que os testes de integração do Celery rodem em um ambiente fiel à produção.
- **Quality Gate:** O build falha se qualquer teste quebrar, impedindo que código instável seja mesclado ao projeto.

### 8. Análise de Sentimentos
**Decisão:** O modelo `bert-base-multilingual-uncased-sentiment`.
**Porquê:** É treinado em múltiplos idiomas, incluindo o Português, capturando nuances sentimentais como positivo, negativo ou neutro com alta precisão. É relativamente leve, com cerca de 168 milhões de parâmetros, permitindo execução em hardware comum sem grande demanda computacional.

### 8. Framework CSS: Bootstrap vs Tailwind
**Decisão:** Bootstrap 5.
**Porquê:** O Bootstrap oferece consistência visual imediata e menor curva de aprendizado, reduzindo tempo de setup.

---

## 📂 Estrutura do Projeto
O projeto segue os princípios de **Clean Architecture** simplificada, separando Domínio, Aplicação e Interface.

    .
    ├── src/
    │   ├── application/            # Lógica de Negócio e Orquestração
    │   │   ├── services/           # Ingestion, Analytics, Dashboard, Sentiment
    │   │   └── tasks/              # Celery Workers (Background Jobs)
    │   │
    │   ├── domain/                 # O Coração do Software
    │   │   ├── models.py           # Entidades do Banco (SQLAlchemy)
    │   │   └── schemas.py          # Contratos de Dados (Pydantic)
    │   │
    │   ├── interface/              # Camada de Apresentação
    │   │   ├── api/                # REST API Endpoints
    │   │   └── web/                # Views Endpoints para Frontend
    │   │
    │   ├── static/                 # Frontend (CSS/JS)
    │   ├── templates/              # Frontend (HTML/Jinja2)
    │   │
    │   ├── app.py                  # Application Factory
    │   ├── celery_app.py           # Entrypoint do Worker
    │   ├── config.py               # Configurações de Ambiente
    │   └── extensions.py           # Singletons (DB, Migrate, Celery)
    │
    ├── migrations/                 # Histórico de versões do Banco (Alembic)
    |
    ├── tests/                      # Estratégia de QA
    │   ├── integration/            # Testes de API e Pipeline Real
    │   └── unit/                   # Testes de Lógica Matemática e Mock AI
    │
    ├── docker-compose.yml          # Orquestração de Containers
    ├── Dockerfile                  # Definição de Imagem
    ├── entrypoint.sh               # Script de Inicialização (Auto-Heal & Bootstrap)
    ├── .env.example                # Template de variáveis de ambiente
    └── requirements.txt            # Dependências

---

## 📚 Documentação da API

O projeto expõe uma API RESTful completa. A documentação interativa e detalhada, incluindo exemplos de cURL e esquemas JSON, está disponível localmente após iniciar o projeto.

**Acesse:** [http://localhost:5000/api-docs](http://localhost:5000/api-docs)

### Principais Endpoints:
- `GET /api/v1/employees`: Listagem paginada com filtros.
- `GET /api/v1/dashboard/company`: Métricas executivas (eNPS, Turnover).
- `GET /api/v1/analytics/sentiment-overview`: Agregação de dados da IA.

---

## 🧪 Testes e Qualidade

Segui uma pirâmide de testes para garantir robustez, atingindo cerca de 85% de cobertura do código Python:

1. **Unit Tests:** Validam a lógica matemática dos dashboards (Cálculo de eNPS, médias) e o mapeamento da IA (ex: garantir que 1 estrela = NEGATIVO).
2. **Logic Tests:** Validam o pipeline de ingestão, garantindo que o sistema de Upsert não duplica dados e que a IA é acionada corretamente apenas quando necessário (mockando chamadas externas).
3. **Integration Tests:** Validam o fluxo completo da API e Status Codes (200, 404, 500).

Para rodar com relatório de cobertura:

    docker-compose exec web pytest --cov=src --cov-report=html

---

## 🧠 Processo de Pensamento & Decisões

Mais do que entregar código, este projeto reflete minha abordagem de **Engenharia de Produto**. Abaixo, detalho como priorizei e tomei decisões durante o desenvolvimento.

### 1. Análise e Priorização (The "Why")

Ao receber o dataset, percebi que o maior valor não estava nos números isolados, mas na correlação entre eles.

- **Problema:** Um eNPS de 8 é bom? Depende. Se o comentário diz "Gosto das pessoas, mas odeio o salário", o 8 mascara um risco de *churn*.
- **Decisão:** Priorizei a construção de um Pipeline de NLP robusto antes mesmo de fazer o primeiro gráfico. Se o dado não fosse enriquecido na entrada, o dashboard seria apenas "mais do mesmo".

### 2. Arquitetura Evolutiva (The "How")

Não tentei fazer tudo de uma vez. Adotei uma abordagem iterativa:

1. **Fundação:** Garanti que o banco (Postgres) e a ingestão (Pandas) fossem sólidos. Se a ingestão falha, o app não tem propósito.
2. **Qualidade:** Implementei testes automatizados cedo. Isso me deu segurança para refatorar o código de ingestão para o modelo de "Upsert Atômico" sem medo de quebrar a lógica existente.
3. **Experiência:** Deixei o Frontend por último, pois a UI deve ser apenas um reflexo de dados bem estruturados.

### 3. Foco no Usuário Final (UX de Dados)

Ao desenhar os dashboards, pensei na jornada do RH:

- **Macro:** "Como está a empresa?" -> *Dashboard Company*
- **Meso:** "Qual time precisa de ajuda?" -> *Dashboard Areas (Comparativo)*
- **Micro:** "Quem eu preciso entrevistar hoje?" -> *Dashboard Employee (Perfil)*

Por isso, implementei o **Gráfico de Eixo Duplo** (Task 7) e os **Radares Comparativos** (Task 8), para que o usuário não precise fazer contas de cabeça.

---

## 🤖 Uso de IA no Desenvolvimento

Seguindo a sugestão do case, utilizei LLMs (Large Language Models) como um **Copiloto Sênior** para acelerar o desenvolvimento. Aqui está sobre onde a IA atuou:

### Onde a IA foi utilizada (Aceleração):

- **Boilerplate e Scaffolding:** Geração inicial de classes Pydantic baseadas nas colunas do CSV (economizando tempo de digitação repetitiva).
- **Frontend (Bootstrap/Chart.js):** Criação rápida de estruturas HTML responsivas e configurações complexas de gráficos (ex: configurações de eixos do Chart.js).
- **Refatoração:** Sugestões para limpar importações e tipagem (Type Hinting) em arquivos longos.

### Onde a IA NÃO foi utilizada (Engenharia Real):

- **Decisões Arquiteturais:** A escolha de usar *Application Factory*, a estratégia de *Atomic Upsert* no banco e a separação de *Services* foi decisão minha baseada em experiência com sistemas escaláveis.
- **Debug Complexo:** A resolução de *Race Conditions* no Docker (entrypoint) e *Circular Imports* no Celery exigiu entendimento profundo do funcionamento interno do Python/Linux, onde a IA muitas vezes sugere soluções genéricas que não funcionam.

A IA atuou como um multiplicador de produtividade, permitindo que eu focasse na **Arquitetura e no Produto**, enquanto ela cuidava da sintaxe e da repetição.

---

**Desenvolvido por Marcelo Nunes Ribeiro** - 2026