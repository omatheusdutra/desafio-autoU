# Email Smart Reply

![FastAPI](https://img.shields.io/badge/FastAPI-0.115.5-009688?logo=fastapi&logoColor=white)
![Python](https://img.shields.io/badge/Python-3.12-blue?logo=python&logoColor=white)
![Pytest](https://img.shields.io/badge/tests-pytest-green?logo=pytest&logoColor=white)
![Coverage](https://codecov.io/gh/omatheusdutra/desafio-autoU/branch/main/graph/badge.svg)
![License](https://img.shields.io/badge/license-MIT-orange)

Email Smart Reply é um backend FastAPI que classifica e-mails nas categorias produtivo/improdutivo (com grupos adicionais) e gera respostas prontas usando Transformers zero-shot, heurísticas locais ou GPT. O projeto inclui uma interface Jinja + CSS com upload único e processamento em lote via ZIP.

## ![badge](https://img.shields.io/badge/secao-Visao%20Geral-0d9488) Visão Geral
- Classificação híbrida: modelo zero-shot `facebook/bart-large-mnli` quando habilitado, caindo para heurísticas rápidas se indisponível.
- Pré-processamento NLP: remoção de stopwords e stemming simples para reforçar as heurísticas locais.
- Respostas inteligentes: integra OpenAI via `OPENAI_API_KEY` ou usa templates em PT-BR quando a chave não está definida.
- Cache inteligente: memória local (e Redis opcional) para evitar recomputar e-mails repetidos.
- Rate limiting: limite padrão de requisições por IP para proteger a API.
- Fila opcional: envio para processamento assíncrono via Redis + RQ.
- PDF melhorado: limpeza de cabeçalhos/rodapés repetidos.
- Idioma: detecção simples PT/EN para ajustar a resposta quando necessário.
- Auditoria segura: cada requisição gera apenas hash + metadados em JSONL.
- UI moderna: modo claro/escuro, copiar resposta, resumo de lote e links diretos para CSVs.

## ![badge](https://img.shields.io/badge/secao-Arquitetura-6366f1) Arquitetura
```
.
- app.py                  # wrapper retrocompatibilidade (importa backend.app)
- backend/
  - app.py                # ponto oficial para uvicorn backend.app:app
  - src/backend_app/
    - app.py              # factory FastAPI e montagem dos assets
    - application/        # casos de uso (NLP, processamento, jobs)
    - infrastructure/     # cache, storage, integrações
    - domain/             # schemas Pydantic
    - presentation/       # controllers FastAPI
    - config/             # Settings + auditoria
    - services/           # wrappers (compatibilidade)
- frontend/
  - src/
    - pages/              # templates Jinja
    - styles/             # CSS global
    - assets/             # favicon e imagens
    - components/
    - services/
    - utils/
- data/
  - sample_emails/
- docs/
  - architecture.md
- scripts/
  - api_smoke.py
  - run_worker.py
- tests/
- requirements.txt
- Dockerfile
- render.yaml
```

## ![badge](https://img.shields.io/badge/secao-Quickstart-14b8a6) Guia rápido
```bash
python -m venv .venv
. .venv/Scripts/activate            # Windows
# source .venv/bin/activate         # Linux/macOS
pip install -r requirements.txt

cp .env.example .env                # ajuste as variáveis conforme necessário

uvicorn backend.app:app --reload --port 7860
# acesse http://localhost:7860
```
> Com `ENABLE_TRANSFORMERS=true` o primeiro start baixa ~1.2 GB. Defina `false` para rodar apenas com heurísticas.

## ![badge](https://img.shields.io/badge/secao-Como%20rodar-0ea5e9) Como rodar (Windows)
```powershell
python -m venv .venv
. .venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
uvicorn backend.app:app --reload --port 7860
```
Abra: http://localhost:7860

### Fila (opcional)
```powershell
F:\Memurai\memurai.exe
python scripts/run_worker.py
```

## ![badge](https://img.shields.io/badge/secao-Configuracao-f97316) Configuração
| Variável | Descrição |
| --- | --- |
| `OPENAI_API_KEY` | Liga respostas GPT; vazio mantém templates. |
| `AUDIT_LOG_PATH` | Arquivo JSONL com hash e metadados. |
| `REPORTS_DIR` | Pasta servida em `/reports` para CSVs. |
| `REPORTS_STORAGE` | `local` ou `s3` para salvar relatórios em storage externo. |
| `S3_BUCKET` | Bucket S3 para relatórios (quando `REPORTS_STORAGE=s3`). |
| `S3_REGION` | Região do bucket S3. |
| `S3_PREFIX` | Prefixo/pasta dentro do bucket. |
| `S3_PUBLIC_BASE_URL` | URL pública opcional para gerar link direto. |
| `ENABLE_TRANSFORMERS` | Ativa/desativa zero-shot. |
| `PORT` | Porta exposta pelo servidor. |
| `KEYWORD_OVERRIDES_PATH` | Caminho opcional para JSON com palavras-chave adicionais. |
| `REDIS_URL` | URL do Redis (cache e fila opcional). |
| `ENABLE_REDIS_CACHE` | Usa Redis como cache de classificações. |
| `CACHE_TTL_SECONDS` | TTL do cache em segundos. |
| `CACHE_MAX_ITEMS` | Máximo de itens no cache local. |
| `ENABLE_RATE_LIMIT` | Ativa rate limit por IP. |
| `RATE_LIMIT_DEFAULT` | Limite padrão (ex.: `60/minute`). |
| `ENABLE_WARMUP` | Pré-carrega o modelo no startup. |
| `ENABLE_JOB_QUEUE` | Habilita processamento assíncrono via fila. |
| `MAX_UPLOAD_MB` | Limite em MB por arquivo (texto, PDF ou ZIP). |
| `BATCH_PREVIEW_LIMIT` | Linhas exibidas no resumo do lote. |
| `CLASSIFICATION_WORKERS` | Paralelismo async para classificações. |
| `PDF_PARSE_WORKERS` | Paralelismo async para extração de PDF. |
| `MAX_BATCH_ITEMS` | Máximo de e-mails aceitos em lote/ZIP. |

## ![badge](https://img.shields.io/badge/secao-API-2563eb) API
| Endpoint | Método | Corpo | Resposta |
| --- | --- | --- | --- |
| `/health` | GET | - | `{"status": "ok"}` |
| `/api/process` | POST | `{"text": "..."}` | Categoria binária + principal, confiança, engine, hash e reply |
| `/api/batch` | POST | `{"texts": ["...", "..."]}` | Lista de resultados com mesma estrutura do endpoint unitário |
| `/api/submit` | POST | `{"text": "..."}` | Enfileira ou processa síncrono se fila off |
| `/api/submit_file` | POST | `multipart/form-data` | Enfileira arquivo ou processa síncrono |
| `/api/job/{id}` | GET | - | Status do job ou resultado final |
| `/api/batch_submit` | POST | `multipart/form-data` | Enfileira ZIP ou processa síncrono |
| `/api/batch_job/{id}` | GET | - | Status/progresso do lote + links de relatório |

## ![badge](https://img.shields.io/badge/secao-UI%20e%20ZIP-3b82f6) UI e processamento ZIP
- Aceita arquivos `.txt`/`.pdf` individuais ou ZIP com múltiplos itens respeitando `MAX_UPLOAD_MB` e `MAX_BATCH_ITEMS`.
- Extração de PDF tenta `pdfminer.six` e depois `PyPDF2`.
- Cada lote gera relatórios TXT/CSV/JSON acessíveis via `/reports`.
- A UI mostra as primeiras linhas do lote conforme `BATCH_PREVIEW_LIMIT`.

## ![badge](https://img.shields.io/badge/secao-Ajuste%20rapido-7c3aed) Ajuste rápido (treinamento leve)
- O arquivo `backend/src/backend_app/config/keyword_overrides.json` permite ajustar a classificação com termos do negócio sem treinar um modelo pesado.
- Para usar um arquivo externo, configure `KEYWORD_OVERRIDES_PATH` no `.env`.
- Esse ajuste complementa o zero-shot e melhora a precisão em categorias muito específicas da operação.

## ![badge](https://img.shields.io/badge/secao-Testes-22c55e) Testes
```bash
python -m pytest
```

## ![badge](https://img.shields.io/badge/secao-Scripts%20uteis-0ea5e9) Scripts úteis
```bash
python scripts/api_smoke.py      # smoke test simples dos endpoints
python scripts/run_worker.py     # inicia o worker RQ no Windows (SimpleWorker)
```

## ![badge](https://img.shields.io/badge/secao-Fila-0ea5e9) Fila (opcional)
Com `ENABLE_JOB_QUEUE=true` e `REDIS_URL` configurado:
```bash
rq worker email-smart-reply
```
### Windows
No Windows, use o SimpleWorker (sem fork) e garanta que `backend/src` esteja no `PYTHONPATH`.
```bash
rq worker -w rq.worker.SimpleWorker email-smart-reply
```
Este projeto inclui `sitecustomize.py` na raiz para ajustar o `sys.path` automaticamente.
Se preferir, use o script utilitário:
```bash
python scripts/run_worker.py
```
O processamento em lote via `/api/batch_submit` expõe progresso em `/api/batch_job/{id}`.
- `tests/test_api.py` cobre `/health`, `/api/process` e `/api/batch` com stubs que evitam downloads.
- `tests/test_web.py` valida a página inicial e o fluxo ZIP.

## ![badge](https://img.shields.io/badge/secao-Deploy-ef4444) Deploy
### Render (Blueprint)
1. Faça fork do repositório.
2. Em [Render](https://render.com) escolha **New → Blueprint** e selecione o fork.
3. `render.yaml` cria o serviço com `uvicorn backend.app:app --host 0.0.0.0 --port $PORT`.
4. Recomende definir `AUDIT_LOG_PATH`, `REPORTS_DIR`, `ENABLE_TRANSFORMERS` e `OPENAI_API_KEY` quando necessário.

## ![badge](https://img.shields.io/badge/secao-Links-9333ea) Links sugeridos
- **App hospedado:** https://email-smart-reply-376k.onrender.com
- **Vídeo / demo:** inclua o link do vídeo de apresentação.

## ![badge](https://img.shields.io/badge/secao-Licenca-0ea5e9) Licença
Projeto licenciado sob MIT. Contribuições e forks são bem-vindos.
