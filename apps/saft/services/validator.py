import logging
from lxml import etree
from io import BytesIO

logger = logging.getLogger(__name__)

class SaftValidator:
    """
    Serviço de validação de ficheiros SAF-T (AO) contra o esquema XSD oficial.
    """
    
    @staticmethod
    def validate_xml(xml_bytes: bytes, xsd_path: str = None) -> tuple[bool, list[str]]:
        """
        Valida o XML contra o XSD. Retorna (sucesso, lista_de_erros).
        """
        if not xsd_path:
            # Em desenvolvimento sem XSD real, apenas validar se é XML bem formado
            try:
                etree.fromstring(xml_bytes)
                return True, []
            except etree.XMLSyntaxError as e:
                return False, [str(e)]

        try:
            schema_doc = etree.parse(xsd_path)
            schema = etree.XMLSchema(schema_doc)
            xml_doc = etree.parse(BytesIO(xml_bytes))
            
            if schema.validate(xml_doc):
                return True, []
            else:
                errors = [str(error) for error in schema.error_log]
                return False, errors
        except Exception as e:
            logger.error(f"Erro inesperado na validação XSD: {str(e)}")
            return False, [f"Erro interno de validação: {str(e)}"]
