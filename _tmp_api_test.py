from fastapi.testclient import TestClient
from app import app

client = TestClient(app)

print('/health =>', client.get('/health').json())

payload = {'text': 'Preciso saber o status do chamado 123, podem atualizar?'}
resp = client.post('/api/process', json=payload)
print('/api/process status', resp.status_code)
print(resp.json())

batch_payload = {'texts': [
    'Enviei os documentos e preciso confirmar o recebimento.',
    'Minha senha expirou e não consigo acessar o portal.',
]}
resp_batch = client.post('/api/batch', json=batch_payload)
print('/api/batch status', resp_batch.status_code)
print(resp_batch.json())
