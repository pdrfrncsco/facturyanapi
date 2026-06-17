import google.generativeai as genai
from django.conf import settings
import json
import logging
from decimal import Decimal

logger = logging.getLogger(__name__)

def extract_invoice_data(file_path, file_content_type):
    """
    Usa o Gemini Pro Vision para extrair dados estruturados de uma factura.
    """
    api_key = getattr(settings, "GEMINI_API_KEY", None)
    if not api_key:
        logger.error("GEMINI_API_KEY não configurada.")
        return None

    genai.configure(api_key=api_key)
    
    # Configuração do modelo
    model = genai.GenerativeModel('gemini-1.5-flash')
    
    prompt = """
    Analise esta factura de fornecedor e extraia os seguintes dados em formato JSON:
    {
      "supplier_name": "Nome da empresa emissora",
      "supplier_nif": "NIF do emissor",
      "invoice_no": "Número do documento",
      "issue_date": "Data de emissão (YYYY-MM-DD)",
      "currency": "Moeda (AOA, USD, etc)",
      "subtotal": 0.00,
      "tax_total": 0.00,
      "grand_total": 0.00,
      "items": [
        {
          "description": "Descrição do item",
          "quantity": 1.0,
          "unit_price": 0.00,
          "tax_rate": 14.0,
          "total": 0.00
        }
      ]
    }
    Responda apenas o JSON puro, sem blocos de código ou markdown.
    """

    try:
        # Carregar o arquivo
        with open(file_path, 'rb') as f:
            file_data = f.read()

        # Enviar para o Gemini
        response = model.generate_content([
            prompt,
            {'mime_type': file_content_type, 'data': file_data}
        ])

        # Limpar resposta
        text_response = response.text.strip()
        if text_response.startswith('```json'):
            text_response = text_response.replace('```json', '').replace('```', '').strip()
        
        return json.loads(text_response)
    except Exception as e:
        logger.error(f"Erro na extração AI: {str(e)}")
        return None
