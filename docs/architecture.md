# Arquitetura (visao geral)

Organizacao em camadas para separar responsabilidades:

- **presentation**: rotas HTTP (FastAPI) e UI.
- **application**: orquestracao de casos de uso (processamento, NLP, filas).
- **infrastructure**: cache, storage e integracoes externas.
- **domain**: modelos/contratos (Pydantic).

## Estrutura atual (resumo)
```
backend/src/backend_app/
├─ app.py
├─ config/
├─ domain/
│  └─ schemas.py
├─ application/
│  ├─ nlp.py
│  ├─ processing.py
│  └─ jobs.py
├─ infrastructure/
│  ├─ cache.py
│  └─ storage.py
└─ presentation/
   └─ controllers/
      ├─ api.py
      ├─ batch.py
      └─ web.py
```

## Compatibilidade
Os caminhos legados (`backend_app.services.*`, `backend_app.controllers.*`,
`backend_app.models.schemas`) foram mantidos como **wrappers** para evitar
quebrar imports externos.
