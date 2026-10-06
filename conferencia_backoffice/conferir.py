'''
Conferência de jogadores no backoffice 9F.

Lê os IDs da planilha "Saldo jogadores 9F", abre cada jogador no backoffice
(usando um navegador onde você já fez login) e salva os dados encontrados em
resultado.csv, na mesma ordem das colunas da planilha (E até Q), pronto para colar.

Uso:
    python conferir.py --descobrir          # 1ª vez: faz login e mostra como o backoffice navega
    python conferir.py                      # confere todos os IDs que ainda não estão no resultado.csv
    python conferir.py --limite 20          # confere só 20 IDs (bom para testar)
    python conferir.py --ids 24318827 28668419
'''

import argparse
import csv
import io
import json
import re
import sys
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

PASTA = Path(__file__).resolve().parent

# --- Configuração -----------------------------------------------------------

PLANILHA_ID = '1_BV7PfufB6SkuOeeFeC4icas4ndkSpUGN195pxcBxbE'
BACKOFFICE = 'https://f9u2g9wkut2o.amazonows.com'

# Endereço da tela de um jogador. {id} é trocado pelo ID do usuário.
# CONFIRMAR com o modo --descobrir: abra um jogador manualmente e veja a URL impressa.
URL_JOGADOR = BACKOFFICE + '/#/player-info/player-summary?userId={id}'

PERFIL_NAVEGADOR = PASTA / 'perfil_navegador'   # guarda o login entre execuções
ARQ_RESULTADO = PASTA / 'resultado.csv'
PASTA_RESPOSTAS = PASTA / 'respostas_api'        # JSON que o backoffice recebe (para conferência)

# Colunas da planilha (E até Q) na ordem em que serão gravadas no resultado.
COLUNAS = [
    'Data de Criação',
    'Nome',
    'Data ultimo Login',
    'Quantidade de Logins',
    'Data Ultimo Saque',
    'Data Ultimo Deposito',
    'Valor Depositado',
    'Quanto foi pago de cashback?',
    'Quanto foi pago de afiliados?',
    'Quanto foi pago de demais bônus',
    'Valor Apostado',
    'Premiação',
    'IP de ultimo login',
]

# Coluna da planilha  <-  rótulo na tela "player-summary" do backoffice
ROTULOS_TELA = {
    'Data de Criação': 'Data de Registro',
    'Valor Depositado': 'Total de Depósitos',
    'Valor Apostado': 'Volume de apostas',
}

# --- Leitura da planilha ----------------------------------------------------

def ler_ids_planilha(caminho_csv=None):
    '''Retorna a lista de IDs (coluna B). Usa um CSV local ou baixa da planilha.'''
    if caminho_csv:
        texto = Path(caminho_csv).read_text(encoding='utf-8-sig')
    else:
        url = f'https://docs.google.com/spreadsheets/d/{PLANILHA_ID}/export?format=csv'
        texto = urllib.request.urlopen(url, timeout=60).read().decode('utf-8-sig')

    linhas = list(csv.reader(io.StringIO(texto)))
    ids = []
    for linha in linhas[1:]:
        if len(linha) > 1 and linha[1].strip().isdigit():
            ids.append(linha[1].strip())
    return ids


def ids_ja_conferidos():
    if not ARQ_RESULTADO.exists():
        return set()
    with ARQ_RESULTADO.open(encoding='utf-8-sig') as f:
        return {linha['ID do usuário'] for linha in csv.DictReader(f)}


def gravar_resultado(dados):
    novo = not ARQ_RESULTADO.exists()
    with ARQ_RESULTADO.open('a', newline='', encoding='utf-8-sig') as f:
        escritor = csv.DictWriter(f, fieldnames=['ID do usuário'] + COLUNAS + ['Observação'])
        if novo:
            escritor.writeheader()
        escritor.writerow(dados)

# --- Leitura da tela do jogador ----------------------------------------------

JS_VALOR_DO_ROTULO = '''
(rotulo) => {
    const celulas = [...document.querySelectorAll('td, th, div, span, label')]
        .filter(el => el.children.length === 0 && el.innerText.trim() === rotulo);
    for (const el of celulas) {
        // sobe até a célula da tabela e pega a célula vizinha
        const celula = el.closest('td, th') || el;
        const vizinha = celula.nextElementSibling;
        if (vizinha) return vizinha.innerText.trim();
    }
    return null;
}
'''

JS_ULTIMO_IP = '''
() => {
    for (const tabela of document.querySelectorAll('table')) {
        const cab = [...tabela.querySelectorAll('th')].map(th => th.innerText.trim());
        const iIp = cab.indexOf('IP');
        if (iIp === -1 || !cab.includes('Hora de Login')) continue;
        // a tabela de cabeçalho e a de corpo podem ser separadas (Element UI)
        const bloco = tabela.closest('.el-table') || tabela;
        const linha = bloco.querySelector('tbody tr');
        if (!linha) return null;
        const celulas = linha.querySelectorAll('td');
        return celulas[iIp] ? celulas[iIp].innerText.trim() : null;
    }
    return null;
}
'''


