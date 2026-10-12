import os
import tempfile

# As partidas dos testes são gravadas em um diretório temporário, nunca na pasta do projeto.
# Precisa acontecer antes de qualquer teste importar o webapp.
os.environ["WAR_DATA_DIR"] = tempfile.mkdtemp(prefix="war-test-")
