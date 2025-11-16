# Email Smart Reply

![FastAPI](https://img.shields.io/badge/FastAPI-0.115.5-009688?logo=fastapi&logoColor=white)
![Python](https://img.shields.io/badge/Python-3.12-blue?logo=python&logoColor=white)
![Pytest](https://img.shields.io/badge/tests-pytest-green?logo=pytest&logoColor=white)
![License](https://img.shields.io/badge/license-MIT-orange)

Email Smart Reply e um backend FastAPI que classifica emails nas categorias produtivo/improdutivo (com grupos adicionais) e gera respostas prontas usando Transformers zero-shot, heuristicas locais ou GPT. O projeto inclui uma interface Jinja + CSS com upload unico e processamento em lote via ZIP.

## ![badge](https://img.shields.io/badge/secao-Visao%20Geral-0d9488) Visao Geral
- Classificacao hibrida: modelo zero-shot `facebook/bart-large-mnli` quando habilitado, caindo para heuristicas rapidas se indisponivel.
- Respostas inteligentes: integra OpenAI via `OPENAI_API_KEY` ou usa templates em PT-BR quando a chave nao esta definida.
- Auditoria segura: cada requisicao gera apenas hash + metadados em JSONL.
- UI moderna: modo claro/escuro, copiar resposta, resumo de lote e links diretos para CSVs.

## ![badge](https://img.shields.io/badge/secao-Arquitetura-6366f1) Arquitetura
```
.
├─ app.py                  # wrapper retrocompatibilidade (importa backend.app)
├─ backend/
│  ├─ app.py               # ponto oficial para uvicorn backend.app:app
│  └─ src/backend_app/
│     ├─ app.py            # factory FastAPI e montagem dos assets
│     ├─ controllers/      # api.py, web.py, batch.py
│     ├─ services/         # processamento, NLP e replies
│     ├─ models/           # schemas Pydantic
│     ├─ config/           # Settings + auditoria
│     └─ middlewares/      # reservado para futuros midwares
├─ frontend/
│  └─ src/
│     ├─ pages/            # templates Jinja
│     ├─ styles/           # CSS global
│     ├─ assets/           # favicon e imagens
│     ├─ components/
│     ├─ services/
│     └─ utils/
├─ sample_emails/
├─ tests/
├─ requirements.txt
├─ Dockerfile
└─ render.yaml
```

## ![badge](https://img.shields.io/badge/secao-Quickstart-14b8a6) Guia rapido
```bash
python -m venv .venv
. .venv/Scripts/activate            # Windows
# source .venv/bin/activate         # Linux/macOS
pip install -r requirements.txt

cp .env.example .env                # ajuste as variaveis conforme necessario

uvicorn backend.app:app --reload --port 7860
# acesse http://localhost:7860
```
> Com `ENABLE_TRANSFORMERS=true` o primeiro start baixa ~1.2 GB. Defina `false` para rodar apenas com heuristicas.

## ![badge](https://img.shields.io/badge/secao-Configuracao-f97316) Configuracao
| Variavel | Descricao |
| --- | --- |
| `OPENAI_API_KEY` | Liga respostas GPT; vazio mantem templates. |
| `AUDIT_LOG_PATH` | Arquivo JSONL com hash e metadados. |
| `REPORTS_DIR` | Pasta servida em `/reports` para CSVs. |
| `ENABLE_TRANSFORMERS` | Ativa/desativa zero-shot. |
| `PORT` | Porta exposta pelo servidor. |
| `MAX_UPLOAD_MB` | Limite em MB por arquivo (texto, PDF ou ZIP). |
| `BATCH_PREVIEW_LIMIT` | Linhas exibidas no resumo do lote. |
| `CLASSIFICATION_WORKERS` | Paralelismo async para classificacoes. |
| `MAX_BATCH_ITEMS` | Maximo de emails aceitos em lote/ZIP. |

## ![badge](https://img.shields.io/badge/secao-API-2563eb) API
| Endpoint | Metodo | Corpo | Resposta |
| --- | --- | --- | --- |
| `/health` | GET | - | `{"status": "ok"}` |
| `/api/process` | POST | `{"text": "..."}` | Categoria binaria + principal, confianca, engine, hash e reply |
| `/api/batch` | POST | `{"texts": ["...", "..."]}` | Lista de resultados com mesma estrutura do endpoint unitario |

## ![badge](https://img.shields.io/badge/secao-UI%20e%20ZIP-3b82f6) UI e processamento ZIP
- Aceita arquivos `.txt`/`.pdf` individuais ou ZIP com multiplos itens respeitando `MAX_UPLOAD_MB` e `MAX_BATCH_ITEMS`.
- Extracao de PDF tenta `pdfminer.six` e depois `PyPDF2`.
- Cada lote gera `reports/report_<timestamp>.csv` acessivel via `/reports`.
- A UI mostra as primeiras linhas do lote conforme `BATCH_PREVIEW_LIMIT`.

## ![badge](https://img.shields.io/badge/secao-Testes-22c55e) Testes
```bash
python -m pytest
```
- `tests/test_api.py` cobre `/health`, `/api/process` e `/api/batch` com stubs que evitam downloads.
- `tests/test_web.py` valida a pagina inicial e o fluxo ZIP.

## ![badge](https://img.shields.io/badge/secao-Deploy-ef4444) Deploy
### Render (Blueprint)
1. Faça fork do repositorio.
2. Em [Render](https://render.com) escolha **New → Blueprint** e selecione o fork.
3. `render.yaml` cria o servico com `uvicorn backend.app:app --host 0.0.0.0 --port $PORT`.
4. Recomende definir `AUDIT_LOG_PATH`, `REPORTS_DIR`, `ENABLE_TRANSFORMERS` e `OPENAI_API_KEY` quando necessario.


## ![badge](https://img.shields.io/badge/secao-Links-9333ea) Links sugeridos
- **App hospedado:** https://email-smart-reply-376k.onrender.com
- **Video / demo:** inclua o link do video de apresentacao.

## ![badge](https://img.shields.io/badge/secao-Licenca-0ea5e9) Licenca
Projeto licenciado sob MIT. Contribuicoes e forks sao bem-vindos.
