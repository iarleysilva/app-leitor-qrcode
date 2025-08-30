# --- Importações necessárias ---
from flask import Flask, render_template, redirect, abort
import gspread
import pandas as pd
from oauth2client.service_account import ServiceAccountCredentials
import os
import json

# --- Configuração do App Flask ---
app = Flask(__name__)

# --- Função para Acessar a Planilha (versão atualizada e segura) ---
def get_sheet_data():
    """
    Conecta-se ao Google Sheets e retorna os dados da aba 'QR_CODE_LPN' como um DataFrame.
    Prioriza credenciais de variáveis de ambiente para produção.
    """
    try:
        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        
        # --- LÓGICA DE CREDENCIAIS SEGURA ---
        # No Render.com, usaremos uma variável de ambiente. Para testes locais, o arquivo .json.
        if 'GOOGLE_CREDENTIALS_JSON' in os.environ:
            creds_json_str = os.environ.get('GOOGLE_CREDENTIALS_JSON')
            creds_dict = json.loads(creds_json_str)
            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
            print("Credenciais carregadas a partir da variável de ambiente.")
        else:
            creds = ServiceAccountCredentials.from_json_keyfile_name('credentials.json', scope)
            print("Credenciais carregadas a partir do arquivo local 'credentials.json'.")

        client = gspread.authorize(creds)
        spreadsheet_url = 'https://docs.google.com/spreadsheets/d/1nuftv1FJltrtpagYdW6PLa3MT_9lCCiyeQ06poO42H8/edit'
        spreadsheet = client.open_by_url(spreadsheet_url)
        sheet = spreadsheet.worksheet('QR_CODE_LPN')
        data = sheet.get_all_records()
        df = pd.DataFrame(data)
        
        # Garante que as colunas de busca sejam tratadas como texto para evitar erros de tipo
        df['NR_PERCURSO'] = df['NR_PERCURSO'].astype(str)
        df['NR_ENTREGA'] = df['NR_ENTREGA'].astype(str)
        df['Placeholder'] = df['Placeholder'].astype(str)
        
        return df
    except Exception as e:
        print(f"Erro ao acessar a planilha: {e}")
        return None

# --- Rota Principal da Aplicação (Com a Nova Lógica) ---
@app.route('/<string:percurso>/<string:entrega>/<string:placeholder>')
def find_data(percurso, entrega, placeholder):
    """
    Esta função é chamada quando alguém acessa a URL com os 3 parâmetros.
    """
    print(f"Buscando por Percurso={percurso}, Entrega={entrega}, Placeholder={placeholder}")
    
    df = get_sheet_data()
    
    if df is None:
        return "Erro: Não foi possível conectar à base de dados (Planilha Google).", 500

    # Busca pela linha que corresponde exatamente aos 3 critérios
    result_row = df[
        (df['NR_PERCURSO'] == percurso) &
        (df['NR_ENTREGA'] == entrega) &
        (df['Placeholder'] == placeholder)
    ]
    
    if result_row.empty:
        print("Nenhum registro encontrado.")
        # Retorna a página de erro 404 se nada for encontrado
        abort(404, description="Registro não encontrado para os dados fornecidos.")

    # Pega a primeira (e única) linha encontrada
    found_data = result_row.iloc[0]
    
    # --- NOVA LÓGICA APLICADA AQUI ---
    
    # Prepara os dados básicos que serão usados em ambas as páginas
    display_data = {
        'nm_cliente': found_data['NM_CLIENTE'],
        'nr_percurso': found_data['NR_PERCURSO'],
        'nr_entrega': found_data['NR_ENTREGA'],
        'cd_produto': found_data['CD_PRODUTO'],
        'tonalidade': found_data['TONALIDADE'],
        'nm_produto': found_data['NM_PRODUTO'],
        'qtde': found_data['QTDE'],
        'unidade': found_data['UNIDADE']
    }

    # Verifica se a coluna PALLET tem algum valor (convertemos para string e removemos espaços)
    if str(found_data['PALLET']).strip():
        print(f"Pallet encontrado ({found_data['PALLET']}). Exibindo dados completos.")
        # Se tiver valor, adiciona o pallet aos dados e mostra a página de detalhes
        display_data['pallet'] = found_data['PALLET']
        return render_template('index.html', data=display_data)
    else:
        # Se a coluna PALLET estiver vazia...
        print("Pallet vazio. Exibindo página de aguardando conferência.")
        # Mostra a nova página de status "Aguardando"
        return render_template('aguardando.html', data=display_data)

# Rota para página de erro 404 personalizada
@app.errorhandler(404)
def page_not_found(e):
    # Passa a descrição do erro para a página 404
    return render_template('404.html', error=e.description), 404

# --- Ponto de entrada para execução (necessário para plataformas como o Render) ---
if __name__ == '__main__':
    # A porta é definida pela variável de ambiente PORT, padrão 5000 para testes locais
    port = int(os.environ.get('PORT', 5000))
    # '0.0.0.0' faz o servidor ser acessível na rede
    app.run(host='0.0.0.0', port=port)

