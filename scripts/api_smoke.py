import sys
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app import app  # noqa: E402

client = TestClient(app)

print('/health =>', client.get('/health').json())

payload = {'text': 'Preciso saber o status do chamado 123, podem atualizar?'}
resp = client.post('/api/process', json=payload)
print('/api/process status', resp.status_code)
print(resp.json())

batch_payload = {'texts': [
    'Enviei os documentos e preciso confirmar o recebimento.',
    'Minha senha expirou e n?o consigo acessar o portal.',
]}
resp_batch = client.post('/api/batch', json=batch_payload)
print('/api/batch status', resp_batch.status_code)
print(resp_batch.json())
