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
    """
    Conecta-se ao Google Sheets e retorna os dados da aba 'QR_CODE_LPN' como um DataFrame.
    """
    try:
        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        
        # Lógica de credenciais segura para produção (Render) e testes locais
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
        
        # Garante que as colunas de busca sejam tratadas como texto
        df['NR_PERCURSO'] = df['NR_PERCURSO'].astype(str)
        df['NR_ENTREGA'] = df['NR_ENTREGA'].astype(str)
        df['Placeholder'] = df['Placeholder'].astype(str)
        
        return df
    except Exception as e:
        print(f"Erro ao acessar a planilha: {e}")
        return None

# --- Rota Principal da Aplicação (com a lógica de REDIRECIONAMENTO) ---
@app.route('/<string:percurso>/<string:entrega>/<string:placeholder>')
def find_data(percurso, entrega, placeholder):
    """
    Busca os dados e aplica a lógica de exibição ou redirecionamento.
    """
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

    found_data = result_row.iloc[0]
    
    # --- LÓGICA FINAL CORRIGIDA ---
    
    # Se a coluna PALLET tiver um valor...
    if str(found_data['PALLET']).strip():
        final_url = found_data['URL_PARA_QR_CODE']
        print(f"Pallet encontrado ({found_data['PALLET']}). Redirecionando para: {final_url}")
        # Redireciona o navegador do usuário para a URL final
        return redirect(final_url)
    else:
        # Se a coluna PALLET estiver vazia...
        print("Pallet vazio. Exibindo página de aguardando conferência.")
        # Prepara os dados para a tela de "Aguardando"
        display_data = {
            'nm_cliente': found_data['NM_CLIENTE'],
            'nr_percurso': found_data['NR_PERCURSO'],
            'nr_entrega': found_data['NR_ENTREGA'],
            'nm_produto': found_data['NM_PRODUTO']
        }
        # Mostra a página de status
        return render_template('aguardando.html', data=display_data)

# Rota para página de erro 404 personalizada
@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html', error=e.description), 404

# Ponto de entrada para execução (necessário para o Render)
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)


