# --- Importações necessárias ---
from flask import Flask, render_template, redirect, abort, url_for
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
        
        creds_json_str = os.environ.get('GOOGLE_CREDENTIALS_JSON', None)
        if creds_json_str:
            creds_dict = json.loads(creds_json_str)
            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
            print("Credenciais carregadas a partir da variável de ambiente.")
        else:
            creds = ServiceAccountCredentials.from_json_keyfile_name('credentials.json', scope)
            print("Credenciais carregadas a partir do ficheiro local 'credentials.json'.")

        client = gspread.authorize(creds)
        spreadsheet_url = 'https://docs.google.com/spreadsheets/d/1nuftv1FJltrtpagYdW6PLa3MT_9lCCiyeQ06poO42H8/edit'
        spreadsheet = client.open_by_url(spreadsheet_url)
        sheet = spreadsheet.worksheet('QR_CODE_LPN')
        data = sheet.get_all_records()
        df = pd.DataFrame(data)
        
        for col in ['NR_PERCURSO', 'NR_ENTREGA', 'Placeholder', 'PALLET']:
            if col in df.columns:
                df[col] = df[col].astype(str)
        
        return df
    except Exception as e:
        print(f"Erro ao acessar a planilha: {e}")
        return None

# --- Função Auxiliar para criar o dicionário de dados ---
def build_display_data(found_data):
    """Cria o dicionário de dados para ser enviado ao template."""
    return {
        'nm_cliente': found_data.get('NM_CLIENTE', 'N/A'),
        'nr_percurso': found_data.get('NR_PERCURSO', 'N/A'),
        'nr_entrega': found_data.get('NR_ENTREGA', 'N/A'),
        'pallet': found_data.get('PALLET', 'N/A'),
        'cd_produto': found_data.get('CD_PRODUTO', 'N/A'),
        'nm_produto': found_data.get('NM_PRODUTO', 'N/A'),
        'tonalidade': found_data.get('TONALIDADE', 'N/A'),
        'qtde': found_data.get('QTDE', 'N/A'),
        'unidade': found_data.get('UNIDADE', '')
    }

# --- Rota Principal da Aplicação (MODIFICADA) ---
@app.route('/<string:percurso>/<string:entrega>/<string:identifier>')
def find_data(percurso, entrega, identifier):
    """
    Recebe um identificador. Se for um Placeholder, redireciona para a URL com o 
    número real do Pallet. Se já for o número do Pallet, exibe os dados.
    """
    print(f"Buscando por Percurso={percurso}, Entrega={entrega}, Identifier={identifier}")
    
    df = get_sheet_data()
    
    if df is None:
        return "Erro: Não foi possível conectar à base de dados.", 500

    # 1. Tenta encontrar o registro usando o 'identifier' como um Placeholder
    result_row_placeholder = df[
        (df['NR_PERCURSO'] == percurso) &
        (df['NR_ENTREGA'] == entrega) &
        (df['Placeholder'] == identifier)
    ]

    # Se encontrou usando o Placeholder, decide se redireciona ou mostra 'aguardando'
    if not result_row_placeholder.empty:
        found_data = result_row_placeholder.iloc[0].to_dict()
        real_pallet = found_data.get('PALLET')
        
        # Se o pallet real existe e não está vazio, redireciona
        if real_pallet and str(real_pallet).strip():
            print(f"Placeholder '{identifier}' encontrado. Redirecionando para o pallet '{real_pallet}'.")
            return redirect(url_for('find_data', percurso=percurso, entrega=entrega, identifier=str(real_pallet)))
        else:
            # Se o pallet está vazio, mostra a página de aguardando
            print("Placeholder encontrado, mas o pallet está vazio. Exibindo página de aguardando conferência.")
            display_data = build_display_data(found_data)
            return render_template('aguardando.html', data=display_data)

    # 2. Se não era um Placeholder, tenta encontrar usando o 'identifier' como um Pallet real
    result_row_pallet = df[
        (df['NR_PERCURSO'] == percurso) &
        (df['NR_ENTREGA'] == entrega) &
        (df['PALLET'] == identifier)
    ]

    # Se encontrou pelo Pallet, exibe a página principal
    if not result_row_pallet.empty:
        found_data = result_row_pallet.iloc[0].to_dict()
        print(f"Pallet '{identifier}' encontrado diretamente. Exibindo dados completos.")
        display_data = build_display_data(found_data)
        return render_template('index.html', data=display_data)
        
    # 3. Se não encontrou de nenhuma forma, retorna erro
    print("Nenhum registro encontrado para o identificador fornecido.")
    abort(404, description="Registro não encontrado para os dados fornecidos.")

@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html', error=e.description), 404

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
