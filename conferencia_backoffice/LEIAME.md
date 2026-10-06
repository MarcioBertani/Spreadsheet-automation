# Conferência de jogadores no backoffice 9F

Roda no seu computador (o backoffice só abre logado e na sua rede).

## Instalar (uma vez)
```
pip install -r requirements.txt
playwright install chromium
```

## 1º passo – descobrir/login
```
python conferir.py --descobrir
```
Faça login no navegador que abrir, abra a tela de um jogador e aperte ENTER.
O script mostra a URL da tela do jogador: confira se bate com `URL_JOGADOR` no topo do `conferir.py`.

## Teste com poucos IDs
```
python conferir.py --limite 10
```

## Rodar tudo
```
python conferir.py
```
Pode parar (Ctrl+C) e rodar de novo: ele continua de onde parou.
O resultado sai em `resultado.csv`, com as colunas E–Q da planilha.
Se o download da planilha falhar, exporte como CSV e use `--csv arquivo.csv`.

`resultado.csv`, `respostas_api/` e `perfil_navegador/` têm dados pessoais/login e **não vão para o Git**.