def ler_tela_jogador(page, id_usuario):
    dados = {'ID do usuário': id_usuario}
    observacoes = []

    for coluna, rotulo in ROTULOS_TELA.items():
        valor = page.evaluate(JS_VALOR_DO_ROTULO, rotulo)
        dados[coluna] = valor if valor else 'N/A'

    texto = page.inner_text('body')

    m = re.search(r'Último Login:\s*([^\n]+?)\s+Total de Logins:\s*(\d+)', texto)
    if m:
        ultimo = m.group(1).strip()
        dados['Data ultimo Login'] = 'N/A' if ultimo.upper() == 'NEVER' else ultimo
        dados['Quantidade de Logins'] = m.group(2)
    else:
        observacoes.append('login não encontrado na tela')

    ip = page.evaluate(JS_ULTIMO_IP)
    dados['IP de ultimo login'] = ip if ip else 'N/A'

    dados['Observação'] = '; '.join(observacoes)
    return dados


def abrir_jogador(page, id_usuario):
    page.goto(URL_JOGADOR.format(id=id_usuario))
    # o backoffice é uma SPA: espera aparecer o ID certo para não ler dados do jogador anterior
    page.wait_for_function(
        '(id) => document.body.innerText.includes("ID: " + id)', arg=id_usuario, timeout=20000)
    page.wait_for_function(
        '() => document.body.innerText.includes("Total de Logins")', timeout=20000)
    page.wait_for_load_state('networkidle')

# --- Execução -----------------------------------------------------------------

def guardar_respostas_api(page, destino):
    '''Salva as respostas JSON do backoffice; servem para descobrir onde estão
    saque, depósito, cashback, bônus etc. sem precisar abrir outras abas.'''
    def ao_responder(resposta):
        if 'json' not in (resposta.headers.get('content-type') or ''):
            return
        try:
            destino.append({'url': resposta.url, 'corpo': resposta.json()})
        except Exception:
            pass
    page.on('response', ao_responder)


def modo_descobrir(page):
    capturadas = []
    guardar_respostas_api(page, capturadas)
    page.goto(BACKOFFICE)
    print('\n1) Faça login no navegador que abriu (se ainda não estiver logado).')
    print('2) Abra manualmente a tela de UM jogador (ex.: 24318827).')
    input('3) Quando a tela do jogador estiver carregada, aperte ENTER aqui... ')
    print('\nURL atual do navegador:\n   ', page.url)
    print('   -> ajuste URL_JOGADOR no topo do script se for diferente do padrão.\n')
    PASTA_RESPOSTAS.mkdir(exist_ok=True)
    arq = PASTA_RESPOSTAS / 'descoberta.json'
    arq.write_text(json.dumps(capturadas, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'Chamadas de API capturadas: {len(capturadas)} (salvas em {arq})')
    for c in capturadas:
        print('   ', c['url'])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--descobrir', action='store_true')
    ap.add_argument('--csv', help='CSV exportado da planilha (se não der para baixar direto)')
    ap.add_argument('--ids', nargs='*')
    ap.add_argument('--limite', type=int)
    args = ap.parse_args()

    with sync_playwright() as p:
        contexto = p.chromium.launch_persistent_context(
            str(PERFIL_NAVEGADOR), headless=False, viewport={'width': 1600, 'height': 900})
        page = contexto.pages[0] if contexto.pages else contexto.new_page()

        if args.descobrir:
            modo_descobrir(page)
            contexto.close()
            return

        ids = args.ids or ler_ids_planilha(args.csv)
        feitos = ids_ja_conferidos()
        pendentes = [i for i in ids if i not in feitos]
        if args.limite:
            pendentes = pendentes[:args.limite]
        print(f'{len(ids)} IDs na lista, {len(feitos)} já conferidos, {len(pendentes)} a conferir.')

        PASTA_RESPOSTAS.mkdir(exist_ok=True)
        capturadas = []
        guardar_respostas_api(page, capturadas)
        for n, id_usuario in enumerate(pendentes, 1):
            capturadas.clear()
            try:
                abrir_jogador(page, id_usuario)
                dados = ler_tela_jogador(page, id_usuario)
            except PWTimeout:
                dados = {'ID do usuário': id_usuario, 'Observação': 'tela não carregou / jogador não encontrado'}
            gravar_resultado(dados)
            (PASTA_RESPOSTAS / f'{id_usuario}.json').write_text(
                json.dumps(capturadas, ensure_ascii=False), encoding='utf-8')
            print(f'[{n}/{len(pendentes)}] {id_usuario}: '
                  f"apostado={dados.get('Valor Apostado')} logins={dados.get('Quantidade de Logins')} "
                  f"{dados.get('Observação', '')}")

        contexto.close()
    print(f'\nPronto. Resultado em {ARQ_RESULTADO}')


if __name__ == '__main__':
    sys.exit(main())
