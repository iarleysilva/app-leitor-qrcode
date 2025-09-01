# --- Importações necessárias ---
from flask import Flask, render_template, redirect, abort
import gspread
import pandas as pd
from oauth2client.service_account import ServiceAccountCredentials
import os
import json

# --- Configuração do App Flask ---
app = Flask(__name__)

# --- Função para Acessar a Planilha ---
def get_sheet_data():
    """ Conecta-se ao Google Sheets e retorna os dados da aba 'QR_CODE_LPN' """
    try:
        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        
        # Lógica de credenciais segura para o Render.com
        creds_json_str = os.environ.get('GOOGLE_CREDENTIALS_JSON', None)
        if creds_json_str:
            creds_dict = json.loads(creds_json_str)
            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
            print("Credenciais carregadas a partir da variável de ambiente.")
        else:
            # Fallback para o ficheiro local para testes
            creds = ServiceAccountCredentials.from_json_keyfile_name('credentials.json', scope)
            print("Credenciais carregadas a partir do ficheiro local 'credentials.json'.")

        client = gspread.authorize(creds)
        spreadsheet_url = 'https://docs.google.com/spreadsheets/d/1nuftv1FJltrtpagYdW6PLa3MT_9lCCiyeQ06poO42H8/edit'
        spreadsheet = client.open_by_url(spreadsheet_url)
        sheet = spreadsheet.worksheet('QR_CODE_LPN')
        data = sheet.get_all_records()
        df = pd.DataFrame(data)
        
        # Garante que as colunas de busca sejam tratadas como texto
        for col in ['NR_PERCURSO', 'NR_ENTREGA', 'Placeholder', 'PALLET']:
            if col in df.columns:
                df[col] = df[col].astype(str)
        
        return df
    except Exception as e:
        print(f"Erro ao acessar a planilha: {e}")
        return None

# --- Rota Principal da Aplicação ---
@app.route('/<string:percurso>/<string:entrega>/<string:placeholder>')
def find_data(percurso, entrega, placeholder):
    """ Função principal que é chamada quando um QR Code é lido. """
    print(f"Buscando por Percurso={percurso}, Entrega={entrega}, Placeholder={placeholder}")
    
    df = get_sheet_data()
    
    if df is None:
        return "Erro: Não foi possível conectar à base de dados.", 500

    result_row = df[
        (df['NR_PERCURSO'] == percurso) &
        (df['NR_ENTREGA'] == entrega) &
        (df['Placeholder'] == placeholder)
    ]
    
    if result_row.empty:
        print("Nenhum registro encontrado.")
        abort(404, description="Registro não encontrado para os dados fornecidos.")

    found_data = result_row.iloc[0].to_dict()
    
    # --- DICIONÁRIO DE DADOS ATUALIZADO ---
    # Agora envia todos os dados com os nomes corretos que o index.html espera
    display_data = {
        'cliente': found_data.get('NM_CLIENTE', 'N/A'),
        'nr_percurso': found_data.get('NR_PERCURSO', 'N/A'),
        'nr_entrega': found_data.get('NR_ENTREGA', 'N/A'),
        'pallet': found_data.get('PALLET', 'N/A'),
        'cod_produto': found_data.get('CD_PRODUTO', 'N/A'),
        'produto': found_data.get('NM_PRODUTO', 'N/A'),
        'tonalidade': found_data.get('TONALIDADE', 'N/A'),
        'qtde': found_data.get('QTDE', 'N/A'),
        'unidade': found_data.get('UNIDADE', '') # Adicionado o campo que faltava
    }

    if str(found_data.get('PALLET', '')).strip():
        print(f"Pallet encontrado ({display_data['pallet']}). Exibindo dados completos.")
        return render_template('index.html', data=display_data)
    else:
        print("Pallet vazio. Exibindo página de aguardando conferência.")
        return render_template('aguardando.html', data=display_data)

@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html', error=e.description), 404

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)

